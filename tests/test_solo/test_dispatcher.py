import pytest

from solo.core.dispatcher import PackageDispatcher, build_dispatcher


def test_build_dispatcher_returns_package_adapter():
    dispatcher = build_dispatcher("package", config=None, agents=None)

    assert isinstance(dispatcher, PackageDispatcher)
    assert dispatcher.name == "package"


def test_build_dispatcher_rejects_unknown_adapter():
    with pytest.raises(ValueError, match="Unknown execution adapter"):
        build_dispatcher("missing", config=None, agents=None)
