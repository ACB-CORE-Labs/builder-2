from __future__ import annotations

"""builder-II — Generic governed platform for local agent-assisted development."""

__version__ = "0.1.0"

import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Sequence

from builder_ii.core._module_aliases import MODULE_ALIASES

_PKG_DIR = Path(__file__).resolve().parent


class DummyLoader(importlib.abc.Loader):
    def create_module(self, spec: importlib.machinery.ModuleSpec) -> ModuleType | None:
        module = sys.modules.get(spec.name)
        return module if isinstance(module, ModuleType) else None

    def exec_module(self, module: ModuleType) -> None:
        return None


class CLIRedirectFinder(importlib.abc.MetaPathFinder):
    """Historical flat CLI module paths → builder_ii.cli.*"""

    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None = None,
        target: ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        if (
            fullname.startswith("builder_ii.")
            and fullname.endswith("_cli")
            and not fullname.startswith("builder_ii.cli.")
        ):
            parts = fullname.split(".")
            cli_name = parts[-1]
            redirected_name = f"builder_ii.cli.{cli_name}"
            try:
                module = importlib.import_module(redirected_name)
            except ModuleNotFoundError:
                return None
            sys.modules[fullname] = module
            parent_name = ".".join(parts[:-1])
            parent_module = sys.modules.get(parent_name)
            if parent_module is not None:
                setattr(parent_module, parts[-1], module)
            return importlib.machinery.ModuleSpec(name=fullname, loader=DummyLoader())
        return None


class AliasModuleLoader(importlib.abc.SourceLoader):
    """Shared module object under an historical short name; supports python -m."""

    def __init__(self, target_name: str, origin: str) -> None:
        self.target_name = target_name
        self._origin = origin

    def get_filename(self, fullname: str) -> str:  # noqa: ARG002
        return self._origin

    def get_data(self, path: str) -> bytes:
        with open(path, "rb") as handle:
            return handle.read()

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> ModuleType | None:
        existing = sys.modules.get(self.target_name)
        if existing is not None:
            sys.modules[spec.name] = existing
            parent = sys.modules.get("builder_ii")
            if parent is not None:
                setattr(parent, spec.name.rsplit(".", 1)[-1], existing)
            return existing
        return None

    def exec_module(self, module: ModuleType) -> None:
        if module is sys.modules.get(self.target_name):
            return
        super().exec_module(module)
        sys.modules.setdefault(self.target_name, module)


class DDDModuleRedirectFinder(importlib.abc.MetaPathFinder):
    """Historical flat builder_ii.<mod> imports → DDD package locations."""

    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None = None,
        target: ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        if not fullname.startswith("builder_ii."):
            return None
        parts = fullname.split(".")
        if len(parts) != 2:
            return None
        short = parts[1]
        if (_PKG_DIR / short).is_dir():
            return None  # never shadow real packages
        target_name = MODULE_ALIASES.get(short)
        if target_name is None or target_name == fullname:
            return None
        try:
            target_spec = importlib.util.find_spec(target_name)
        except (ModuleNotFoundError, ValueError):
            return None
        if target_spec is None or not target_spec.origin:
            return None
        loader = AliasModuleLoader(target_name, target_spec.origin)
        is_pkg = target_spec.submodule_search_locations is not None
        spec = importlib.machinery.ModuleSpec(
            name=fullname,
            loader=loader,
            origin=target_spec.origin,
            is_package=is_pkg,
        )
        spec.has_location = True
        if is_pkg and target_spec.submodule_search_locations is not None:
            spec.submodule_search_locations = list(target_spec.submodule_search_locations)
        return spec


if not any(type(f).__name__ == "CLIRedirectFinder" for f in sys.meta_path):
    sys.meta_path.insert(0, CLIRedirectFinder())
if not any(type(f).__name__ == "DDDModuleRedirectFinder" for f in sys.meta_path):
    sys.meta_path.insert(0, DDDModuleRedirectFinder())


def __getattr__(name: str):
    if (_PKG_DIR / name).is_dir():
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    target = MODULE_ALIASES.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    mod = importlib.import_module(target)
    globals()[name] = mod
    return mod


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(MODULE_ALIASES))
