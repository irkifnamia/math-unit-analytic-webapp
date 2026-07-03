from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PACKAGE_DIR = ROOT / ".python_packages"

if PACKAGE_DIR.exists():
    sys.path.insert(0, str(PACKAGE_DIR))
sys.path.insert(0, str(ROOT))

from streamlit.web import cli as streamlit_cli  # noqa: E402


if __name__ == "__main__":
    sys.argv = [
        "streamlit",
        "run",
        str(ROOT / "app.py"),
        "--global.developmentMode=false",
        *sys.argv[1:],
    ]
    streamlit_cli.main()
