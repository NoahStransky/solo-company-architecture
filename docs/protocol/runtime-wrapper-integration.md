# Runtime Wrapper Integration

Solo integrates real agent CLIs as external runtimes. Codex, Claude Code, Hermes, OpenClaw, and similar tools own their model calls, subagents, sessions, memory, and internal orchestration. Solo owns the durable project protocol around them: task state, phase handoffs, artifacts, validation, and `solo-os` dashboard fields.

## What Solo Does Not Own

Do not duplicate mature runtime features inside Solo:

- model-provider API calling,
- Codex or Claude Code subagent/team scheduling,
- `/goal` evaluator loops,
- dynamic workflow engines,
- long-lived runtime memory,
- tool-specific approval UX.

Solo may pass a goal, acceptance criteria, and artifact contract to a runtime. The runtime decides whether to execute that with one agent, subagents, an agent team, or a workflow.

## Why Generic Wrapper First

The generic wrapper path keeps Solo small:

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

For Hermes, OpenClaw, or any other non-built-in harness, use a project-local wrapper script if the CLI needs setup files, sessions, or non-stdin input:

```bash
solo setup runtime hermes-local \
  --command python \
  --arg "$(pwd)/scripts/hermes_solo_wrapper.py" \
  --set-default
```

That script still reads Solo's environment variables and writes Solo's structured artifacts.

## Goal-Aware Wrappers

When an external runtime has a native goal loop, map Solo's phase acceptance criteria into that runtime instead of reimplementing the loop in Solo.

Claude Code example:

```bash
claude -p "/goal $(cat \"$SOLO_PACKAGE_INSTRUCTION\")"
```

Codex example:

```bash
codex exec "/goal $(cat \"$SOLO_PACKAGE_INSTRUCTION\")"
```

The exact command should live in a wrapper script once quoting, streaming, approvals, and result extraction matter. Solo only requires that the wrapper writes the expected structured artifact and exits with a meaningful status code.

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

For legacy agent pools, each agent instance can get its own wrapper invocation. New integrations should usually prefer the runtime's native subagents, agent teams, or workflow engine inside a single Solo phase, because Codex and Claude Code now provide richer coordination, approval, and inspection surfaces than Solo should duplicate.

## Adapter Policy

Do not add dedicated Hermes, OpenClaw, Codex CLI, or Claude Code CLI adapters just to mirror their command flags. Use explicit wrapper scripts.

Consider a deeper adapter only for a stable programmatic API that gives Solo something the command wrapper cannot:

- streaming incremental events back into `.solo/state/events.jsonl`,
- stable thread/session identifiers,
- structured approvals,
- machine-readable subagent progress,
- richer failure classification than return code plus stdout/stderr.

The current likely candidate for a spike is Codex SDK/app-server, because it exposes programmatic threads and event streams. Claude Code should stay behind the CLI wrapper until its programmatic surface is needed and stable enough for Solo's protocol.
