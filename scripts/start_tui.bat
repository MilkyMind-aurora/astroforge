# -*- coding: utf-8 -*-
# AstroForge TUI 启动脚本（Windows）
rem MF3: banner via star_console (replaces the old slogan echo line)
@echo off
python "%~dp0..\modules\_shared\star_console.py" banner start_tui "TUI - Forging Order from Stellar Chaos." 2>nul
where conda >nul 2>nul
if %errorlevel%==0 (
    conda run -n env_astroforge --no-capture-output python -m tui
) else (
    python -m tui
)
