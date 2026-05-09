"""solo complete command."""

from pathlib import Path
from typing import Any, Dict, Optional

import click

from solo.core.dispatcher import build_dispatcher, phase_event_details
from solo.core.project import SoloProject
from solo.core.task import AGENT, AGENT_POOL, COMPLETED, HUMAN_GATE, IN_PROGRESS, PENDING, SKIPPED, SYSTEM, AgentInstance, Task, TaskPhase
from solo.utils.ui import print_json, success


def complete_task(project: SoloProject, task_id: Optional[str] = None, phase_name: Optional[str] = None) -> Dict[str, Any]:
    tasks = project.state.load_tasks()
    if not tasks:
        raise click.ClickException("No tasks found.")

    task = _select_task(tasks, task_id)
    phase = task.get_phase(phase_name or task.current_phase)
    if phase is None:
        raise click.ClickException(f"Phase not found: {phase_name or task.current_phase}")

    phase.status = COMPLETED
    _set_instances_for_phase(task, phase.name, COMPLETED)
    project.state.append_event("phase.completed", task.id, phase=phase.name)

    next_phase = _next_runnable_phase(task)
    package = None
    if next_phase is None:
        task.status = COMPLETED
        task.current_phase = ""
        project.state.append_event("task.completed", task.id)
        project.state.append_message(
            task.id,
            from_agent=_phase_actor(phase),
            to_agent="ceo",
            message_type="result",
            phase=phase.name,
            summary=f"{phase.name} completed for {task.title}",
            artifact=str(Path(task.artifacts_dir) / f"{phase.name}_output.md"),
        )
    else:
        next_phase.status = IN_PROGRESS
        task.current_phase = next_phase.name
        _ensure_instances_for_phase(task, next_phase)
        _set_instances_for_phase(task, next_phase.name, IN_PROGRESS)
        if next_phase.type in (AGENT, AGENT_POOL, SYSTEM):
            config = project.require_config()
            dispatcher = build_dispatcher(config.execution.default_adapter, config, project.agents)
            package = dispatcher.prepare_phase(task, next_phase)
        project.state.append_event(
            "phase.started",
            task.id,
            phase=next_phase.name,
            details=phase_event_details(package) if package else None,
        )
        project.state.append_message(
            task.id,
            from_agent=_phase_actor(phase),
            to_agent=_phase_actor(next_phase),
            message_type="handoff",
            phase=next_phase.name,
            summary=f"{phase.name} completed; {next_phase.name} is ready for {task.title}",
            artifact=(package or {}).get("instruction", (package or {}).get("report", "")),
            details=phase_event_details(package) if package else None,
        )

    task.touch()
    project.state.update_task(task)

    return {
        "task": task.to_dict(),
        "completed_phase": phase.name,
        "next_phase": next_phase.to_dict() if next_phase else None,
        "package": package,
    }


def _select_task(tasks: list, task_id: Optional[str]) -> Task:
    if task_id:
        for task in tasks:
            if task.id == task_id:
                return task
        raise click.ClickException(f"Task not found: {task_id}")
    for task in reversed(tasks):
        if task.status == IN_PROGRESS:
            return task
    return tasks[-1]


def _next_runnable_phase(task: Task) -> Optional[TaskPhase]:
    completed = {phase.name for phase in task.phases if phase.status in (COMPLETED, SKIPPED)}
    while True:
        candidate = None
        for phase in task.phases:
            if phase.status != PENDING:
                continue
            if all(dep in completed for dep in phase.depends_on):
                candidate = phase
                break
        if candidate is None:
            return None
        if candidate.type == HUMAN_GATE and candidate.optional:
            candidate.status = SKIPPED
            completed.add(candidate.name)
            continue
        return candidate


def _set_instances_for_phase(task: Task, phase_name: str, status: str) -> None:
    for instance in task.agent_instances:
        if instance.phase == phase_name:
            instance.status = status


def _ensure_instances_for_phase(task: Task, phase: TaskPhase) -> None:
    if any(instance.phase == phase.name for instance in task.agent_instances):
        return
    if phase.type == AGENT:
        role = phase.role or phase.name
        task.agent_instances.append(AgentInstance(id=f"{phase.name}-1", role=role, phase=phase.name, status=PENDING))
    elif phase.type == AGENT_POOL:
        role = phase.role or phase.name
        for instance_id in phase.instance_ids:
            task.agent_instances.append(AgentInstance(id=instance_id, role=role, phase=phase.name, status=PENDING))


def _phase_actor(phase: TaskPhase) -> str:
    if phase.type == HUMAN_GATE:
        return "ceo"
    return phase.role or phase.name


@click.command("complete")
@click.option("--task", "task_id", default=None, help="Task id. Defaults to latest active task.")
@click.option("--phase", "phase_name", default=None, help="Phase name. Defaults to current phase.")
@click.option("--json", "as_json", is_flag=True, help="Print structured JSON.")
def complete(task_id: str, phase_name: str, as_json: bool):
    """Mark a phase complete and prepare the next execution package."""
    project = SoloProject.find(Path.cwd())
    if project is None:
        raise click.ClickException("No .solo project found. Run solo init first.")
    result = complete_task(project, task_id=task_id, phase_name=phase_name)
    if as_json:
        print_json(result)
        return
    success(f"completed phase {result['completed_phase']}")
    if result["next_phase"]:
        click.echo(f"Next phase: {result['next_phase']['name']}")
        if result["package"]:
            package = result["package"]
            click.echo(f"Instruction: {package.get('instruction') or package.get('report')}")
    else:
        click.echo("Task complete.")
