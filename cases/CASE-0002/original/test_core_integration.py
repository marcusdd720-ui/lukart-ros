from core.configuration import Configuration
from core.container import Container
from core.event_bus import EventBus
from core.plugin_manager import PluginManager
from core.registry import Registry


def test_core_integration():

    container = Container()

    container.register("config", Configuration)
    container.register("registry", Registry)
    container.register("plugins", PluginManager)
    container.register("events", EventBus)

    config = container.resolve("config")
    registry = container.resolve("registry")
    plugins = container.resolve("plugins")
    events = container.resolve("events")

    assert isinstance(config, Configuration)
    assert isinstance(registry, Registry)
    assert isinstance(plugins, PluginManager)
    assert isinstance(events, EventBus)

    registry.register("config", config)

    assert registry.get("config") is config

    config.set("system", "KOS")

    assert config.get("system") == "KOS"
