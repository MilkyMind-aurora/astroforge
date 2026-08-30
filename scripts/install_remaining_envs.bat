# -*- coding: utf-8 -*-
# AstroForge Windows conda 环境补全脚本（Phase 0 Task 0.1.x）
@echo off
echo === AstroForge install remaining envs (Windows) ===

conda env list | findstr env_astroforge >nul
if %errorlevel%==0 (
    echo [SKIP] env_astroforge exists
) else (
    conda create -n env_astroforge python=3.12 -y
)

conda run -n env_astroforge pip install -e "%~dp0..\server"
conda run -n env_astroforge pip install -e "%~dp0..\tui"
echo.
echo [NEXT] 1) Download GGUF models into models\ (see scripts\download_models.bat)
echo        2) Init database via scripts\db_init.sql
echo        3) scripts\start_service.bat
