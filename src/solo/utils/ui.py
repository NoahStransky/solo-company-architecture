"""Small UI helpers with no hard dependency on rich."""

import json
from typing import Any, Dict

import click


def print_json(data: Dict[str, Any]) -> None:
    click.echo(json.dumps(data, ensure_ascii=False, indent=2))


def heading(text: str) -> None:
    click.echo(text)
    click.echo("=" * len(text))


def success(text: str) -> None:
    click.echo(f"OK {text}")


def warn(text: str) -> None:
    click.echo(f"WARN {text}")
