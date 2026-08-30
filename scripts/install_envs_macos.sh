#!/usr/bin/env bash
# AstroForge macOS conda/venv 环境补全脚本（Phase 10）
set -e
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
