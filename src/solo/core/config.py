"""Config loading for .solo/config.yaml."""

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List

import yaml


SOLO_PROTOCOL_VERSION = 1


@dataclass
class AgentConfig:
    provider: str
    model: str
    temperature: float = 0.3
    max_tokens: int = 32000
    skills: List[str] = field(default_factory=list)
    mcp_servers: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentConfig":
        return cls(
            provider=str(data.get("provider", "")),
            model=str(data.get("model", "")),
            temperature=float(data.get("temperature", 0.3)),
            max_tokens=int(data.get("max_tokens", 32000)),
            skills=list(data.get("skills", [])),
            mcp_servers=list(data.get("mcp_servers", [])),
            tools=list(data.get("tools", [])),
        )


@dataclass
class ProviderConfig:
    type: str
    api_key_env: str = ""
    base_url: str = ""
    organization_env: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProviderConfig":
        known = {"type", "api_key_env", "base_url", "organization_env"}
        return cls(
            type=str(data.get("type", "")),
            api_key_env=str(data.get("api_key_env", "")),
            base_url=str(data.get("base_url", "")),
            organization_env=str(data.get("organization_env", "")),
            extra={key: value for key, value in data.items() if key not in known},
        )

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "type": self.type,
            "api_key_env": self.api_key_env,
            "base_url": self.base_url,
            "organization_env": self.organization_env,
        }
        data.update(self.extra)
        return {key: value for key, value in data.items() if value not in ("", None, {}, [])}


@dataclass
class MCPServerConfig:
    command: str
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    description: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPServerConfig":
        return cls(
            command=str(data.get("command", "")),
            args=[str(item) for item in data.get("args", [])],
            env={str(key): str(value) for key, value in (data.get("env") or {}).items()},
            enabled=bool(data.get("enabled", True)),
            description=str(data.get("description", "")),
        )


@dataclass
class SkillConfig:
    description: str
    path: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkillConfig":
        return cls(
            description=str(data.get("description", "")),
            path=str(data.get("path", "")),
        )


@dataclass
class ProjectConfig:
    name: str
    description: str = ""
    version: str = "0.1.0"
    repo: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectConfig":
        return cls(
            name=str(data.get("name", "")),
            description=str(data.get("description", "")),
            version=str(data.get("version", "0.1.0")),
            repo=str(data.get("repo", "")),
        )


@dataclass
class DelegationConfig:
    max_parallel: int = 3
    timeout: int = 300
    max_retries: int = 3
    max_parallel_dev_agents: int = 3

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DelegationConfig":
        return cls(
            max_parallel=int(data.get("max_parallel", 3)),
            timeout=int(data.get("timeout", 300)),
            max_retries=int(data.get("max_retries", 3)),
            max_parallel_dev_agents=int(data.get("max_parallel_dev_agents", data.get("max_parallel", 3))),
        )


@dataclass
class SoloConfig:
    project: ProjectConfig
    agents: Dict[str, AgentConfig]
    providers: Dict[str, ProviderConfig] = field(default_factory=dict)
    mcp_servers: Dict[str, MCPServerConfig] = field(default_factory=dict)
    skills: Dict[str, SkillConfig] = field(default_factory=dict)
    delegation: DelegationConfig = field(default_factory=DelegationConfig)
    default_workflow: str = "feature"
    solo_protocol_version: int = SOLO_PROTOCOL_VERSION

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SoloConfig":
        version = int(data.get("solo_protocol_version", SOLO_PROTOCOL_VERSION))
        if version != SOLO_PROTOCOL_VERSION:
            raise ValueError(f"Unsupported solo_protocol_version: {version}")
        agents = {
            name: AgentConfig.from_dict(value)
            for name, value in (data.get("agents") or {}).items()
        }
        return cls(
            project=ProjectConfig.from_dict(data.get("project") or {}),
            agents=agents,
            providers={
                name: ProviderConfig.from_dict(value)
                for name, value in (data.get("providers") or {}).items()
            },
            mcp_servers={
                name: MCPServerConfig.from_dict(value)
                for name, value in (data.get("mcp_servers") or {}).items()
            },
            skills={
                name: SkillConfig.from_dict(value)
                for name, value in (data.get("skills") or {}).items()
            },
            delegation=DelegationConfig.from_dict(data.get("delegation") or {}),
            default_workflow=str(data.get("default_workflow", "feature")),
            solo_protocol_version=version,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "solo_protocol_version": self.solo_protocol_version,
            "project": asdict(self.project),
            "providers": {name: config.to_dict() for name, config in self.providers.items()},
            "mcp_servers": {name: asdict(config) for name, config in self.mcp_servers.items()},
            "skills": {name: asdict(config) for name, config in self.skills.items()},
            "agents": {name: asdict(config) for name, config in self.agents.items()},
            "delegation": asdict(self.delegation),
            "default_workflow": self.default_workflow,
        }

    def get_agent(self, role: str) -> AgentConfig:
        if role not in self.agents:
            raise KeyError(f"Unknown agent role: {role}")
        return self.agents[role]

    def get_provider_for_agent(self, role: str) -> ProviderConfig:
        agent = self.get_agent(role)
        if agent.provider not in self.providers:
            raise KeyError(f"Unknown provider for agent {role}: {agent.provider}")
        return self.providers[agent.provider]

    def get_mcp_for_agent(self, role: str) -> Dict[str, MCPServerConfig]:
        agent = self.get_agent(role)
        return {
            name: self.mcp_servers[name]
            for name in agent.mcp_servers
            if name in self.mcp_servers and self.mcp_servers[name].enabled
        }

    def get_skills_for_agent(self, role: str) -> Dict[str, SkillConfig]:
        agent = self.get_agent(role)
        return {
            name: self.skills[name]
            for name in agent.skills
            if name in self.skills
        }


def load_config(path: Path) -> SoloConfig:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return SoloConfig.from_dict(data)


def save_config(config: SoloConfig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(config.to_dict(), handle, sort_keys=False, allow_unicode=False)
