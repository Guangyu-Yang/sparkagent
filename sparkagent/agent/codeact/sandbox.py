"""Soft sandbox: restricted builtins and import filtering for CodeAct exec()."""

from __future__ import annotations

import builtins
import importlib
from typing import Any

# Modules the LLM is allowed to import
IMPORT_ALLOWLIST: frozenset[str] = frozenset({
    "json", "re", "math", "datetime", "collections", "itertools",
    "functools", "pathlib", "base64", "csv", "io", "textwrap",
    "urllib.parse", "hashlib", "string", "operator",
})

# Modules explicitly blocked (dangerous I/O, process, network primitives)
IMPORT_BLOCKLIST: frozenset[str] = frozenset({
    "os", "sys", "subprocess", "shutil", "socket", "http", "ctypes",
    "multiprocessing", "threading", "signal", "pickle", "importlib",
})

# Builtins blocked inside exec()
_BLOCKED_BUILTINS: frozenset[str] = frozenset({
    "exec", "eval", "compile", "open", "globals", "locals",
    "__import__", "breakpoint", "exit", "quit",
})

# Builtins explicitly allowed
_ALLOWED_BUILTINS: tuple[str, ...] = (
    "print", "len", "range", "int", "float", "str", "bool",
    "list", "dict", "tuple", "set", "frozenset",
    "enumerate", "zip", "sorted", "reversed", "map", "filter",
    "isinstance", "issubclass", "type", "callable", "hasattr", "getattr",
    "abs", "min", "max", "sum", "round", "pow", "divmod",
    "any", "all", "repr", "format", "chr", "ord",
    "hex", "oct", "bin",
    "ValueError", "TypeError", "KeyError", "IndexError",
    "RuntimeError", "StopIteration", "AttributeError",
    "Exception", "True", "False", "None",
)


def _guarded_import(
    name: str,
    globals: dict | None = None,
    locals: dict | None = None,
    fromlist: tuple = (),
    level: int = 0,
) -> Any:
    """Import hook that enforces the allow/blocklist."""
    top_level = name.split(".")[0]

    if top_level in IMPORT_BLOCKLIST:
        raise ImportError(f"Importing '{name}' is not allowed in CodeAct mode")

    if name not in IMPORT_ALLOWLIST and top_level not in IMPORT_ALLOWLIST:
        raise ImportError(
            f"Importing '{name}' is not allowed. "
            f"Allowed modules: {', '.join(sorted(IMPORT_ALLOWLIST))}"
        )

    return importlib.import_module(name)


def build_safe_builtins() -> dict[str, Any]:
    """Return a dict of safe builtins for use in exec() globals."""
    safe: dict[str, Any] = {}

    for name in _ALLOWED_BUILTINS:
        obj = getattr(builtins, name, None)
        if obj is not None:
            safe[name] = obj

    safe["__import__"] = _guarded_import
    return safe
