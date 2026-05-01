# RED Test: 对话框自动处理
# test_bh_dialog.py
# 状态：RED（应该失败，直到实现为止）

import pytest
import os
import tempfile
from unittest.mock import MagicMock


# ── 测试：DialogHandler 基本行为 ────────────────────────────

def test_dialog_handler_has_setup():
    """
    RED: DialogHandler 应有 setup() 方法注册到 page.on("dialog")
    """
    from bh_tools import DialogHandler

    mock_page = MagicMock()
    handler = DialogHandler(mock_page)

    # setup() 应返回 self（链式调用）
    result = handler.setup()
    assert result is handler, "setup() 应返回 self"

    # page.on 应被调用一次，参数是 "dialog"
    mock_page.on.assert_called_once()
    args = mock_page.on.call_args
    assert args[0][0] == "dialog"


def test_dialog_handler_accept_alert():
    """
    RED: alert 对话框应被自动 accept
    """
    from bh_tools import DialogHandler

    mock_page = MagicMock()
    mock_dialog = MagicMock()
    mock_dialog.type = "alert"
    mock_dialog.message = "Hello!"

    handler = DialogHandler(mock_page, accept=True)
    handler.setup()

    # 模拟触发 dialog 事件
    handler._on_dialog(mock_dialog)

    mock_dialog.accept.assert_called_once()
    assert handler.last_message == "Hello!"
    assert handler.dialogs_handled == 1


def test_dialog_handler_accept_confirm():
    """
    RED: confirm 对话框应被自动 accept
    """
    from bh_tools import DialogHandler

    mock_page = MagicMock()
    mock_dialog = MagicMock()
    mock_dialog.type = "confirm"
    mock_dialog.message = "Are you sure?"

    handler = DialogHandler(mock_page, accept=True)
    handler.setup()
    handler._on_dialog(mock_dialog)

    mock_dialog.accept.assert_called_once()


def test_dialog_handler_dismiss_confirm():
    """
    RED: accept=False 时 confirm 对话框应被 dismiss
    """
    from bh_tools import DialogHandler

    mock_page = MagicMock()
    mock_dialog = MagicMock()
    mock_dialog.type = "confirm"
    mock_dialog.message = "Delete?"

    handler = DialogHandler(mock_page, accept=False)
    handler.setup()
    handler._on_dialog(mock_dialog)

    mock_dialog.dismiss.assert_called_once()


def test_dialog_handler_prompt_accept():
    """
    RED: prompt 对话框应接受并填入 prompt_text
    """
    from bh_tools import DialogHandler

    mock_page = MagicMock()
    mock_dialog = MagicMock()
    mock_dialog.type = "prompt"
    mock_dialog.message = "Enter name:"

    handler = DialogHandler(mock_page, accept=True, prompt_text="Alice")
    handler.setup()
    handler._on_dialog(mock_dialog)

    mock_dialog.accept.assert_called_once_with("Alice")


def test_dialog_handler_prompt_dismiss():
    """
    RED: prompt 对话框在 dismiss_prompt=True 时应被拒绝
    """
    from bh_tools import DialogHandler

    mock_page = MagicMock()
    mock_dialog = MagicMock()
    mock_dialog.type = "prompt"

    handler = DialogHandler(mock_page, accept=True, dismiss_prompt=True)
    handler.setup()
    handler._on_dialog(mock_dialog)

    mock_dialog.dismiss.assert_called_once()
    mock_dialog.accept.assert_not_called()


def test_dialog_handler_beforeunload_dismiss():
    """
    RED: beforeunload 对话框应被 dismiss（不阻断导航）
    注意：beforeunload 是浏览器原生的，通常用 dismiss
    """
    from bh_tools import DialogHandler

    mock_page = MagicMock()
    mock_dialog = MagicMock()
    mock_dialog.type = "beforeunload"

    handler = DialogHandler(mock_page, accept=True)
    handler.setup()
    handler._on_dialog(mock_dialog)

    # beforeunload 通常 dismiss，不阻断页面离开
    mock_dialog.dismiss.assert_called_once()


def test_dialog_handler_close_removes_listener():
    """
    RED: close() 应移除对话框监听
    """
    from bh_tools import DialogHandler

    mock_page = MagicMock()
    handler = DialogHandler(mock_page)
    handler.setup()

    handler.close()

    mock_page.remove_listener.assert_called_once()


def test_setup_dialog_listener_returns_handler():
    """
    RED: setup_dialog_listener() 应返回可用的 DialogHandler
    """
    from bh_tools import setup_dialog_listener

    mock_page = MagicMock()
    handler = setup_dialog_listener(mock_page, accept=True)

    assert handler is not None
    assert hasattr(handler, "setup")
    assert hasattr(handler, "close")
    assert hasattr(handler, "dialogs_handled")
