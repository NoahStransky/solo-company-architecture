"""solo run command."""

from pathlib import Path

import click

from solo.commands.complete_cmd import complete_task
from solo.core.project import SoloProject
from solo.utils.ui import print_json, success


@click.command("run")
@click.option("--task", "task_id", default=None, help="Task id. Defaults to latest active task.")
@click.option("--once", is_flag=True, help="Advance one phase. This is the only supported run mode for now.")
@click.option("--json", "as_json", is_flag=True, help="Print structured JSON.")
def run(task_id: str, once: bool, as_json: bool):
    """Run or advance the current task phase."""
    project = SoloProject.find(Path.cwd())
    if project is None:
        raise click.ClickException("No .solo project found. Run solo init first.")
    if not once:
        raise click.ClickException("Only solo run --once is supported in this version.")
    result = complete_task(project, task_id=task_id)
    if as_json:
        print_json(result)
        return
    success(f"advanced phase {result['completed_phase']}")
    if result["next_phase"]:
        click.echo(f"Next phase: {result['next_phase']['name']} ({result['next_phase']['status']})")
    else:
        click.echo("Task complete.")
