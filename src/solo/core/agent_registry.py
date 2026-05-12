"""Agent prompt registry."""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


@dataclass
class AgentDefinition:
    role: str
    prompt_path: Path
    prompt: str


class AgentRegistry:
    def __init__(self, agents_dir: Path):
        self.agents_dir = agents_dir

    def load(self, role: str) -> AgentDefinition:
        path = self.agents_dir / f"{role}.md"
        if not path.exists():
            raise FileNotFoundError(f"Agent prompt not found: {role}")
        return AgentDefinition(role=role, prompt_path=path, prompt=path.read_text(encoding="utf-8"))

    def list_roles(self) -> List[str]:
        if not self.agents_dir.exists():
            return []
        return sorted(path.stem for path in self.agents_dir.glob("*.md"))

    def load_all(self) -> Dict[str, AgentDefinition]:
        return {role: self.load(role) for role in self.list_roles()}
