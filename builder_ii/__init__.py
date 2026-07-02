from __future__ import annotations

"""builder-II — Generic governed platform for local agent-assisted development."""

__version__ = "0.1.0"

import importlib
import importlib.abc
import importlib.machinery
import sys
from types import ModuleType
from typing import Sequence


class DummyLoader(importlib.abc.Loader):
    def create_module(self, spec: importlib.machinery.ModuleSpec) -> ModuleType | None:
        module = sys.modules.get(spec.name)
        return module if isinstance(module, ModuleType) else None

    def exec_module(self, module: ModuleType) -> None:
        return None


class CLIRedirectFinder(importlib.abc.MetaPathFinder):
    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None = None,
        target: ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        if fullname.startswith("builder_ii.") and fullname.endswith("_cli") and not fullname.startswith("builder_ii.cli."):
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


sys.meta_path.insert(0, CLIRedirectFinder())
