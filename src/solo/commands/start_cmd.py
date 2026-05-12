"""solo start command."""

from pathlib import Path

import click

from solo.commands.dispatch_cmd import dispatch_task
from solo.commands.status_cmd import build_status
from solo.core.project import SoloProject
from solo.utils.ui import heading, success


@click.command("start")
def start():
    """Start the CEO to Secretary interactive loop."""
    project = SoloProject.find(Path.cwd())
    if project is None:
        raise click.ClickException("No .solo project found. Run solo init first.")

    config = project.require_config()
    heading(f"Solo Company: {config.project.name}")
    click.echo("You are CEO. Secretary is ready.")
    click.echo("Commands: /status, /quit")

    while True:
        try:
            text = input("CEO > ").strip()
        except (EOFError, KeyboardInterrupt):
            click.echo("")
            break
        if not text:
            continue
        if text in ("/quit", "/exit"):
            break
        if text == "/status":
            payload = build_status(project, include_all=False)
            click.echo(f"Tasks: {payload['summary']['total_tasks']} total, {payload['summary']['active_tasks']} active")
            continue

        click.echo("Secretary > I will ask CTO to break this down first.")
        result = dispatch_task(project, text)
        task = result["task"]
        success(f"task {task['id']} created")
        click.echo(f"Secretary > CTO package is ready: {result['package']['instruction']}")
