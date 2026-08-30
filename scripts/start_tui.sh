#!/usr/bin/env bash
# AstroForge TUI 启动脚本（macOS/Linux）
echo "AstroForge — Forging Order from Stellar Chaos."
if command -v conda >/dev/null 2>&1; then
    conda run -n env_astroforge --no-capture-output python -m tui
else
    python3 -m tui
fi
