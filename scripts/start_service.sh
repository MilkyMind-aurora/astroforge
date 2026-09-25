#!/usr/bin/env bash
# AstroForge 服务核心启动脚本（macOS/Linux）
# 前台启动；守护模式：nohup bash scripts/start_service.sh > /dev/null 2>&1 &
# 星幕输出（MF3）：横幅经 star_console（替代原标语 echo 行）；python 缺失时静默跳过
python3 "$(dirname "$0")/../modules/_shared/star_console.py" \
    banner start_service "Sidereal Core v0.1.0 starting - Forging Order from Stellar Chaos." 2>/dev/null || true

if command -v conda >/dev/null 2>&1; then
    conda run -n env_astroforge --no-capture-output python -m astroforge serve
else
    python3 -m astroforge serve
fi
