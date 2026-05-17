import json

from click.testing import CliRunner

from solo.cli import main


def test_status_json_is_solo_os_friendly():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes", "--name", "status-demo"]).exit_code == 0
        assert runner.invoke(main, ["dispatch", "Implement auth API"]).exit_code == 0

        result = runner.invoke(main, ["status", "--json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["project"]["name"] == "status-demo"
        assert payload["solo_protocol_version"] == 1
        assert payload["protocol"] == {
            "current_version": 1,
            "supported_version": 1,
            "compatible": True,
            "migration_needed": False,
            "migration_available": False,
            "migration_error": "",
            "migration_steps": [],
        }
        assert payload["paths"]["root"]
        assert payload["paths"]["config"].endswith(".solo/config.yaml")
        assert payload["paths"]["events"].endswith(".solo/state/events.jsonl")
        assert payload["paths"]["messages"].endswith(".solo/state/messages.jsonl")
        assert payload["execution"]["default_adapter"] == "package"
        assert payload["execution"]["default_profile"] == ""
        assert payload["execution"]["runtime_profiles"] == []
        assert "command" in payload["execution"]["available_adapters"]
        assert payload["summary"]["total_tasks"] == 1
        assert payload["summary"]["active_tasks"] == 1
        assert payload["summary"]["failed_tasks"] == 0
        assert payload["summary"]["completed_tasks"] == 0
        assert payload["dashboard"]["active_task_ids"] == [payload["tasks"][0]["id"]]
        assert payload["dashboard"]["failed_task_ids"] == []
        dashboard_task = payload["dashboard"]["tasks"][0]
        assert dashboard_task["task_id"] == payload["tasks"][0]["id"]
        assert dashboard_task["phase_progress"]["total"] == 6
        assert dashboard_task["phase_progress"]["percent"] == 0
        assert dashboard_task["agent_progress"]["total"] == 3
        assert dashboard_task["failed_reason"] is None
        assert payload["tasks"][0]["current_phase"] == "cto_breakdown"
        assert payload["recent_events"]
        assert payload["recent_messages"]
        assert payload["recent_messages"][-1]["to"] == "cto"


def test_status_text_includes_dashboard_progress():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes", "--name", "status-text-demo"]).exit_code == 0
        assert runner.invoke(main, ["dispatch", "Implement auth API"]).exit_code == 0

        result = runner.invoke(main, ["status"])

        assert result.exit_code == 0, result.output
        assert "Solo status: status-text-demo" in result.output
        assert "Tasks: 1 total, 1 active, 0 failed, 0 completed" in result.output
        assert "Execution: adapter=package profile=-" in result.output
        assert "cto_breakdown" in result.output
        assert "phases: 0/6 done" in result.output
        assert "agents:" in result.output
