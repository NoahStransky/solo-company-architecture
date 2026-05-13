"""Task phase running, advancement, and recovery services."""

import json
from pathlib import Path
from typing import Any, Dict, Optional

import click

from solo.core.dispatcher import build_dispatcher, phase_event_details, runtime_failed
from solo.core.project import SoloProject
from solo.core.task import (
    AGENT,
    AGENT_POOL,
    COMPLETED,
    FAILED,
    HUMAN_GATE,
    IN_PROGRESS,
    PENDING,
    SKIPPED,
    SYSTEM,
    AgentInstance,
    PhaseResult,
    Task,
    TaskPhase,
    WorkPackage,
)


def complete_task(project: SoloProject, task_id: Optional[str] = None, phase_name: Optional[str] = None) -> Dict[str, Any]:
    """Complete a task phase and prepare the next runnable phase."""
    task = select_task(project.state.load_tasks(), task_id)
    phase = task.get_phase(phase_name or task.current_phase)
    if phase is None:
        raise click.ClickException(f"Phase not found: {phase_name or task.current_phase}")
    if phase.status == FAILED:
        raise click.ClickException(f"Phase is failed and cannot be completed without retry: {phase.name}")
    return _complete_phase(project, task, phase)


def run_until(project: SoloProject, task_id: Optional[str], target: str) -> Dict[str, Any]:
    """Advance a task until a phase, failure, or completion stop condition."""
    if target not in ("blocked", "done") and not target.strip():
        raise click.ClickException("--until requires a phase name, blocked, or done.")

    completed_phases = []
    last_result = None
    max_steps = 100
    for _ in range(max_steps):
        task = select_task(project.state.load_tasks(), task_id)
        failed_phase = _failed_phase_name(task)
        if task.status == FAILED or failed_phase:
            return {
                "task": task.to_dict(),
                "stopped_reason": "failed",
                "completed_phases": completed_phases,
                "failed_phase": failed_phase or task.current_phase,
                "last_result": last_result,
            }
        if task.status == COMPLETED:
            return {
                "task": task.to_dict(),
                "stopped_reason": "completed",
                "completed_phases": completed_phases,
                "failed_phase": "",
                "last_result": last_result,
            }
        if target == "blocked":
            last_result = complete_task(project, task_id=task.id)
            completed_phases.append(last_result["completed_phase"])
            continue
        if target == "done":
            last_result = complete_task(project, task_id=task.id)
            completed_phases.append(last_result["completed_phase"])
            continue
        if task.current_phase == target:
            return {
                "task": task.to_dict(),
                "stopped_reason": "reached_phase",
                "completed_phases": completed_phases,
                "failed_phase": "",
                "last_result": last_result,
            }
        last_result = complete_task(project, task_id=task.id)
        completed_phases.append(last_result["completed_phase"])

    task = select_task(project.state.load_tasks(), task_id)
    return {
        "task": task.to_dict(),
        "stopped_reason": "no_progress",
        "completed_phases": completed_phases,
        "failed_phase": _failed_phase_name(task),
        "last_result": last_result,
    }


def reopen_phase(project: SoloProject, task_id: Optional[str], phase_name: str) -> Dict[str, Any]:
    """Reopen a failed or previously prepared phase without running runtime."""
    task = select_task(project.state.load_tasks(), task_id)
    phase = task.get_phase(phase_name)
    if phase is None:
        raise click.ClickException(f"Phase not found: {phase_name}")
    _reopen_loaded_phase(project, task, phase)
    project.state.append_event("phase.reopened", task.id, phase=phase.name)
    task.touch()
    project.state.update_task(task)
    return {
        "task": task.to_dict(),
        "phase": phase.to_dict(),
    }


def retry_phase(project: SoloProject, task_id: Optional[str], phase_name: str) -> Dict[str, Any]:
    """Reopen, rerun, and complete a phase if its runtime succeeds."""
    task = select_task(project.state.load_tasks(), task_id)
    phase = task.get_phase(phase_name)
    if phase is None:
        raise click.ClickException(f"Phase not found: {phase_name}")

    _reopen_loaded_phase(project, task, phase)
    project.state.append_event("phase.retried", task.id, phase=phase.name)
    package = _prepare_phase(project, task, phase)
    if runtime_failed(package):
        task.touch()
        project.state.update_task(task)
        return {
            "task": task.to_dict(),
            "completed_phase": "",
            "next_phase": None,
            "package": package,
            "retried_phase": phase.name,
        }
    result = _complete_phase(project, task, phase)
    result["retried_phase"] = phase.name
    result["retry_package"] = package
    return result


def retry_agent(project: SoloProject, task_id: Optional[str], agent_id: str) -> Dict[str, Any]:
    """Rerun one agent instance inside an agent pool phase."""
    task = select_task(project.state.load_tasks(), task_id)
    instance = _find_agent_instance(task, agent_id)
    phase = task.get_phase(instance.phase or "")
    if phase is None:
        raise click.ClickException(f"Phase not found for agent: {agent_id}")
    if phase.type != AGENT_POOL:
        raise click.ClickException(f"Agent retry requires an agent pool phase: {agent_id}")

    task.status = IN_PROGRESS
    task.current_phase = phase.name
    phase.status = IN_PROGRESS
    instance.status = IN_PROGRESS
    project.state.append_event("agent.retried", task.id, phase=phase.name, details={"agent": agent_id})

    config = project.require_config()
    adapter = config.get_execution_adapter_for_role(phase.role or phase.name)
    dispatcher = build_dispatcher(adapter, config, project.agents)
    if not hasattr(dispatcher, "prepare_agent_instance"):
        raise click.ClickException(f"Adapter does not support agent retry: {adapter}")
    package = dispatcher.prepare_agent_instance(task, phase, agent_id)
    runtime = package.get("runtime") or {}
    if runtime.get("returncode", 0) == 0:
        instance.status = COMPLETED
        project.state.append_event("agent.completed", task.id, phase=phase.name, details={"agent": agent_id})
    else:
        instance.status = FAILED
        phase.status = FAILED
        task.status = FAILED
        project.state.append_event("agent.failed", task.id, phase=phase.name, details={"agent": agent_id, "returncode": runtime.get("returncode")})
        project.state.append_event("phase.failed", task.id, phase=phase.name, details=phase_event_details(package))
        task.touch()
        project.state.update_task(task)
        return {
            "task": task.to_dict(),
            "agent": instance.to_dict(),
            "package": package,
            "next_phase": None,
        }

    task.touch()
    project.state.update_task(task)
    if _phase_instances(task, phase.name) and all(item.status == COMPLETED for item in _phase_instances(task, phase.name)):
        result = complete_task(project, task_id=task.id, phase_name=phase.name)
        result["retried_agent"] = agent_id
        result["retry_package"] = package
        return result

    return {
        "task": task.to_dict(),
        "agent": instance.to_dict(),
        "package": package,
        "next_phase": None,
    }


def select_task(tasks: list, task_id: Optional[str]) -> Task:
    if not tasks:
        raise click.ClickException("No tasks found.")
    if task_id:
        for task in tasks:
            if task.id == task_id:
                return task
        raise click.ClickException(f"Task not found: {task_id}")
    for task in reversed(tasks):
        if task.status == IN_PROGRESS:
            return task
    return tasks[-1]


def _complete_phase(project: SoloProject, task: Task, phase: TaskPhase) -> Dict[str, Any]:
    phase.status = COMPLETED
    _set_instances_for_phase(task, phase.name, COMPLETED)
    loaded_work_packages = _load_phase_work_packages(task, phase)
    if loaded_work_packages:
        task.work_packages = loaded_work_packages
        _assign_work_packages(task)
        project.state.append_event(
            "work_packages.updated",
            task.id,
            phase=phase.name,
            details={"count": len(task.work_packages)},
        )
    loaded_phase_results = _load_phase_results(task, phase)
    if loaded_phase_results:
        _upsert_phase_results(task, loaded_phase_results)
        updated_work_packages = _sync_work_package_statuses(task, loaded_phase_results)
        project.state.append_event(
            "phase_results.updated",
            task.id,
            phase=phase.name,
            details={"count": len(loaded_phase_results)},
        )
        if updated_work_packages:
            project.state.append_event(
                "work_packages.updated",
                task.id,
                phase=phase.name,
                details={"count": updated_work_packages},
            )
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
            artifact=_phase_result_artifact(task, phase),
        )
    else:
        task.status = IN_PROGRESS
        next_phase.status = IN_PROGRESS
        task.current_phase = next_phase.name
        _ensure_instances_for_phase(task, next_phase)
        _set_instances_for_phase(task, next_phase.name, IN_PROGRESS)
        package = _prepare_phase(project, task, next_phase)
        if not runtime_failed(package):
            _append_handoff_messages(project, task, phase, next_phase, package)

    task.touch()
    project.state.update_task(task)

    return {
        "task": task.to_dict(),
        "completed_phase": phase.name,
        "next_phase": next_phase.to_dict() if next_phase else None,
        "package": package,
    }


def _prepare_phase(project: SoloProject, task: Task, phase: TaskPhase) -> Dict[str, Any]:
    package = None
    if phase.type in (AGENT, AGENT_POOL, SYSTEM):
        config = project.require_config()
        adapter = config.get_execution_adapter_for_role(phase.role or phase.name)
        dispatcher = build_dispatcher(adapter, config, project.agents)
        package = dispatcher.prepare_phase(task, phase)
    if package is None:
        package = {"adapter": "", "phase": phase.name, "agent_role": phase.role or phase.name}
    failed = runtime_failed(package)
    _apply_runtime_statuses(task, phase, package)
    if failed:
        phase.status = FAILED
        task.status = FAILED
    project.state.append_event(
        "phase.started",
        task.id,
        phase=phase.name,
        details=phase_event_details(package) if package else None,
    )
    if failed:
        project.state.append_event(
            "phase.failed",
            task.id,
            phase=phase.name,
            details=phase_event_details(package),
        )
    return package


def _apply_runtime_statuses(task: Task, phase: TaskPhase, package: Dict[str, Any]) -> None:
    agent_runtimes = package.get("agent_runtimes") or (package.get("runtime") or {}).get("agent_runtimes") or {}
    if phase.type == AGENT_POOL and agent_runtimes:
        for instance in _phase_instances(task, phase.name):
            runtime = (agent_runtimes.get(instance.id) or {}).get("runtime") or {}
            if "returncode" not in runtime:
                continue
            instance.status = COMPLETED if runtime["returncode"] == 0 else FAILED
        return

    runtime = package.get("runtime") or {}
    if "returncode" not in runtime:
        return
    status = COMPLETED if runtime["returncode"] == 0 else FAILED
    _set_instances_for_phase(task, phase.name, status)


def _reopen_loaded_phase(project: SoloProject, task: Task, phase: TaskPhase) -> None:
    task.status = IN_PROGRESS
    task.current_phase = phase.name
    phase.status = IN_PROGRESS
    _ensure_instances_for_phase(task, phase)
    _set_instances_for_phase(task, phase.name, IN_PROGRESS)
    phase_index = task.phases.index(phase)
    for downstream in task.phases[phase_index + 1:]:
        if downstream.status != PENDING:
            downstream.status = PENDING
        for instance in _phase_instances(task, downstream.name):
            instance.status = PENDING


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


def _phase_instances(task: Task, phase_name: str) -> list:
    return [instance for instance in task.agent_instances if instance.phase == phase_name]


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


def _load_phase_work_packages(task: Task, phase: TaskPhase) -> list:
    if phase.name != "cto_breakdown":
        return []
    artifact_dir = Path(task.artifacts_dir)
    for path in (artifact_dir / "work_packages.json", artifact_dir / f"{phase.name}_output.json"):
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("work_packages", [])
        else:
            raise ValueError(f"Invalid work package payload: {path}")
        if not isinstance(items, list):
            raise ValueError(f"Invalid work package payload: {path}")
        return [_work_package_from_payload(item, index) for index, item in enumerate(items)]
    return []


def _work_package_from_payload(data: Dict[str, Any], index: int) -> WorkPackage:
    if not isinstance(data, dict):
        raise ValueError("Each work package must be an object")
    title = str(data.get("title", "")).strip()
    description = str(data.get("description", "")).strip()
    if not title or not description:
        raise ValueError("Each work package requires title and description")
    return WorkPackage(
        id=str(data.get("id") or f"wp-{index + 1}"),
        title=title,
        description=description,
        agent_role=str(data.get("agent_role", "dev")),
        files_scope=[str(item) for item in data.get("files_scope", [])],
        depends_on=[str(item) for item in data.get("depends_on", [])],
        agent_instance=str(data["agent_instance"]) if data.get("agent_instance") else None,
    )


def _assign_work_packages(task: Task) -> None:
    dev_instances = [
        instance
        for instance in task.agent_instances
        if instance.role == "dev" and instance.phase == "dev_pool"
    ]
    if not dev_instances:
        return
    for index, package in enumerate(task.work_packages):
        if package.agent_role != "dev":
            continue
        assigned = package.agent_instance or dev_instances[index % len(dev_instances)].id
        package.agent_instance = assigned
        for instance in dev_instances:
            if instance.id == assigned and not instance.work_package_id:
                instance.work_package_id = package.id


def _load_phase_results(task: Task, phase: TaskPhase) -> list:
    artifact_dir = Path(task.artifacts_dir)
    candidates = _phase_result_candidates(artifact_dir, phase)
    results = []
    seen = set()
    for from_agent, path in candidates:
        if path in seen or not path.exists():
            continue
        seen.add(path)
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        result = _phase_result_from_payload(payload, phase, from_agent, path)
        if result:
            results.append(result)
    return results


def _phase_result_candidates(artifact_dir: Path, phase: TaskPhase) -> list:
    phase_actor = _phase_actor(phase)
    instance_candidates = []
    for instance_id in phase.instance_ids:
        instance_candidates.extend([
            (instance_id, artifact_dir / f"{instance_id}_agent_result.json"),
            (instance_id, artifact_dir / f"{instance_id}_result.json"),
            (instance_id, artifact_dir / f"{instance_id}_output.json"),
        ])
    candidates = [
        (phase_actor, artifact_dir / f"{phase.name}_agent_result.json"),
        (phase_actor, artifact_dir / f"{phase.name}_result.json"),
        (phase_actor, artifact_dir / f"{phase.name}_output.json"),
    ]
    if phase.role == "qa" or phase.name == "qa":
        candidates.insert(0, (phase_actor, artifact_dir / "qa_report.json"))
    return instance_candidates + candidates


def _phase_result_from_payload(
    payload: Any,
    phase: TaskPhase,
    from_agent: str,
    path: Path,
) -> Optional[PhaseResult]:
    if not isinstance(payload, dict) or not payload.get("summary"):
        return None
    return PhaseResult(
        phase=phase.name,
        from_agent=from_agent,
        summary=str(payload["summary"]),
        status=str(payload.get("status", "")),
        verdict=str(payload["verdict"]) if payload.get("verdict") else None,
        artifact=str(path.resolve()),
        data=payload,
    )


def _upsert_phase_results(task: Task, results: list) -> None:
    by_key = {(result.phase, result.from_agent): result for result in task.phase_results}
    for result in results:
        by_key[(result.phase, result.from_agent)] = result
    task.phase_results = list(by_key.values())


def _sync_work_package_statuses(task: Task, results: list) -> int:
    updated = 0
    for result in results:
        if result.phase != "dev_pool":
            continue
        explicit_statuses = _work_package_statuses_from_result(result)
        if explicit_statuses:
            for work_package in task.work_packages:
                status = explicit_statuses.get(work_package.id)
                if status and work_package.status != status:
                    work_package.status = status
                    updated += 1
            continue
        status = result.status or COMPLETED
        for work_package in task.work_packages:
            if work_package.agent_instance == result.from_agent and work_package.status != status:
                work_package.status = status
                updated += 1
    return updated


def _work_package_statuses_from_result(result: PhaseResult) -> Dict[str, str]:
    statuses = {}
    items = result.data.get("work_packages", [])
    if not isinstance(items, list):
        return statuses
    for item in items:
        if not isinstance(item, dict):
            continue
        package_id = str(item.get("id", "")).strip()
        status = str(item.get("status", "")).strip()
        if package_id and status:
            statuses[package_id] = status
    return statuses


def _append_handoff_messages(
    project: SoloProject,
    task: Task,
    phase: TaskPhase,
    next_phase: TaskPhase,
    package: Optional[Dict[str, Any]],
) -> None:
    artifact = _phase_result_artifact(task, phase)
    for sender in _phase_senders(phase):
        for recipient in _phase_recipients(next_phase):
            details = _handoff_details(package, recipient)
            project.state.append_message(
                task.id,
                from_agent=sender,
                to_agent=recipient,
                message_type="handoff",
                phase=next_phase.name,
                summary=f"{phase.name} completed; {next_phase.name} is ready for {task.title}",
                artifact=artifact,
                details=details,
            )


def _phase_actor(phase: TaskPhase) -> str:
    if phase.type == HUMAN_GATE:
        return "ceo"
    return phase.role or phase.name


def _phase_senders(phase: TaskPhase) -> list:
    if phase.type == AGENT_POOL and phase.instance_ids:
        return list(phase.instance_ids)
    return [_phase_actor(phase)]


def _phase_recipients(phase: TaskPhase) -> list:
    if phase.type == AGENT_POOL and phase.instance_ids:
        return list(phase.instance_ids)
    return [_phase_actor(phase)]


def _phase_result_artifact(task: Task, phase: TaskPhase) -> str:
    artifact_dir = Path(task.artifacts_dir)
    for candidate in (
        artifact_dir / f"{phase.name}_output.md",
        artifact_dir / f"{phase.name}.md",
    ):
        if candidate.exists():
            return str(candidate)
    return ""


def _handoff_details(package: Optional[Dict[str, Any]], recipient: str = "") -> Optional[Dict[str, Any]]:
    if not package:
        return None
    details = phase_event_details(package)
    details.pop("agent_packages", None)
    agent_package = (package.get("agent_packages") or {}).get(recipient, {})
    next_instruction = agent_package.get("instruction") or package.get("instruction") or package.get("report")
    next_input = agent_package.get("input")
    if next_instruction:
        details["next_instruction"] = next_instruction
    if next_input:
        details["next_input"] = next_input
    if agent_package.get("work_packages"):
        details["work_packages"] = agent_package["work_packages"]
    return details


def _failed_phase_name(task: Task) -> str:
    for phase in task.phases:
        if phase.status == FAILED:
            return phase.name
    return ""


def _find_agent_instance(task: Task, agent_id: str) -> AgentInstance:
    for instance in task.agent_instances:
        if instance.id == agent_id:
            return instance
    raise click.ClickException(f"Agent instance not found: {agent_id}")
