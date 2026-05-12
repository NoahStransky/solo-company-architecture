import json
from pathlib import Path

from click.testing import CliRunner

from solo.cli import main


def test_complete_advances_to_dev_pool_after_cto_breakdown():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0
        assert runner.invoke(main, ["dispatch", "Build backend API and frontend UI"]).exit_code == 0
        task_id = json.loads(Path(".solo/state/tasks.json").read_text())["tasks"][0]["id"]
        cto_output = Path(".solo/artifacts") / task_id / "cto_breakdown_output.md"
        cto_output.write_text("CTO work packages", encoding="utf-8")

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
        handoffs = [message for message in messages if message["type"] == "handoff" and message["phase"] == "dev_pool"]
        assert [message["to"] for message in handoffs] == ["dev-1", "dev-2"]
        assert {message["from"] for message in handoffs} == {"cto"}
        assert {message["artifact"] for message in handoffs} == {str(cto_output.resolve())}
        assert all(Path(message["details"]["next_instruction"]).exists() for message in handoffs)

        dev_output = Path(".solo/artifacts") / task_id / "dev_pool_output.md"
        dev_output.write_text("Implemented backend and frontend", encoding="utf-8")

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
        handoffs = [message for message in messages if message["type"] == "handoff" and message["phase"] == "qa"]
        assert [message["from"] for message in handoffs] == ["dev-1", "dev-2"]
        assert {message["to"] for message in handoffs} == {"qa"}
        assert {message["artifact"] for message in handoffs} == {str(dev_output.resolve())}
        assert all(Path(message["details"]["next_instruction"]).exists() for message in handoffs)


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
        assert "artifact" not in messages[-1]


def test_complete_ingests_cto_work_packages():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0
        assert runner.invoke(main, ["dispatch", "Build backend API and frontend UI"]).exit_code == 0
        task_id = json.loads(Path(".solo/state/tasks.json").read_text())["tasks"][0]["id"]
        artifact_dir = Path(".solo/artifacts") / task_id
        (artifact_dir / "work_packages.json").write_text(
            json.dumps({
                "work_packages": [
                    {
                        "id": "api",
                        "title": "Build API",
                        "description": "Implement backend routes",
                        "files_scope": ["src/api.py"],
                    },
                    {
                        "id": "ui",
                        "title": "Build UI",
                        "description": "Implement frontend view",
                        "files_scope": ["src/ui.tsx"],
                    },
                ]
            }),
            encoding="utf-8",
        )

        result = runner.invoke(main, ["complete", "--json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        task = payload["task"]
        package = payload["package"]
        assert [item["id"] for item in task["work_packages"]] == ["api", "ui"]
        assert [item["agent_instance"] for item in task["work_packages"]] == ["dev-1", "dev-2"]
        assert [item["id"] for item in package["work_packages"]] == ["api", "ui"]
        state = json.loads(Path(".solo/state/tasks.json").read_text())
        assert state["tasks"][0]["work_packages"][0]["agent_instance"] == "dev-1"
        events = [
            json.loads(line)
            for line in Path(".solo/state/events.jsonl").read_text().splitlines()
            if line.strip()
        ]
        assert any(event["event"] == "work_packages.updated" and event["details"]["count"] == 2 for event in events)


def test_complete_ingests_cto_output_list_work_packages():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0
        assert runner.invoke(main, ["dispatch", "Build CLI setup flow"]).exit_code == 0
        task_id = json.loads(Path(".solo/state/tasks.json").read_text())["tasks"][0]["id"]
        artifact_dir = Path(".solo/artifacts") / task_id
        (artifact_dir / "cto_breakdown_output.json").write_text(
            json.dumps([
                {
                    "id": "setup-runtime",
                    "title": "Add setup runtime command",
                    "description": "Implement runtime profile setup flow",
                }
            ]),
            encoding="utf-8",
        )

        result = runner.invoke(main, ["complete", "--json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["task"]["work_packages"][0]["id"] == "setup-runtime"
        assert payload["task"]["work_packages"][0]["agent_instance"] == "dev-1"
