"""AI 指令三层降级解析器（方案 3.7 / 附录补丁 1，强制机制）。

第一层：剥离 ```json 代码块；第二层：清洗后直接 json.loads；
第三层：正则关键词兜底。兜底触发必须回显提示（fallback_notice）。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from astroforge.core.config_loader import AiSettings

CODEBLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)
THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)  # Qwen3 系推理块，解析前剥离
VALID_ACTIONS = {"spider", "parse", "convert", "pipeline"}
VALID_TASK_TYPES = {
    "spider_single", "spider_site", "spider_pdf", "spider_table",
    "mineru", "wpd", "anydoc", "md2docx", "pipeline",
}
KEYWORD_TASK_TYPES = {
    "academic": "academic", "论文": "academic",
    "技术文档": "tech_doc", "数模": "math_model", "报告": "formal_report",
}
URL_RE = re.compile(r"https?://[^\s\"'<>]+")
PATH_RE = re.compile(
    r"[A-Za-z]:[\\/][^\s\"']+|~[/\\][^\s\"']+|[\w\-./]+\.(?:pdf|docx?|pptx?|xlsx?|md|csv|epub)",
    re.IGNORECASE,
)
ACTION_KEYWORDS = [
    (re.compile(r"爬取|爬虫|抓取|采集"), "spider"),
    (re.compile(r"解析|识别|OCR"), "parse"),
    (re.compile(r"转换|转成|导出|生成.*(?:Word|DOCX|docx)"), "convert"),
    (re.compile(r"流水线|全流程|一条龙"), "pipeline"),
]


@dataclass
class InstructionResult:
    instruction: dict[str, Any] | None = None
    fallback: bool = False            # 是否走了第三层关键词兜底
    raw_reply: str = ""               # 原始模型输出（对话展示用）
    dropped_notes: list[str] = field(default_factory=list)


def _loads_strict(text: str) -> dict[str, Any] | None:
    """严格解析并校验 action/task_type 合法性。"""
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("action") not in VALID_ACTIONS:
        return None
    if payload.get("task_type") not in VALID_TASK_TYPES:
        return None
    payload.setdefault("params", {})
    if not isinstance(payload["params"], dict):
        payload["params"] = {}
    return payload


def _extract_codeblock(text: str) -> dict[str, Any] | None:
    """第一层：优先提取 ```json ... ``` 包裹内容。"""
    for match in CODEBLOCK_RE.finditer(text):
        parsed = _loads_strict(match.group(1))
        if parsed is not None:
            return parsed
    return None


def _extract_loose(text: str) -> dict[str, Any] | None:
    """第二层：截取首个 { 到末个 } 的片段直接解析。"""
    match = JSON_OBJECT_RE.search(text)
    if match:
        return _loads_strict(match.group(0))
    return None


def _keyword_fallback(text: str) -> dict[str, Any] | None:
    """第三层：正则关键词匹配核心实体，按默认参数构建指令。"""
    action = next((act for pattern, act in ACTION_KEYWORDS if pattern.search(text)), None)
    if action is None:
        return None
    params: dict[str, Any] = {}
    url = URL_RE.search(text)
    path = PATH_RE.search(text)
    if action == "spider":
        # 模型自述/Markdown 链接常带尾随括号标点，剥掉避免脏 URL
        params["url"] = url.group(0).rstrip(").,，;；、!！?？") if url else None
        task_type = "spider_single" if url else "spider_site"
    elif action == "parse":
        params["input_path"] = path.group(0) if path else None
        task_type = "mineru"
    elif action == "convert":
        params["input_path"] = path.group(0) if path else None
        for keyword, template in KEYWORD_TASK_TYPES.items():
            if keyword in text:
                params["template"] = template
                break
        task_type = "md2docx"
    else:
        task_type = "pipeline"
        params["pipeline"] = "paper_process"
    return {"action": action, "task_type": task_type, "params": params,
            "title": text.strip()[:40]}


def parse_instruction(model_output: str, settings: AiSettings | None = None) -> InstructionResult:
    """三层降级入口：模型输出 → 指令（可能为 None，纯对话场景）。"""
    result = InstructionResult(raw_reply=model_output)
    text = THINK_RE.sub("", model_output)  # 剥离推理块再解析
    parsed = _extract_codeblock(text) or _extract_loose(text)
    if parsed is not None:
        result.instruction = parsed
        return result
    if settings is None or settings.instruction.fallback_keyword_mode:
        fallback = _keyword_fallback(model_output)
        if fallback is not None:
            result.instruction = fallback
            result.fallback = True
            if settings is None or settings.instruction.fallback_notice:
                result.dropped_notes.append("⚠️ AI 走神了，已用快捷模式执行，建议检查参数")
    return result
