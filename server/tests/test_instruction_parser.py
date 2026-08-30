"""AI 指令三层降级解析测试（方案附录补丁 1 验收）。"""
from __future__ import annotations

from astroforge.ai.instruction_parser import parse_instruction

JSON = (
    '{"action": "spider", "task_type": "spider_site", '
    '"params": {"url": "https://cn.vuejs.org/guide/introduction.html"}, '
    '"title": "爬取Vue文档"}'
)


def test_layer1_codeblock():
    output = f"好的，已为你生成：\n```json\n{JSON}\n```\n请查收"
    result = parse_instruction(output)
    assert result.instruction is not None
    assert not result.fallback
    assert result.instruction["task_type"] == "spider_site"


def test_layer2_loose_json():
    output = f"好的，已为你生成 {JSON} 请查收"
    result = parse_instruction(output)
    assert result.instruction is not None
    assert not result.fallback


def test_layer3_keyword_fallback():
    result = parse_instruction("帮我爬取 https://example.com/docs 这个站点的文档")
    assert result.instruction is not None
    assert result.fallback
    assert result.instruction["action"] == "spider"
    assert result.instruction["params"]["url"] == "https://example.com/docs"
    assert any("走神" in note for note in result.dropped_notes)


def test_layer3_convert_with_template():
    result = parse_instruction("把 report.md 转换成学术论文格式的 Word")
    assert result.instruction is not None
    assert result.instruction["task_type"] == "md2docx"
    assert result.instruction["params"].get("template") == "academic"


def test_plain_chat_no_instruction():
    result = parse_instruction("今天天气不错，适合写代码。")
    assert result.instruction is None
    assert not result.fallback


def test_invalid_action_rejected():
    result = parse_instruction('{"action": "delete_all", "task_type": "mineru"}')
    assert result.instruction is None


def test_qwen3_think_block_stripped():
    """Qwen3 系模型 <think> 块不影响指令提取。"""
    output = "<think>\n用户想爬取页面\n</think>\n```json\n" + JSON + "\n```"
    result = parse_instruction(output)
    assert result.instruction is not None
    assert result.instruction["task_type"] == "spider_site"


def test_user_intent_preferred_over_model_prose():
    """用户消息直接关键词派发（用户意图优先于模型散文）；URL 尾随括号剥离。"""
    user = parse_instruction("帮我爬取 https://cn.vuejs.org/guide/introduction.html 这个页面")
    assert user.instruction is not None
    assert user.instruction["params"]["url"] == "https://cn.vuejs.org/guide/introduction.html"
    # 模型输出是含 Markdown 链接的散文（URL 带尾括号），不应污染参数
    prose = parse_instruction(
        "# 指南\n[Vue](https://vuejs.org/)；无法访问外部内容，我不会爬取。")
    assert prose.instruction is None or \
        prose.instruction["params"].get("url") != "https://vuejs.org/)"
