"""Execution package generation."""

from abc import ABC, abstractmethod
import json
from pathlib import Path
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


def build_dispatcher(adapter: str, config: SoloConfig, agents: AgentRegistry) -> ExecutionAdapter:
    """Create an execution adapter by name."""
    if adapter == PackageDispatcher.name:
        return PackageDispatcher(config, agents)
    raise ValueError(f"Unknown execution adapter: {adapter}")
