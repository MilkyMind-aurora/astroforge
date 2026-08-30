#!/usr/bin/env bash
# AstroForge 服务核心启动脚本（macOS/Linux）
# 前台启动；守护模式：nohup bash scripts/start_service.sh > /dev/null 2>&1 &

echo "AstroForge — Forging Order from Stellar Chaos."
echo "Sidereal Core v0.1.0 starting..."

if command -v conda >/dev/null 2>&1; then
    conda run -n env_astroforge --no-capture-output python -m astroforge serve
else
    python3 -m astroforge serve
fi
