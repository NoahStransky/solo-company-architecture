import json
from pathlib import Path

from solo.core.state import StateStore
from solo.core.task import IN_PROGRESS, Task, TaskPhase


def test_state_store_round_trips_tasks_and_events(tmp_path):
    solo_dir = tmp_path / ".solo"
    store = StateStore(solo_dir)
    store.init()

    task = Task(
        id="TASK-test",
        title="Test task",
        description="Verify state",
        status=IN_PROGRESS,
        workflow="feature",
        current_phase="cto_breakdown",
        phases=[TaskPhase(name="cto_breakdown", role="cto", status=IN_PROGRESS)],
        artifacts_dir=".solo/artifacts/TASK-test",
    )

    store.add_task(task)
    store.append_event("task.created", task.id, phase="cto_breakdown")
    store.append_message(
        task.id,
        from_agent="secretary",
        to_agent="cto",
        message_type="assignment",
        phase="cto_breakdown",
        summary="Break down the task",
        artifact=".solo/artifacts/TASK-test/cto_breakdown_instruction.md",
    )

    loaded = store.load_tasks()
    events = store.load_events()
    messages = store.load_messages()

    assert loaded[0].id == "TASK-test"
    assert loaded[0].current_phase == "cto_breakdown"
    assert events[0]["event"] == "task.created"
    assert messages[0]["from"] == "secretary"
    assert messages[0]["to"] == "cto"
    assert messages[0]["type"] == "assignment"
    assert json.loads((solo_dir / "state" / "tasks.json").read_text())["schema_version"] == 1
    assert (solo_dir / "state" / ".lock").exists()


def test_state_store_atomic_update_replaces_existing_task(tmp_path):
    solo_dir = tmp_path / ".solo"
    store = StateStore(solo_dir)
    store.init()

    task = Task(
        id="TASK-test",
        title="Test task",
        description="Verify state",
        status=IN_PROGRESS,
        workflow="feature",
        current_phase="cto_breakdown",
        phases=[TaskPhase(name="cto_breakdown", role="cto", status=IN_PROGRESS)],
        artifacts_dir=".solo/artifacts/TASK-test",
    )

    store.add_task(task)
    task.current_phase = "dev_pool"
    store.update_task(task)

    loaded = store.load_tasks()
    assert len(loaded) == 1
    assert loaded[0].current_phase == "dev_pool"
    assert not (solo_dir / "state" / "tasks.json.tmp").exists()
