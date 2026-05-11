"""solo setup commands."""

from pathlib import Path
from typing import Dict, Iterable, Optional

import click

from solo.core.config import CommandRuntimeConfig, RuntimeProfileConfig, save_config
from solo.core.project import SoloProject
from solo.utils.ui import success


RUNTIME_PRESETS: Dict[str, RuntimeProfileConfig] = {
    "package": RuntimeProfileConfig(
        adapter="package",
        description="Generate execution packages without running an external runtime.",
    ),
    "codex": RuntimeProfileConfig(
        adapter="command",
        description="Run a local Codex CLI wrapper. Adjust args to match your installed CLI.",
        command=CommandRuntimeConfig(command="codex", args=["{instruction}"], timeout=900),
    ),
    "claude-code": RuntimeProfileConfig(
        adapter="command",
        description="Run a local Claude Code CLI wrapper. Adjust args to match your installed CLI.",
        command=CommandRuntimeConfig(command="claude", args=["{instruction}"], timeout=900),
    ),
    "hermes": RuntimeProfileConfig(
        adapter="command",
        description="Run a local Hermes wrapper command.",
        command=CommandRuntimeConfig(command="hermes", args=["{instruction}"], timeout=900),
    ),
    "openclaw": RuntimeProfileConfig(
        adapter="command",
        description="Run a local OpenClaw wrapper command.",
        command=CommandRuntimeConfig(command="openclaw", args=["{instruction}"], timeout=900),
    ),
}


@click.group("setup")
def setup():
    """Configure solo project helpers."""


@setup.command("runtime")
@click.argument("name")
@click.option("--preset", type=click.Choice(sorted(RUNTIME_PRESETS.keys())), default=None, help="Start from a built-in runtime preset.")
@click.option("--adapter", default=None, help="Runtime adapter. Defaults to the preset adapter or command.")
@click.option("--command", "command_name", default=None, help="External command for command adapter profiles.")
@click.option("--arg", "args", multiple=True, help="Argument for the command profile. Repeat for multiple args.")
@click.option("--timeout", type=int, default=None, help="Command timeout in seconds.")
@click.option("--env", "env_items", multiple=True, help="Environment entry as KEY=VALUE. Repeat for multiple entries.")
@click.option("--description", default=None, help="Profile description.")
@click.option("--set-default", is_flag=True, help="Use this profile as the project default runtime.")
@click.option("--for", "roles", multiple=True, help="Assign this runtime profile to an agent role. Repeat for multiple roles.")
def setup_runtime(
    name: str,
    preset: Optional[str],
    adapter: Optional[str],
    command_name: Optional[str],
    args: Iterable[str],
    timeout: Optional[int],
    env_items: Iterable[str],
    description: Optional[str],
    set_default: bool,
    roles: Iterable[str],
):
    """Create or update a runtime profile in .solo/config.yaml."""
    project = SoloProject.find(Path.cwd())
    if project is None:
        raise click.ClickException("No .solo project found. Run solo init first.")

    config = project.require_config()
    base = RUNTIME_PRESETS[preset] if preset else RuntimeProfileConfig()
    profile = RuntimeProfileConfig(
        adapter=adapter or base.adapter,
        description=description if description is not None else base.description,
        command=CommandRuntimeConfig(
            command=command_name if command_name is not None else base.command.command,
            args=list(args) if args else list(base.command.args),
            timeout=timeout if timeout is not None else base.command.timeout,
            env=_parse_env(env_items) if env_items else dict(base.command.env),
        ),
    )

    if profile.adapter == "command" and not profile.command.command:
        raise click.ClickException("Command adapter profiles require --command or a command preset.")

    config.runtime_profiles[name] = profile

    if set_default:
        config.execution.default_profile = name
        config.execution.default_adapter = profile.adapter

    for role in roles:
        if role not in config.agents:
            raise click.ClickException(f"Unknown agent role: {role}")
        config.agents[role].runtime = name

    save_config(config, project.config_path)
    success(f"saved runtime profile {name}")
    if set_default:
        click.echo(f"Default runtime: {name}")
    for role in roles:
        click.echo(f"{role} runtime: {name}")


def _parse_env(items: Iterable[str]) -> Dict[str, str]:
    env: Dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise click.ClickException(f"Invalid --env value, expected KEY=VALUE: {item}")
        key, value = item.split("=", 1)
        if not key:
            raise click.ClickException(f"Invalid --env value, expected KEY=VALUE: {item}")
        env[key] = value
    return env
