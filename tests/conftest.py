# -*- coding: utf-8 -*-
"""tests 目录公共夹具：把功能模块目录加入 sys.path（模块为独立脚本布局）。"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULES = REPO_ROOT / "modules"
for name in ("spider", "wpd"):
    path = MODULES / name
    if path.exists() and str(path) not in sys.path:
        sys.path.insert(0, str(path))
shared = MODULES / "_shared"
if str(shared) not in sys.path:
    sys.path.insert(0, str(shared))
