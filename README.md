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
solo setup runtime local-codex --preset codex --for dev --for qa
solo dispatch --adapter command --json "Run with an external runtime"
solo inspect --json
solo complete
solo status
solo status --json
solo validate --json
solo start
```

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

`solo-os` should treat this as a stable file protocol. It can read `config.yaml`, `state/tasks.json`, `state/events.jsonl`, `state/messages.jsonl`, and call `solo status --json` or `solo dispatch --json` when it needs structured interaction. `solo status --json` also exposes project paths and execution adapter capabilities for dashboard registration.

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

Agent communication uses a durable mailbox in `.solo/state/messages.jsonl`. Messages only store routing metadata and artifact pointers; large task briefs, instructions, runtime output, implementation reports, and QA reports stay in `.solo/artifacts/<task_id>/`. For handoffs, `artifact` points to an existing sender result when one exists, while `details.next_instruction` points to the next phase package. Agent pools are expanded to concrete recipients and execution packages such as `dev-1_input.json` / `dev-1_instruction.md`.

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

The generic `command` adapter can hand the prepared package to Hermes, OpenClaw, Codex, Claude Code, or a local wrapper script. `command.args` supports `{task_id}`, `{phase}`, `{agent_role}`, `{input}`, `{instruction}`, and `{output_dir}` placeholders. The command also receives `SOLO_TASK_ID`, `SOLO_PHASE`, `SOLO_AGENT_ROLE`, `SOLO_PACKAGE_INPUT`, `SOLO_PACKAGE_INSTRUCTION`, and `SOLO_OUTPUT_DIR` environment variables.

Command execution metadata is written to `.solo/artifacts/<task_id>/<phase>_runtime.json`; `events.jsonl` stores a lightweight pointer and return code for dashboards.

## Protocol Validation

Use `solo validate` to check whether the local `.solo/` protocol directory is healthy. It verifies required files, contract schemas, config references, workflow phase dependencies, and JSON/JSONL state files.

```bash
solo validate
solo validate --json
```

## Current Commands

```bash
solo init
solo dispatch
solo inspect
solo complete
solo status
solo start
solo setup runtime
solo validate
```

The protocol-first dispatcher can either generate packages for manual completion or run a configured external command adapter.

## Docs

- [solo CLI research](docs/research/solo-cli-research.md)
- [solo-os research](docs/research/solo-os-research.md)
- [solo CLI plan](docs/planning/solo-cli-plan.md)
