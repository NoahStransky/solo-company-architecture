import json
from pathlib import Path

from click.testing import CliRunner

from solo.cli import main


def test_complete_advances_to_dev_pool_after_cto_breakdown():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0
        assert runner.invoke(main, ["dispatch", "Build backend API and frontend UI"]).exit_code == 0

        result = runner.invoke(main, ["complete", "--json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        task = payload["task"]
        assert payload["completed_phase"] == "cto_breakdown"
        assert payload["next_phase"]["name"] == "dev_pool"
        assert task["current_phase"] == "dev_pool"
        assert payload["package"]["phase"] == "dev_pool"
        assert Path(payload["package"]["instruction"]).exists()
        messages = [
            json.loads(line)
            for line in Path(".solo/state/messages.jsonl").read_text().splitlines()
            if line.strip()
        ]
        handoff = messages[-1]
        assert handoff["type"] == "handoff"
        assert handoff["from"] == "cto"
        assert handoff["to"] == "dev"
        assert handoff["phase"] == "dev_pool"
        assert Path(handoff["artifact"]).exists()

        result = runner.invoke(main, ["complete", "--json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["completed_phase"] == "dev_pool"
        assert payload["next_phase"]["name"] == "qa"
        messages = [
            json.loads(line)
            for line in Path(".solo/state/messages.jsonl").read_text().splitlines()
            if line.strip()
        ]
        handoff = messages[-1]
        assert handoff["type"] == "handoff"
        assert handoff["from"] == "dev"
        assert handoff["to"] == "qa"
        assert handoff["phase"] == "qa"


def test_complete_can_finish_direct_task():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0
        dispatch = runner.invoke(main, ["dispatch", "--to", "cto", "--json", "Review architecture"])
        task_id = json.loads(dispatch.output)["task"]["id"]

        result = runner.invoke(main, ["complete", "--task", task_id, "--json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["next_phase"] is None
        assert payload["task"]["status"] == "completed"
        messages = [
            json.loads(line)
            for line in Path(".solo/state/messages.jsonl").read_text().splitlines()
            if line.strip()
        ]
        assert messages[-1]["type"] == "result"
        assert messages[-1]["from"] == "cto"
        assert messages[-1]["to"] == "ceo"
