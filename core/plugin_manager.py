from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Type
import importlib
import logging
import pkgutil


@dataclass
class PluginInfo:
    name: str
    version: str = "1.0"
    author: str = ""
    description: str = ""
    class_ref: Optional[Type] = None


class Plugin:
    """Bazowa klasa wszystkich pluginów."""
    __plugin__ = True


class PluginManager:
    def __init__(self):
        self._plugins: Dict[str, PluginInfo] = {}
        self._instances: Dict[str, Any] = {}
        self._logger = logging.getLogger(__name__)

    def register(
        self,
        plugin_class: Type,
        name: Optional[str] = None,
        info: Optional[dict] = None,
    ):
        """Rejestruje plugin."""

        if not issubclass(plugin_class, Plugin):
            raise TypeError(
                f"{plugin_class.__name__} must inherit from Plugin"
            )

        plugin_name = name or plugin_class.__name__

        if plugin_name in self._plugins:
            raise ValueError(
                f"Plugin '{plugin_name}' already registered"
            )

        info = info or {}

        self._plugins[plugin_name] = PluginInfo(
            name=plugin_name,
            version=info.get("version", "1.0"),
            author=info.get("author", ""),
            description=info.get("description", ""),
            class_ref=plugin_class,
        )

        self._logger.info("Plugin registered: %s", plugin_name)
        return self

    def unregister(self, name: str):
        if name in self._plugins:
            del self._plugins[name]
            self._instances.pop(name, None)
            self._logger.info("Plugin removed: %s", name)

    def has(self, name: str) -> bool:
        return name in self._plugins

    def get(self, name: str):
        """Zwraca singleton pluginu."""

        if name not in self._plugins:
            raise ValueError(f"Plugin '{name}' not registered")

        if name not in self._instances:
            self._instances[name] = self._plugins[name].class_ref()

        return self._instances[name]

    def create(self, name: str):
        """Tworzy nową instancję pluginu."""

        if name not in self._plugins:
            raise ValueError(f"Plugin '{name}' not registered")

        return self._plugins[name].class_ref()

    def clear_instances(self):
        """Czyści cache singletonów."""
        self._instances.clear()

    def clear(self):
        """Czyści cały PluginManager."""
        self._instances.clear()
        self._plugins.clear()

    def plugin_count(self) -> int:
        return len(self._plugins)

    def list_plugins(self) -> List[str]:
        return sorted(self._plugins.keys())

    def get_info(self, name: str) -> PluginInfo:
        if name not in self._plugins:
            raise ValueError(f"Plugin '{name}' not registered")
        return self._plugins[name]

    def discover(self, package_name: str):

        package = importlib.import_module(package_name)

        if not hasattr(package, "__path__"):
            raise ValueError(
                f"'{package_name}' is not a package"
            )

        for _, module_name, _ in pkgutil.iter_modules(package.__path__):
            try:
                module = importlib.import_module(
                    f"{package_name}.{module_name}"
                )

                for attribute_name in dir(module):
                    obj = getattr(module, attribute_name)

                    if (
                        isinstance(obj, type)
                        and issubclass(obj, Plugin)
                        and obj is not Plugin
                    ):
                        self.register(
                            obj,
                            f"{module_name}.{attribute_name}",
                        )

            except Exception as exc:
                self._logger.warning(
                    "Cannot load plugin %s: %s",
                    module_name,
                    exc,
                )