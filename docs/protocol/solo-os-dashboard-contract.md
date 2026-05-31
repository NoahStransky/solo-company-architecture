# solo-os Read-only Dashboard Contract

This document defines the first stable contract that a separate `solo-os` project can use to show a read-only dashboard for initialized `solo` projects.

## Boundaries

`solo-os` may read `.solo/` files and call public `solo ... --json` commands. It must not import `solo.core.*` or write `.solo/state/*` directly.

For the first dashboard version, `solo-os` should be read-only:

- Register project paths in the `solo-os` project registry.
- Detect project health and protocol compatibility.
- Render task, phase, agent, work package, artifact, event, and mailbox state.
- Link to artifacts by path.
- Offer CLI command suggestions for recovery, but do not mutate the project.

## Required Files

Every dashboard project must have:

```text
.solo/config.yaml
.solo/state/tasks.json
.solo/state/events.jsonl
.solo/state/messages.jsonl
.solo/artifacts/
```

If any required file is missing, the dashboard should mark the project as unhealthy and ask the user to run:

```bash
solo validate
```

## Preferred CLI Reads

Prefer CLI JSON over reconstructing state by hand:

```bash
solo status --json --all
solo inspect --task <task_id> --json
solo validate --json
solo migrate --check --json
```

Use direct file reads as a fallback when the CLI is unavailable, too old, or returns a protocol compatibility error.

## Protocol Compatibility

`solo status --json` and `solo inspect --json` include:

```json
{
  "protocol": {
    "current_version": 1,
    "supported_version": 1,
    "compatible": true,
    "migration_needed": false,
    "migration_available": false,
    "migration_error": "",
    "migration_steps": []
  }
}
```

Dashboard behavior:

| State | Behavior |
|------|----------|
| `compatible=true` | Render normally. |
| `migration_needed=true` | Render limited state and suggest `solo migrate --check`, then `solo migrate`. |
| `migration_error` is non-empty | Mark unsupported and show the error. |
| CLI cannot load config | Try `solo migrate --check --json`; if that fails, fall back to raw `config.yaml` and `tasks.json`. |

## Dashboard Payload

Use `solo status --json --all` for project cards and task lists.

Important top-level fields:

- `project`: project name, description, version, repo.
- `protocol`: compatibility summary.
- `paths`: root, `.solo/`, config, task state, events, messages, artifacts.
- `execution`: default adapter, default profile, available adapters, runtime profiles.
- `summary`: task counts and last update.
- `dashboard.tasks[*]`: compact dashboard cards.
- `recent_events`: latest project events.
- `recent_messages`: latest mailbox messages.

Each `dashboard.tasks[*]` item contains:

- `task_id`, `title`, `status`, `workflow`, `current_phase`, `current_phase_index`.
- `phase_progress`: total, completed, skipped, done, percent.
- `agent_progress`: total, by_status, failed_agents, percent.
- `work_package_progress`: total, by_status, percent.
- `failed_reason`: phase, message, failed agents, return code, runtime report when available.
- `phases[*]`: phase index, name, type, role, status, current/failed flags.

Use `solo inspect --task <task_id> --json` for detail drawers or task pages. It includes the same `protocol` and `dashboard` summary plus:

- full `task` snapshot,
- `handoff` summary for downstream project orchestration,
- task-scoped `events`,
- task-scoped `messages`,
- `artifacts` manifest with name, path, relative_path, size_bytes, kind.

## Cross-Project Handoff

`solo-os` may pass its cross-task identity into a child project during dispatch:

```bash
solo dispatch --json \
  --external-source solo-os \
  --external-id XPROJ-20260528-001 \
  --external-node frontend \
  --context-file dependency-context.md \
  "Build frontend integration"
```

The child task stores:

- `task.external`: external source/id/node.
- `task.context.files[*]`: copied context artifacts under `.solo/artifacts/<task_id>/context/`.

`solo inspect --json` exposes a compact `handoff` object for downstream projects:

- task id, title, status, workflow, current phase.
- external metadata and context file pointers.
- phase, agent, and work package progress.
- failed reason when present.
- recent phase results and QA reports.
- key artifacts such as context files, outputs, work packages, QA reports, agent results, and runtime reports.

## Polling

Suggested read-only polling loop:

1. Every 2-5 seconds for active projects, run `solo status --json --all`.
2. If `summary.last_updated` changes, refresh open task detail panels with `solo inspect --task <task_id> --json`.
3. If command execution fails, retry once after a short delay, then fall back to direct file reads.
4. If `protocol.compatible=false`, stop normal polling and show the migration state.

`events.jsonl` and `messages.jsonl` are append-only, so a dashboard may also keep file offsets and tail incrementally. The CLI JSON path is still preferred for the first version because it centralizes compatibility and summary logic.

## Message Semantics

Mailbox messages live in `.solo/state/messages.jsonl`.

Required fields:

- `ts`
- `task_id`
- `from`
- `to`
- `type`

Optional fields:

- `phase`
- `summary`
- `artifact`
- `details`

Rules for dashboard links:

- If `artifact` is present, it must point to an existing sender result or execution package.
- For handoffs, `details.next_instruction` points to the next recipient instruction file.
- Agent pool handoffs should address concrete recipients such as `dev-1`, `dev-2`, not only the role `dev`.

## Artifact Kinds

`solo inspect --json` classifies artifact manifest entries with stable `kind` values:

| Kind | Meaning |
|------|---------|
| `input` | JSON phase or agent input package. |
| `instruction` | Markdown instruction for an agent/runtime. |
| `runtime` | Runtime execution report. |
| `agent_result` | Structured agent result. |
| `qa_report` | Structured QA report. |
| `work_packages` | CTO work package breakdown. |
| `task_snapshot` | Task snapshot written into artifacts. |
| `output` | Generic phase output. |
| `context` | External or dependency context copied during dispatch. |

Unknown files should still be shown with their extension-derived kind.

## Health Checks

Use:

```bash
solo validate --json
```

The dashboard should display `errors` and `warnings` directly. It should treat any non-zero exit code as unhealthy but still parse JSON output when present.

Use:

```bash
solo migrate --check --json
```

when protocol compatibility is unclear or `validate` reports `unsupported_protocol_version`.

## Test Coverage

The contract is covered by:

```bash
docker compose run --rm test pytest tests/test_solo/test_protocol_contract.py -q
```

Those tests create a completed dummy-runtime flow and verify the dashboard JSON, task state, mailbox, handoff pointers, and artifact manifest fields.
