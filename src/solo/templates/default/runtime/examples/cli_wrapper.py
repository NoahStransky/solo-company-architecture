"""Generic Solo command runtime wrapper.

Usage:
  python .solo/runtime/examples/cli_wrapper.py -- <external-cli> [args...]

The wrapper sends the Solo instruction markdown to the external command on stdin,
captures stdout/stderr, and writes a structured Solo result artifact. If no
external command is provided, it writes a dry-run result.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = _strip_separator(args.command)

    phase = os.environ["SOLO_PHASE"]
    agent_instance = os.environ.get("SOLO_AGENT_INSTANCE", "")
    output_dir = Path(os.environ["SOLO_OUTPUT_DIR"])
    instruction_path = Path(os.environ["SOLO_PACKAGE_INSTRUCTION"])
    instruction = instruction_path.read_text(encoding="utf-8")

    if command:
        completed = subprocess.run(
            command,
            input=instruction,
            text=True,
            capture_output=True,
            cwd=output_dir,
            check=False,
        )
        summary = completed.stdout.strip().splitlines()[0] if completed.stdout.strip() else f"{phase} command finished"
        returncode = completed.returncode
        payload = {
            "summary": summary,
            "status": "completed" if returncode == 0 else "failed",
            "command": command,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    else:
        returncode = 0
        payload = {
            "summary": f"Dry-run wrapper completed {agent_instance or phase}",
            "status": "completed",
            "command": [],
            "stdout": "",
            "stderr": "",
        }

    _write_result(output_dir, phase, agent_instance, payload)
    return returncode


def _strip_separator(command: list) -> list:
    if command and command[0] == "--":
        return command[1:]
    return command


def _write_result(output_dir: Path, phase: str, agent_instance: str, payload: dict) -> None:
    if agent_instance:
        path = output_dir / f"{agent_instance}_agent_result.json"
    elif phase == "qa":
        payload.setdefault("verdict", "pass" if payload.get("status") == "completed" else "fail")
        path = output_dir / "qa_report.json"
    else:
        path = output_dir / f"{phase}_result.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
