# -*- coding: utf-8 -*-
# AstroForge anydoc 构建脚本（Windows，需 Rust 工具链）
@echo off
echo === AstroForge build anydoc (Rust) ===
where cargo >nul 2>nul || (echo [MISS] cargo - install from https://rustup.rs & exit /b 1)
if not exist "%~dp0..\modules\anydoc\bin" mkdir "%~dp0..\modules\anydoc\bin"
cd /d "%~dp0..\modules\anydoc"
cargo install --path . --root "%~dp0..\modules\anydoc\bin_local" 2>nul || echo [INFO] anydoc 源码包未就绪：将 modules/anydoc 建为 cargo 项目后重试（Phase 4.1）
echo Expected binary: modules\anydoc\bin\anydoc.exe
