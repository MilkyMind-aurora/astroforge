#!/usr/bin/env bash
# AstroForge anydoc 构建脚本（macOS/Linux，需 Rust 工具链）
set -e
echo "=== AstroForge build anydoc (Rust) ==="
command -v cargo >/dev/null || { echo "[MISS] cargo -> https://rustup.rs"; exit 1; }
mkdir -p "$(dirname "$0")/../modules/anydoc/bin"
cd "$(dirname "$0")/../modules/anydoc"
cargo install --path . --root ./bin_local || echo "[INFO] anydoc 源码包未就绪：将 modules/anydoc 建为 cargo 项目后重试（Phase 4.1）"
echo "Expected binary: modules/anydoc/bin/anydoc"
