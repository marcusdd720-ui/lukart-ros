import pytest

from core.plugin_manager import PluginManager, Plugin


class TestPlugin(Plugin):
    pass


class AnotherPlugin(Plugin):
    pass


def test_register_plugin():
    manager = PluginManager()

    manager.register(TestPlugin)

    assert manager.has("TestPlugin")


def test_get_returns_singleton():
    manager = PluginManager()

    manager.register(TestPlugin)

    p1 = manager.get("TestPlugin")
    p2 = manager.get("TestPlugin")

    assert p1 is p2


def test_create_returns_new_instance():
    manager = PluginManager()

    manager.register(TestPlugin)

    p1 = manager.create("TestPlugin")
    p2 = manager.create("TestPlugin")

    assert p1 is not p2


def test_unregister_plugin():
    manager = PluginManager()

    manager.register(TestPlugin)

    manager.unregister("TestPlugin")

    assert not manager.has("TestPlugin")


def test_plugin_count():
    manager = PluginManager()

    manager.register(TestPlugin)
    manager.register(AnotherPlugin)

    assert manager.plugin_count() == 2


def test_duplicate_registration():
    manager = PluginManager()

    manager.register(TestPlugin)

    with pytest.raises(ValueError):
        manager.register(TestPlugin)


def test_unknown_plugin():
    manager = PluginManager()

    with pytest.raises(ValueError):
        manager.get("UnknownPlugin")


def test_clear():
    manager = PluginManager()

    manager.register(TestPlugin)

    manager.clear()

    assert manager.plugin_count() == 0