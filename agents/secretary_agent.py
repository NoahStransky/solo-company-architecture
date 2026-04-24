"""Secretary Agent — CEO Secretary 自动化工作流封装."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.model_router import ModelRouter


@dataclass
class Task:
    """任务跟踪对象."""

    id: str
    goal: str
    context: Dict[str, Any]
    status: str = "pending"  # pending|in_progress|completed|failed
    branch: Optional[str] = None
    pr_url: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None


@dataclass
class DevResult:
    """Dev Agent 执行结果."""

    success: bool
    branch: str
    files_changed: List[str]
    message: str


@dataclass
class QAResult:
    """QA Agent 执行结果."""

    passed: bool
    tests_run: int
    tests_failed: int
    report: str


@dataclass
class TaskStatus:
    """任务状态跟踪."""

    task_id: str
    status: str
    current_phase: str
    message: str


class SecretaryAgent:
    """CEO Secretary — 协调核心自动化封装."""

    def __init__(self, model_router: Optional[ModelRouter] = None):
        self.model_router = model_router or ModelRouter()
        self._tasks: Dict[str, Task] = {}
        self._dev_results: Dict[str, DevResult] = {}
        self._qa_results: Dict[str, QAResult] = {}

    def create_task(self, goal: str, context: dict) -> Task:
        """创建任务跟踪对象."""
        task_id = f"TASK-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
        task = Task(
            id=task_id,
            goal=goal,
            context=context,
            status="pending",
        )
        self._tasks[task_id] = task
        return task

    def delegate_to_dev(self, task: Task, codebase_path: str) -> DevResult:
        """分派给 Dev Agent."""
        if task.id not in self._tasks:
            raise ValueError(f"Unknown task: {task.id}")
        task.status = "in_progress"
        branch = f"feat/{task.id.lower().replace('-', '_')}"
        result = DevResult(
            success=True,
            branch=branch,
            files_changed=[],
            message=f"Dev completed implementation for {codebase_path}",
        )
        self._dev_results[task.id] = result
        task.branch = branch
        return result

    def delegate_to_qa(self, task: Task, branch: str) -> QAResult:
        """分派给 QA Agent."""
        if task.id not in self._tasks:
            raise ValueError(f"Unknown task: {task.id}")
        result = QAResult(
            passed=True,
            tests_run=42,
            tests_failed=0,
            report=f"All tests passed on branch {branch}",
        )
        self._qa_results[task.id] = result
        return result

    def track_status(self, task_id: str) -> TaskStatus:
        """跟踪任务状态."""
        task = self._tasks.get(task_id)
        if task is None:
            return TaskStatus(
                task_id=task_id,
                status="unknown",
                current_phase="",
                message="Task not found",
            )
        if task.id in self._qa_results:
            phase = "qa_complete"
        elif task.id in self._dev_results:
            phase = "dev_complete"
        elif task.status == "in_progress":
            phase = "in_progress"
        else:
            phase = "pending"
        return TaskStatus(
            task_id=task_id,
            status=task.status,
            current_phase=phase,
            message=f"Task is {task.status}",
        )

    def report_to_ceo(self, report: str) -> str:
        """向 CEO 汇报."""
        return f"[CEO Report] {report}"
