#!/usr/bin/env bash
# AstroForge anydoc 构建脚本（macOS/Linux，需 Rust 工具链）
# 星幕输出（MF3）：横幅经 star_console；python 缺失时静默跳过（set -e 下必须 || true）
set -e
python3 "$(dirname "$0")/../modules/_shared/star_console.py" banner install_anydoc "build anydoc (Rust)" 2>/dev/null || true
echo "=== AstroForge build anydoc (Rust) ==="
command -v cargo >/dev/null || { echo "[MISS] cargo -> https://rustup.rs"; exit 1; }
mkdir -p "$(dirname "$0")/../modules/anydoc/bin"
cd "$(dirname "$0")/../modules/anydoc"
cargo install --path . --root ./bin_local || echo "[INFO] anydoc 源码包未就绪：将 modules/anydoc 建为 cargo 项目后重试（Phase 4.1）"
echo "Expected binary: modules/anydoc/bin/anydoc"
