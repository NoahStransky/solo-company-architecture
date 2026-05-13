"""Example Solo runtime wrapper for local smoke tests."""

import json
import os
from pathlib import Path


def main() -> int:
    phase = os.environ["SOLO_PHASE"]
    agent_instance = os.environ.get("SOLO_AGENT_INSTANCE", "")
    output_dir = Path(os.environ["SOLO_OUTPUT_DIR"])
    input_path = Path(os.environ["SOLO_PACKAGE_INPUT"])
    package = json.loads(input_path.read_text(encoding="utf-8"))

    if phase == "cto_breakdown":
        (output_dir / "work_packages.json").write_text(
            json.dumps({
                "work_packages": [
                    {
                        "id": "implementation",
                        "title": "Implement requested change",
                        "description": package["task_description"],
                        "agent_role": "dev",
                    }
                ]
            }, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    elif agent_instance:
        assigned = package.get("assigned_work_packages", [])
        (output_dir / f"{agent_instance}_agent_result.json").write_text(
            json.dumps({
                "summary": f"{agent_instance} completed assigned work",
                "status": "completed",
                "work_packages": [
                    {"id": item["id"], "status": "completed"}
                    for item in assigned
                    if item.get("id")
                ],
            }, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    elif phase == "qa":
        (output_dir / "qa_report.json").write_text(
            json.dumps({
                "summary": "Dummy runtime QA passed",
                "verdict": "pass",
                "tests_run": [],
                "findings": [],
            }, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    else:
        (output_dir / f"{phase}_result.json").write_text(
            json.dumps({
                "summary": f"Dummy runtime completed {phase}",
                "status": "completed",
            }, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
