"""solo status command."""

from pathlib import Path
from typing import Any, Dict, List

import click

from solo.core.dispatcher import available_adapters
from solo.core.project import SoloProject
from solo.core.task import Task
from solo.utils.ui import heading, print_json


def build_status(project: SoloProject, include_all: bool = False) -> Dict[str, Any]:
    config = project.require_config()
    tasks = project.state.load_tasks()
    selected = tasks if include_all else tasks[-5:]
    active = [task for task in tasks if task.status in ("pending", "in_progress", "blocked", "waiting_approval")]
    return {
        "project": config.project.__dict__,
        "solo_protocol_version": config.solo_protocol_version,
        "paths": {
            "root": str(project.path),
            "solo_dir": str(project.solo_dir),
            "config": str(project.config_path),
            "tasks": str(project.state.tasks_file),
            "events": str(project.state.events_file),
            "artifacts": str(project.solo_dir / "artifacts"),
        },
        "execution": {
            "default_adapter": config.execution.default_adapter,
            "available_adapters": available_adapters(),
        },
        "summary": {
            "total_tasks": len(tasks),
            "active_tasks": len(active),
            "last_updated": tasks[-1].updated_at if tasks else None,
        },
        "tasks": [task.to_dict() for task in selected],
        "recent_events": project.state.load_events(limit=10),
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
    if not payload["tasks"]:
        click.echo("No tasks yet.")
        return
    for task in payload["tasks"]:
        click.echo(f"{task['id']}  {task['status']}  {task['current_phase']}  {task['title']}")
        if task.get("planned_dev_agents"):
            click.echo(f"  planned dev agents: {task['planned_dev_agents']}")
