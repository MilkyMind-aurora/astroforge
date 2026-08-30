"""表格批量爬取：参数校验后诚实降级（结构化表格 + XHR 捕获属 Phase 2）。"""
from __future__ import annotations


def run_table_crawl(cfg: dict) -> dict:
    return {
        "code": 3006,
        "message": "表格爬取属 Phase 2 开发中（spider_table：Scrapling 选择器 + capture_xhr）",
        "data": {"url": cfg.get("url"), "selector": cfg.get("selector")},
    }
