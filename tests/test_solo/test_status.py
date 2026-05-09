import json

from click.testing import CliRunner

from solo.cli import main


def test_status_json_is_solo_os_friendly():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes", "--name", "status-demo"]).exit_code == 0
        assert runner.invoke(main, ["dispatch", "Implement auth API"]).exit_code == 0

        result = runner.invoke(main, ["status", "--json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["project"]["name"] == "status-demo"
        assert payload["solo_protocol_version"] == 1
        assert payload["summary"]["total_tasks"] == 1
        assert payload["summary"]["active_tasks"] == 1
        assert payload["tasks"][0]["current_phase"] == "cto_breakdown"
        assert payload["recent_events"]
