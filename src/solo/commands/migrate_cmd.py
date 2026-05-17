"""solo migrate command."""

from pathlib import Path

import click

from solo.core.migration import find_solo_root, load_raw_config, migrate_config, migration_plan, save_raw_config
from solo.utils.ui import print_json, success


@click.command("migrate")
@click.option("--check", is_flag=True, help="Only report whether migration is needed.")
@click.option("--backup/--no-backup", default=True, help="Write a config backup before applying migration.")
@click.option("--json", "as_json", is_flag=True, help="Print structured JSON.")
def migrate(check: bool, backup: bool, as_json: bool):
    """Inspect or migrate the local .solo protocol version."""
    root = find_solo_root(Path.cwd())
    if root is None:
        raise click.ClickException("No .solo project found. Run solo init first.")

    config_path = root / ".solo" / "config.yaml"
    try:
        config_data = load_raw_config(config_path)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    plan = migration_plan(config_data)
    if not plan["ok"]:
        if as_json:
            print_json({**plan, "applied": False, "backup": ""})
            raise click.exceptions.Exit(1)
        raise click.ClickException(plan["error"])

    payload = {**plan, "applied": False, "backup": ""}
    if not check and plan["needed"]:
        backup_path = ""
        if backup:
            backup_target = config_path.with_suffix(f".yaml.bak.v{plan['from_version']}")
            backup_target.write_text(config_path.read_text(encoding="utf-8"), encoding="utf-8")
            backup_path = str(backup_target)
        migrated = migrate_config(config_data)
        save_raw_config(migrated, config_path)
        payload["applied"] = True
        payload["backup"] = backup_path

    if as_json:
        print_json(payload)
        return
    if payload["applied"]:
        success(f"migrated .solo protocol {payload['from_version']} -> {payload['to_version']}")
        if payload["backup"]:
            click.echo(f"Backup: {payload['backup']}")
    elif payload["needed"]:
        click.echo(f"Migration needed: {payload['from_version']} -> {payload['to_version']}")
        for step in payload["steps"]:
            click.echo(f"- {step}")
    else:
        success(f".solo protocol is current: {payload['to_version']}")
