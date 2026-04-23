import sys
from pathlib import Path

import pytest

# Ensure agents/ is on path
sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))

from core.model_router import ModelRouter
from agents import agent_orchestrator as orch


@pytest.fixture(autouse=True)
def tmp_workspace(monkeypatch, tmp_path):
    """Redirect WORKSPACE to a temporary directory for every test."""
    monkeypatch.setattr(orch, "WORKSPACE", tmp_path)
    return tmp_path


class TestSecretaryIntegration:
    def test_generate_context_package_with_real_model_router(self, tmp_path):
        """使用真实 ModelRouter + 临时 models.yaml 验证 context package."""
        # 创建临时 models.yaml
        models_yaml = tmp_path / "models.yaml"
        models_yaml.write_text(
            """
agents:
  dev:
    tier: coding
    default: "anthropic/claude-sonnet-4"
    fallback: "openai/gpt-4o"
    max_tokens: 32000
    temperature: 0.1
"""
        )

        secretary = orch.Secretary()
        # 替换为使用临时配置的 ModelRouter
        secretary.model_router = ModelRouter(config_path=str(models_yaml))

        task = secretary.create_task("集成测试任务", ["dev"])
        package = secretary.generate_context_package(task, "dev")

        assert "model_config" in package
        assert package["model_config"]["model"] == "anthropic/claude-sonnet-4"
        assert package["model_config"]["fallback"] == "openai/gpt-4o"
        assert package["model_config"]["max_tokens"] == 32000
        assert package["model_config"]["temperature"] == 0.1

    def test_generate_context_package_with_project_override(self, tmp_path):
        """使用真实 ModelRouter + 项目覆盖验证 context package."""
        # 创建临时 models.yaml
        models_yaml = tmp_path / "models.yaml"
        models_yaml.write_text(
            """
agents:
  dev:
    tier: coding
    default: "anthropic/claude-sonnet-4"
    fallback: "openai/gpt-4o"
    max_tokens: 32000
    temperature: 0.1

projects:
  project-a-hotspot:
    dev:
      model: "openai/gpt-4o"
"""
        )

        secretary = orch.Secretary()
        # 替换为使用临时配置的 ModelRouter
        secretary.model_router = ModelRouter(config_path=str(models_yaml))

        task = secretary.create_task("项目覆盖测试任务", ["dev"], project="project-a-hotspot")
        package = secretary.generate_context_package(task, "dev")

        assert "model_config" in package
        assert package["model_config"]["model"] == "openai/gpt-4o"
        assert package["model_config"]["fallback"] == "openai/gpt-4o"
        assert package["model_config"]["max_tokens"] == 32000
        assert package["model_config"]["temperature"] == 0.1
