"""Double-click launcher: re-runs with the .venv interpreter when started by the system one."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_PYW = ROOT / ".venv" / "Scripts" / "pythonw.exe"

if VENV_PYW.exists() and Path(sys.executable).resolve() != VENV_PYW.resolve():
    subprocess.Popen([str(VENV_PYW), "-m", "ytddlg"], cwd=ROOT)
    sys.exit(0)

os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
from ytddlg.__main__ import run  # noqa: E402

run()
