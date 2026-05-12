from pathlib import Path

from click.testing import CliRunner

from solo.cli import main
from solo.core.project import SoloProject


def test_default_feature_workflow_has_dev_pool():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0
        project = SoloProject.find(Path.cwd())
        assert project is not None

        workflow = project.workflows.load("feature")
        phase_types = {phase.name: phase.type for phase in workflow.phases}

        assert phase_types["cto_breakdown"] == "agent"
        assert phase_types["dev_pool"] == "agent_pool"
        assert phase_types["ceo_check"] == "human_gate"
