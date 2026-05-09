"""State store for .solo/state."""

import contextlib
import fcntl
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from .task import TASK_SCHEMA_VERSION, Task, utc_now_iso


class StateStore:
    """Read and write .solo task snapshots and event logs."""

    def __init__(self, solo_dir: Path):
        self.solo_dir = solo_dir
        self.state_dir = solo_dir / "state"
        self.tasks_file = self.state_dir / "tasks.json"
        self.events_file = self.state_dir / "events.jsonl"
        self.lock_file = self.state_dir / ".lock"

    def init(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        if not self.tasks_file.exists():
            self.save_tasks([])
        if not self.events_file.exists():
            self.events_file.write_text("", encoding="utf-8")

    def load_tasks(self) -> List[Task]:
        if not self.tasks_file.exists():
            return []
        with self.tasks_file.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return [Task.from_dict(item) for item in data.get("tasks", [])]

    def save_tasks(self, tasks: List[Task]) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": TASK_SCHEMA_VERSION,
            "tasks": [task.to_dict() for task in tasks],
        }
        self._atomic_write_json(self.tasks_file, payload)

    def add_task(self, task: Task) -> None:
        with self.locked():
            tasks = self.load_tasks()
            tasks.append(task)
            self.save_tasks(tasks)

    def update_task(self, task: Task) -> None:
        with self.locked():
            tasks = self.load_tasks()
            replaced = False
            for index, existing in enumerate(tasks):
                if existing.id == task.id:
                    tasks[index] = task
                    replaced = True
                    break
            if not replaced:
                tasks.append(task)
            self.save_tasks(tasks)

    def get_task(self, task_id: str) -> Optional[Task]:
        for task in self.load_tasks():
            if task.id == task_id:
                return task
        return None

    def append_event(self, event: str, task_id: str, phase: str = "", details: Optional[Dict[str, Any]] = None) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        payload: Dict[str, Any] = {
            "ts": utc_now_iso(),
            "task_id": task_id,
            "event": event,
        }
        if phase:
            payload["phase"] = phase
        if details:
            payload["details"] = details
        with self.locked():
            with self.events_file.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def load_events(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        if not self.events_file.exists():
            return []
        events = []
        with self.events_file.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
        if limit is not None:
            return events[-limit:]
        return events

    @contextlib.contextmanager
    def locked(self) -> Iterator[None]:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        with self.lock_file.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _atomic_write_json(self, path: Path, payload: Dict[str, Any]) -> None:
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        tmp_path.replace(path)
