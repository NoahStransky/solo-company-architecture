import json
from pathlib import Path

from click.testing import CliRunner
import yaml

from solo.cli import main


def test_migrate_check_reports_current_protocol():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0

        result = runner.invoke(main, ["migrate", "--check", "--json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["needed"] is False
        assert payload["from_version"] == 1
        assert payload["to_version"] == 1
        assert payload["applied"] is False


def test_migrate_updates_legacy_protocol_and_writes_backup():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0
        config_path = Path(".solo/config.yaml")
        config = yaml.safe_load(config_path.read_text())
        config["solo_protocol_version"] = 0
        config.pop("runtime_profiles", None)
        config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

        check = runner.invoke(main, ["migrate", "--check", "--json"])
        result = runner.invoke(main, ["migrate", "--json"])

        assert check.exit_code == 0, check.output
        assert json.loads(check.output)["needed"] is True
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["applied"] is True
        assert payload["from_version"] == 0
        assert payload["to_version"] == 1
        assert Path(payload["backup"]).exists()
        migrated = yaml.safe_load(config_path.read_text())
        assert migrated["solo_protocol_version"] == 1
        assert migrated["runtime_profiles"] == {}
        assert runner.invoke(main, ["validate", "--json"]).exit_code == 0


def test_migrate_rejects_newer_protocol_version():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0
        config_path = Path(".solo/config.yaml")
        config = yaml.safe_load(config_path.read_text())
        config["solo_protocol_version"] = 999
        config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

        result = runner.invoke(main, ["migrate", "--json"])

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert payload["ok"] is False
        assert "newer than this CLI supports" in payload["error"]
