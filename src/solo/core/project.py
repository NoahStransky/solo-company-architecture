"""Project discovery and initialization."""

from importlib import resources
from pathlib import Path
from typing import Optional

from .agent_registry import AgentRegistry
from .config import SoloConfig, load_config
from .state import StateStore
from .workflow import WorkflowRegistry


class SoloProject:
    """A project initialized with a .solo directory."""

    def __init__(self, path: Path):
        self.path = path.resolve()
        self.solo_dir = self.path / ".solo"
        self.config_path = self.solo_dir / "config.yaml"
        self.config: Optional[SoloConfig] = None
        self.state = StateStore(self.solo_dir)
        self.agents = AgentRegistry(self.solo_dir / "agents")
        self.workflows = WorkflowRegistry(self.solo_dir / "workflows")

    @classmethod
    def find(cls, path: Path) -> Optional["SoloProject"]:
        current = path.resolve()
        if current.is_file():
            current = current.parent
        for candidate in [current] + list(current.parents):
            if (candidate / ".solo" / "config.yaml").exists():
                return cls(candidate).load()
        return None

    @classmethod
    def init(cls, path: Path, template: str = "default", yes: bool = False) -> "SoloProject":
        project = cls(path)
        if project.solo_dir.exists():
            raise FileExistsError(f"{project.solo_dir} already exists")

        template_root = resources.files("solo.templates").joinpath(template)
        if not template_root.is_dir():
            raise FileNotFoundError(f"Unknown template: {template}")

        _copy_resource_tree(template_root, project.solo_dir)
        soloignore = project.solo_dir / ".soloignore"
        if soloignore.exists():
            target = project.path / ".soloignore"
            if target.exists():
                soloignore.unlink()
            else:
                soloignore.replace(target)

        (project.solo_dir / "state" / "sessions").mkdir(parents=True, exist_ok=True)
        (project.solo_dir / "artifacts").mkdir(parents=True, exist_ok=True)
        (project.solo_dir / "contracts").mkdir(parents=True, exist_ok=True)
        project.state.init()
        return project.load()

    def load(self) -> "SoloProject":
        if not self.config_path.exists():
            raise FileNotFoundError(f"Missing {self.config_path}")
        self.config = load_config(self.config_path)
        return self

    def require_config(self) -> SoloConfig:
        if self.config is None:
            self.load()
        assert self.config is not None
        return self.config

    def artifacts_dir_for(self, task_id: str) -> Path:
        return self.solo_dir / "artifacts" / task_id


def _copy_resource_tree(source, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        target = destination / item.name
        if item.is_dir():
            _copy_resource_tree(item, target)
        else:
            target.write_bytes(item.read_bytes())
