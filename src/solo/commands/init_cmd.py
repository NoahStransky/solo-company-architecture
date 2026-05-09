"""solo init command."""

from pathlib import Path

import click

from solo.core.config import save_config
from solo.core.project import SoloProject
from solo.utils.ui import success


@click.command("init")
@click.option("--template", default="default", show_default=True, help="Template name.")
@click.option("--yes", is_flag=True, help="Use defaults.")
@click.option("--name", default=None, help="Project name.")
@click.option("--description", default="", help="Project description.")
def init(template: str, yes: bool, name: str, description: str):
    """Initialize .solo in the current project."""
    project_path = Path.cwd()
    project_name = name or project_path.name
    try:
        project = SoloProject.init(project_path, template=template, yes=yes)
    except (FileExistsError, FileNotFoundError) as exc:
        raise click.ClickException(str(exc)) from exc
    config = project.require_config()
    config.project.name = project_name
    if description:
        config.project.description = description
    save_config(config, project.config_path)
    success(f"created {project.solo_dir}")
    success("created .solo/state/tasks.json")
    success("created .solo/state/events.jsonl")
    click.echo("Next: solo dispatch \"Describe the work\"")
