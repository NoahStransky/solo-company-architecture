import json
from pathlib import Path
import sys

from click.testing import CliRunner
import yaml

from solo.cli import main


def test_setup_runtime_creates_profile_and_assigns_roles():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0

        result = runner.invoke(
            main,
            [
                "setup",
                "runtime",
                "local-python",
                "--command",
                sys.executable,
                "--arg",
                "-c",
                "--arg",
                "import os, pathlib; pathlib.Path(os.environ['SOLO_OUTPUT_DIR'], 'profile.txt').write_text(os.environ['SOLO_AGENT_ROLE'])",
                "--set-default",
                "--for",
                "cto",
            ],
        )

        assert result.exit_code == 0, result.output
        config = yaml.safe_load(Path(".solo/config.yaml").read_text())
        assert config["execution"]["default_profile"] == "local-python"
        assert config["execution"]["default_adapter"] == "command"
        assert config["runtime_profiles"]["local-python"]["command"]["command"] == sys.executable
        assert config["agents"]["cto"]["runtime"] == "local-python"

        dispatch = runner.invoke(main, ["dispatch", "--json", "Run via profile"])

        assert dispatch.exit_code == 0, dispatch.output
        payload = json.loads(dispatch.output)
        package = payload["package"]
        assert package["adapter"] == "command"
        assert package["runtime_profile"] == "local-python"
        assert package["runtime"]["returncode"] == 0
        assert Path(payload["task"]["artifacts_dir"], "profile.txt").read_text() == "cto"


def test_setup_runtime_rejects_unknown_role():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0

        result = runner.invoke(main, ["setup", "runtime", "codex", "--preset", "codex", "--for", "missing"])

        assert result.exit_code != 0
        assert "Unknown agent role" in result.output


def test_setup_runtime_package_preset_can_be_default_without_command():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0

        result = runner.invoke(
            main,
            [
                "setup",
                "runtime",
                "offline-package",
                "--preset",
                "package",
                "--set-default",
                "--for",
                "qa",
            ],
        )

        assert result.exit_code == 0, result.output
        config = yaml.safe_load(Path(".solo/config.yaml").read_text())
        assert config["runtime_profiles"]["offline-package"]["adapter"] == "package"
        assert config["execution"]["default_profile"] == "offline-package"
        assert config["execution"]["default_adapter"] == "package"
        assert config["agents"]["qa"]["runtime"] == "offline-package"
        assert "Default runtime: offline-package" in result.output
        assert "qa runtime: offline-package" in result.output


def test_setup_runtime_rejects_invalid_env_and_empty_command_profile():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0

        invalid_env = runner.invoke(
            main,
            ["setup", "runtime", "bad-env", "--command", sys.executable, "--env", "BROKEN"],
        )
        assert invalid_env.exit_code != 0
        assert "Invalid --env value" in invalid_env.output

        empty_command = runner.invoke(main, ["setup", "runtime", "empty-command"])
        assert empty_command.exit_code != 0
        assert "Command adapter profiles require --command" in empty_command.output


def test_dispatch_rejects_missing_runtime_profile():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0
        config_path = Path(".solo/config.yaml")
        config = yaml.safe_load(config_path.read_text())
        config["agents"]["cto"]["runtime"] = "missing-profile"
        config_path.write_text(yaml.safe_dump(config, sort_keys=False))

        result = runner.invoke(main, ["dispatch", "--json", "Use missing runtime profile"])

        assert result.exit_code != 0
        assert "Unknown runtime profile" in result.output


def test_setup_provider_mcp_skill_and_agent_update_config():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0

        provider = runner.invoke(
            main,
            [
                "setup",
                "provider",
                "local-openai",
                "--type",
                "openai-compatible",
                "--api-key-env",
                "LOCAL_API_KEY",
                "--base-url",
                "http://localhost:11434/v1",
            ],
        )
        mcp = runner.invoke(
            main,
            [
                "setup",
                "mcp",
                "local-files",
                "--command",
                "npx",
                "--arg",
                "-y",
                "--arg",
                "@modelcontextprotocol/server-filesystem",
                "--env",
                "ROOT=.",
                "--description",
                "Local filesystem access",
                "--enable",
            ],
        )
        skill = runner.invoke(
            main,
            [
                "setup",
                "skill",
                "debugging",
                "--path",
                "skills/debugging.md",
                "--description",
                "Debug failures",
                "--create-file",
            ],
        )
        agent = runner.invoke(
            main,
            [
                "setup",
                "agent",
                "dev",
                "--provider",
                "local-openai",
                "--model",
                "qwen-coder",
                "--skill",
                "debugging",
                "--mcp",
                "local-files",
                "--tool",
                "run_tests",
            ],
        )

        assert provider.exit_code == 0, provider.output
        assert mcp.exit_code == 0, mcp.output
        assert skill.exit_code == 0, skill.output
        assert agent.exit_code == 0, agent.output
        config = yaml.safe_load(Path(".solo/config.yaml").read_text())
        assert config["providers"]["local-openai"]["base_url"] == "http://localhost:11434/v1"
        assert config["mcp_servers"]["local-files"]["args"] == ["-y", "@modelcontextprotocol/server-filesystem"]
        assert config["mcp_servers"]["local-files"]["env"] == {"ROOT": "."}
        assert config["skills"]["debugging"]["path"] == "skills/debugging.md"
        assert Path(".solo/skills/debugging.md").exists()
        assert config["agents"]["dev"]["provider"] == "local-openai"
        assert config["agents"]["dev"]["model"] == "qwen-coder"
        assert config["agents"]["dev"]["skills"] == ["debugging"]
        assert config["agents"]["dev"]["mcp_servers"] == ["local-files"]


def test_setup_agent_rejects_unknown_references():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0

        result = runner.invoke(main, ["setup", "agent", "dev", "--provider", "missing"])

        assert result.exit_code != 0
        assert "Unknown provider: missing" in result.output
