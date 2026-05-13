import json
from pathlib import Path
import sys

from click.testing import CliRunner
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


def test_run_until_done_with_template_cli_wrapper_runtime():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0
        wrapper = str((Path.cwd() / ".solo/runtime/examples/cli_wrapper.py").resolve())
        setup = runner.invoke(
            main,
            [
                "setup",
                "runtime",
                "generic-cli",
                "--command",
                sys.executable,
                "--arg",
                wrapper,
                "--set-default",
            ],
        )
        assert setup.exit_code == 0, setup.output
        dispatch = runner.invoke(main, ["dispatch", "--json", "Build generic wrapper flow"])
        assert dispatch.exit_code == 0, dispatch.output
        task_id = json.loads(dispatch.output)["task"]["id"]

        result = runner.invoke(main, ["run", "--until", "done", "--json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["stopped_reason"] == "completed"
        assert payload["task"]["status"] == "completed"
        artifact_dir = Path(".solo/artifacts") / task_id
        assert (artifact_dir / "cto_breakdown_result.json").exists()
        assert (artifact_dir / "dev-1_agent_result.json").exists()
        assert (artifact_dir / "qa_report.json").exists()
        assert (artifact_dir / "secretary_report.md").exists()
        validate = runner.invoke(main, ["validate", "--json"])
        assert validate.exit_code == 0, validate.output


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
        phase_statuses = {phase["name"]: phase["status"] for phase in payload["task"]["phases"]}
        assert phase_statuses["cto_breakdown"] == "completed"
        assert phase_statuses["ceo_check"] == "skipped"
        assert phase_statuses["dev_pool"] == "completed"
        assert payload["stopped_reason"] == "reached_phase"


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
