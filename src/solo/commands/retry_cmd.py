"""solo retry command."""

from pathlib import Path

import click

from solo.core.project import SoloProject
from solo.core.runner import retry_agent, retry_phase
from solo.utils.ui import print_json, success


@click.command("retry")
@click.option("--task", "task_id", default=None, help="Task id. Defaults to latest active task.")
@click.option("--phase", "phase_name", default=None, help="Phase name to retry.")
@click.option("--agent", "agent_id", default=None, help="Agent instance id to retry.")
@click.option("--json", "as_json", is_flag=True, help="Print structured JSON.")
def retry(task_id: str, phase_name: str, agent_id: str, as_json: bool):
    """Retry a failed phase or one agent instance."""
    project = SoloProject.find(Path.cwd())
    if project is None:
        raise click.ClickException("No .solo project found. Run solo init first.")
    if bool(phase_name) == bool(agent_id):
        raise click.ClickException("Use exactly one of --phase or --agent.")
    result = retry_agent(project, task_id=task_id, agent_id=agent_id) if agent_id else retry_phase(project, task_id=task_id, phase_name=phase_name)
    if as_json:
        print_json(result)
        return
    if agent_id:
        success(f"retried agent {agent_id}")
    else:
        success(f"retried phase {phase_name}")
