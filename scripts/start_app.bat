# -*- coding: utf-8 -*-
# AstroForge Flutter GUI 启动脚本（Windows，开发期）
@echo off
echo AstroForge - Forging Order from Stellar Chaos.
echo Dev run: cd app ^&^& flutter run -d windows
cd /d "%~dp0..\app"
flutter run -d windows
