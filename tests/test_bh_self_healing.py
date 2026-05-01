# RED Test: Self-Healing Agent
# test_bh_self_healing.py
# 状态：GREEN（实现完成后应全部通过）

import pytest
import re
from pathlib import Path


def test_self_healing_writer_exists():
    from bh_tools import SelfHealingToolWriter
    assert SelfHealingToolWriter is not None


def test_validate_tool_name_valid():
    from bh_tools import SelfHealingToolWriter
    writer = SelfHealingToolWriter()
    assert writer.validate_tool_name("my_tool") is True
    assert writer.validate_tool_name("get_page_title") is True


def test_validate_tool_name_invalid():
    from bh_tools import SelfHealingToolWriter
    writer = SelfHealingToolWriter()
    assert writer.validate_tool_name("123abc") is False
    assert writer.validate_tool_name("my-tool") is False
    assert writer.validate_tool_name("_private") is False
    assert writer.validate_tool_name("") is False


def test_validate_code_valid():
    from bh_tools import SelfHealingToolWriter
    writer = SelfHealingToolWriter()
    assert writer.validate_code("def foo():\n    return 1") is True
    assert writer.validate_code("def bar(x, y):\n    return x + y") is True


def test_validate_code_invalid():
    from bh_tools import SelfHealingToolWriter
    writer = SelfHealingToolWriter()
    assert writer.validate_code("def foo(\n    return 1") is False
    assert writer.validate_code("def foo():\n    if True\n        pass") is False


def test_generate_function_code():
    from bh_tools import SelfHealingToolWriter
    writer = SelfHealingToolWriter()
    code = writer.generate_function_code(
        name="get_title",
        params=["page"],
        body="return page.title()",
        doc="Get page title"
    )
    assert "def get_title(page):" in code
    assert 'Get page title' in code and 'def get_title(page):' in code
    assert "    return page.title()" in code


def test_write_tool_valid_definition():
    from bh_tools import SelfHealingToolWriter
    writer = SelfHealingToolWriter()
    tool_def = {
        "name": "test_fetch_placeholder_v3",
        "params": ["url: str"],
        "body": "return f'Fetched: {url}'",
        "doc": "Test placeholder tool"
    }
    success, msg = writer.write_tool(tool_def)
    assert success is True, f"Write failed: {msg}"
    assert "test_fetch_placeholder_v3" in msg


def test_write_tool_invalid_name():
    from bh_tools import SelfHealingToolWriter
    writer = SelfHealingToolWriter()
    tool_def = {"name": "123-invalid", "params": [], "body": "pass", "doc": ""}
    success, msg = writer.write_tool(tool_def)
    assert success is False
    assert "illegal" in msg.lower() or "invalid" in msg.lower()


def test_write_tool_empty_body():
    from bh_tools import SelfHealingToolWriter
    writer = SelfHealingToolWriter()
    tool_def = {"name": "empty_tool", "params": [], "body": "", "doc": ""}
    success, msg = writer.write_tool(tool_def)
    assert success is False
    assert "empty" in msg or "body" in msg or "\u7a7a" in msg  # "空" in Chinese


def test_write_tool_syntax_error():
    from bh_tools import SelfHealingToolWriter
    writer = SelfHealingToolWriter()
    tool_def = {"name": "bad_tool", "params": [], "body": "this is not valid python", "doc": ""}
    success, msg = writer.write_tool(tool_def)
    assert success is False
    assert "syntax" in msg or "error" in msg or "\u8bed\u6cd5" in msg  # "语法" in Chinese


def test_list_written_tools():
    from bh_tools import SelfHealingToolWriter
    writer = SelfHealingToolWriter()
    tool_def = {"name": "test_list_tool_v3", "params": [], "body": "pass", "doc": ""}
    writer.write_tool(tool_def)
    tools = writer.list_written_tools()
    assert len(tools) == 1
    assert tools[0]["name"] == "test_list_tool_v3"


def test_write_tool_appends_to_all():
    """write_tool() 写入后，工具名应出现在 bh_tools.py 的 __all__ 列表中"""
    from bh_tools import SelfHealingToolWriter
    writer = SelfHealingToolWriter()
    tool_name = "test_append_tool_v7"
    tool_def = {"name": tool_name, "params": [], "body": "pass", "doc": ""}
    success, _ = writer.write_tool(tool_def)
    assert success is True
    content = writer.BH_TOOLS_PATH.read_text(encoding="utf-8")
    # Find the LAST occurrence of __all__ = [
    all_start = content.rfind("__all__ = [")
    assert all_start != -1, "Cannot find __all__"
    list_start = content.find("[", all_start)
    # Bracket counting to find matching ]
    bc = 0
    i = list_start
    while i < len(content):
        if content[i] == "[":
            bc += 1
        elif content[i] == "]":
            bc -= 1
            if bc == 0:
                break
        i += 1
    all_content = content[list_start:i+1]
    assert f'"{tool_name}"' in all_content or f"'{tool_name}'" in all_content, \
        f"{tool_name} not found in __all__"
