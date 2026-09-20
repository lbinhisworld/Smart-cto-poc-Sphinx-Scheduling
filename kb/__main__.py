"""`python -m kb` → sealed_kb CLI。卡片目录与推理包分开。"""

from __future__ import annotations

import sys
from pathlib import Path

_packages = Path(__file__).resolve().parents[1] / "packages"
if str(_packages) not in sys.path:
    sys.path.insert(0, str(_packages))

from sealed_kb.__main__ import main

main()
