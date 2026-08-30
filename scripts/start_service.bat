# -*- coding: utf-8 -*-
# AstroForge 服务核心启动脚本（Windows）
# 前台启动 Sidereal Core（127.0.0.1:8420）；守护模式请用 pythonw -m astroforge serve
@echo off
echo AstroForge - Forging Order from Stellar Chaos.
echo Sidereal Core v0.1.0 starting...

where conda >nul 2>nul
if %errorlevel%==0 (
    conda run -n env_astroforge --no-capture-output python -m astroforge serve
) else (
    python -m astroforge serve
)
