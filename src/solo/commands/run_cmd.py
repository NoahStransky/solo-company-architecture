"""solo run command."""

from pathlib import Path

import click

from solo.core.project import SoloProject
from solo.core.runner import complete_task, run_until
from solo.utils.ui import print_json, success


@click.command("run")
@click.option("--task", "task_id", default=None, help="Task id. Defaults to latest active task.")
@click.option("--once", is_flag=True, help="Advance one phase.")
@click.option("--until", default=None, help="Advance until a phase, blocked, or done.")
@click.option("--json", "as_json", is_flag=True, help="Print structured JSON.")
def run(task_id: str, once: bool, until: str, as_json: bool):
    """Run or advance the current task phase."""
    project = SoloProject.find(Path.cwd())
    if project is None:
        raise click.ClickException("No .solo project found. Run solo init first.")
    if once and until:
        raise click.ClickException("Use either --once or --until, not both.")
    if until:
        result = run_until(project, task_id=task_id, target=until)
        if as_json:
            print_json(result)
            return
        click.echo(f"Stopped: {result['stopped_reason']}")
        if result["failed_phase"]:
            click.echo(f"Failed phase: {result['failed_phase']}")
        return
    if not once:
        raise click.ClickException("Only solo run --once or solo run --until is supported.")
    result = complete_task(project, task_id=task_id)
    if as_json:
        print_json(result)
        return
    success(f"advanced phase {result['completed_phase']}")
    if result["next_phase"]:
        click.echo(f"Next phase: {result['next_phase']['name']} ({result['next_phase']['status']})")
    else:
        click.echo("Task complete.")
