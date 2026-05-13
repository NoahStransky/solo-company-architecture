"""solo complete command."""

from pathlib import Path

import click

from solo.core.project import SoloProject
from solo.core.runner import complete_task
from solo.utils.ui import print_json, success


@click.command("complete")
@click.option("--task", "task_id", default=None, help="Task id. Defaults to latest active task.")
@click.option("--phase", "phase_name", default=None, help="Phase name. Defaults to current phase.")
@click.option("--json", "as_json", is_flag=True, help="Print structured JSON.")
def complete(task_id: str, phase_name: str, as_json: bool):
    """Mark a phase complete and prepare the next execution package."""
    project = SoloProject.find(Path.cwd())
    if project is None:
        raise click.ClickException("No .solo project found. Run solo init first.")
    try:
        result = complete_task(project, task_id=task_id, phase_name=phase_name)
    except (KeyError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    if as_json:
        print_json(result)
        return
    success(f"completed phase {result['completed_phase']}")
    if result["next_phase"]:
        click.echo(f"Next phase: {result['next_phase']['name']}")
        if result["package"]:
            package = result["package"]
            click.echo(f"Instruction: {package.get('instruction') or package.get('report')}")
    else:
        click.echo("Task complete.")
