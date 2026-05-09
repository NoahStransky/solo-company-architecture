"""solo dispatch command."""

import json
from pathlib import Path
from typing import Any, Dict, Optional

import click

from solo.core.dispatcher import build_dispatcher
from solo.core.project import SoloProject
from solo.core.secretary import Secretary
from solo.core.task import AGENT, TaskPhase
from solo.core.workflow import Workflow
from solo.utils.ui import print_json, success


def dispatch_task(
    project: SoloProject,
    description: str,
    workflow_name: Optional[str] = None,
    role: Optional[str] = None,
    adapter: Optional[str] = None,
) -> Dict[str, Any]:
    config = project.require_config()
    workflow_name = workflow_name or config.default_workflow
    adapter = adapter or config.execution.default_adapter

    if role:
        workflow = Workflow(name=f"direct:{role}", description="Direct role dispatch", phases=[])
    else:
        workflow = project.workflows.load(workflow_name)

    secretary = Secretary(config)
    task = secretary.create_task(
        description=description,
        workflow=workflow,
        artifacts_dir=project.solo_dir / "artifacts",
        direct_role=role,
    )

    phase = task.get_phase(task.current_phase)
    if phase is None:
        phase = TaskPhase(name=role or "secretary", type=AGENT, role=role or "secretary")

    dispatcher = build_dispatcher(adapter, config, project.agents)
    package = dispatcher.prepare_phase(task, phase)

    project.state.add_task(task)
    project.state.append_event("task.created", task.id, phase=task.current_phase)
    project.state.append_event("phase.started", task.id, phase=task.current_phase, details={"agent_role": package["agent_role"]})

    return {
        "task": task.to_dict(),
        "package": package,
    }


@click.command("dispatch")
@click.option("--to", "role", default=None, help="Dispatch directly to an agent role.")
@click.option("--workflow", "workflow_name", default=None, help="Workflow name.")
@click.option("--adapter", default=None, help="Execution adapter. Defaults to config execution.default_adapter.")
@click.option("--json", "as_json", is_flag=True, help="Print structured JSON.")
@click.argument("description", nargs=-1, required=True)
def dispatch(role: str, workflow_name: str, adapter: str, as_json: bool, description):
    """Create a task and generate the next agent execution package."""
    project = SoloProject.find(Path.cwd())
    if project is None:
        raise click.ClickException("No .solo project found. Run solo init first.")
    text = " ".join(description).strip()
    result = dispatch_task(project, text, workflow_name=workflow_name, role=role, adapter=adapter)
    if as_json:
        print_json(result)
        return
    task = result["task"]
    package = result["package"]
    success(f"created task {task['id']}")
    click.echo(f"Current phase: {task['current_phase']}")
    click.echo(f"Planned dev agents: {task['planned_dev_agents']}")
    click.echo(f"Instruction: {package['instruction']}")
    click.echo(f"Input: {package['input']}")
