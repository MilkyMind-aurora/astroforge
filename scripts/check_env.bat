# -*- coding: utf-8 -*-
# AstroForge 环境体检脚本（Windows）
@echo off
echo === AstroForge env check (Windows) ===
python --version
where conda || echo [MISS] conda
where psql   || echo [MISS] psql (PostgreSQL)
if defined ASTROFORGE_PG_PASSWORD (echo [OK] ASTROFORGE_PG_PASSWORD set) else (echo [MISS] ASTROFORGE_PG_PASSWORD not set)
if exist "%~dp0..\data\service_token" (echo [OK] service token exists) else (echo [INFO] token will be created on first service start)
echo Done. Fix items above, then run scripts\start_service.bat
