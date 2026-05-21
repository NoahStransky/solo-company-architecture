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
        assert "qwen-coder" in Path("AGENTS.md").read_text()
        assert "qwen-coder" in Path(".claude/agents/dev.md").read_text()
        mcp_payload = json.loads(Path(".mcp.json").read_text())
        assert "local-files" in mcp_payload["mcpServers"]


def test_setup_agent_rejects_unknown_references():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0

        result = runner.invoke(main, ["setup", "agent", "dev", "--provider", "missing"])

        assert result.exit_code != 0
        assert "Unknown provider: missing" in result.output


def test_setup_list_and_show_return_config_entries():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0
        assert runner.invoke(main, ["setup", "runtime", "dummy", "--preset", "package", "--set-default"]).exit_code == 0

        listed = runner.invoke(main, ["setup", "list", "--json"])
        agent = runner.invoke(main, ["setup", "show", "agent", "dev", "--json"])
        runtime = runner.invoke(main, ["setup", "show", "runtime", "dummy", "--json"])
        execution = runner.invoke(main, ["setup", "show", "execution", "--json"])

        assert listed.exit_code == 0, listed.output
        assert agent.exit_code == 0, agent.output
        assert runtime.exit_code == 0, runtime.output
        assert execution.exit_code == 0, execution.output
        listed_payload = json.loads(listed.output)
        assert "dev" in listed_payload["agents"]
        assert "openai" in listed_payload["providers"]
        assert "dummy" in listed_payload["runtimes"]
        assert json.loads(agent.output)["provider"] == "anthropic"
        assert json.loads(runtime.output)["adapter"] == "package"
        assert json.loads(execution.output)["default_profile"] == "dummy"


def test_setup_show_rejects_missing_name_and_unknown_entry():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0

        missing_name = runner.invoke(main, ["setup", "show", "agent"])
        unknown = runner.invoke(main, ["setup", "show", "runtime", "missing"])

        assert missing_name.exit_code != 0
        assert "requires a name" in missing_name.output
        assert unknown.exit_code != 0
        assert "Unknown runtime: missing" in unknown.output


def test_setup_tooling_sync_and_doctor_report_generated_files():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes", "--name", "tooling-demo"]).exit_code == 0
        Path("AGENTS.md").unlink()
        Path(".claude/agents/dev.md").unlink()

        sync = runner.invoke(main, ["setup", "tooling", "sync", "--json"])
        doctor = runner.invoke(main, ["setup", "tooling", "doctor", "--json"])

        assert sync.exit_code == 0, sync.output
        assert doctor.exit_code == 0, doctor.output
        sync_payload = json.loads(sync.output)
        doctor_payload = json.loads(doctor.output)
        assert sync_payload["ok"] is True
        assert "AGENTS.md" in sync_payload["written"]
        assert ".claude/agents/dev.md" in sync_payload["written"]
        assert doctor_payload["ok"] is True
        assert "AGENTS.md" in doctor_payload["checked"]
        assert ".claude/commands/review.md" in doctor_payload["checked"]
        assert ".solo/generated/codex/default/commands/review.md" in doctor_payload["checked"]
        assert "tooling-demo Agent Instructions" in Path("CLAUDE.md").read_text()


def test_setup_tooling_sync_skips_unmanaged_files_without_force():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0
        Path("AGENTS.md").write_text("custom instructions\n")

        sync = runner.invoke(main, ["setup", "tooling", "sync", "--target", "codex", "--json"])
        doctor = runner.invoke(main, ["setup", "tooling", "doctor", "--target", "codex", "--json"])

        assert sync.exit_code == 0, sync.output
        assert doctor.exit_code == 0, doctor.output
        sync_payload = json.loads(sync.output)
        doctor_payload = json.loads(doctor.output)
        assert sync_payload["skipped"] == ["AGENTS.md"]
        assert Path("AGENTS.md").read_text() == "custom instructions\n"
        assert doctor_payload["ok"] is False
        assert doctor_payload["unmanaged"] == ["AGENTS.md"]

        forced = runner.invoke(main, ["setup", "tooling", "sync", "--target", "codex", "--force", "--json"])
        assert forced.exit_code == 0, forced.output
        assert "Generated by solo tooling sync" in Path("AGENTS.md").read_text()
