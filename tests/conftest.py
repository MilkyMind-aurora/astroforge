# -*- coding: utf-8 -*-
"""tests 目录公共夹具：把 spider 模块目录加入 sys.path（模块为独立脚本布局）。"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SPIDER_DIR = REPO_ROOT / "modules" / "spider"
for path in (SPIDER_DIR, SPIDER_DIR.parent / "_shared"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
