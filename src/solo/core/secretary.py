"""Secretary orchestration logic."""

from pathlib import Path
from typing import List, Optional
from uuid import uuid4

from .config import SoloConfig
from .task import AGENT, AGENT_POOL, AgentInstance, IN_PROGRESS, PENDING, Task, TaskPhase, utc_now_iso
from .workflow import Workflow


class Secretary:
    """Default CEO-facing coordinator for one solo project."""

    def __init__(self, config: SoloConfig):
        self.config = config

    def create_task(
        self,
        description: str,
        workflow: Workflow,
        artifacts_dir: Path,
        direct_role: Optional[str] = None,
        external: Optional[dict] = None,
        context: Optional[dict] = None,
    ) -> Task:
        task_id = self._new_task_id()
        title = self._make_title(description)
        if direct_role:
            phases = [TaskPhase(name=direct_role, type=AGENT, role=direct_role)]
            workflow_name = f"direct:{direct_role}"
        else:
            phases = workflow.to_task_phases()
            workflow_name = workflow.name

        planned_dev_agents = self.estimate_dev_agent_count(description, phases)
        self._attach_planned_dev_instances(phases, planned_dev_agents)
        current_phase = self._first_executable_phase(phases)
        for phase in phases:
            if phase.name == current_phase:
                phase.status = IN_PROGRESS
                break

        return Task(
            id=task_id,
            title=title,
            description=description,
            status=IN_PROGRESS,
            workflow=workflow_name,
            current_phase=current_phase,
            phases=phases,
            planned_dev_agents=planned_dev_agents,
            agent_instances=self._make_agent_instances(phases),
            artifacts_dir=str(artifacts_dir / task_id),
            external=external or {},
            context=context or {},
        )

    def estimate_dev_agent_count(self, description: str, phases: List[TaskPhase]) -> int:
        has_dev_pool = any(phase.type == AGENT_POOL and (phase.role or phase.name).startswith("dev") for phase in phases)
        has_dev = any((phase.role == "dev" or phase.name == "dev") for phase in phases)
        if not has_dev_pool and not has_dev:
            return 0

        text = description.lower()
        score = 1
        large_markers = ["refactor", "migration", "full", "system", "platform", "multi", "多个", "重构", "系统", "平台"]
        medium_markers = ["api", "database", "frontend", "backend", "test", "auth", "dashboard", "接口", "数据库", "前端", "后端"]
        if len(description) > 180 or any(marker in text for marker in large_markers):
            score = 3
        elif len(description) > 80 or any(marker in text for marker in medium_markers):
            score = 2
        return min(score, self.config.delegation.max_parallel_dev_agents)

    def _attach_planned_dev_instances(self, phases: List[TaskPhase], planned_dev_agents: int) -> None:
        if planned_dev_agents <= 0:
            return
        for phase in phases:
            if phase.type == AGENT_POOL and phase.role == "dev":
                phase.instance_ids = [f"dev-{index + 1}" for index in range(planned_dev_agents)]

    def _make_agent_instances(self, phases: List[TaskPhase]) -> List[AgentInstance]:
        instances: List[AgentInstance] = []
        for phase in phases:
            if phase.type == AGENT and phase.status == IN_PROGRESS:
                role = phase.role or phase.name
                instances.append(AgentInstance(id=f"{phase.name}-1", role=role, phase=phase.name, status=phase.status))
            elif phase.type == AGENT_POOL:
                role = phase.role or phase.name
                for instance_id in phase.instance_ids:
                    instances.append(AgentInstance(id=instance_id, role=role, phase=phase.name, status=PENDING))
        return instances

    def _first_executable_phase(self, phases: List[TaskPhase]) -> str:
        for phase in phases:
            if phase.type in (AGENT, AGENT_POOL):
                return phase.name
        return phases[0].name if phases else ""

    def _new_task_id(self) -> str:
        stamp = utc_now_iso().replace("-", "").replace(":", "").replace("+00:00", "Z")
        return f"TASK-{stamp}-{uuid4().hex[:6]}"

    def _make_title(self, description: str) -> str:
        first_line = description.strip().splitlines()[0] if description.strip() else "Untitled task"
        return first_line[:80]
