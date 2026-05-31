import json
from pathlib import Path
import sys

from click.testing import CliRunner

from solo.cli import main


PROTOCOL_KEYS = {
    "current_version",
    "supported_version",
    "compatible",
    "migration_needed",
    "migration_available",
    "migration_error",
    "migration_steps",
}

DASHBOARD_TASK_KEYS = {
    "task_id",
    "title",
    "status",
    "workflow",
    "current_phase",
    "current_phase_index",
    "phase_progress",
    "phases",
    "agent_progress",
    "work_package_progress",
    "failed_reason",
    "updated_at",
}


def test_solo_os_dashboard_json_contract_fields_are_stable():
    runner = CliRunner()
    with runner.isolated_filesystem():
        task_id = _run_completed_dummy_flow(runner)

        status = runner.invoke(main, ["status", "--json", "--all"])
        inspect = runner.invoke(main, ["inspect", "--task", task_id, "--json"])

        assert status.exit_code == 0, status.output
        assert inspect.exit_code == 0, inspect.output
        status_payload = json.loads(status.output)
        inspect_payload = json.loads(inspect.output)

        assert {
            "project",
            "solo_protocol_version",
            "protocol",
            "paths",
            "execution",
            "summary",
            "dashboard",
            "tasks",
            "recent_events",
            "recent_messages",
        } <= set(status_payload)
        assert set(status_payload["protocol"]) == PROTOCOL_KEYS
        assert status_payload["protocol"]["compatible"] is True
        assert {"root", "solo_dir", "config", "tasks", "events", "messages", "artifacts"} <= set(status_payload["paths"])
        assert {"default_adapter", "default_profile", "available_adapters", "runtime_profiles"} <= set(status_payload["execution"])

        dashboard_task = status_payload["dashboard"]["tasks"][0]
        assert DASHBOARD_TASK_KEYS <= set(dashboard_task)
        assert {"total", "completed", "skipped", "done", "percent"} <= set(dashboard_task["phase_progress"])
        assert {"total", "by_status", "failed_agents", "percent"} <= set(dashboard_task["agent_progress"])
        assert {"total", "by_status", "percent"} <= set(dashboard_task["work_package_progress"])

        assert {"project", "protocol", "task", "dashboard", "handoff", "paths", "artifacts", "events", "messages"} <= set(inspect_payload)
        assert set(inspect_payload["protocol"]) == PROTOCOL_KEYS
        assert inspect_payload["dashboard"]["task_id"] == task_id
        assert DASHBOARD_TASK_KEYS <= set(inspect_payload["dashboard"])
        assert {
            "summary",
            "task_id",
            "status",
            "external",
            "context",
            "phase_progress",
            "artifacts",
        } <= set(inspect_payload["handoff"])
        assert {"root", "solo_dir", "artifacts_dir", "events", "messages"} <= set(inspect_payload["paths"])
        assert inspect_payload["artifacts"]
        assert {"name", "path", "relative_path", "size_bytes", "kind"} <= set(inspect_payload["artifacts"][0])


def test_state_message_and_artifact_contract_fields_are_stable():
    runner = CliRunner()
    with runner.isolated_filesystem():
        task_id = _run_completed_dummy_flow(runner)
        task_state = json.loads(Path(".solo/state/tasks.json").read_text(encoding="utf-8"))
        messages = [
            json.loads(line)
            for line in Path(".solo/state/messages.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        inspect = runner.invoke(main, ["inspect", "--task", task_id, "--json"])

        assert task_state["schema_version"] == 1
        task = task_state["tasks"][0]
        assert {
            "id",
            "title",
            "description",
            "status",
            "workflow",
            "current_phase",
            "phases",
            "planned_dev_agents",
            "external",
            "context",
            "work_packages",
            "phase_results",
            "agent_instances",
            "artifacts_dir",
            "created_at",
            "updated_at",
        } <= set(task)
        assert {"name", "type", "status"} <= set(task["phases"][0])
        assert {"id", "role", "status", "phase"} <= set(task["agent_instances"][0])
        assert {"id", "title", "description", "agent_role", "status", "agent_instance"} <= set(task["work_packages"][0])

        assert messages
        for message in messages:
            assert {"ts", "task_id", "from", "to", "type"} <= set(message)
            if message.get("artifact"):
                assert Path(message["artifact"]).exists()
            if message["type"] == "handoff":
                assert "next_instruction" in message.get("details", {})
                assert Path(message["details"]["next_instruction"]).exists()

        inspect_payload = json.loads(inspect.output)
        artifact_kinds = {artifact["kind"] for artifact in inspect_payload["artifacts"]}
        assert {"input", "instruction", "runtime", "agent_result", "qa_report", "work_packages", "task_snapshot"} <= artifact_kinds


def _run_completed_dummy_flow(runner: CliRunner) -> str:
    assert runner.invoke(main, ["init", "--yes", "--name", "contract-demo"]).exit_code == 0
    dummy_runtime = str((Path.cwd() / ".solo/runtime/examples/dummy_runtime.py").resolve())
    setup = runner.invoke(
        main,
        [
            "setup",
            "runtime",
            "dummy",
            "--command",
            sys.executable,
            "--arg",
            dummy_runtime,
            "--set-default",
        ],
    )
    assert setup.exit_code == 0, setup.output
    dispatch = runner.invoke(main, ["dispatch", "--json", "Build protocol contract fixture"])
    assert dispatch.exit_code == 0, dispatch.output
    task_id = json.loads(dispatch.output)["task"]["id"]
    run = runner.invoke(main, ["run", "--until", "done", "--json"])
    assert run.exit_code == 0, run.output
    payload = json.loads(run.output)
    assert payload["task"]["status"] == "completed"
    return task_id
