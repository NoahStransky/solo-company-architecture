from pathlib import Path

from click.testing import CliRunner

from solo.cli import main
from solo.core.project import SoloProject


def test_init_creates_solo_protocol_files():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["init", "--yes", "--name", "demo"])

        assert result.exit_code == 0, result.output
        assert Path(".solo/config.yaml").exists()
        assert Path(".solo/agents/secretary.md").exists()
        assert Path(".solo/skills/architecture.md").exists()
        assert Path(".solo/workflows/feature.yaml").exists()
        assert Path(".solo/state/tasks.json").exists()
        assert Path(".solo/state/events.jsonl").exists()
        assert Path(".solo/state/messages.jsonl").exists()
        assert Path(".solo/artifacts").is_dir()
        assert Path(".soloignore").exists()

        project = SoloProject.find(Path.cwd())
        assert project is not None
        assert project.require_config().project.name == "demo"
        assert "anthropic" in project.require_config().providers
        assert "filesystem" in project.require_config().mcp_servers
        assert project.require_config().get_agent("cto").skills == ["architecture", "code-review", "research"]


def test_init_refuses_existing_solo_dir():
    runner = CliRunner()
    with runner.isolated_filesystem():
        first = runner.invoke(main, ["init", "--yes"])
        second = runner.invoke(main, ["init", "--yes"])

        assert first.exit_code == 0
        assert second.exit_code != 0
        assert "already exists" in second.output
