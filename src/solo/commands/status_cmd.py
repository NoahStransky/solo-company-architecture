"""solo status command."""

from pathlib import Path
from typing import Any, Dict, List

import click

from solo.core.dispatcher import available_adapters
from solo.core.dashboard import ACTIVE_STATUSES, build_protocol_dashboard, build_task_dashboard
from solo.core.project import SoloProject
from solo.utils.ui import heading, print_json


def build_status(project: SoloProject, include_all: bool = False) -> Dict[str, Any]:
    config = project.require_config()
    tasks = project.state.load_tasks()
    selected = tasks if include_all else tasks[-5:]
    active = [task for task in tasks if task.status in ACTIVE_STATUSES]
    events = project.state.load_events()
    events_by_task: Dict[str, List[Dict[str, Any]]] = {}
    for event in events:
        events_by_task.setdefault(event.get("task_id", ""), []).append(event)
    dashboard_tasks = [
        build_task_dashboard(task, events=events_by_task.get(task.id, []))
        for task in selected
    ]
    return {
        "project": config.project.__dict__,
        "solo_protocol_version": config.solo_protocol_version,
        "protocol": build_protocol_dashboard(config),
        "paths": {
            "root": str(project.path),
            "solo_dir": str(project.solo_dir),
            "config": str(project.config_path),
            "tasks": str(project.state.tasks_file),
            "events": str(project.state.events_file),
            "messages": str(project.state.messages_file),
            "artifacts": str(project.solo_dir / "artifacts"),
        },
        "execution": {
            "default_adapter": config.execution.default_adapter,
            "default_profile": config.execution.default_profile,
            "available_adapters": available_adapters(),
            "runtime_profiles": sorted(config.runtime_profiles.keys()),
        },
        "summary": {
            "total_tasks": len(tasks),
            "active_tasks": len(active),
            "failed_tasks": len([task for task in tasks if task.status == "failed"]),
            "completed_tasks": len([task for task in tasks if task.status == "completed"]),
            "last_updated": tasks[-1].updated_at if tasks else None,
        },
        "dashboard": {
            "tasks": dashboard_tasks,
            "active_task_ids": [task.id for task in active],
            "failed_task_ids": [task.id for task in tasks if task.status == "failed"],
        },
        "tasks": [task.to_dict() for task in selected],
        "recent_events": events[-10:],
        "recent_messages": project.state.load_messages(limit=10),
    }


@click.command("status")
@click.option("--all", "include_all", is_flag=True, help="Show all tasks.")
@click.option("--json", "as_json", is_flag=True, help="Print structured JSON.")
def status(include_all: bool, as_json: bool):
    """Show current project task status."""
    project = SoloProject.find(Path.cwd())
    if project is None:
        raise click.ClickException("No .solo project found. Run solo init first.")
    payload = build_status(project, include_all=include_all)
    if as_json:
        print_json(payload)
        return

    heading(f"Solo status: {payload['project']['name']}")
    summary = payload["summary"]
    execution = payload["execution"]
    click.echo(
        "Tasks: "
        f"{summary['total_tasks']} total, "
        f"{summary['active_tasks']} active, "
        f"{summary['failed_tasks']} failed, "
        f"{summary['completed_tasks']} completed"
    )
    click.echo(
        "Execution: "
        f"adapter={execution['default_adapter']} "
        f"profile={execution['default_profile'] or '-'}"
    )
    if not payload["tasks"]:
        click.echo("No tasks yet.")
        return
    for task in payload["dashboard"]["tasks"]:
        phase_progress = task["phase_progress"]
        agent_progress = task["agent_progress"]
        work_progress = task["work_package_progress"]
        click.echo(
            f"{task['task_id']}  {task['status']}  "
            f"{phase_progress['percent']}%  "
            f"{task['current_phase'] or '-'}  {task['title']}"
        )
        click.echo(
            f"  phases: {phase_progress['done']}/{phase_progress['total']} done"
            f" ({phase_progress['completed']} completed, {phase_progress['skipped']} skipped)"
        )
        if agent_progress["total"]:
            click.echo(
                f"  agents: {agent_progress['percent']}% "
                f"{_format_status_counts(agent_progress['by_status'])}"
            )
        if work_progress["total"]:
            click.echo(
                f"  work packages: {work_progress['percent']}% "
                f"{_format_status_counts(work_progress['by_status'])}"
            )
        failed_reason = task.get("failed_reason")
        if failed_reason:
            click.echo(f"  failed: {_format_failed_reason(failed_reason)}")


def _format_status_counts(counts: Dict[str, int]) -> str:
    if not counts:
        return "-"
    return ", ".join(f"{status}={count}" for status, count in sorted(counts.items()))


def _format_failed_reason(reason: Dict[str, Any]) -> str:
    parts = [reason.get("message", "Task failed")]
    if reason.get("runtime_returncode") is not None:
        parts.append(f"returncode={reason['runtime_returncode']}")
    if reason.get("failed_agents"):
        parts.append(f"agents={','.join(reason['failed_agents'])}")
    return " | ".join(parts)
