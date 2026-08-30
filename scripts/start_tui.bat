# -*- coding: utf-8 -*-
# AstroForge TUI 启动脚本（Windows）
@echo off
echo AstroForge - Forging Order from Stellar Chaos.
where conda >nul 2>nul
if %errorlevel%==0 (
    conda run -n env_astroforge --no-capture-output python -m tui
) else (
    python -m tui
)
