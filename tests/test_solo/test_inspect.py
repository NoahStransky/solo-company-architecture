import json
from pathlib import Path
import sys

from click.testing import CliRunner
import yaml

from solo.cli import main


def test_inspect_json_returns_task_context():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes", "--name", "inspect-demo"]).exit_code == 0
        dispatch = runner.invoke(main, ["dispatch", "--json", "Build inspect view"])
        assert dispatch.exit_code == 0, dispatch.output
        task_id = json.loads(dispatch.output)["task"]["id"]

        result = runner.invoke(main, ["inspect", "--json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["project"]["name"] == "inspect-demo"
        assert payload["protocol"]["current_version"] == 1
        assert payload["protocol"]["supported_version"] == 1
        assert payload["protocol"]["compatible"] is True
        assert payload["protocol"]["migration_needed"] is False
        assert payload["task"]["id"] == task_id
        assert payload["dashboard"]["task_id"] == task_id
        assert payload["dashboard"]["current_phase"] == "cto_breakdown"
        assert payload["dashboard"]["phase_progress"]["total"] == 6
        assert payload["dashboard"]["phases"][0]["is_current"] is True
        assert payload["dashboard"]["failed_reason"] is None
        assert payload["paths"]["artifacts_dir"].endswith(f".solo/artifacts/{task_id}")
        assert [event["event"] for event in payload["events"]] == ["task.created", "phase.started"]
        assert [message["type"] for message in payload["messages"]] == ["request", "assignment"]
        artifact_kinds = {artifact["kind"] for artifact in payload["artifacts"]}
        assert {"input", "instruction", "task_snapshot"} <= artifact_kinds


def test_inspect_text_includes_dashboard_summary_and_recent_activity():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes", "--name", "inspect-text-demo"]).exit_code == 0
        dispatch = runner.invoke(main, ["dispatch", "--json", "Build inspect text view"])
        task_id = json.loads(dispatch.output)["task"]["id"]

        result = runner.invoke(main, ["inspect", "--task", task_id])

        assert result.exit_code == 0, result.output
        assert f"Solo task: {task_id}" in result.output
        assert "Phase progress: 0% (0/6 done, 0 skipped)" in result.output
        assert "Agent progress:" in result.output
        assert "Artifacts:" in result.output
        assert "instruction:" in result.output
        assert "Events:" in result.output
        assert "phase.started cto_breakdown" in result.output
        assert "Messages:" in result.output
        assert "secretary -> cto assignment" in result.output


def test_inspect_can_select_task_by_id():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0
        first = runner.invoke(main, ["dispatch", "--to", "cto", "--json", "Review architecture"])
        second = runner.invoke(main, ["dispatch", "--to", "qa", "--json", "Review tests"])
        first_id = json.loads(first.output)["task"]["id"]
        second_id = json.loads(second.output)["task"]["id"]

        result = runner.invoke(main, ["inspect", "--task", first_id, "--json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["task"]["id"] == first_id
        assert payload["task"]["id"] != second_id


def test_inspect_lists_structured_result_artifacts():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0
        dispatch = runner.invoke(main, ["dispatch", "--json", "Build result artifacts"])
        task_id = json.loads(dispatch.output)["task"]["id"]
        artifact_dir = Path(".solo/artifacts") / task_id
        (artifact_dir / "cto_breakdown_output.md").write_text("CTO work packages", encoding="utf-8")
        assert runner.invoke(main, ["complete", "--json"]).exit_code == 0
        (artifact_dir / "dev-1_agent_result.json").write_text(
            json.dumps({"summary": "Implemented worker one"}),
            encoding="utf-8",
        )

        result = runner.invoke(main, ["inspect", "--task", task_id, "--json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        dev_result = [artifact for artifact in payload["artifacts"] if artifact["name"] == "dev-1_agent_result.json"][0]
        assert dev_result["kind"] == "agent_result"


def test_inspect_dashboard_reports_failed_runtime_reason():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0
        dispatch = runner.invoke(main, ["dispatch", "--json", "Build failing inspect view"])
        task_id = json.loads(dispatch.output)["task"]["id"]
        artifact_dir = Path(".solo/artifacts") / task_id
        (artifact_dir / "cto_breakdown_output.md").write_text("CTO work packages", encoding="utf-8")
        config_path = Path(".solo/config.yaml")
        config = yaml.safe_load(config_path.read_text())
        config["execution"]["default_adapter"] = "command"
        config["execution"]["command"] = {
            "command": sys.executable,
            "args": ["-c", "import sys; sys.exit(9)"],
            "timeout": 30,
            "env": {},
        }
        config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

        failed = runner.invoke(main, ["run", "--once", "--json"])
        assert failed.exit_code == 0, failed.output
        result = runner.invoke(main, ["inspect", "--task", task_id, "--json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["dashboard"]["failed_reason"]["phase"] == "dev_pool"
        assert payload["dashboard"]["failed_reason"]["runtime_returncode"] == 9
        expected_failed_agents = {
            instance["id"]
            for instance in payload["task"]["agent_instances"]
            if instance["phase"] == "dev_pool"
        }
        assert set(payload["dashboard"]["failed_reason"]["failed_agents"]) == expected_failed_agents


def test_inspect_text_includes_failed_reason():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0
        dispatch = runner.invoke(main, ["dispatch", "--json", "Build failing inspect text"])
        task_id = json.loads(dispatch.output)["task"]["id"]
        artifact_dir = Path(".solo/artifacts") / task_id
        (artifact_dir / "cto_breakdown_output.md").write_text("CTO work packages", encoding="utf-8")
        config_path = Path(".solo/config.yaml")
        config = yaml.safe_load(config_path.read_text())
        config["execution"]["default_adapter"] = "command"
        config["execution"]["command"] = {
            "command": sys.executable,
            "args": ["-c", "import sys; sys.exit(12)"],
            "timeout": 30,
            "env": {},
        }
        config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
        assert runner.invoke(main, ["run", "--once", "--json"]).exit_code == 0

        result = runner.invoke(main, ["inspect", "--task", task_id])

        assert result.exit_code == 0, result.output
        assert "Failed: Phase dev_pool failed | returncode=12" in result.output
        assert "agents=" in result.output
