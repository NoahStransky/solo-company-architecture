# Solo Company CLI

`solo` turns one repository into a project-level Solo Company workspace.

You are the CEO. `solo start` opens a conversation with the default Secretary agent. The Secretary turns your intent into a task, asks the CTO to break it down, and prepares execution packages that Codex, Claude Code, Hermes, OpenClaw, or another runtime can carry out.

The implementation is protocol-first: it creates `.solo/` state, workflows, agent prompts, and execution packages that external runtimes and `solo-os` can consume. Solo is not trying to replace Codex, Claude Code, Hermes, or other agent harnesses; it gives them a durable project protocol, handoff surface, and dashboard-readable state.

## Install For Development

```bash
python3 -m pip install -e .
```

## Test With Docker Compose

Run tests without relying on the host Python environment:

```bash
docker compose run --rm test
```

Try the CLI in an isolated workspace:

```bash
docker compose run --rm cli init --yes
docker compose run --rm cli dispatch "Build RSS subscriptions"
docker compose run --rm cli status --json
```

## Quick Start

```bash
solo init --yes
solo dispatch --workflow feature "Build RSS subscriptions"
solo run --once
solo inspect --json
solo complete
solo status
solo status --json
solo validate --json
solo start
```

## End-To-End Dummy Runtime Demo

New projects include a local dummy runtime that writes valid Solo artifacts without calling a real model. This is the fastest way to check the whole workflow.

```bash
solo init --yes --name demo-company
solo setup runtime dummy \
  --command python \
  --arg "$(pwd)/.solo/runtime/examples/dummy_runtime.py" \
  --set-default
solo dispatch --json "Build a small RSS subscription feature"
solo run --until done --json
solo status --json
solo inspect --json
solo validate --json
```

Expected result:

- `solo run --until done` advances through CTO breakdown, dev pool, QA, CTO review, and secretary report.
- `.solo/artifacts/<task_id>/` contains instruction/input files, runtime reports, work packages, dev results, QA report, and the final report.
- `solo status` and `solo inspect` show progress, agent/work package status, recent activity, artifacts, and failure details in a terminal-friendly format.
- `solo status --json` includes stable protocol compatibility fields and `dashboard.tasks[*]` cards with phase progress, agent progress, work package progress, and failed reason fields.
- `solo inspect --json` includes the same protocol/dashboard summary plus full events, messages, and artifact manifest for one task.

## Project Protocol

After `solo init`, a project has:

```text
.solo/
├── config.yaml
├── agents/
├── tooling/
├── workflows/
├── state/
│   ├── tasks.json
│   ├── events.jsonl
│   ├── messages.jsonl
│   └── sessions/
├── artifacts/
└── contracts/
```

`solo-os` should treat this as a stable file protocol. It can read `config.yaml`, `state/tasks.json`, `state/events.jsonl`, `state/messages.jsonl`, and call `solo status --json`, `solo inspect --json`, or `solo dispatch --json` when it needs structured interaction. `solo status --json` and `solo inspect --json` expose protocol compatibility, project paths, execution adapter capabilities, phase progress, agent progress, work package progress, and failed reason fields for dashboard registration.

The read-only dashboard contract is documented in `docs/protocol/solo-os-dashboard-contract.md`. Runtime wrapper guidance for Codex, Claude Code, Hermes, and OpenClaw is documented in `docs/protocol/runtime-wrapper-integration.md`.

For cross-project orchestration, `solo-os` can attach its own identity and dependency context during dispatch:

```bash
solo dispatch --json \
  --external-source solo-os \
  --external-id XPROJ-20260528-001 \
  --external-node frontend \
  --context-file dependency-context.md \
  "Build frontend billing integration"
```

The task snapshot stores `external` and `context`, the context file is copied into task artifacts, and `solo inspect --json` exposes a compact `handoff` object for downstream project prompts.

## Child-Agent Tooling Sync

`solo init` also creates a central tooling manifest at `.solo/tooling/manifest.yaml` and immediately syncs generated files for local child-agent CLIs:

```text
AGENTS.md
CLAUDE.md
.claude/CLAUDE.md
.claude/settings.json
.claude/agents/*.md
.claude/skills/*/SKILL.md
.claude/commands/*.md
.mcp.json
.solo/generated/codex/default/config.toml
.solo/generated/codex/default/commands/*.md
```

The source of truth stays in `.solo/config.yaml`, `.solo/agents/`, `.solo/skills/`, and `.solo/tooling/`. After changing providers, models, MCP servers, skills, or tooling rules, regenerate the Codex and Claude Code files:

```bash
solo setup tooling sync
solo setup tooling doctor
```

`solo setup agent/provider/mcp/skill/runtime` automatically runs tooling sync after saving config, so normal setup flows keep child-agent files fresh. Generated files include a Solo marker. Sync overwrites managed files, skips unmanaged hand-written files by default, and supports `--force` when you intentionally want Solo to take ownership of the target file.

## Runtime Shape

Default feature flow:

```text
CEO request
  -> Secretary
  -> CTO breakdown
  -> implementation phase
  -> QA
  -> CTO review
  -> Secretary report
```

Solo keeps phase state, mailbox messages, work packages, artifacts, failure status, and retry/reopen semantics. It does not need to own the internal team model of a runtime. Codex or Claude Code may use `/goal`, subagents, agent teams, or workflows inside one Solo phase, then write the structured result artifact back to `.solo/artifacts/<task_id>/`.

Legacy Solo agent-pool fields remain in the protocol for compatibility with existing tasks and tests:

```yaml
delegation:
  max_parallel_dev_agents: 3
```

Agent communication uses a durable mailbox in `.solo/state/messages.jsonl`. Messages only store routing metadata and artifact pointers; large task briefs, instructions, runtime output, implementation reports, and QA reports stay in `.solo/artifacts/<task_id>/`. For handoffs, `artifact` points to an existing sender result when one exists, while `details.next_instruction` points to the next phase package. If a workflow still uses an agent pool, Solo records concrete recipients and per-agent package paths for compatibility, but new integrations should prefer the external runtime's native subagent/team mechanism within the implementation phase.

Dev results can update work package status with:

```json
{
  "summary": "Implemented API; tests are blocked",
  "work_packages": [
    {"id": "api", "status": "completed"},
    {"id": "tests", "status": "blocked"}
  ]
}
```

## Agent Providers, MCP, And Skills

Configure agent routing in `.solo/config.yaml`.

```yaml
providers:
  openai:
    type: openai
    api_key_env: OPENAI_API_KEY
  anthropic:
    type: anthropic
    api_key_env: ANTHROPIC_API_KEY

mcp_servers:
  filesystem:
    enabled: true
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem", "."]

skills:
  architecture:
    description: Design architecture and work packages.
    path: skills/architecture.md

agents:
  cto:
    provider: anthropic
    model: claude-opus-4
    skills: [architecture]
    mcp_servers: [filesystem]
  qa:
    provider: openai
    model: gpt-4o-mini
    skills: [testing, code-review]
```

`solo dispatch --json` includes each agent's resolved model config, provider config, enabled MCP servers, and skill content in the generated execution package.

## Execution Adapters

The default `package` adapter writes execution packages into `.solo/artifacts/<task_id>/`.

Use runtime profiles when you want agents to share reusable launch settings without copying every tool-specific option into each agent:

```yaml
execution:
  default_adapter: package
  default_profile: ""

runtime_profiles:
  local-codex:
    adapter: command
    description: Local Codex CLI wrapper
    command:
      command: codex
      args: ["{instruction}"]
      timeout: 900
      env: {}

agents:
  dev:
    runtime: local-codex
```

Create or update profiles from the CLI:

```bash
solo setup runtime local-codex --preset codex --for dev --for qa
solo setup runtime local-wrapper --command ./scripts/solo-runtime --arg "{instruction}" --set-default
```

Built-in presets are intentionally small: `package`, `codex`, and `claude-code`. For Hermes, OpenClaw, or any other harness, use an explicit `--command` wrapper so Solo does not pretend to own that tool's setup, memory, session, or orchestration model.

Other common configuration can also be managed without editing YAML by hand:

```bash
solo setup provider local-openai \
  --type openai-compatible \
  --api-key-env LOCAL_API_KEY \
  --base-url http://localhost:11434/v1

solo setup mcp local-files \
  --command npx \
  --arg=-y \
  --arg=@modelcontextprotocol/server-filesystem \
  --arg . \
  --enable

solo setup skill debugging \
  --path skills/debugging.md \
  --description "Debug failing tests" \
  --create-file

solo setup agent dev \
  --provider local-openai \
  --model qwen-coder \
  --skill implementation \
  --skill testing \
  --mcp local-files
```

The generic `command` adapter can hand the prepared package to Codex, Claude Code, Hermes, OpenClaw, or a local wrapper script. `command.args` supports `{task_id}`, `{phase}`, `{agent_role}`, `{agent_instance}`, `{input}`, `{instruction}`, and `{output_dir}` placeholders. The command also receives `SOLO_TASK_ID`, `SOLO_PHASE`, `SOLO_AGENT_ROLE`, `SOLO_AGENT_INSTANCE`, `SOLO_PACKAGE_INPUT`, `SOLO_PACKAGE_INSTRUCTION`, and `SOLO_OUTPUT_DIR` environment variables.

For legacy agent pool phases, the command adapter can still run once per agent instance and pass the instance-specific package paths, such as `dev-1_input.json` and `dev-1_instruction.md`. New Codex and Claude Code wrappers should normally pass a single phase instruction and let the runtime decide whether to use `/goal`, subagents, agent teams, or dynamic workflows internally.

Command execution metadata is written to `.solo/artifacts/<task_id>/<phase>_runtime.json`; `events.jsonl` stores a lightweight pointer and return code for dashboards.

Use `solo run --once` to advance the current task by one phase. If a command runtime returns a non-zero exit code, Solo marks the phase and task as `failed`, writes a `phase.failed` event, and does not hand off to the next agent.

New projects include `.solo/runtime/wrapper-contract.md`, `.solo/runtime/examples/dummy_runtime.py`, and `.solo/runtime/examples/cli_wrapper.py`. The dummy runtime is useful for checking the end-to-end workflow before wiring a real external agent CLI. The generic CLI wrapper sends the Solo instruction to an external command on stdin and writes a structured Solo result:

```bash
solo setup runtime generic-cli \
  --command python \
  --arg "$(pwd)/.solo/runtime/examples/cli_wrapper.py" \
  --arg=-- \
  --arg your-agent-cli \
  --set-default
```

Inspect setup without opening YAML:

```bash
solo setup list
solo setup list --json
solo setup show agent dev --json
solo setup show runtime generic-cli --json
solo setup show execution --json
solo setup tooling sync
solo setup tooling doctor --json
```

## Protocol Validation

Use `solo validate` to check whether the local `.solo/` protocol directory is healthy. It verifies required files, contract schemas, config references, workflow phase dependencies, JSON/JSONL state files, message pointers, phase/task consistency, runtime reports, generated child-agent tooling files, and structured artifact contracts.

```bash
solo validate
solo validate --json
```

## Protocol Migration

Use `solo migrate` to inspect or update `.solo/config.yaml` when the protocol version changes.

```bash
solo migrate --check
solo migrate --check --json
solo migrate --json
solo migrate --no-backup
```

`solo migrate` can run even when the current CLI cannot load the project config. When it applies a migration, it writes a backup by default.

## Current Commands

```bash
solo init
solo dispatch
solo inspect
solo migrate
solo complete
solo reopen
solo retry
solo run
solo status
solo start
solo setup runtime
solo setup list
solo setup show
solo setup agent
solo setup provider
solo setup mcp
solo setup skill
solo setup tooling sync
solo setup tooling doctor
solo validate
```

The protocol-first dispatcher can either generate packages for manual completion or run a configured external command adapter.

## Docs

- [solo CLI research](docs/research/solo-cli-research.md)
- [solo-os research](docs/research/solo-os-research.md)
- [solo CLI plan](docs/planning/solo-cli-plan.md)
