"""solo reopen command."""

from pathlib import Path

import click

from solo.core.project import SoloProject
from solo.core.runner import reopen_phase
from solo.utils.ui import print_json, success


@click.command("reopen")
@click.option("--task", "task_id", default=None, help="Task id. Defaults to latest active task.")
@click.option("--phase", "phase_name", required=True, help="Phase name to reopen.")
@click.option("--json", "as_json", is_flag=True, help="Print structured JSON.")
def reopen(task_id: str, phase_name: str, as_json: bool):
    """Reopen a failed or prepared phase without running runtime."""
    project = SoloProject.find(Path.cwd())
    if project is None:
        raise click.ClickException("No .solo project found. Run solo init first.")
    result = reopen_phase(project, task_id=task_id, phase_name=phase_name)
    if as_json:
        print_json(result)
        return
    success(f"reopened phase {phase_name}")
