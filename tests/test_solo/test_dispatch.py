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
        assert Path(payload["task"]["artifacts_dir"], "runtime.txt").read_text() == "cto_breakdown"
