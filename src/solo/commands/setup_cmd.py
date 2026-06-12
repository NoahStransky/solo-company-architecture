"""solo setup commands."""

from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import click

from solo.core.config import AgentConfig, CommandRuntimeConfig, MCPServerConfig, ProviderConfig, RuntimeProfileConfig, SkillConfig, save_config
from solo.core.project import SoloProject
from solo.core.tooling import doctor_tooling, sync_tooling
from solo.utils.ui import print_json, success


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
}


@click.group("setup")
def setup():
    """Configure solo project helpers."""


@setup.command("list")
@click.option("--json", "as_json", is_flag=True, help="Print structured JSON.")
def setup_list(as_json: bool):
    """List configured agents, providers, runtimes, MCP servers, and skills."""
    project = _require_project()
    config = project.require_config()
    payload = _setup_index(config.to_dict())
    if as_json:
        print_json(payload)
        return
    for key, values in payload.items():
        click.echo(f"{key}: {', '.join(values) if values else '-'}")


@setup.command("show")
@click.argument("kind", type=click.Choice(["agent", "provider", "runtime", "mcp", "skill", "execution"]))
@click.argument("name", required=False)
@click.option("--json", "as_json", is_flag=True, help="Print structured JSON.")
def setup_show(kind: str, name: Optional[str], as_json: bool):
    """Show one setup entry."""
    project = _require_project()
    config = project.require_config()
    config_data = config.to_dict()
    payload = _setup_entry(config_data, kind, name)
    if as_json:
        print_json(payload)
        return
    click.echo(f"{kind}{f' {name}' if name else ''}:")
    for key, value in payload.items():
        click.echo(f"  {key}: {value}")


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
    _sync_tooling_after_config_change(project)
    if set_default:
        click.echo(f"Default runtime: {name}")
    for role in roles:
        click.echo(f"{role} runtime: {name}")


@setup.command("agent")
@click.argument("role")
@click.option("--provider", default=None, help="Provider name for this agent.")
@click.option("--model", default=None, help="Model name for this agent.")
@click.option("--runtime", default=None, help="Runtime profile name for this agent.")
@click.option("--temperature", type=float, default=None, help="Sampling temperature.")
@click.option("--max-tokens", type=int, default=None, help="Max output tokens.")
@click.option("--skill", "skills", multiple=True, help="Skill name. Repeat to replace the skill list.")
@click.option("--mcp", "mcp_servers", multiple=True, help="MCP server name. Repeat to replace the MCP list.")
@click.option("--tool", "tools", multiple=True, help="Tool name. Repeat to replace the tool list.")
def setup_agent(
    role: str,
    provider: Optional[str],
    model: Optional[str],
    runtime: Optional[str],
    temperature: Optional[float],
    max_tokens: Optional[int],
    skills: Iterable[str],
    mcp_servers: Iterable[str],
    tools: Iterable[str],
):
    """Create or update one agent role in .solo/config.yaml."""
    project = _require_project()
    config = project.require_config()
    existing = config.agents.get(role) or AgentConfig(provider="", model="")
    if provider and provider not in config.providers:
        raise click.ClickException(f"Unknown provider: {provider}")
    if runtime and runtime not in config.runtime_profiles:
        raise click.ClickException(f"Unknown runtime profile: {runtime}")
    for skill in skills:
        if skill not in config.skills:
            raise click.ClickException(f"Unknown skill: {skill}")
    for server in mcp_servers:
        if server not in config.mcp_servers:
            raise click.ClickException(f"Unknown MCP server: {server}")
    config.agents[role] = AgentConfig(
        provider=provider if provider is not None else existing.provider,
        model=model if model is not None else existing.model,
        runtime=runtime if runtime is not None else existing.runtime,
        temperature=temperature if temperature is not None else existing.temperature,
        max_tokens=max_tokens if max_tokens is not None else existing.max_tokens,
        skills=list(skills) if skills else list(existing.skills),
        mcp_servers=list(mcp_servers) if mcp_servers else list(existing.mcp_servers),
        tools=list(tools) if tools else list(existing.tools),
    )
    save_config(config, project.config_path)
    success(f"saved agent {role}")
    _sync_tooling_after_config_change(project)


@setup.command("provider")
@click.argument("name")
@click.option("--type", "provider_type", required=True, help="Provider type, e.g. openai, anthropic, openai-compatible.")
@click.option("--api-key-env", default="", help="Environment variable containing the API key.")
@click.option("--base-url", default="", help="Provider base URL.")
@click.option("--organization-env", default="", help="Environment variable containing the organization id.")
def setup_provider(
    name: str,
    provider_type: str,
    api_key_env: str,
    base_url: str,
    organization_env: str,
):
    """Create or update a provider config."""
    project = _require_project()
    config = project.require_config()
    config.providers[name] = ProviderConfig(
        type=provider_type,
        api_key_env=api_key_env,
        base_url=base_url,
        organization_env=organization_env,
    )
    save_config(config, project.config_path)
    success(f"saved provider {name}")
    _sync_tooling_after_config_change(project)


@setup.command("mcp")
@click.argument("name")
@click.option("--command", "command_name", required=True, help="MCP server command.")
@click.option("--arg", "args", multiple=True, help="MCP server argument. Repeat for multiple args.")
@click.option("--env", "env_items", multiple=True, help="Environment entry as KEY=VALUE. Repeat for multiple entries.")
@click.option("--description", default="", help="MCP server description.")
@click.option("--enable/--disable", default=True, help="Enable or disable this MCP server.")
def setup_mcp(
    name: str,
    command_name: str,
    args: Iterable[str],
    env_items: Iterable[str],
    description: str,
    enable: bool,
):
    """Create or update an MCP server config."""
    project = _require_project()
    config = project.require_config()
    config.mcp_servers[name] = MCPServerConfig(
        command=command_name,
        args=list(args),
        env=_parse_env(env_items),
        enabled=enable,
        description=description,
    )
    save_config(config, project.config_path)
    success(f"saved mcp server {name}")
    _sync_tooling_after_config_change(project)


@setup.command("skill")
@click.argument("name")
@click.option("--path", "skill_path", required=True, help="Skill file path relative to .solo.")
@click.option("--description", default="", help="Skill description.")
@click.option("--create-file", is_flag=True, help="Create the skill file if it does not exist.")
def setup_skill(name: str, skill_path: str, description: str, create_file: bool):
    """Create or update a skill config."""
    project = _require_project()
    config = project.require_config()
    config.skills[name] = SkillConfig(description=description, path=skill_path)
    target = project.solo_dir / skill_path
    if create_file and not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"# {name}\n\n{description}\n", encoding="utf-8")
    save_config(config, project.config_path)
    success(f"saved skill {name}")
    _sync_tooling_after_config_change(project)


@setup.group("tooling")
def setup_tooling():
    """Sync generated Codex and Claude Code project files."""


@setup_tooling.command("sync")
@click.option("--target", type=click.Choice(["all", "codex", "claude"]), default="all", show_default=True, help="Tooling target to render.")
@click.option("--force", is_flag=True, help="Overwrite unmanaged target files.")
@click.option("--json", "as_json", is_flag=True, help="Print structured JSON.")
def setup_tooling_sync(target: str, force: bool, as_json: bool):
    """Render AGENTS.md, CLAUDE.md, MCP, skills, and exported config files."""
    project = _require_project()
    try:
        result = sync_tooling(project, target=target, force=force)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    if as_json:
        print_json(result.to_dict())
        return
    success(f"synced {len(result.written)} tooling files")
    if result.skipped:
        click.echo("Skipped unmanaged files:")
        for path in result.skipped:
            click.echo(f"  {path}")


@setup_tooling.command("doctor")
@click.option("--target", type=click.Choice(["all", "codex", "claude"]), default="all", show_default=True, help="Tooling target to check.")
@click.option("--json", "as_json", is_flag=True, help="Print structured JSON.")
def setup_tooling_doctor(target: str, as_json: bool):
    """Check whether generated tooling files are present and managed by Solo."""
    project = _require_project()
    result = doctor_tooling(project, target=target)
    if as_json:
        print_json(result.to_dict())
        return
    if result.ok:
        success(f"tooling ok ({len(result.checked)} files checked)")
        return
    for path in result.missing:
        click.echo(f"missing: {path}")
    for path in result.unmanaged:
        click.echo(f"unmanaged: {path}")
    for error in result.errors:
        click.echo(f"error: {error}")
    raise click.ClickException("Tooling check failed.")


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


def _require_project() -> SoloProject:
    project = SoloProject.find(Path.cwd())
    if project is None:
        raise click.ClickException("No .solo project found. Run solo init first.")
    return project


def _sync_tooling_after_config_change(project: SoloProject) -> None:
    try:
        result = sync_tooling(project)
    except ValueError as exc:
        click.echo(f"tooling sync skipped: {exc}")
        return
    success(f"synced {len(result.written)} tooling files")
    if result.skipped:
        click.echo("Skipped unmanaged tooling files:")
        for path in result.skipped:
            click.echo(f"  {path}")


def _setup_index(config_data: Dict[str, Any]) -> Dict[str, list]:
    return {
        "agents": sorted(config_data.get("agents", {}).keys()),
        "providers": sorted(config_data.get("providers", {}).keys()),
        "runtimes": sorted(config_data.get("runtime_profiles", {}).keys()),
        "mcp_servers": sorted(config_data.get("mcp_servers", {}).keys()),
        "skills": sorted(config_data.get("skills", {}).keys()),
        "tooling_targets": ["codex", "claude"],
    }


def _setup_entry(config_data: Dict[str, Any], kind: str, name: Optional[str]) -> Dict[str, Any]:
    if kind == "execution":
        if name:
            raise click.ClickException("setup show execution does not take a name.")
        return config_data.get("execution", {})
    key_by_kind = {
        "agent": "agents",
        "provider": "providers",
        "runtime": "runtime_profiles",
        "mcp": "mcp_servers",
        "skill": "skills",
    }
    collection_key = key_by_kind[kind]
    if not name:
        raise click.ClickException(f"setup show {kind} requires a name.")
    collection = config_data.get(collection_key, {})
    if name not in collection:
        raise click.ClickException(f"Unknown {kind}: {name}")
    return collection[name]
