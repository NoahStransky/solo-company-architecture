"""Tests for core.model_router."""

import pytest
from unittest.mock import patch, mock_open
from core.model_router import ModelRouter


SAMPLE_CONFIG = """
tiers:
  reasoning:
    description: "Deep reasoning"
    models:
      - "anthropic/claude-opus-4"
      - "openai/gpt-5"
  coding:
    description: "Code implementation"
    models:
      - "anthropic/claude-sonnet-4"
      - "openai/gpt-4o"
  fast:
    description: "Quick tasks"
    models:
      - "anthropic/claude-haiku-4"
      - "openai/gpt-4o-mini"

agents:
  cto:
    tier: reasoning
    default: "anthropic/claude-opus-4"
    fallback: "openai/gpt-5"
    max_tokens: 64000
    temperature: 0.2
  dev:
    tier: coding
    default: "anthropic/claude-sonnet-4"
    fallback: "openai/gpt-4o"
    max_tokens: 32000
    temperature: 0.1
  qa:
    tier: fast
    default: "anthropic/claude-haiku-4"
    fallback: "openai/gpt-4o-mini"
    max_tokens: 16000
    temperature: 0.1

projects:
  project-a-hotspot:
    dev:
      model: "openai/gpt-4o"
"""


class TestModelRouter:
    @pytest.fixture
    def router(self):
        with patch("pathlib.Path.open", mock_open(read_data=SAMPLE_CONFIG)):
            with patch.object(ModelRouter, "_default_config_path", return_value=None):
                return ModelRouter(config_path="/fake/config/models.yaml")

    def test_resolve_basic(self, router):
        result = router.resolve("dev")
        assert result == {
            "model": "anthropic/claude-sonnet-4",
            "fallback": "openai/gpt-4o",
            "max_tokens": 32000,
            "temperature": 0.1,
        }

    def test_resolve_project_override(self, router):
        result = router.resolve("dev", project="project-a-hotspot")
        assert result["model"] == "openai/gpt-4o"
        assert result["fallback"] == "openai/gpt-4o"
        assert result["max_tokens"] == 32000
        assert result["temperature"] == 0.1

    def test_resolve_project_no_override(self, router):
        result = router.resolve("cto", project="project-a-hotspot")
        assert result["model"] == "anthropic/claude-opus-4"
        assert result["fallback"] == "openai/gpt-5"

    def test_resolve_unknown_agent(self, router):
        with pytest.raises(KeyError):
            router.resolve("unknown-agent")

    def test_resolve_unknown_project(self, router):
        # Unknown project should fall back to defaults
        result = router.resolve("dev", project="nonexistent")
        assert result["model"] == "anthropic/claude-sonnet-4"

    def test_list_models_by_tier(self, router):
        models = router.list_models(tier="coding")
        assert models == ["anthropic/claude-sonnet-4", "openai/gpt-4o"]

    def test_list_models_all(self, router):
        models = router.list_models()
        assert "reasoning" in models
        assert "coding" in models
        assert "fast" in models
        assert models["reasoning"] == ["anthropic/claude-opus-4", "openai/gpt-5"]
        assert models["coding"] == ["anthropic/claude-sonnet-4", "openai/gpt-4o"]
        assert models["fast"] == ["anthropic/claude-haiku-4", "openai/gpt-4o-mini"]

    def test_list_models_unknown_tier(self, router):
        with pytest.raises(KeyError):
            router.list_models(tier="unknown")
