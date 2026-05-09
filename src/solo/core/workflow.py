"""Workflow loading and phase expansion."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .task import AGENT, TaskPhase


@dataclass
class WorkflowPhase:
    name: str
    type: str = AGENT
    role: Optional[str] = None
    depends_on: List[str] = field(default_factory=list)
    optional: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowPhase":
        return cls(
            name=str(data["name"]),
            type=str(data.get("type", AGENT)),
            role=data.get("role"),
            depends_on=list(data.get("depends_on", [])),
            optional=bool(data.get("optional", False)),
        )

    def to_task_phase(self) -> TaskPhase:
        return TaskPhase(
            name=self.name,
            type=self.type,
            role=self.role,
            depends_on=list(self.depends_on),
            optional=self.optional,
        )


@dataclass
class Workflow:
    name: str
    description: str
    phases: List[WorkflowPhase]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Workflow":
        return cls(
            name=str(data["name"]),
            description=str(data.get("description", "")),
            phases=[WorkflowPhase.from_dict(item) for item in data.get("phases", [])],
        )

    def to_task_phases(self) -> List[TaskPhase]:
        return [phase.to_task_phase() for phase in self.phases]


class WorkflowRegistry:
    def __init__(self, workflows_dir: Path):
        self.workflows_dir = workflows_dir

    def load(self, name: str) -> Workflow:
        path = self.workflows_dir / f"{name}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Workflow not found: {name}")
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        return Workflow.from_dict(data)

    def list_names(self) -> List[str]:
        if not self.workflows_dir.exists():
            return []
        return sorted(path.stem for path in self.workflows_dir.glob("*.yaml"))
