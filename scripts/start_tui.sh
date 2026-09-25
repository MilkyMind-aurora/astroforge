#!/usr/bin/env bash
# AstroForge TUI 启动脚本（macOS/Linux）
# 星幕输出（MF3）：横幅经 star_console（替代原标语 echo 行）；python 缺失时静默跳过
python3 "$(dirname "$0")/../modules/_shared/star_console.py" \
    banner start_tui "TUI - Forging Order from Stellar Chaos." 2>/dev/null || true

if command -v conda >/dev/null 2>&1; then
    conda run -n env_astroforge --no-capture-output python -m tui
else
    python3 -m tui
fi
