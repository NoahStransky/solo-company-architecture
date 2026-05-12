import json
from pathlib import Path

from click.testing import CliRunner
import yaml

from solo.cli import main


def test_validate_json_accepts_initialized_project():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes", "--name", "valid-demo"]).exit_code == 0

        result = runner.invoke(main, ["validate", "--json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["ok"] is True
        assert payload["project"]["name"] == "valid-demo"
        assert payload["summary"]["errors"] == 0


def test_validate_reports_config_reference_errors():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0
        config_path = Path(".solo/config.yaml")
        config = yaml.safe_load(config_path.read_text())
        config["agents"]["cto"]["skills"].append("unknown-skill")
        config["agents"]["dev"]["runtime"] = "missing-runtime"
        config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

        result = runner.invoke(main, ["validate", "--json"])

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert payload["ok"] is False
        assert {issue["code"] for issue in payload["errors"]} >= {"missing_skill", "missing_runtime_profile"}


def test_validate_reports_invalid_jsonl():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0
        Path(".solo/state/messages.jsonl").write_text("{not-json}\n", encoding="utf-8")

        result = runner.invoke(main, ["validate", "--json"])

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert payload["errors"][0]["code"] == "invalid_message_log"


def test_validate_reports_invalid_work_package_artifact():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0
        dispatch = runner.invoke(main, ["dispatch", "--json", "Build artifact validation"])
        task_id = json.loads(dispatch.output)["task"]["id"]
        artifact_dir = Path(".solo/artifacts") / task_id
        (artifact_dir / "work_packages.json").write_text(
            json.dumps({"work_packages": [{"id": "api", "title": "Build API"}]}),
            encoding="utf-8",
        )

        result = runner.invoke(main, ["validate", "--json"])

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert any(issue["code"] == "invalid_work_packages" for issue in payload["errors"])


def test_validate_reports_invalid_qa_report_artifact():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0
        dispatch = runner.invoke(main, ["dispatch", "--json", "Build qa validation"])
        task_id = json.loads(dispatch.output)["task"]["id"]
        artifact_dir = Path(".solo/artifacts") / task_id
        (artifact_dir / "qa_report.json").write_text(
            json.dumps({"summary": "Tests looked fine", "verdict": "maybe"}),
            encoding="utf-8",
        )

        result = runner.invoke(main, ["validate", "--json"])

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert any(issue["code"] == "invalid_qa_report" for issue in payload["errors"])
