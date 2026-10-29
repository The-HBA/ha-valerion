"""Shared test setup.

The protocol library lives inside the integration package, and importing
``custom_components.valerion`` would execute the integration's ``__init__``
which needs Home Assistant. On machines without Home Assistant (Windows
laptops, the library CI job) we register the package by hand so that
``custom_components.valerion.lib`` can be imported on its own. When Home
Assistant is installed the real package is used.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
PACKAGE_DIR = ROOT / "custom_components" / "valerion"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if (
    importlib.util.find_spec("homeassistant") is None
    and "custom_components.valerion" not in sys.modules
):
    import custom_components  # namespace package, no __init__.py

    spec = importlib.machinery.ModuleSpec("custom_components.valerion", None, is_package=True)
    package = importlib.util.module_from_spec(spec)
    package.__path__ = [str(PACKAGE_DIR)]
    sys.modules["custom_components.valerion"] = package
    custom_components.valerion = package  # type: ignore[attr-defined]
