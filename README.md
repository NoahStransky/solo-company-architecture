# Solo Company CLI

`solo` turns one repository into a project-level Solo Company workspace.

You are the CEO. `solo start` opens a conversation with the default Secretary agent. The Secretary turns your intent into a task, asks the CTO to break it down, and prepares work for a bounded pool of Dev agents.

The first implementation is protocol-first: it creates `.solo/` state, workflows, agent prompts, and execution packages that future runtimes and `solo-os` can consume.

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
- `solo status --json` includes stable `dashboard.tasks[*]` cards with phase progress, agent progress, work package progress, and failed reason fields.
- `solo inspect --json` includes the same dashboard summary plus full events, messages, and artifact manifest for one task.

## Project Protocol

After `solo init`, a project has:

```text
.solo/
├── config.yaml
├── agents/
├── workflows/
├── state/
│   ├── tasks.json
│   ├── events.jsonl
│   ├── messages.jsonl
│   └── sessions/
├── artifacts/
└── contracts/
```

`solo-os` should treat this as a stable file protocol. It can read `config.yaml`, `state/tasks.json`, `state/events.jsonl`, `state/messages.jsonl`, and call `solo status --json` or `solo dispatch --json` when it needs structured interaction. `solo status --json` also exposes project paths, execution adapter capabilities, phase progress, agent progress, work package progress, and failed reason fields for dashboard registration.

## Runtime Shape

Default feature flow:

```text
CEO request
  -> Secretary
  -> CTO breakdown
  -> bounded Dev agent pool
  -> QA
  -> CTO review
  -> Secretary report
```

Dev agent count is estimated from task size and capped by:

```yaml
delegation:
  max_parallel_dev_agents: 3
```

Agent communication uses a durable mailbox in `.solo/state/messages.jsonl`. Messages only store routing metadata and artifact pointers; large task briefs, instructions, runtime output, implementation reports, and QA reports stay in `.solo/artifacts/<task_id>/`. For handoffs, `artifact` points to an existing sender result when one exists, while `details.next_instruction` points to the next phase package. Agent pools are expanded to concrete recipients and execution packages such as `dev-1_input.json` / `dev-1_instruction.md`; structured dev results update their assigned work package status.

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

Use runtime profiles when you want agents to share reusable execution settings without copying every tool-specific option into each agent:

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

The generic `command` adapter can hand the prepared package to Hermes, OpenClaw, Codex, Claude Code, or a local wrapper script. `command.args` supports `{task_id}`, `{phase}`, `{agent_role}`, `{agent_instance}`, `{input}`, `{instruction}`, and `{output_dir}` placeholders. The command also receives `SOLO_TASK_ID`, `SOLO_PHASE`, `SOLO_AGENT_ROLE`, `SOLO_AGENT_INSTANCE`, `SOLO_PACKAGE_INPUT`, `SOLO_PACKAGE_INSTRUCTION`, and `SOLO_OUTPUT_DIR` environment variables.

For agent pool phases, the command adapter runs once per agent instance and passes the instance-specific package paths, such as `dev-1_input.json` and `dev-1_instruction.md`. Runtime reports are written per agent, plus an aggregate phase runtime report.

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
```

## Protocol Validation

Use `solo validate` to check whether the local `.solo/` protocol directory is healthy. It verifies required files, contract schemas, config references, workflow phase dependencies, JSON/JSONL state files, message pointers, phase/task consistency, runtime reports, and structured artifact contracts.

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
solo validate
```

The protocol-first dispatcher can either generate packages for manual completion or run a configured external command adapter.

## Docs

- [solo CLI research](docs/research/solo-cli-research.md)
- [solo-os research](docs/research/solo-os-research.md)
- [solo CLI plan](docs/planning/solo-cli-plan.md)
