#!/usr/bin/env bash
# AstroForge macOS conda/venv 环境补全脚本（Phase 10）
# 星幕输出（MF3）：横幅经 star_console；python 缺失时静默跳过（set -e 下必须 || true）
set -e
python3 "$(dirname "$0")/../modules/_shared/star_console.py" banner install_envs_macos "conda/venv envs setup" 2>/dev/null || true
echo "=== AstroForge install envs (macOS) ==="

if command -v conda >/dev/null 2>&1; then
    conda env list | grep -q env_astroforge || conda create -n env_astroforge python=3.12 -y
    conda run -n env_astroforge pip install -e server
    conda run -n env_astroforge pip install -e tui
else
    echo "[INFO] conda not found, fallback to venv (.venv)"
    python3 -m venv .venv
    ./.venv/bin/pip install -e server
    ./.venv/bin/pip install -e tui
fi

echo ""
echo "[NEXT] 1) bash scripts/install_check.sh  (deps checklist)"
echo "       2) Download GGUF models into ~/Library/Application Support/AstroForge/models/"
