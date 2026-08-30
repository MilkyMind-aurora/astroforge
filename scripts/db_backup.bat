# -*- coding: utf-8 -*-
# AstroForge 数据库每日备份脚本（Windows 任务计划）
@echo off
rem 用法：计划任务每日执行；密码走环境变量，不落明文
if not defined ASTROFORGE_PG_PASSWORD (
    echo [MISS] ASTROFORGE_PG_PASSWORD not set & exit /b 1
)
if not exist "%~dp0..\data\backups" mkdir "%~dp0..\data\backups"
set TODAY=%date:~0,4%%date:~5,2%%date:~8,2%
set PGPASSWORD=%ASTROFORGE_PG_PASSWORD%
pg_dump -Fc -U astroforge -T monitor_metrics -f "%~dp0..\data\backups\astroforge_%TODAY%.dump" astroforge
rem 轮转：删除 7 天前的备份
forfiles /p "%~dp0..\data\backups" /m astroforge_*.dump /d -7 /c "cmd /c del @path" 2>nul
echo [OK] backup done: astroforge_%TODAY%.dump
