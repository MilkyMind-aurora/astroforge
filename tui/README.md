# AstroForge TUI 工作台

终端沉浸式客户端（Textual），对接 Sidereal Core 服务核心。

## 运行

```bash
pip install -e tui
astroforge-tui          # 或 python -m tui
```

前提：服务核心已启动（`scripts/start_service.bat|.sh`）；token 位于 `data/service_token`
（可用环境变量 `ASTROFORGE_SERVICE_TOKEN` / `ASTROFORGE_TOKEN_FILE` 覆盖读取方式）。

## 快捷键

| 键位 | 功能 |
| --- | --- |
| 1-8 | 切换页面（首页/采集/解析/转换/流水线/监控/历史/设置） |
| Ctrl+Shift+A | 星伴 AI 抽屉（Phase 6 接入引擎） |
| Ctrl+` | 底部日志面板（Phase 1.1.4 接入 WS 日志流） |
| q | 退出 |
