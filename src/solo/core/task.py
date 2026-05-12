"""Task protocol models for .solo/state/tasks.json."""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


TASK_SCHEMA_VERSION = 1

PENDING = "pending"
IN_PROGRESS = "in_progress"
BLOCKED = "blocked"
WAITING_APPROVAL = "waiting_approval"
COMPLETED = "completed"
FAILED = "failed"
SKIPPED = "skipped"

AGENT = "agent"
AGENT_POOL = "agent_pool"
HUMAN_GATE = "human_gate"
SYSTEM = "system"


def utc_now_iso() -> str:
    """Return a stable ISO timestamp for protocol files."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class TaskPhase:
    name: str
    type: str = AGENT
    status: str = PENDING
    role: Optional[str] = None
    depends_on: List[str] = field(default_factory=list)
    instance_ids: List[str] = field(default_factory=list)
    optional: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskPhase":
        return cls(
            name=data["name"],
            type=data.get("type", AGENT),
            status=data.get("status", PENDING),
            role=data.get("role"),
            depends_on=list(data.get("depends_on", [])),
            instance_ids=list(data.get("instance_ids", [])),
            optional=bool(data.get("optional", False)),
        )

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        return {key: value for key, value in data.items() if value not in (None, [], False)}


@dataclass
class AgentInstance:
    id: str
    role: str
    status: str = PENDING
    phase: Optional[str] = None
    work_package_id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentInstance":
        return cls(
            id=data["id"],
            role=data["role"],
            status=data.get("status", PENDING),
            phase=data.get("phase"),
            work_package_id=data.get("work_package_id"),
        )

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        return {key: value for key, value in data.items() if value is not None}


@dataclass
class WorkPackage:
    id: str
    title: str
    description: str
    agent_role: str = "dev"
    status: str = PENDING
    files_scope: List[str] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)
    agent_instance: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkPackage":
        return cls(
            id=data["id"],
            title=data["title"],
            description=data.get("description", ""),
            agent_role=data.get("agent_role", "dev"),
            status=data.get("status", PENDING),
            files_scope=list(data.get("files_scope", [])),
            depends_on=list(data.get("depends_on", [])),
            agent_instance=data.get("agent_instance"),
        )

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        return {key: value for key, value in data.items() if value not in (None, [])}


@dataclass
class PhaseResult:
    phase: str
    from_agent: str
    summary: str
    status: str = ""
    verdict: Optional[str] = None
    artifact: str = ""
    data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PhaseResult":
        return cls(
            phase=data["phase"],
            from_agent=data.get("from_agent", data.get("agent", "")),
            summary=data.get("summary", ""),
            status=data.get("status", ""),
            verdict=data.get("verdict"),
            artifact=data.get("artifact", ""),
            data=dict(data.get("data", {})),
        )

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        return {key: value for key, value in data.items() if value not in (None, "", {})}


@dataclass
class Task:
    id: str
    title: str
    description: str
    status: str
    workflow: str
    current_phase: str
    phases: List[TaskPhase]
    artifacts_dir: str
    planned_dev_agents: int = 0
    work_packages: List[WorkPackage] = field(default_factory=list)
    phase_results: List[PhaseResult] = field(default_factory=list)
    agent_instances: List[AgentInstance] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        return cls(
            id=data["id"],
            title=data.get("title", data.get("description", "")),
            description=data.get("description", ""),
            status=data.get("status", PENDING),
            workflow=data.get("workflow", "feature"),
            current_phase=data.get("current_phase", ""),
            phases=[TaskPhase.from_dict(item) for item in data.get("phases", [])],
            artifacts_dir=data.get("artifacts_dir", ""),
            planned_dev_agents=int(data.get("planned_dev_agents", 0)),
            work_packages=[WorkPackage.from_dict(item) for item in data.get("work_packages", [])],
            phase_results=[PhaseResult.from_dict(item) for item in data.get("phase_results", [])],
            agent_instances=[AgentInstance.from_dict(item) for item in data.get("agent_instances", [])],
            created_at=data.get("created_at", utc_now_iso()),
            updated_at=data.get("updated_at", utc_now_iso()),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "workflow": self.workflow,
            "current_phase": self.current_phase,
            "phases": [phase.to_dict() for phase in self.phases],
            "planned_dev_agents": self.planned_dev_agents,
            "work_packages": [package.to_dict() for package in self.work_packages],
            "phase_results": [result.to_dict() for result in self.phase_results],
            "agent_instances": [instance.to_dict() for instance in self.agent_instances],
            "artifacts_dir": self.artifacts_dir,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def touch(self) -> None:
        self.updated_at = utc_now_iso()

    def get_phase(self, name: str) -> Optional[TaskPhase]:
        for phase in self.phases:
            if phase.name == name:
                return phase
        return None
