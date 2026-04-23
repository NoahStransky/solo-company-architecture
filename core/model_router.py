"""Model Router — 根据 Agent 角色和项目配置解析模型参数."""

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


class ModelRouter:
    """解析 config/models.yaml，为 Agent 提供模型配置."""

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = self._default_config_path()

        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = self._load_config()

    @classmethod
    def _default_config_path(cls) -> str:
        """基于项目根目录返回默认配置路径."""
        # core/model_router.py -> parent -> parent = project root
        project_root = Path(__file__).resolve().parent.parent
        return str(project_root / "config" / "models.yaml")

    def _load_config(self) -> Dict[str, Any]:
        with self.config_path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def resolve(self, agent_name: str, project: Optional[str] = None) -> Dict[str, Any]:
        """解析指定 Agent 的模型配置.

        Args:
            agent_name: Agent 名称，如 "dev", "cto".
            project: 项目名称，用于应用项目级覆盖.

        Returns:
            {"model": ..., "fallback": ..., "max_tokens": ..., "temperature": ...}
        """
        agents = self._config.get("agents", {})
        if agent_name not in agents:
            raise KeyError(f"Unknown agent: {agent_name}")

        agent_config = agents[agent_name].copy()
        result = {
            "model": agent_config.get("default"),
            "fallback": agent_config.get("fallback"),
            "max_tokens": agent_config.get("max_tokens"),
            "temperature": agent_config.get("temperature"),
        }

        # 项目级覆盖
        if project:
            projects = self._config.get("projects", {})
            project_config = projects.get(project, {})
            override = project_config.get(agent_name, {})
            if override and "model" in override:
                result["model"] = override["model"]

        return result

    def list_models(self, tier: Optional[str] = None) -> Any:
        """列出模型.

        Args:
            tier: 模型层级名称，如 "coding", "reasoning".
                  为 None 时返回所有层级的模型字典.

        Returns:
            tier 为 None -> {"reasoning": [...], "coding": [...], ...}
            tier 指定 -> ["model-1", "model-2", ...]
        """
        tiers = self._config.get("tiers", {})

        if tier is None:
            return {
                name: info.get("models", [])
                for name, info in tiers.items()
            }

        if tier not in tiers:
            raise KeyError(f"Unknown tier: {tier}")

        return tiers[tier].get("models", [])
