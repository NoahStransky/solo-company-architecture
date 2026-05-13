import json
from pathlib import Path

from click.testing import CliRunner
import pytest

from solo.cli import main


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (["dispatch", "Build outside a solo project"], "No .solo project found"),
        (["status"], "No .solo project found"),
        (["inspect"], "No .solo project found"),
        (["complete"], "No .solo project found"),
        (["run", "--once"], "No .solo project found"),
        (["start"], "No .solo project found"),
        (["validate"], "No .solo project found"),
        (["setup", "runtime", "local", "--command", "echo"], "No .solo project found"),
    ],
)
def test_project_commands_require_initialized_solo_project(args, expected):
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, args)

        assert result.exit_code != 0
        assert expected in result.output


def test_cli_help_lists_all_project_commands():
    runner = CliRunner()

    result = runner.invoke(main, ["--help"])

    assert result.exit_code == 0, result.output
    for command in ("init", "dispatch", "inspect", "complete", "run", "status", "start", "setup", "validate"):
        assert command in result.output


def test_start_interactive_loop_handles_status_dispatch_and_quit():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes", "--name", "start-demo"]).exit_code == 0

        result = runner.invoke(main, ["start"], input="/status\nBuild from start\n/quit\n")

        assert result.exit_code == 0, result.output
        assert "Solo Company: start-demo" in result.output
        assert "Tasks: 0 total, 0 active" in result.output
        assert "Secretary > I will ask CTO to break this down first." in result.output
        assert "CTO package is ready" in result.output
        state = json.loads(Path(".solo/state/tasks.json").read_text())
        assert len(state["tasks"]) == 1
        assert state["tasks"][0]["title"] == "Build from start"


def test_status_all_includes_more_than_default_recent_window():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0
        for index in range(6):
            result = runner.invoke(main, ["dispatch", "--to", "cto", "--json", f"Task {index}"])
            assert result.exit_code == 0, result.output

        recent = runner.invoke(main, ["status", "--json"])
        all_tasks = runner.invoke(main, ["status", "--all", "--json"])

        assert recent.exit_code == 0, recent.output
        assert all_tasks.exit_code == 0, all_tasks.output
        recent_payload = json.loads(recent.output)
        all_payload = json.loads(all_tasks.output)
        assert recent_payload["summary"]["total_tasks"] == 6
        assert len(recent_payload["tasks"]) == 5
        assert len(all_payload["tasks"]) == 6
        assert all_payload["tasks"][0]["title"] == "Task 0"


def test_inspect_reports_no_tasks_and_missing_task_id():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0

        empty = runner.invoke(main, ["inspect", "--json"])
        assert empty.exit_code != 0
        assert "No tasks found" in empty.output

        assert runner.invoke(main, ["dispatch", "--to", "cto", "Review architecture"]).exit_code == 0
        missing = runner.invoke(main, ["inspect", "--task", "missing", "--json"])
        assert missing.exit_code != 0
        assert "Task not found: missing" in missing.output


def test_complete_reports_no_tasks_missing_task_and_missing_phase():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0

        empty = runner.invoke(main, ["complete", "--json"])
        assert empty.exit_code != 0
        assert "No tasks found" in empty.output

        assert runner.invoke(main, ["dispatch", "--to", "cto", "Review architecture"]).exit_code == 0
        missing_task = runner.invoke(main, ["complete", "--task", "missing", "--json"])
        assert missing_task.exit_code != 0
        assert "Task not found: missing" in missing_task.output

        missing_phase = runner.invoke(main, ["complete", "--phase", "missing", "--json"])
        assert missing_phase.exit_code != 0
        assert "Phase not found: missing" in missing_phase.output
