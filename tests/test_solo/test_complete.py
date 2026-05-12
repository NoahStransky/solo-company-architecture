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
        assert Path(payload["package"]["agent_packages"]["dev-1"]["instruction"]).exists()
        assert Path(payload["package"]["agent_packages"]["dev-2"]["instruction"]).exists()
        package_input = json.loads(Path(payload["package"]["input"]).read_text())
        assert package_input["agent_packages"]["dev-1"]["instruction"].endswith("dev-1_instruction.md")
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
        assert handoffs[0]["details"]["next_instruction"].endswith("dev-1_instruction.md")
        assert handoffs[1]["details"]["next_instruction"].endswith("dev-2_instruction.md")
        assert handoffs[0]["details"]["next_input"].endswith("dev-1_input.json")
        assert handoffs[1]["details"]["next_input"].endswith("dev-2_input.json")

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
        assert [item["id"] for item in package["agent_packages"]["dev-1"]["work_packages"]] == ["api"]
        assert [item["id"] for item in package["agent_packages"]["dev-2"]["work_packages"]] == ["ui"]
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


def test_complete_ingests_agent_results_into_next_package():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0
        assert runner.invoke(main, ["dispatch", "Build backend API and frontend UI"]).exit_code == 0
        task_id = json.loads(Path(".solo/state/tasks.json").read_text())["tasks"][0]["id"]
        artifact_dir = Path(".solo/artifacts") / task_id
        (artifact_dir / "work_packages.json").write_text(
            json.dumps({
                "work_packages": [
                    {"id": "api", "title": "Build API", "description": "Implement backend routes"},
                    {"id": "ui", "title": "Build UI", "description": "Implement frontend view"},
                ]
            }),
            encoding="utf-8",
        )
        assert runner.invoke(main, ["complete", "--json"]).exit_code == 0
        (artifact_dir / "dev-1_result.json").write_text(
            json.dumps({
                "summary": "Implemented API",
                "status": "completed",
                "files_changed": ["src/api.py"],
                "tests": ["pytest tests/test_api.py"],
            }),
            encoding="utf-8",
        )
        (artifact_dir / "dev-2_result.json").write_text(
            json.dumps({
                "summary": "Implemented UI",
                "status": "completed",
                "files_changed": ["src/ui.tsx"],
            }),
            encoding="utf-8",
        )

        result = runner.invoke(main, ["complete", "--json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        task = payload["task"]
        package = payload["package"]
        assert [item["from_agent"] for item in task["phase_results"]] == ["dev-1", "dev-2"]
        assert [item["summary"] for item in task["phase_results"]] == ["Implemented API", "Implemented UI"]
        assert [item["status"] for item in task["work_packages"]] == ["completed", "completed"]
        assert package["phase_results"] == task["phase_results"]
        events = [
            json.loads(line)
            for line in Path(".solo/state/events.jsonl").read_text().splitlines()
            if line.strip()
        ]
        assert any(event["event"] == "phase_results.updated" and event["details"]["count"] == 2 for event in events)
        assert any(event["event"] == "work_packages.updated" and event["phase"] == "dev_pool" for event in events)


def test_complete_ingests_qa_report_result():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0
        assert runner.invoke(main, ["dispatch", "Build backend API and frontend UI"]).exit_code == 0
        task_id = json.loads(Path(".solo/state/tasks.json").read_text())["tasks"][0]["id"]
        artifact_dir = Path(".solo/artifacts") / task_id
        (artifact_dir / "cto_breakdown_output.md").write_text("CTO work packages", encoding="utf-8")
        assert runner.invoke(main, ["complete", "--json"]).exit_code == 0
        (artifact_dir / "dev_pool_output.md").write_text("Implemented backend and frontend", encoding="utf-8")
        assert runner.invoke(main, ["complete", "--json"]).exit_code == 0
        (artifact_dir / "qa_report.json").write_text(
            json.dumps({
                "summary": "Smoke tests passed",
                "verdict": "pass",
                "tests_run": ["pytest"],
            }),
            encoding="utf-8",
        )

        result = runner.invoke(main, ["complete", "--json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        qa_result = payload["task"]["phase_results"][0]
        assert qa_result["phase"] == "qa"
        assert qa_result["from_agent"] == "qa"
        assert qa_result["verdict"] == "pass"
        assert qa_result["data"]["tests_run"] == ["pytest"]
