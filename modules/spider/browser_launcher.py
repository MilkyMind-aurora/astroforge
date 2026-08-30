# -*- coding: utf-8 -*-
"""Scrapling 浏览器启动器（Phase 2 Task 2.1.1）。

scrapling 0.4.x API：渲染会话参数（executable_path/headless/沙箱旗标等）
属于 fetch() 的 PlaywrightSession kwargs，而非构造函数；本模块统一封装，
从任务配置读取浏览器参数并执行渲染抓取。
平台差异：--no-sandbox 在 Windows 强制开启（方案附录补丁 2）。
"""
from __future__ import annotations

import platform
from typing import Any


def build_session_kwargs(cfg: dict[str, Any]) -> dict[str, Any]:
    """从任务配置提取 DynamicFetcher.fetch() 会话参数。"""
    is_windows = platform.system() == "Windows"
    no_sandbox = bool(cfg.get("no_sandbox", True)) if is_windows else bool(cfg.get("no_sandbox", False))
    kwargs: dict[str, Any] = {
        "headless": bool(cfg.get("headless", True)),
    }
    chromium = cfg.get("chromium_path")
    if chromium:
        kwargs["executable_path"] = chromium
    if no_sandbox:
        kwargs["extra_flags"] = ["--no-sandbox", "--disable-setuid-sandbox"]
    return kwargs


def render_fetch(url: str, cfg: dict[str, Any]) -> str:
    """用本地 Chromium（DynamicFetcher）渲染抓取，返回 HTML；未安装抛 RuntimeError。"""
    try:
        from scrapling import DynamicFetcher  # type: ignore
    except ImportError as exc:
        raise RuntimeError("scrapling 未安装（env_spider: pip install scrapling[all]）") from exc
    session_kwargs = build_session_kwargs(cfg)
    response = DynamicFetcher().fetch(url, **session_kwargs)
    return response.html_content


def make_fetcher(cfg: dict[str, Any]):
    """纯 HTTP 场景的 Fetcher（无渲染需求时使用）。"""
    try:
        from scrapling import Fetcher  # type: ignore
    except ImportError as exc:
        raise RuntimeError("scrapling 未安装（env_spider: pip install scrapling[all]）") from exc
    return Fetcher(headless=bool(cfg.get("headless", True)))
