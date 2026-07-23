from core.bootstrap import bootstrap
from core.plugin_manager import PluginManager


def test_bootstrap_returns_plugin_manager():
    manager = bootstrap()

    assert isinstance(manager, PluginManager)