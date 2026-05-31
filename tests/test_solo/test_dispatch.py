import json
from pathlib import Path
import sys

from click.testing import CliRunner
import yaml

from solo.cli import main


def test_dispatch_creates_cto_package_and_task_state():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0

        result = runner.invoke(
            main,
            [
                "dispatch",
                "--workflow",
                "feature",
                "--json",
                "Build a dashboard with backend API, database migration, frontend UI, and tests",
            ],
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        task = payload["task"]
        package = payload["package"]

        assert task["current_phase"] == "cto_breakdown"
        assert task["planned_dev_agents"] == 3
        assert any(phase["name"] == "dev_pool" and phase["type"] == "agent_pool" for phase in task["phases"])
        assert Path(package["instruction"]).exists()
        assert Path(package["input"]).exists()
        assert package["model_config"]["provider"] == "anthropic"
        assert "architecture" in package["skills"]
        assert package["skills"]["architecture"]["content"]

        state = json.loads(Path(".solo/state/tasks.json").read_text())
        assert state["schema_version"] == 1
        assert state["tasks"][0]["id"] == task["id"]
        assert Path(".solo/state/events.jsonl").read_text().count("phase.started") == 1
        messages = [
            json.loads(line)
            for line in Path(".solo/state/messages.jsonl").read_text().splitlines()
            if line.strip()
        ]
        assert [message["type"] for message in messages] == ["request", "assignment"]
        assert messages[0]["from"] == "ceo"
        assert messages[0]["to"] == "secretary"
        assert messages[1]["from"] == "secretary"
        assert messages[1]["to"] == "cto"
        assert Path(messages[1]["artifact"]).exists()


def test_dispatch_direct_role():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0

        result = runner.invoke(main, ["dispatch", "--to", "cto", "--json", "Review this architecture"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["task"]["workflow"] == "direct:cto"
        assert payload["task"]["current_phase"] == "cto"
        assert payload["package"]["agent_role"] == "cto"


def test_dispatch_records_external_metadata_and_context_file():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0
        Path("dependency-context.md").write_text("Backend contract: GET /billing\n", encoding="utf-8")

        result = runner.invoke(
            main,
            [
                "dispatch",
                "--json",
                "--external-id",
                "XPROJ-20260528-001",
                "--external-source",
                "solo-os",
                "--external-node",
                "frontend",
                "--context-file",
                "dependency-context.md",
                "Build frontend billing integration",
            ],
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        task = payload["task"]
        package = payload["package"]
        assert task["external"] == {
            "id": "XPROJ-20260528-001",
            "source": "solo-os",
            "node": "frontend",
        }
        context_file = task["context"]["files"][0]
        assert context_file["name"] == "dependency-context.md"
        assert Path(context_file["artifact"]).read_text(encoding="utf-8") == "Backend contract: GET /billing\n"
        assert package["external"] == task["external"]
        assert package["context"] == task["context"]
        instruction = Path(package["instruction"]).read_text(encoding="utf-8")
        assert "## External orchestration" in instruction
        assert "XPROJ-20260528-001" in instruction
        assert "context/dependency-context.md" in instruction

        state = json.loads(Path(".solo/state/tasks.json").read_text(encoding="utf-8"))
        assert state["tasks"][0]["external"]["source"] == "solo-os"
        assert state["tasks"][0]["context"]["files"][0]["relative_path"] == "context/dependency-context.md"


def test_dispatch_rejects_unknown_adapter_and_role():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0

        bad_workflow = runner.invoke(main, ["dispatch", "--workflow", "missing", "Build with missing workflow"])
        assert bad_workflow.exit_code != 0
        assert "Workflow not found: missing" in bad_workflow.output

        bad_adapter = runner.invoke(main, ["dispatch", "--adapter", "missing", "Build with missing adapter"])
        assert bad_adapter.exit_code != 0
        assert "Unknown execution adapter: missing" in bad_adapter.output

        bad_role = runner.invoke(main, ["dispatch", "--to", "missing", "Build with missing role"])
        assert bad_role.exit_code != 0
        assert "Unknown agent role: missing" in bad_role.output


def test_dispatch_command_adapter_runs_configured_command():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0
        config_path = Path(".solo/config.yaml")
        config = yaml.safe_load(config_path.read_text())
        config["execution"]["command"] = {
            "command": sys.executable,
            "args": [
                "-c",
                "import os, pathlib; pathlib.Path(os.environ['SOLO_OUTPUT_DIR'], 'runtime.txt').write_text(os.environ['SOLO_PHASE'])",
            ],
            "timeout": 30,
            "env": {},
        }
        config_path.write_text(yaml.safe_dump(config, sort_keys=False))

        result = runner.invoke(main, ["dispatch", "--adapter", "command", "--json", "Run command adapter"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        package = payload["package"]
        assert package["adapter"] == "command"
        assert package["runtime"]["returncode"] == 0
        assert Path(package["runtime_report"]).exists()
        assert Path(payload["task"]["artifacts_dir"], "runtime.txt").read_text() == "cto_breakdown"
        events = [
            json.loads(line)
            for line in Path(".solo/state/events.jsonl").read_text().splitlines()
            if line.strip()
        ]
        phase_started = [event for event in events if event["event"] == "phase.started"][-1]
        assert phase_started["details"]["adapter"] == "command"
        assert phase_started["details"]["runtime_returncode"] == 0
        assert Path(phase_started["details"]["runtime_report"]).exists()
