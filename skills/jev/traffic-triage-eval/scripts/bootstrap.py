"""Make `python3 evaluate.py` work on a machine with nothing but Python.

The script needs one pure-Python package: openpyxl
(.xlsx). Rather than asking the user to install anything, this creates a
private virtual environment under the system temp directory on first run,
installs it with the pip that ships with Python, and
re-executes the script from that environment. Later runs find the venv and
re-exec immediately. If pip or the network is unavailable the caller carries
on without the packages and the rest of the code degrades gracefully.

`uv run evaluate.py` bypasses all of this: uv resolves the inline metadata
itself and the imports succeed on the first try.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REQUIRED = {"openpyxl": "openpyxl>=3.1"}
VENV_DIR = Path(tempfile.gettempdir()) / "traffic-triage-eval" / "venv"
GUARD = "TRAFFIC_TRIAGE_EVAL_BOOTSTRAPPED"


def missing_packages() -> list[str]:
    return [spec for name, spec in REQUIRED.items() if importlib.util.find_spec(name) is None]


def venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def ensure_dependencies(argv: list[str]) -> None:
    """Re-exec under a private venv that has the dependencies, if we can make one."""
    if os.environ.get(GUARD) or not missing_packages():
        return
    python = venv_python()
    if not python.exists() and not _create_venv():
        return  # no venv possible; continue degraded
    if not _install(python):
        return
    os.environ[GUARD] = "1"
    os.execv(str(python), [str(python), *argv])


def _create_venv() -> bool:
    print(f"first run: creating a private environment in {VENV_DIR} ...", file=sys.stderr)
    try:
        VENV_DIR.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)],
                       check=True, capture_output=True)
        return True
    except (subprocess.CalledProcessError, OSError) as err:
        print(f"note: could not create a venv ({err}); continuing without openpyxl",
              file=sys.stderr)
        return False


def _install(python: Path) -> bool:
    check = subprocess.run([str(python), "-c", "import openpyxl"], capture_output=True)
    if check.returncode == 0:
        return True
    print("installing openpyxl into it ...", file=sys.stderr)
    result = subprocess.run(
        [str(python), "-m", "pip", "install", "--quiet", "--disable-pip-version-check",
         *REQUIRED.values()], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"note: pip install failed ({result.stderr.strip()[:200]}); "
              "continuing without openpyxl", file=sys.stderr)
        return False
    return True
