import json
from pathlib import Path
import sys

from click.testing import CliRunner
import pytest
import yaml

from solo.cli import main


def test_run_once_advances_current_phase():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0
        assert runner.invoke(main, ["dispatch", "Build backend API and frontend UI"]).exit_code == 0
        task_id = json.loads(Path(".solo/state/tasks.json").read_text())["tasks"][0]["id"]
        (Path(".solo/artifacts") / task_id / "cto_breakdown_output.md").write_text("CTO work packages", encoding="utf-8")

        result = runner.invoke(main, ["run", "--once", "--json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["completed_phase"] == "cto_breakdown"
        assert payload["next_phase"]["name"] == "dev_pool"
        assert payload["task"]["current_phase"] == "dev_pool"


def test_run_requires_once_flag():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0
        assert runner.invoke(main, ["dispatch", "Build backend API"]).exit_code == 0

        result = runner.invoke(main, ["run"])

        assert result.exit_code == 1
        assert "Only solo run --once" in result.output


def test_run_marks_next_phase_failed_when_runtime_fails():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0
        assert runner.invoke(main, ["dispatch", "Build backend API and frontend UI"]).exit_code == 0
        config_path = Path(".solo/config.yaml")
        config = yaml.safe_load(config_path.read_text())
        config["execution"]["default_adapter"] = "command"
        config["execution"]["command"] = {
            "command": sys.executable,
            "args": ["-c", "import sys; sys.exit(7)"],
            "timeout": 30,
            "env": {},
        }
        config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
        task_id = json.loads(Path(".solo/state/tasks.json").read_text())["tasks"][0]["id"]
        (Path(".solo/artifacts") / task_id / "cto_breakdown_output.md").write_text("CTO work packages", encoding="utf-8")

        result = runner.invoke(main, ["run", "--once", "--json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["task"]["status"] == "failed"
        assert payload["next_phase"]["name"] == "dev_pool"
        assert payload["next_phase"]["status"] == "failed"
        assert payload["package"]["runtime"]["returncode"] == 7
        state = json.loads(Path(".solo/state/tasks.json").read_text())
        assert state["tasks"][0]["status"] == "failed"
        events = [
            json.loads(line)
            for line in Path(".solo/state/events.jsonl").read_text().splitlines()
            if line.strip()
        ]
        assert any(event["event"] == "phase.failed" and event["phase"] == "dev_pool" for event in events)


def test_dispatch_marks_initial_phase_failed_when_runtime_fails():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0
        config_path = Path(".solo/config.yaml")
        config = yaml.safe_load(config_path.read_text())
        config["execution"]["command"] = {
            "command": sys.executable,
            "args": ["-c", "import sys; sys.exit(5)"],
            "timeout": 30,
            "env": {},
        }
        config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

        result = runner.invoke(main, ["dispatch", "--adapter", "command", "--json", "Run failing command"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["task"]["status"] == "failed"
        assert payload["task"]["phases"][0]["status"] == "failed"
        events = [
            json.loads(line)
            for line in Path(".solo/state/events.jsonl").read_text().splitlines()
            if line.strip()
        ]
        assert any(event["event"] == "phase.failed" and event["phase"] == "cto_breakdown" for event in events)


def test_run_with_template_dummy_runtime_advances_multiple_phases():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0
        config_path = Path(".solo/config.yaml")
        config = yaml.safe_load(config_path.read_text())
        dummy_runtime = str((Path.cwd() / ".solo/runtime/examples/dummy_runtime.py").resolve())
        config["execution"]["default_adapter"] = "command"
        config["execution"]["command"] = {
            "command": sys.executable,
            "args": [dummy_runtime],
            "timeout": 30,
            "env": {},
        }
        config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
        dispatch = runner.invoke(main, ["dispatch", "--json", "Build dummy runtime flow"])
        task_id = json.loads(dispatch.output)["task"]["id"]

        first = runner.invoke(main, ["run", "--once", "--json"])
        second = runner.invoke(main, ["run", "--once", "--json"])

        assert first.exit_code == 0, first.output
        assert second.exit_code == 0, second.output
        first_payload = json.loads(first.output)
        second_payload = json.loads(second.output)
        assert first_payload["next_phase"]["name"] == "dev_pool"
        assert second_payload["next_phase"]["name"] == "qa"
        artifact_dir = Path(".solo/artifacts") / task_id
        assert (artifact_dir / "work_packages.json").exists()
        assert (artifact_dir / "dev-1_agent_result.json").exists()
        state = json.loads(Path(".solo/state/tasks.json").read_text())
        assert state["tasks"][0]["work_packages"][0]["status"] == "completed"


@pytest.mark.xfail(strict=True, reason="solo run --until is not implemented yet")
def test_run_until_qa_advances_until_requested_phase():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0
        config_path = Path(".solo/config.yaml")
        config = yaml.safe_load(config_path.read_text())
        dummy_runtime = str((Path.cwd() / ".solo/runtime/examples/dummy_runtime.py").resolve())
        config["execution"]["default_adapter"] = "command"
        config["execution"]["command"] = {
            "command": sys.executable,
            "args": [dummy_runtime],
            "timeout": 30,
            "env": {},
        }
        config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
        assert runner.invoke(main, ["dispatch", "--json", "Build run until qa flow"]).exit_code == 0

        result = runner.invoke(main, ["run", "--until", "qa", "--json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["task"]["status"] == "in_progress"
        assert payload["task"]["current_phase"] == "qa"
        assert [phase["status"] for phase in payload["task"]["phases"][:2]] == ["completed", "completed"]
        assert payload["stopped_reason"] == "reached_phase"


@pytest.mark.xfail(strict=True, reason="solo run --until is not implemented yet")
def test_run_until_blocked_stops_on_runtime_failure():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0
        config_path = Path(".solo/config.yaml")
        config = yaml.safe_load(config_path.read_text())
        config["execution"]["default_adapter"] = "command"
        config["execution"]["command"] = {
            "command": sys.executable,
            "args": ["-c", "import sys; sys.exit(11)"],
            "timeout": 30,
            "env": {},
        }
        config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
        assert runner.invoke(main, ["dispatch", "--json", "Build failing run until flow"]).exit_code == 0

        result = runner.invoke(main, ["run", "--until", "blocked", "--json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["task"]["status"] == "failed"
        assert payload["stopped_reason"] == "failed"
        assert payload["failed_phase"] == "cto_breakdown"
