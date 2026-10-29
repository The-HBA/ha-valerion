"""Run the AWOL Link command line tool without Home Assistant installed.

Usage, from the repository root::

    python scripts/awollink.py --host 192.168.1.50 probe
    python scripts/awollink.py --host 192.168.1.50 query POWR
    python scripts/awollink.py --host 192.168.1.50 survey -o survey-pro2.json

The protocol library lives inside the integration package; importing that
package directly would pull in Home Assistant. This runner registers the
package without executing the integration's ``__init__`` and then starts the
library's command line interface.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parent.parent
PACKAGE_DIR = ROOT / "custom_components" / "valerion"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if importlib.util.find_spec("homeassistant") is None:
    import custom_components  # namespace package

    spec = importlib.machinery.ModuleSpec("custom_components.valerion", None, is_package=True)
    package = importlib.util.module_from_spec(spec)
    package.__path__ = [str(PACKAGE_DIR)]
    sys.modules["custom_components.valerion"] = package
    custom_components.valerion = package  # type: ignore[attr-defined]

runpy.run_module("custom_components.valerion.lib.cli", run_name="__main__")
