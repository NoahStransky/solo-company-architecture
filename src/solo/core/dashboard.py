"""Dashboard-friendly task summary helpers."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from solo.core.task import COMPLETED, FAILED, IN_PROGRESS, PENDING, SKIPPED, Task


ACTIVE_STATUSES = {PENDING, IN_PROGRESS, "blocked", "waiting_approval"}


def build_task_dashboard(task: Task, events: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Return a stable, compact task view for dashboards."""
    events = events or []
    total_phases = len(task.phases)
    completed_phases = [phase for phase in task.phases if phase.status == COMPLETED]
    skipped_phases = [phase for phase in task.phases if phase.status == SKIPPED]
    done_count = len(completed_phases) + len(skipped_phases)
    current_index = _current_phase_index(task)
    return {
        "task_id": task.id,
        "title": task.title,
        "status": task.status,
        "workflow": task.workflow,
        "current_phase": task.current_phase,
        "current_phase_index": current_index,
        "phase_progress": {
            "total": total_phases,
            "completed": len(completed_phases),
            "skipped": len(skipped_phases),
            "done": done_count,
            "percent": int((done_count / total_phases) * 100) if total_phases else 0,
        },
        "phases": [
            {
                "index": index,
                "name": phase.name,
                "type": phase.type,
                "role": phase.role or phase.name,
                "status": phase.status,
                "is_current": phase.name == task.current_phase,
                "is_failed": phase.status == FAILED,
            }
            for index, phase in enumerate(task.phases)
        ],
        "agent_progress": _agent_progress(task),
        "work_package_progress": _work_package_progress(task),
        "failed_reason": _failed_reason(task, events),
        "updated_at": task.updated_at,
    }


def _current_phase_index(task: Task) -> int:
    for index, phase in enumerate(task.phases):
        if phase.name == task.current_phase:
            return index
    return -1


def _agent_progress(task: Task) -> Dict[str, Any]:
    by_status: Dict[str, int] = {}
    failed_agents = []
    for instance in task.agent_instances:
        by_status[instance.status] = by_status.get(instance.status, 0) + 1
        if instance.status == FAILED:
            failed_agents.append(instance.id)
    total = len(task.agent_instances)
    done = by_status.get(COMPLETED, 0)
    return {
        "total": total,
        "by_status": by_status,
        "failed_agents": failed_agents,
        "percent": int((done / total) * 100) if total else 0,
    }


def _work_package_progress(task: Task) -> Dict[str, Any]:
    by_status: Dict[str, int] = {}
    for package in task.work_packages:
        by_status[package.status] = by_status.get(package.status, 0) + 1
    total = len(task.work_packages)
    done = by_status.get(COMPLETED, 0)
    return {
        "total": total,
        "by_status": by_status,
        "percent": int((done / total) * 100) if total else 0,
    }


def _failed_reason(task: Task, events: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    failed_phase = next((phase for phase in task.phases if phase.status == FAILED), None)
    failed_agents = [instance.id for instance in task.agent_instances if instance.status == FAILED]
    if task.status != FAILED and failed_phase is None and not failed_agents:
        return None

    phase_name = failed_phase.name if failed_phase else task.current_phase
    payload: Dict[str, Any] = {
        "phase": phase_name,
        "message": f"Phase {phase_name} failed" if phase_name else "Task failed",
        "failed_agents": failed_agents,
    }
    event = _latest_phase_failed_event(events, phase_name)
    details = event.get("details", {}) if event else {}
    if details.get("runtime_returncode") is not None:
        payload["runtime_returncode"] = details["runtime_returncode"]
    if details.get("runtime_report"):
        payload["runtime_report"] = details["runtime_report"]

    runtime_payload = _load_runtime_payload(task, phase_name)
    if runtime_payload:
        if "returncode" in runtime_payload:
            payload["runtime_returncode"] = runtime_payload["returncode"]
        failed_from_runtime = _failed_agents_from_runtime(runtime_payload)
        if failed_from_runtime:
            payload["failed_agents"] = sorted(set(payload["failed_agents"]) | set(failed_from_runtime))
    return payload


def _latest_phase_failed_event(events: List[Dict[str, Any]], phase_name: str) -> Optional[Dict[str, Any]]:
    for event in reversed(events):
        if event.get("event") == "phase.failed" and (not phase_name or event.get("phase") == phase_name):
            return event
    return None


def _load_runtime_payload(task: Task, phase_name: str) -> Dict[str, Any]:
    if not phase_name:
        return {}
    path = Path(task.artifacts_dir) / f"{phase_name}_runtime.json"
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _failed_agents_from_runtime(runtime_payload: Dict[str, Any]) -> List[str]:
    failed = []
    for agent_id, item in (runtime_payload.get("agent_runtimes") or {}).items():
        runtime = item.get("runtime") or {}
        if runtime.get("returncode", 0) != 0:
            failed.append(agent_id)
    return failed
