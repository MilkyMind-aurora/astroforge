#!/usr/bin/env bash
# AstroForge 环境体检脚本（macOS/Linux）
# 星幕输出（MF3）：横幅经 star_console；python 缺失时静默跳过，不影响体检本体
python3 "$(dirname "$0")/../modules/_shared/star_console.py" banner check_env "环境体检" 2>/dev/null || true
echo "=== AstroForge env check ==="
python3 --version
command -v conda >/dev/null && echo "[OK] conda" || echo "[MISS] conda"
command -v psql  >/dev/null && echo "[OK] psql"  || echo "[MISS] psql (PostgreSQL)"
[ -n "$ASTROFORGE_PG_PASSWORD" ] && echo "[OK] ASTROFORGE_PG_PASSWORD set" || echo "[MISS] ASTROFORGE_PG_PASSWORD not set"
[ -f "$(dirname "$0")/../data/service_token" ] && echo "[OK] service token exists" || echo "[INFO] token will be created on first service start"
echo "Done."
