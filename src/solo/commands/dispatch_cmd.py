"""solo dispatch command."""

import json
from pathlib import Path
from typing import Any, Dict, Optional
from shutil import copyfile

import click

from solo.core.dispatcher import build_dispatcher, phase_event_details, runtime_failed
from solo.core.project import SoloProject
from solo.core.secretary import Secretary
from solo.core.task import AGENT, FAILED, TaskPhase
from solo.core.workflow import Workflow
from solo.utils.ui import print_json, success


def dispatch_task(
    project: SoloProject,
    description: str,
    workflow_name: Optional[str] = None,
    role: Optional[str] = None,
    adapter: Optional[str] = None,
    external_id: str = "",
    external_source: str = "",
    external_node: str = "",
    context_file: Optional[Path] = None,
) -> Dict[str, Any]:
    config = project.require_config()
    workflow_name = workflow_name or config.default_workflow

    if role:
        if role not in config.agents:
            raise click.ClickException(f"Unknown agent role: {role}")
        workflow = Workflow(name=f"direct:{role}", description="Direct role dispatch", phases=[])
    else:
        workflow = project.workflows.load(workflow_name)

    secretary = Secretary(config)
    task = secretary.create_task(
        description=description,
        workflow=workflow,
        artifacts_dir=project.solo_dir / "artifacts",
        direct_role=role,
        external=_external_payload(external_id, external_source, external_node),
    )
    if context_file:
        task.context = _copy_context_file(task, context_file)

    phase = task.get_phase(task.current_phase)
    if phase is None:
        phase = TaskPhase(name=role or "secretary", type=AGENT, role=role or "secretary")

    adapter = config.get_execution_adapter_for_role(phase.role or phase.name, override=adapter or "")
    dispatcher = build_dispatcher(adapter, config, project.agents)
    package = dispatcher.prepare_phase(task, phase)
    failed = runtime_failed(package)
    if failed:
        task.status = FAILED
        phase.status = FAILED
        for instance in task.agent_instances:
            if instance.phase == phase.name:
                instance.status = FAILED

    project.state.add_task(task)
    project.state.append_event("task.created", task.id, phase=task.current_phase)
    project.state.append_event("phase.started", task.id, phase=task.current_phase, details=phase_event_details(package))
    if failed:
        project.state.append_event("phase.failed", task.id, phase=task.current_phase, details=phase_event_details(package))
    project.state.append_message(
        task.id,
        from_agent="ceo",
        to_agent="secretary",
        message_type="request",
        phase=task.current_phase,
        summary=task.title,
        details={"external": task.external, "context": task.context},
    )
    project.state.append_message(
        task.id,
        from_agent="secretary",
        to_agent=package["agent_role"],
        message_type="assignment",
        phase=task.current_phase,
        summary=f"Prepare {task.current_phase} for {task.title}",
        artifact=package.get("instruction", package.get("report", "")),
        details=phase_event_details(package),
    )

    return {
        "task": task.to_dict(),
        "package": package,
    }


def _external_payload(external_id: str, external_source: str, external_node: str) -> Dict[str, Any]:
    payload = {
        "id": external_id,
        "source": external_source,
        "node": external_node,
    }
    return {key: value for key, value in payload.items() if value}


def _copy_context_file(task, context_file: Path) -> Dict[str, Any]:
    source = context_file.expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise click.ClickException(f"Context file not found: {context_file}")
    artifact_dir = Path(task.artifacts_dir)
    context_dir = artifact_dir / "context"
    context_dir.mkdir(parents=True, exist_ok=True)
    target = context_dir / source.name
    copyfile(source, target)
    return {
        "files": [
            {
                "source_path": str(source),
                "artifact": str(target),
                "relative_path": str(target.relative_to(artifact_dir)),
                "name": source.name,
            }
        ]
    }


@click.command("dispatch")
@click.option("--to", "role", default=None, help="Dispatch directly to an agent role.")
@click.option("--workflow", "workflow_name", default=None, help="Workflow name.")
@click.option("--adapter", default=None, help="Execution adapter. Defaults to config execution.default_adapter.")
@click.option("--external-id", default="", help="External orchestration id, e.g. solo-os cross task id.")
@click.option("--external-source", default="", help="External orchestration source, e.g. solo-os.")
@click.option("--external-node", default="", help="External project node id.")
@click.option("--context-file", type=click.Path(exists=True, dir_okay=False, path_type=Path), default=None, help="Context file to copy into task artifacts.")
@click.option("--json", "as_json", is_flag=True, help="Print structured JSON.")
@click.argument("description", nargs=-1, required=True)
def dispatch(role: str, workflow_name: str, adapter: str, external_id: str, external_source: str, external_node: str, context_file: Optional[Path], as_json: bool, description):
    """Create a task and generate the next agent execution package."""
    project = SoloProject.find(Path.cwd())
    if project is None:
        raise click.ClickException("No .solo project found. Run solo init first.")
    text = " ".join(description).strip()
    try:
        result = dispatch_task(
            project,
            text,
            workflow_name=workflow_name,
            role=role,
            adapter=adapter,
            external_id=external_id,
            external_source=external_source,
            external_node=external_node,
            context_file=context_file,
        )
    except (FileNotFoundError, KeyError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
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
