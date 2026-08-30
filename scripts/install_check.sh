#!/usr/bin/env bash
# AstroForge macOS 一键体检（开源用户自装依赖清单，Phase 10.2.4）
echo "=== AstroForge macOS install check ==="

command -v brew >/dev/null && echo "[OK] Homebrew" || echo "[MISS] Homebrew -> https://brew.sh"
command -v conda >/dev/null && echo "[OK] Miniforge/Miniconda" || echo "[MISS] conda -> brew install miniforge"
command -v psql  >/dev/null && echo "[OK] PostgreSQL CLI" || echo "[MISS] postgresql@16 -> brew install postgresql@16 && brew services start postgresql@16"
command -v cargo >/dev/null && echo "[OK] Rust (anydoc build)" || echo "[MISS] Rust -> https://rustup.rs"
command -v flutter >/dev/null && echo "[OK] Flutter" || echo "[MISS] Flutter (optional, GUI client)"

MAC_DATA="$HOME/Library/Application Support/AstroForge"
[ -d "$MAC_DATA/models" ] && echo "[OK] models dir ($MAC_DATA/models)" || echo "[MISS] models dir -> mkdir -p '$MAC_DATA/models' 并按 README 下载 GGUF"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
[ -x "$CHROME" ] && echo "[OK] Chrome (spider)" || echo "[MISS] Chrome -> 配置 browser.chromium_path 指向你的 Chromium"

echo ""
echo "缺失项按上方指引自行安装后重跑本脚本；全部 [OK] 后执行 scripts/install_envs_macos.sh"
