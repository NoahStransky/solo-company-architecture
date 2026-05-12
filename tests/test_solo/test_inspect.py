import json
from pathlib import Path

from click.testing import CliRunner

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
        assert payload["task"]["id"] == task_id
        assert payload["paths"]["artifacts_dir"].endswith(f".solo/artifacts/{task_id}")
        assert [event["event"] for event in payload["events"]] == ["task.created", "phase.started"]
        assert [message["type"] for message in payload["messages"]] == ["request", "assignment"]
        artifact_kinds = {artifact["kind"] for artifact in payload["artifacts"]}
        assert {"input", "instruction", "task_snapshot"} <= artifact_kinds


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
