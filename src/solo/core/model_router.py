"""Model routing from .solo/config.yaml."""

from typing import Any, Dict

from .config import SoloConfig


class ModelRouter:
    def __init__(self, config: SoloConfig):
        self.config = config

    def resolve(self, agent_name: str) -> Dict[str, Any]:
        agent = self.config.get_agent(agent_name)
        provider = self.config.providers.get(agent.provider)
        return {
            "provider": agent.provider,
            "provider_type": provider.type if provider else agent.provider,
            "model": agent.model,
            "temperature": agent.temperature,
            "max_tokens": agent.max_tokens,
            "tools": list(agent.tools),
        }
