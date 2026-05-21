# Solo Project Rules

- Treat `.solo/config.yaml` as the source of truth for agent models, providers, MCP servers, skills, and runtimes.
- Treat `.solo/state/` and `.solo/artifacts/` as durable protocol state. Read them before changing task state.
- Do not hand large results through chat text when a Solo artifact exists. Link or update the artifact instead.
- Keep generated files synchronized through `solo setup tooling sync` instead of editing generated sections by hand.
