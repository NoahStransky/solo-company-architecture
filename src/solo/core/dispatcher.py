"""Execution package generation."""

from abc import ABC, abstractmethod
import json
import os
from pathlib import Path
import subprocess
from typing import Any, Dict

from .agent_registry import AgentRegistry
from .config import SoloConfig
from .model_router import ModelRouter
from .task import AGENT_POOL, SYSTEM, Task, TaskPhase


class ExecutionAdapter(ABC):
    """Adapter boundary for preparing or running a task phase."""

    name: str

    @abstractmethod
    def prepare_phase(self, task: Task, phase: TaskPhase) -> Dict[str, Any]:
        """Prepare or execute a phase and return structured metadata."""


class PackageDispatcher(ExecutionAdapter):
    """MVP dispatcher that writes agent instructions instead of running a model."""

    name = "package"

    def __init__(self, config: SoloConfig, agents: AgentRegistry):
        self.config = config
        self.agents = agents
        self.router = ModelRouter(config)

    def prepare_phase(self, task: Task, phase: TaskPhase) -> Dict[str, Any]:
        role = phase.role or phase.name
        artifact_dir = Path(task.artifacts_dir)
        artifact_dir.mkdir(parents=True, exist_ok=True)

        if phase.type == SYSTEM:
            report_path = artifact_dir / f"{phase.name}.md"
            task_path = artifact_dir / "task.json"
            report_path.write_text(self._system_report(task, phase), encoding="utf-8")
            task_path.write_text(json.dumps(task.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return {
                "adapter": "package",
                "phase": phase.name,
                "agent_role": role,
                "system": True,
                "report": str(report_path),
                "task": str(task_path),
            }

        agent = self.agents.load(role)
        model_config = self.router.resolve(role)
        provider_config = self.config.get_provider_for_agent(role).to_dict()
        mcp_servers = {
            name: {
                "command": config.command,
                "args": config.args,
                "env": config.env,
                "description": config.description,
            }
            for name, config in self.config.get_mcp_for_agent(role).items()
        }
        solo_dir = agent.prompt_path.parent.parent
        skills = {}
        for name, config in self.config.get_skills_for_agent(role).items():
            skill_path = solo_dir / config.path
            skills[name] = {
                "description": config.description,
                "path": config.path,
                "content": skill_path.read_text(encoding="utf-8") if skill_path.exists() else "",
            }
        package = {
            "task_id": task.id,
            "task_title": task.title,
            "task_description": task.description,
            "phase": phase.to_dict(),
            "agent_role": role,
            "agent_prompt_path": str(agent.prompt_path),
            "model_config": model_config,
            "provider_config": provider_config,
            "mcp_servers": mcp_servers,
            "skills": skills,
            "planned_dev_agents": task.planned_dev_agents,
            "agent_instances": [instance.to_dict() for instance in task.agent_instances],
            "work_packages": [package.to_dict() for package in task.work_packages],
            "output_dir": str(artifact_dir),
        }

        input_path = artifact_dir / f"{phase.name}_input.json"
        instruction_path = artifact_dir / f"{phase.name}_instruction.md"
        task_path = artifact_dir / "task.json"

        input_path.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        task_path.write_text(json.dumps(task.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        instruction_path.write_text(self._instruction(agent.prompt, package, phase), encoding="utf-8")

        return {
            "adapter": "package",
            "phase": phase.name,
            "agent_role": role,
            "model_config": model_config,
            "provider_config": provider_config,
            "mcp_servers": mcp_servers,
            "skills": skills,
            "input": str(input_path),
            "instruction": str(instruction_path),
            "task": str(task_path),
        }

    def _instruction(self, prompt: str, package: Dict[str, Any], phase: TaskPhase) -> str:
        lines = [
            f"# Agent execution package: {phase.name}",
            "",
            f"Task: {package['task_title']}",
            "",
            "## Role prompt",
            "",
            prompt.strip(),
            "",
            "## Task description",
            "",
            package["task_description"],
            "",
            "## Model",
            "",
            f"Provider: `{package['model_config']['provider']}`",
            f"Model: `{package['model_config']['model']}`",
            "",
            "## Skills",
            "",
            *(self._skill_lines(package["skills"])),
            "",
            "## MCP servers",
            "",
            *(self._mcp_lines(package["mcp_servers"])),
            "",
            "## Output",
            "",
            f"Write your result into `{package['output_dir']}/{phase.name}_output.md`.",
        ]
        if phase.type == AGENT_POOL:
            lines.extend([
                "",
                "## Dev pool",
                "",
                f"Secretary planned {package['planned_dev_agents']} dev agent(s) for this task.",
                "CTO should provide work packages that can be assigned without overlapping file ownership.",
            ])
        return "\n".join(lines) + "\n"

    def _system_report(self, task: Task, phase: TaskPhase) -> str:
        return "\n".join([
            f"# {phase.name}",
            "",
            f"Task: {task.title}",
            f"Status: {task.status}",
            f"Current phase: {task.current_phase}",
            "",
            "This report was generated by the package dispatcher.",
            "",
        ])

    def _skill_lines(self, skills: Dict[str, Any]) -> list:
        if not skills:
            return ["No extra skills enabled."]
        return [
            f"- `{name}`: {config.get('description', '')} ({config.get('path', '')})"
            for name, config in skills.items()
        ]

    def _mcp_lines(self, mcp_servers: Dict[str, Any]) -> list:
        if not mcp_servers:
            return ["No MCP servers enabled."]
        return [
            f"- `{name}`: `{config.get('command', '')} {' '.join(config.get('args', []))}`"
            for name, config in mcp_servers.items()
        ]


class CommandDispatcher(ExecutionAdapter):
    """Runtime adapter that executes a configured external command."""

    name = "command"

    def __init__(self, config: SoloConfig, agents: AgentRegistry):
        self.config = config
        self.package_dispatcher = PackageDispatcher(config, agents)

    def prepare_phase(self, task: Task, phase: TaskPhase) -> Dict[str, Any]:
        package_result = self.package_dispatcher.prepare_phase(task, phase)
        if package_result.get("system"):
            package_result["adapter"] = self.name
            package_result["runtime"] = {"skipped": "system phase"}
            return package_result

        runtime = self.config.execution.command
        if not runtime.command:
            raise ValueError("execution.command.command is required for command adapter")

        env = os.environ.copy()
        env.update(runtime.env)
        env.update({
            "SOLO_TASK_ID": task.id,
            "SOLO_PHASE": phase.name,
            "SOLO_AGENT_ROLE": package_result["agent_role"],
            "SOLO_PACKAGE_INPUT": package_result["input"],
            "SOLO_PACKAGE_INSTRUCTION": package_result["instruction"],
            "SOLO_OUTPUT_DIR": str(Path(task.artifacts_dir)),
        })

        command = [
            runtime.command,
            *[
                self._format_arg(arg, package_result, task, phase)
                for arg in runtime.args
            ],
        ]
        completed = subprocess.run(
            command,
            cwd=Path(task.artifacts_dir),
            env=env,
            text=True,
            capture_output=True,
            timeout=runtime.timeout,
            check=False,
        )
        runtime_result = {
            "command": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
        runtime_path = Path(task.artifacts_dir) / f"{phase.name}_runtime.json"
        runtime_path.write_text(json.dumps(runtime_result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = dict(package_result)
        result["adapter"] = self.name
        result["runtime"] = runtime_result
        result["runtime_report"] = str(runtime_path)
        return result

    def _format_arg(self, arg: str, package_result: Dict[str, Any], task: Task, phase: TaskPhase) -> str:
        return arg.format(
            task_id=task.id,
            phase=phase.name,
            agent_role=package_result["agent_role"],
            input=package_result.get("input", ""),
            instruction=package_result.get("instruction", ""),
            output_dir=str(Path(task.artifacts_dir)),
        )


def build_dispatcher(adapter: str, config: SoloConfig, agents: AgentRegistry) -> ExecutionAdapter:
    """Create an execution adapter by name."""
    if adapter == PackageDispatcher.name:
        return PackageDispatcher(config, agents)
    if adapter == CommandDispatcher.name:
        return CommandDispatcher(config, agents)
    raise ValueError(f"Unknown execution adapter: {adapter}")


def available_adapters() -> list:
    """Return adapter names supported by this CLI build."""
    return [PackageDispatcher.name, CommandDispatcher.name]


def phase_event_details(package: Dict[str, Any]) -> Dict[str, Any]:
    """Build a small event payload for dashboards and status readers."""
    details: Dict[str, Any] = {
        "adapter": package.get("adapter", ""),
        "agent_role": package.get("agent_role", ""),
    }
    for key in ("input", "instruction", "report", "runtime_report"):
        if package.get(key):
            details[key] = package[key]
    runtime = package.get("runtime") or {}
    if "returncode" in runtime:
        details["runtime_returncode"] = runtime["returncode"]
    if runtime.get("skipped"):
        details["runtime_skipped"] = runtime["skipped"]
    return {key: value for key, value in details.items() if value not in ("", None)}
