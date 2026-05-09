import pytest

from solo.core.dispatcher import CommandDispatcher, PackageDispatcher, build_dispatcher
from solo.core.config import ProjectConfig, SoloConfig
from solo.core.task import SYSTEM, IN_PROGRESS, Task, TaskPhase


def test_build_dispatcher_returns_package_adapter():
    dispatcher = build_dispatcher("package", config=None, agents=None)

    assert isinstance(dispatcher, PackageDispatcher)
    assert dispatcher.name == "package"


def test_build_dispatcher_returns_command_adapter():
    dispatcher = build_dispatcher("command", config=None, agents=None)

    assert isinstance(dispatcher, CommandDispatcher)
    assert dispatcher.name == "command"


def test_build_dispatcher_rejects_unknown_adapter():
    with pytest.raises(ValueError, match="Unknown execution adapter"):
        build_dispatcher("missing", config=None, agents=None)


def test_command_adapter_skips_system_phase_without_command(tmp_path):
    config = SoloConfig(project=ProjectConfig(name="demo"), agents={})
    task = Task(
        id="task-1",
        title="Demo",
        description="Demo task",
        status=IN_PROGRESS,
        workflow="feature",
        current_phase="ceo_gate",
        phases=[],
        artifacts_dir=str(tmp_path),
    )
    phase = TaskPhase(name="ceo_gate", type=SYSTEM)
    dispatcher = CommandDispatcher(config, agents=None)

    package = dispatcher.prepare_phase(task, phase)

    assert package["adapter"] == "command"
    assert package["system"] is True
    assert package["runtime"] == {"skipped": "system phase"}
