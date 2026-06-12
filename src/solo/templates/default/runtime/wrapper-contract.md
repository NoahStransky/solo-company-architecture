# Solo Runtime Wrapper Contract

Runtime wrappers let `solo` hand a prepared agent package to an external tool such as Codex, Claude Code, Hermes, OpenClaw, or a local script. The external tool owns model calls, sessions, subagents, goal loops, memory, and approvals. Solo owns the phase contract, artifacts, state, and dashboard-readable handoff.

The wrapper is launched by the `command` adapter. It receives:

| Environment variable | Meaning |
|---|---|
| `SOLO_TASK_ID` | Task id |
| `SOLO_PHASE` | Current workflow phase |
| `SOLO_AGENT_ROLE` | Agent role, such as `cto`, `dev`, or `qa` |
| `SOLO_AGENT_INSTANCE` | Concrete pool instance, such as `dev-1`; empty for single-agent phases |
| `SOLO_PACKAGE_INPUT` | JSON execution package path |
| `SOLO_PACKAGE_INSTRUCTION` | Markdown instruction path |
| `SOLO_OUTPUT_DIR` | Artifact directory for the task |

The command runs with `SOLO_OUTPUT_DIR` as its working directory. Use an absolute wrapper path or install the wrapper on `PATH` if it lives outside the artifact directory.

Command arguments may use these placeholders:

```text
{task_id}
{phase}
{agent_role}
{agent_instance}
{input}
{instruction}
{output_dir}
```

## Required Outputs

Wrappers should write phase-specific structured outputs into `SOLO_OUTPUT_DIR`.

### CTO Breakdown

Write `work_packages.json`:

```json
{
  "work_packages": [
    {
      "id": "api",
      "title": "Build API",
      "description": "Implement backend routes",
      "agent_role": "dev",
      "files_scope": ["src/api.py"]
    }
  ]
}
```

### Implementation Agent

For a single implementation phase, write `<phase>_agent_result.json` or `<phase>_result.json`. For legacy agent pools, write `<agent_instance>_agent_result.json`:

```json
{
  "summary": "Implemented API routes",
  "status": "completed",
  "files_changed": ["src/api.py"],
  "tests": ["pytest tests/test_api.py"],
  "work_packages": [
    {"id": "api", "status": "completed"}
  ]
}
```

### QA

Write `qa_report.json`:

```json
{
  "summary": "Smoke tests passed",
  "verdict": "pass",
  "tests_run": ["pytest"],
  "findings": []
}
```

## Exit Codes

- `0`: runtime succeeded; `solo run --once` may advance the workflow.
- non-zero: runtime failed; Solo marks the phase and task as `failed`, writes `phase.failed`, and stops handoff.

Wrappers may still write partial artifacts on failure. Solo keeps stdout, stderr, command, and return code in runtime reports.
