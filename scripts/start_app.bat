# -*- coding: utf-8 -*-
# AstroForge Flutter GUI 启动脚本（Windows，开发期）
rem MF3: banner via star_console (replaces the old slogan echo line)
@echo off
python "%~dp0..\modules\_shared\star_console.py" banner start_app "Flutter GUI dev run" 2>nul
echo Dev run: cd app ^&^& flutter run -d windows
cd /d "%~dp0..\app"
flutter run -d windows
