"""Protocol version inspection and migration helpers."""

from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from solo.core.config import SOLO_PROTOCOL_VERSION


def find_solo_root(path: Path) -> Optional[Path]:
    """Find a project root with .solo/config.yaml without loading config."""
    current = path.resolve()
    if current.is_file():
        current = current.parent
    for candidate in [current] + list(current.parents):
        if (candidate / ".solo" / "config.yaml").exists():
            return candidate
    return None


def load_raw_config(config_path: Path) -> Dict[str, Any]:
    with config_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError("config.yaml must be a YAML object")
    return data


def protocol_version(config_data: Dict[str, Any]) -> int:
    return int(config_data.get("solo_protocol_version", 0))


def migration_plan(config_data: Dict[str, Any]) -> Dict[str, Any]:
    from_version = protocol_version(config_data)
    steps = []
    if from_version > SOLO_PROTOCOL_VERSION:
        return {
            "ok": False,
            "needed": False,
            "from_version": from_version,
            "to_version": SOLO_PROTOCOL_VERSION,
            "steps": [],
            "error": f"Project protocol version {from_version} is newer than this CLI supports ({SOLO_PROTOCOL_VERSION}).",
        }
    if from_version < 1:
        steps.extend([
            "set solo_protocol_version to 1",
            "ensure providers/mcp_servers/skills/runtime_profiles sections exist",
            "ensure delegation/execution/default_workflow sections exist",
        ])
    return {
        "ok": True,
        "needed": from_version < SOLO_PROTOCOL_VERSION,
        "from_version": from_version,
        "to_version": SOLO_PROTOCOL_VERSION,
        "steps": steps,
        "error": "",
    }


def migrate_config(config_data: Dict[str, Any]) -> Dict[str, Any]:
    """Return a migrated config dict for supported legacy protocol versions."""
    version = protocol_version(config_data)
    if version > SOLO_PROTOCOL_VERSION:
        raise ValueError(f"Project protocol version {version} is newer than this CLI supports ({SOLO_PROTOCOL_VERSION}).")
    migrated = dict(config_data)
    if version < 1:
        migrated["solo_protocol_version"] = 1
        migrated.setdefault("providers", {})
        migrated.setdefault("mcp_servers", {})
        migrated.setdefault("skills", {})
        migrated.setdefault("runtime_profiles", {})
        migrated.setdefault("agents", {})
        migrated.setdefault("delegation", {})
        migrated.setdefault("execution", {"default_adapter": "package", "default_profile": "", "command": {"command": "", "args": [], "timeout": 300, "env": {}}})
        migrated.setdefault("default_workflow", "feature")
    return migrated


def save_raw_config(config_data: Dict[str, Any], config_path: Path) -> None:
    with config_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(config_data, handle, sort_keys=False, allow_unicode=False)
