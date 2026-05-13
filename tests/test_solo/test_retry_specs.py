import json
from pathlib import Path
import sys

from click.testing import CliRunner
import yaml

from solo.cli import main


def _configure_command(config_path: Path, command: str, args: list) -> None:
    config = yaml.safe_load(config_path.read_text())
    config["execution"]["default_adapter"] = "command"
    config["execution"]["command"] = {
        "command": command,
        "args": args,
        "timeout": 30,
        "env": {},
    }
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")


def test_retry_phase_reruns_failed_phase_and_restores_progress():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0
        assert runner.invoke(main, ["dispatch", "Build backend API and frontend UI"]).exit_code == 0
        config_path = Path(".solo/config.yaml")
        _configure_command(config_path, sys.executable, ["-c", "import sys; sys.exit(9)"])
        task_id = json.loads(Path(".solo/state/tasks.json").read_text())["tasks"][0]["id"]
        artifact_dir = Path(".solo/artifacts") / task_id
        (artifact_dir / "cto_breakdown_output.md").write_text("CTO work packages", encoding="utf-8")
        failed = runner.invoke(main, ["run", "--once", "--json"])
        assert failed.exit_code == 0, failed.output
        assert json.loads(failed.output)["task"]["status"] == "failed"
        dummy_runtime = str((Path.cwd() / ".solo/runtime/examples/dummy_runtime.py").resolve())
        _configure_command(config_path, sys.executable, [dummy_runtime])

        retried = runner.invoke(main, ["retry", "--phase", "dev_pool", "--json"])

        assert retried.exit_code == 0, retried.output
        payload = json.loads(retried.output)
        assert payload["task"]["status"] == "in_progress"
        assert payload["task"]["current_phase"] == "qa"
        dev_phase = [phase for phase in payload["task"]["phases"] if phase["name"] == "dev_pool"][0]
        assert dev_phase["status"] == "completed"
        assert payload["next_phase"]["name"] == "qa"
        events = [
            json.loads(line)
            for line in Path(".solo/state/events.jsonl").read_text().splitlines()
            if line.strip()
        ]
        assert any(event["event"] == "phase.retried" and event["phase"] == "dev_pool" for event in events)


def test_reopen_failed_phase_resets_state_without_running_runtime():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0
        assert runner.invoke(main, ["dispatch", "Build backend API and frontend UI"]).exit_code == 0
        config_path = Path(".solo/config.yaml")
        _configure_command(config_path, sys.executable, ["-c", "import sys; sys.exit(3)"])
        task_id = json.loads(Path(".solo/state/tasks.json").read_text())["tasks"][0]["id"]
        (Path(".solo/artifacts") / task_id / "cto_breakdown_output.md").write_text("CTO work packages", encoding="utf-8")
        failed = runner.invoke(main, ["run", "--once", "--json"])
        assert failed.exit_code == 0, failed.output

        reopened = runner.invoke(main, ["reopen", "--phase", "dev_pool", "--json"])

        assert reopened.exit_code == 0, reopened.output
        payload = json.loads(reopened.output)
        assert payload["task"]["status"] == "in_progress"
        assert payload["task"]["current_phase"] == "dev_pool"
        dev_phase = [phase for phase in payload["task"]["phases"] if phase["name"] == "dev_pool"][0]
        assert dev_phase["status"] == "in_progress"
        assert all(instance["status"] == "in_progress" for instance in payload["task"]["agent_instances"] if instance["phase"] == "dev_pool")
        events = [
            json.loads(line)
            for line in Path(".solo/state/events.jsonl").read_text().splitlines()
            if line.strip()
        ]
        assert any(event["event"] == "phase.reopened" and event["phase"] == "dev_pool" for event in events)


def test_retry_agent_only_reruns_target_failed_agent_instance():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0
        config_path = Path(".solo/config.yaml")
        script = (
            "import os, pathlib, sys; "
            "out = pathlib.Path(os.environ['SOLO_OUTPUT_DIR']); "
            "inst = os.environ['SOLO_AGENT_INSTANCE']; "
            "count_path = out / (inst + '_count.txt'); "
            "count = int(count_path.read_text()) if count_path.exists() else 0; "
            "count_path.write_text(str(count + 1)); "
            "sys.exit(4 if inst == 'dev-1' and count == 0 else 0)"
        )
        _configure_command(config_path, sys.executable, ["-c", script])
        assert runner.invoke(main, ["dispatch", "Build backend API and frontend UI"]).exit_code == 0
        task_id = json.loads(Path(".solo/state/tasks.json").read_text())["tasks"][0]["id"]
        (Path(".solo/artifacts") / task_id / "cto_breakdown_output.md").write_text("CTO work packages", encoding="utf-8")
        failed = runner.invoke(main, ["run", "--once", "--json"])
        assert failed.exit_code == 0, failed.output

        retried = runner.invoke(main, ["retry", "--agent", "dev-1", "--json"])

        assert retried.exit_code == 0, retried.output
        artifact_dir = Path(".solo/artifacts") / task_id
        assert (artifact_dir / "dev-1_count.txt").read_text() == "2"
        assert (artifact_dir / "dev-2_count.txt").read_text() == "1"
        payload = json.loads(retried.output)
        assert [instance["status"] for instance in payload["task"]["agent_instances"] if instance["id"] == "dev-1"] == ["completed"]
