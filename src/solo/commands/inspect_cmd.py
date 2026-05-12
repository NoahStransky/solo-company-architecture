"""solo inspect command."""

from pathlib import Path
from typing import Any, Dict, Optional

import click

from solo.core.project import SoloProject
from solo.core.task import IN_PROGRESS, Task
from solo.utils.ui import heading, print_json


def inspect_task(project: SoloProject, task_id: Optional[str] = None) -> Dict[str, Any]:
    """Return a dashboard-friendly task detail payload."""
    tasks = project.state.load_tasks()
    if not tasks:
        raise click.ClickException("No tasks found.")
    task = _select_task(tasks, task_id)
    artifact_dir = Path(task.artifacts_dir)
    return {
        "project": project.require_config().project.__dict__,
        "task": task.to_dict(),
        "paths": {
            "root": str(project.path),
            "solo_dir": str(project.solo_dir),
            "artifacts_dir": str(artifact_dir),
            "events": str(project.state.events_file),
            "messages": str(project.state.messages_file),
        },
        "artifacts": _list_artifacts(artifact_dir),
        "events": [
            event
            for event in project.state.load_events()
            if event.get("task_id") == task.id
        ],
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
    heading(f"Solo task: {task['id']}")
    click.echo(f"Status: {task['status']}")
    click.echo(f"Current phase: {task['current_phase']}")
    click.echo(f"Title: {task['title']}")
    click.echo(f"Artifacts: {len(payload['artifacts'])}")
    click.echo(f"Events: {len(payload['events'])}")
    click.echo(f"Messages: {len(payload['messages'])}")
