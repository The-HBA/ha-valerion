"""The protocol library must not depend on Home Assistant.

This keeps the door open to publishing ``lib`` as a stand-alone package and
to a future Home Assistant core submission, which requires a separate
library.
"""

from __future__ import annotations

import ast
from pathlib import Path

LIB_DIR = Path(__file__).resolve().parent.parent / "custom_components" / "valerion" / "lib"
FORBIDDEN_PREFIXES = ("homeassistant", "custom_components", "probatio", "voluptuous")


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module)
    return names


def test_lib_has_no_home_assistant_imports() -> None:
    offenders: dict[str, set[str]] = {}
    for path in LIB_DIR.glob("*.py"):
        bad = {name for name in _imports(path) if name.startswith(FORBIDDEN_PREFIXES)}
        if bad:
            offenders[path.name] = bad
    assert not offenders, f"lib imports forbidden packages: {offenders}"


def test_lib_ships_py_typed() -> None:
    assert (LIB_DIR / "py.typed").exists()
