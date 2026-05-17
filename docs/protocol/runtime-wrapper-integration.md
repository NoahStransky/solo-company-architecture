# Runtime Wrapper Integration

Solo should integrate real agent CLIs through the generic `command` adapter first. Codex, Claude Code, Hermes, and OpenClaw all remain external runtimes from Solo's point of view.

## Why Generic Wrapper First

Special adapters should wait until there is a proven need for tool-specific behavior. The generic wrapper path keeps Solo small:

- Agent model/provider config stays in `.solo/config.yaml`.
- Runtime launch config stays in `runtime_profiles`.
- Agent CLIs keep their own authentication and local setup.
- Solo owns workflow state, artifacts, mailbox, and dashboard protocol.
- Wrappers translate between Solo's phase package and each tool's CLI shape.

This avoids copying each tool's setup surface into Solo.

## Contract

All real runtimes should satisfy `.solo/runtime/wrapper-contract.md`.

Solo provides:

- `SOLO_TASK_ID`
- `SOLO_PHASE`
- `SOLO_AGENT_ROLE`
- `SOLO_AGENT_INSTANCE`
- `SOLO_PACKAGE_INPUT`
- `SOLO_PACKAGE_INSTRUCTION`
- `SOLO_OUTPUT_DIR`

Wrappers should:

- read the instruction and input package,
- call the external CLI,
- write the expected structured artifact for the current phase,
- return `0` on success,
- return non-zero when Solo should mark the phase or agent as failed.

## Recommended Shape

Use the bundled generic wrapper when the external CLI can read stdin:

```bash
solo setup runtime codex-cli \
  --command python \
  --arg "$(pwd)/.solo/runtime/examples/cli_wrapper.py" \
  --arg=-- \
  --arg codex \
  --arg exec \
  --arg - \
  --set-default
```

Use the same shape for Claude Code:

```bash
solo setup runtime claude-code \
  --command python \
  --arg "$(pwd)/.solo/runtime/examples/cli_wrapper.py" \
  --arg=-- \
  --arg claude \
  --arg -p \
  --arg - \
  --set-default
```

For Hermes/OpenClaw, prefer a tiny project-local wrapper script if their CLI needs setup files, sessions, or non-stdin input:

```bash
solo setup runtime hermes-local \
  --command python \
  --arg "$(pwd)/scripts/hermes_solo_wrapper.py" \
  --set-default
```

That script still reads Solo's environment variables and writes Solo's structured artifacts.

## Phase Outputs

Wrappers should write these artifacts:

| Phase | Expected artifact |
|------|-------------------|
| `cto_breakdown` | `work_packages.json` or `cto_breakdown_result.json` |
| `dev_pool` agent instance | `<agent_instance>_agent_result.json` |
| `qa` | `qa_report.json` |
| `cto_review` | `cto_review_result.json` |
| `secretary_report` | `secretary_report.md` or `secretary_report_result.json` |

The command adapter always writes runtime reports such as `<phase>_runtime.json` or `<agent_instance>_runtime.json`.

## Provider And Model Ownership

Solo resolves `agent.provider`, `agent.model`, `agent.skills`, and `agent.mcp_servers` into execution packages. The wrapper decides how much of that to pass through to the external CLI.

Recommended mapping:

- If the external CLI owns model/provider selection, the wrapper may ignore Solo's model fields.
- If the external CLI accepts model flags, the wrapper should map `resolved_model.model` to those flags.
- If the tool has its own MCP/plugin setup, keep it there; Solo only records desired MCP context in the package.

## Failure Semantics

Wrappers should use exit codes intentionally:

- `0`: artifact is complete enough for Solo to continue.
- non-zero: runtime failed; Solo records return code and stops at the failed phase.
- partial artifacts are allowed; dashboards can link to them through the artifact manifest.

For agent pools, each agent instance gets its own wrapper invocation. Solo records per-agent runtime reports and supports retrying failed agents.

## When To Add A Special Adapter

Add a dedicated adapter only after the generic wrapper cannot express a required capability:

- streaming incremental events back into `.solo/state/events.jsonl`,
- persistent sessions that Solo must manage,
- structured tool calls that need direct API access,
- richer failure classification than return code plus stdout/stderr.

Until then, keep Codex/Claude Code/Hermes/OpenClaw behind `command` runtime profiles.
