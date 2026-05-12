"""solo validate command."""

import json
from pathlib import Path
from typing import Any, Dict, List

import click

from solo.core.config import SoloConfig
from solo.core.dispatcher import available_adapters
from solo.core.project import SoloProject
from solo.core.workflow import Workflow
from solo.utils.ui import print_json, success


REQUIRED_CONTRACTS = [
    "work_packages.schema.json",
    "agent_result.schema.json",
    "qa_report.schema.json",
    "message.schema.json",
]
QA_VERDICTS = {"pass", "fail", "blocked", "needs_review"}


def validate_project(project: SoloProject) -> Dict[str, Any]:
    """Validate the local .solo protocol surface."""
    config = project.require_config()
    errors: List[Dict[str, str]] = []
    warnings: List[Dict[str, str]] = []

    _check_required_paths(project, errors)
    _check_config(project, config, errors, warnings)
    _check_workflows(project, config, errors, warnings)
    _check_state_files(project, errors)
    _check_artifact_contracts(project, errors)

    return {
        "ok": not errors,
        "project": config.project.__dict__,
        "solo_protocol_version": config.solo_protocol_version,
        "summary": {
            "errors": len(errors),
            "warnings": len(warnings),
        },
        "errors": errors,
        "warnings": warnings,
    }


def _issue(code: str, message: str, path: Path = Path("")) -> Dict[str, str]:
    payload = {"code": code, "message": message}
    if str(path):
        payload["path"] = str(path)
    return payload


def _check_required_paths(project: SoloProject, errors: List[Dict[str, str]]) -> None:
    required_paths = [
        project.solo_dir,
        project.config_path,
        project.solo_dir / "agents",
        project.solo_dir / "workflows",
        project.solo_dir / "skills",
        project.solo_dir / "state",
        project.state.tasks_file,
        project.state.events_file,
        project.state.messages_file,
        project.solo_dir / "artifacts",
        project.solo_dir / "contracts",
    ]
    for path in required_paths:
        if not path.exists():
            errors.append(_issue("missing_path", f"Missing required path: {path}", path))
    for name in REQUIRED_CONTRACTS:
        path = project.solo_dir / "contracts" / name
        if not path.exists():
            errors.append(_issue("missing_contract", f"Missing contract schema: {name}", path))


def _check_config(
    project: SoloProject,
    config: SoloConfig,
    errors: List[Dict[str, str]],
    warnings: List[Dict[str, str]],
) -> None:
    adapters = set(available_adapters())
    if config.execution.default_adapter not in adapters:
        errors.append(_issue("unknown_default_adapter", f"Unknown default adapter: {config.execution.default_adapter}", project.config_path))
    if config.default_workflow and not (project.solo_dir / "workflows" / f"{config.default_workflow}.yaml").exists():
        errors.append(_issue("missing_default_workflow", f"Missing default workflow: {config.default_workflow}", project.config_path))

    for role, agent in config.agents.items():
        prompt_path = project.solo_dir / "agents" / f"{role}.md"
        if not prompt_path.exists():
            errors.append(_issue("missing_agent_prompt", f"Missing prompt for agent role: {role}", prompt_path))
        if agent.provider not in config.providers:
            errors.append(_issue("missing_provider", f"Agent {role} references unknown provider: {agent.provider}", project.config_path))
        if agent.runtime and agent.runtime not in config.runtime_profiles:
            errors.append(_issue("missing_runtime_profile", f"Agent {role} references unknown runtime profile: {agent.runtime}", project.config_path))
        for skill in agent.skills:
            if skill not in config.skills:
                errors.append(_issue("missing_skill", f"Agent {role} references unknown skill: {skill}", project.config_path))
        for server in agent.mcp_servers:
            if server not in config.mcp_servers:
                errors.append(_issue("missing_mcp_server", f"Agent {role} references unknown MCP server: {server}", project.config_path))

    for name, profile in config.runtime_profiles.items():
        if profile.adapter not in adapters:
            errors.append(_issue("unknown_profile_adapter", f"Runtime profile {name} uses unknown adapter: {profile.adapter}", project.config_path))
        if profile.adapter == "command" and not profile.command.command:
            warnings.append(_issue("empty_command_profile", f"Runtime profile {name} has no command configured", project.config_path))

    for name, skill in config.skills.items():
        skill_path = project.solo_dir / skill.path
        if not skill_path.exists():
            errors.append(_issue("missing_skill_file", f"Skill {name} points to missing file: {skill.path}", skill_path))


def _check_workflows(
    project: SoloProject,
    config: SoloConfig,
    errors: List[Dict[str, str]],
    warnings: List[Dict[str, str]],
) -> None:
    for workflow_name in project.workflows.list_names():
        workflow_path = project.solo_dir / "workflows" / f"{workflow_name}.yaml"
        try:
            workflow = project.workflows.load(workflow_name)
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(_issue("invalid_workflow", f"Invalid workflow {workflow_name}: {exc}", workflow_path))
            continue
        _check_workflow(project, config, workflow, errors, warnings)


def _check_workflow(
    project: SoloProject,
    config: SoloConfig,
    workflow: Workflow,
    errors: List[Dict[str, str]],
    warnings: List[Dict[str, str]],
) -> None:
    phase_names = {phase.name for phase in workflow.phases}
    workflow_path = project.solo_dir / "workflows" / f"{workflow.name}.yaml"
    if not workflow.phases:
        warnings.append(_issue("empty_workflow", f"Workflow {workflow.name} has no phases", workflow_path))
    for phase in workflow.phases:
        role = phase.role or phase.name
        if phase.type in ("agent", "agent_pool") and role not in config.agents:
            errors.append(_issue("missing_workflow_agent", f"Workflow {workflow.name} phase {phase.name} references unknown role: {role}", workflow_path))
        for dependency in phase.depends_on:
            if dependency not in phase_names:
                errors.append(_issue("missing_phase_dependency", f"Workflow {workflow.name} phase {phase.name} depends on missing phase: {dependency}", workflow_path))


def _check_state_files(project: SoloProject, errors: List[Dict[str, str]]) -> None:
    try:
        project.state.load_tasks()
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        errors.append(_issue("invalid_tasks_state", f"Invalid tasks state: {exc}", project.state.tasks_file))
    _check_jsonl(project.state.events_file, "invalid_event_log", errors)
    _check_jsonl(project.state.messages_file, "invalid_message_log", errors)


def _check_jsonl(path: Path, code: str, errors: List[Dict[str, str]]) -> None:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(_issue(code, f"Invalid JSONL at line {line_number}: {exc}", path))


def _check_artifact_contracts(project: SoloProject, errors: List[Dict[str, str]]) -> None:
    try:
        tasks = project.state.load_tasks()
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return
    for task in tasks:
        artifact_dir = Path(task.artifacts_dir)
        if not artifact_dir.exists():
            continue
        for path in sorted(item for item in artifact_dir.rglob("*.json") if item.is_file()):
            name = path.name
            if name == "work_packages.json" or name == "cto_breakdown_output.json":
                payload = _load_json_artifact(path, errors)
                if payload is not None:
                    _validate_work_packages_payload(payload, path, errors)
            elif name == "qa_report.json":
                payload = _load_json_artifact(path, errors)
                if payload is not None:
                    _validate_qa_report_payload(payload, path, errors)
            elif (name.endswith("_agent_result.json") or name.endswith("_result.json")) and not name.endswith("_runtime.json"):
                payload = _load_json_artifact(path, errors)
                if payload is not None:
                    _validate_agent_result_payload(payload, path, errors)


def _load_json_artifact(path: Path, errors: List[Dict[str, str]]) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:
        errors.append(_issue("invalid_artifact_json", f"Invalid artifact JSON: {exc}", path))
        return None


def _validate_work_packages_payload(payload: Any, path: Path, errors: List[Dict[str, str]]) -> None:
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = payload.get("work_packages", [])
    else:
        errors.append(_issue("invalid_work_packages", "Work packages payload must be an object or array", path))
        return
    if not isinstance(items, list):
        errors.append(_issue("invalid_work_packages", "work_packages must be an array", path))
        return
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            errors.append(_issue("invalid_work_packages", f"Work package #{index} must be an object", path))
            continue
        missing = [key for key in ("id", "title", "description") if not str(item.get(key, "")).strip()]
        if missing:
            errors.append(_issue("invalid_work_packages", f"Work package #{index} is missing: {', '.join(missing)}", path))


def _validate_agent_result_payload(payload: Any, path: Path, errors: List[Dict[str, str]]) -> None:
    if not isinstance(payload, dict):
        errors.append(_issue("invalid_agent_result", "Agent result must be an object", path))
        return
    if not str(payload.get("summary", "")).strip():
        errors.append(_issue("invalid_agent_result", "Agent result requires summary", path))
    work_packages = payload.get("work_packages", [])
    if work_packages and not isinstance(work_packages, list):
        errors.append(_issue("invalid_agent_result", "Agent result work_packages must be an array", path))
        return
    for index, item in enumerate(work_packages, start=1):
        if not isinstance(item, dict):
            errors.append(_issue("invalid_agent_result", f"Agent result work package #{index} must be an object", path))
            continue
        missing = [key for key in ("id", "status") if not str(item.get(key, "")).strip()]
        if missing:
            errors.append(_issue("invalid_agent_result", f"Agent result work package #{index} is missing: {', '.join(missing)}", path))


def _validate_qa_report_payload(payload: Any, path: Path, errors: List[Dict[str, str]]) -> None:
    if not isinstance(payload, dict):
        errors.append(_issue("invalid_qa_report", "QA report must be an object", path))
        return
    if not str(payload.get("summary", "")).strip():
        errors.append(_issue("invalid_qa_report", "QA report requires summary", path))
    verdict = str(payload.get("verdict", "")).strip()
    if verdict not in QA_VERDICTS:
        errors.append(_issue("invalid_qa_report", f"QA report verdict must be one of: {', '.join(sorted(QA_VERDICTS))}", path))


@click.command("validate")
@click.option("--json", "as_json", is_flag=True, help="Print structured JSON.")
def validate(as_json: bool):
    """Validate the local .solo protocol directory."""
    project = SoloProject.find(Path.cwd())
    if project is None:
        raise click.ClickException("No .solo project found. Run solo init first.")
    payload = validate_project(project)
    if as_json:
        print_json(payload)
    else:
        if payload["ok"]:
            success("solo protocol is valid")
        for issue in payload["errors"]:
            click.echo(f"ERROR {issue['code']}: {issue['message']}", err=True)
        for issue in payload["warnings"]:
            click.echo(f"WARN {issue['code']}: {issue['message']}", err=True)
    if not payload["ok"]:
        raise click.exceptions.Exit(1)
