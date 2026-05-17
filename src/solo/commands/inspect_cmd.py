"""solo inspect command."""

from pathlib import Path
from typing import Any, Dict, Optional

import click

from solo.core.dashboard import build_protocol_dashboard, build_task_dashboard
from solo.core.project import SoloProject
from solo.core.task import IN_PROGRESS, Task
from solo.utils.ui import heading, print_json


def inspect_task(project: SoloProject, task_id: Optional[str] = None) -> Dict[str, Any]:
    """Return a dashboard-friendly task detail payload."""
    tasks = project.state.load_tasks()
    if not tasks:
        raise click.ClickException("No tasks found.")
    task = _select_task(tasks, task_id)
    config = project.require_config()
    artifact_dir = Path(task.artifacts_dir)
    events = [
        event
        for event in project.state.load_events()
        if event.get("task_id") == task.id
    ]
    return {
        "project": config.project.__dict__,
        "protocol": build_protocol_dashboard(config),
        "task": task.to_dict(),
        "dashboard": build_task_dashboard(task, events=events),
        "paths": {
            "root": str(project.path),
            "solo_dir": str(project.solo_dir),
            "artifacts_dir": str(artifact_dir),
            "events": str(project.state.events_file),
            "messages": str(project.state.messages_file),
        },
        "artifacts": _list_artifacts(artifact_dir),
        "events": events,
        "messages": project.state.load_messages(task_id=task.id),
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


def _list_artifacts(artifact_dir: Path) -> list:
    if not artifact_dir.exists():
        return []
    artifacts = []
    for path in sorted(item for item in artifact_dir.rglob("*") if item.is_file()):
        stat = path.stat()
        artifacts.append({
            "name": path.name,
            "path": str(path),
            "relative_path": str(path.relative_to(artifact_dir)),
            "size_bytes": stat.st_size,
            "kind": _artifact_kind(path),
        })
    return artifacts


def _artifact_kind(path: Path) -> str:
    name = path.name
    if name.endswith("_instruction.md"):
        return "instruction"
    if name.endswith("_input.json"):
        return "input"
    if name.endswith("_runtime.json"):
        return "runtime"
    if name.endswith("_result.json") or name.endswith("_agent_result.json"):
        return "agent_result"
    if name == "qa_report.json":
        return "qa_report"
    if name == "work_packages.json":
        return "work_packages"
    if name == "task.json":
        return "task_snapshot"
    if name.endswith("_output.md") or name.endswith("_output.json"):
        return "output"
    return path.suffix.lstrip(".") or "file"


@click.command("inspect")
@click.option("--task", "task_id", default=None, help="Task id. Defaults to latest active task.")
@click.option("--json", "as_json", is_flag=True, help="Print structured JSON.")
def inspect(task_id: str, as_json: bool):
    """Inspect one task with events, messages, and artifacts."""
    project = SoloProject.find(Path.cwd())
    if project is None:
        raise click.ClickException("No .solo project found. Run solo init first.")
    payload = inspect_task(project, task_id=task_id)
    if as_json:
        print_json(payload)
        return
    task = payload["task"]
    dashboard = payload["dashboard"]
    phase_progress = dashboard["phase_progress"]
    agent_progress = dashboard["agent_progress"]
    work_progress = dashboard["work_package_progress"]
    heading(f"Solo task: {task['id']}")
    click.echo(f"Status: {task['status']}")
    click.echo(f"Current phase: {task['current_phase']}")
    click.echo(f"Title: {task['title']}")
    click.echo(
        "Phase progress: "
        f"{phase_progress['percent']}% "
        f"({phase_progress['done']}/{phase_progress['total']} done, "
        f"{phase_progress['skipped']} skipped)"
    )
    if agent_progress["total"]:
        click.echo(f"Agent progress: {agent_progress['percent']}% {_format_status_counts(agent_progress['by_status'])}")
    if work_progress["total"]:
        click.echo(f"Work package progress: {work_progress['percent']}% {_format_status_counts(work_progress['by_status'])}")
    if dashboard.get("failed_reason"):
        click.echo(f"Failed: {_format_failed_reason(dashboard['failed_reason'])}")
    click.echo(f"Artifacts: {len(payload['artifacts'])}")
    for artifact in payload["artifacts"][:8]:
        click.echo(f"  {artifact['kind']}: {artifact['relative_path']}")
    if len(payload["artifacts"]) > 8:
        click.echo(f"  ... {len(payload['artifacts']) - 8} more")
    click.echo(f"Events: {len(payload['events'])}")
    for event in payload["events"][-5:]:
        click.echo(f"  {event['event']} {event.get('phase', '')}".rstrip())
    click.echo(f"Messages: {len(payload['messages'])}")
    for message in payload["messages"][-5:]:
        click.echo(f"  {message['from']} -> {message['to']} {message['type']}")


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
    if reason.get("runtime_report"):
        parts.append(f"runtime_report={reason['runtime_report']}")
    return " | ".join(parts)
