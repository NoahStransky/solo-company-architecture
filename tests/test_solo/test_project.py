from pathlib import Path

from click.testing import CliRunner

from solo.cli import main
from solo.core.project import SoloProject


def test_project_find_walks_up_from_child_directory():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["init", "--yes", "--name", "root-project"])
        assert result.exit_code == 0, result.output

        child = Path("a/b/c")
        child.mkdir(parents=True)
        project = SoloProject.find(child)

        assert project is not None
        assert project.path == Path.cwd()
        assert project.require_config().project.name == "root-project"
