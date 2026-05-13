"""solo dispatch command."""

import json
from pathlib import Path
from typing import Any, Dict, Optional

import click

from solo.core.dispatcher import build_dispatcher, phase_event_details, runtime_failed
from solo.core.project import SoloProject
from solo.core.secretary import Secretary
from solo.core.task import AGENT, FAILED, TaskPhase
from solo.core.workflow import Workflow
from solo.utils.ui import print_json, success


def dispatch_task(
    project: SoloProject,
    description: str,
    workflow_name: Optional[str] = None,
    role: Optional[str] = None,
    adapter: Optional[str] = None,
) -> Dict[str, Any]:
    config = project.require_config()
    workflow_name = workflow_name or config.default_workflow

    if role:
        if role not in config.agents:
            raise click.ClickException(f"Unknown agent role: {role}")
        workflow = Workflow(name=f"direct:{role}", description="Direct role dispatch", phases=[])
    else:
        workflow = project.workflows.load(workflow_name)

    secretary = Secretary(config)
    task = secretary.create_task(
        description=description,
        workflow=workflow,
        artifacts_dir=project.solo_dir / "artifacts",
        direct_role=role,
    )

    phase = task.get_phase(task.current_phase)
    if phase is None:
        phase = TaskPhase(name=role or "secretary", type=AGENT, role=role or "secretary")

    adapter = config.get_execution_adapter_for_role(phase.role or phase.name, override=adapter or "")
    dispatcher = build_dispatcher(adapter, config, project.agents)
    package = dispatcher.prepare_phase(task, phase)
    failed = runtime_failed(package)
    if failed:
        task.status = FAILED
        phase.status = FAILED
        for instance in task.agent_instances:
            if instance.phase == phase.name:
                instance.status = FAILED

    project.state.add_task(task)
    project.state.append_event("task.created", task.id, phase=task.current_phase)
    project.state.append_event("phase.started", task.id, phase=task.current_phase, details=phase_event_details(package))
    if failed:
        project.state.append_event("phase.failed", task.id, phase=task.current_phase, details=phase_event_details(package))
    project.state.append_message(
        task.id,
        from_agent="ceo",
        to_agent="secretary",
        message_type="request",
        phase=task.current_phase,
        summary=task.title,
    )
    project.state.append_message(
        task.id,
        from_agent="secretary",
        to_agent=package["agent_role"],
        message_type="assignment",
        phase=task.current_phase,
        summary=f"Prepare {task.current_phase} for {task.title}",
        artifact=package.get("instruction", package.get("report", "")),
        details=phase_event_details(package),
    )

    return {
        "task": task.to_dict(),
        "package": package,
    }


@click.command("dispatch")
@click.option("--to", "role", default=None, help="Dispatch directly to an agent role.")
@click.option("--workflow", "workflow_name", default=None, help="Workflow name.")
@click.option("--adapter", default=None, help="Execution adapter. Defaults to config execution.default_adapter.")
@click.option("--json", "as_json", is_flag=True, help="Print structured JSON.")
@click.argument("description", nargs=-1, required=True)
def dispatch(role: str, workflow_name: str, adapter: str, as_json: bool, description):
    """Create a task and generate the next agent execution package."""
    project = SoloProject.find(Path.cwd())
    if project is None:
        raise click.ClickException("No .solo project found. Run solo init first.")
    text = " ".join(description).strip()
    try:
        result = dispatch_task(project, text, workflow_name=workflow_name, role=role, adapter=adapter)
    except (FileNotFoundError, KeyError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    if as_json:
        print_json(result)
        return
    task = result["task"]
    package = result["package"]
    success(f"created task {task['id']}")
    click.echo(f"Current phase: {task['current_phase']}")
    click.echo(f"Planned dev agents: {task['planned_dev_agents']}")
    click.echo(f"Instruction: {package['instruction']}")
    click.echo(f"Input: {package['input']}")
