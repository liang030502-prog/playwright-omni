"""
tests/test_orchestrator_action_exec.py — Playwright-Omni _execute_action TDD
测试 BrowserAgent._execute_action 对所有 ActionType 的处理
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

# Add scripts to path for imports
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from orchestrator import BrowserAgent, AgentResult
from vision_decision import ActionType


class TestExecuteActionCoordClick:
    """COORD_CLICK action 应该能解析 x,y 坐标并点击"""

    def test_coord_click_parses_xy(self):
        """COORD_CLICK target='200,300' 应该执行 page.mouse.click(200.0, 300.0)"""
        from orchestrator import BrowserAgent

        agent = BrowserAgent(api_key="mock", llm_provider="openai")

        mock_browser = MagicMock()
        mock_page = MagicMock()
        mock_browser.page = mock_page

        # 调用 _execute_action with COORD_CLICK
        agent._execute_action(mock_browser, ActionType.COORD_CLICK, "200,300", "")

        mock_page.mouse.click.assert_called_once_with(200.0, 300.0, button="left")

    def test_coord_click_with_button(self):
        """COORD_CLICK target='100,200,right' 应该用右键点击"""
        from orchestrator import BrowserAgent

        agent = BrowserAgent(api_key="mock", llm_provider="openai")
        mock_browser = MagicMock()
        mock_page = MagicMock()
        mock_browser.page = mock_page

        agent._execute_action(mock_browser, ActionType.COORD_CLICK, "100,200,right", "")

        mock_page.mouse.click.assert_called_once_with(100.0, 200.0, button="right")

    def test_coord_click_missing_y_uses_x(self):
        """COORD_CLICK 只有 x 坐标时，y 也用 x"""
        from orchestrator import BrowserAgent

        agent = BrowserAgent(api_key="mock", llm_provider="openai")
        mock_browser = MagicMock()
        mock_page = MagicMock()
        mock_browser.page = mock_page

        agent._execute_action(mock_browser, ActionType.COORD_CLICK, "150", "")

        mock_page.mouse.click.assert_called_once_with(150.0, 150.0, button="left")

    def test_coord_click_with_left_button(self):
        """COORD_CLICK target='10,20,left' 应该用左键点击（默认）"""
        from orchestrator import BrowserAgent

        agent = BrowserAgent(api_key="mock", llm_provider="openai")
        mock_browser = MagicMock()
        mock_page = MagicMock()
        mock_browser.page = mock_page

        agent._execute_action(mock_browser, ActionType.COORD_CLICK, "10,20,left", "")

        mock_page.mouse.click.assert_called_once_with(10.0, 20.0, button="left")


class TestExecuteActionJsExec:
    """JS_EXEC action 应该执行 JavaScript"""

    def test_js_exec_calls_evaluate(self):
        """JS_EXEC target='script content' 应该调用 page.evaluate()"""
        from orchestrator import BrowserAgent

        agent = BrowserAgent(api_key="mock", llm_provider="openai")
        mock_browser = MagicMock()
        mock_page = MagicMock()
        mock_browser.page = mock_page

        script = "document.querySelector('.btn').click()"
        agent._execute_action(mock_browser, ActionType.JS_EXEC, script, "")

        mock_page.evaluate.assert_called_once_with(script)

    def test_js_exec_debug_mode_prints_result(self):
        """JS_EXEC 在 debug=True 时应打印 evaluate 结果"""
        from orchestrator import BrowserAgent

        agent = BrowserAgent(api_key="mock", llm_provider="openai", debug=True)
        mock_browser = MagicMock()
        mock_page = MagicMock()
        mock_browser.page = mock_page
        mock_page.evaluate.return_value = "result_123"

        # 不应抛出异常
        agent._execute_action(mock_browser, ActionType.JS_EXEC, "return 42", "")

        mock_page.evaluate.assert_called_once()


class TestExecuteActionHttpGet:
    """HTTP_GET action 应该用 bh_tools.http_get"""

    def test_http_get_calls_bh_tools_http_get(self):
        """HTTP_GET target='url' 应该调用 bh_tools.http_get"""
        from orchestrator import BrowserAgent

        agent = BrowserAgent(api_key="mock", llm_provider="openai", debug=True)
        mock_browser = MagicMock()

        test_url = "https://api.example.com/data"

        # http_get 在 _execute_action 内部通过 local import 导入
        with patch('bh_tools.http_get') as mock_http_get:
            mock_http_get.return_value = "<html>mock response</html>"

            agent._execute_action(mock_browser, ActionType.HTTP_GET, test_url, "")

            mock_http_get.assert_called_once_with(test_url)

    def test_http_get_raises_on_error(self):
        """HTTP_GET 失败时应抛出 RuntimeError"""
        from orchestrator import BrowserAgent

        agent = BrowserAgent(api_key="mock", llm_provider="openai")
        mock_browser = MagicMock()

        with patch('bh_tools.http_get') as mock_http_get:
            mock_http_get.side_effect = Exception("Connection refused")

            with pytest.raises(RuntimeError) as exc_info:
                agent._execute_action(mock_browser, ActionType.HTTP_GET, "https://bad.url", "")

            assert "http_get failed" in str(exc_info.value)

    def test_http_get_debug_prints_length(self):
        """HTTP_GET 在 debug 模式下应打印响应长度"""
        from orchestrator import BrowserAgent

        agent = BrowserAgent(api_key="mock", llm_provider="openai", debug=True)
        mock_browser = MagicMock()

        with patch('bh_tools.http_get') as mock_http_get:
            mock_http_get.return_value = "<html>" + "x" * 1000 + "</html>"

            # 不应抛出异常
            agent._execute_action(mock_browser, ActionType.HTTP_GET, "https://example.com", "")


class TestExecuteActionDone:
    """DONE action 不应执行任何操作"""

    def test_done_does_nothing(self):
        """DONE action 应该直接 pass，不抛出异常"""
        from orchestrator import BrowserAgent

        agent = BrowserAgent(api_key="mock", llm_provider="openai")
        mock_browser = MagicMock()

        # 不应抛出异常
        agent._execute_action(mock_browser, ActionType.DONE, "", "")


class TestExecuteActionFail:
    """FAIL action 应该抛出 RuntimeError"""

    def test_fail_raises_runtime_error(self):
        """FAIL action 应该抛出 RuntimeError，包含失败原因"""
        from orchestrator import BrowserAgent

        agent = BrowserAgent(api_key="mock", llm_provider="openai")
        mock_browser = MagicMock()

        with pytest.raises(RuntimeError) as exc_info:
            agent._execute_action(mock_browser, ActionType.FAIL, "", "元素不可点击")

        assert "元素不可点击" in str(exc_info.value)


class TestExecuteActionClick:
    """CLICK action 的 fallback 行为"""

    def test_click_fails_then_tries_coordinates(self):
        """click() 返回 False 时，应该尝试用 bounding_box 坐标点击"""
        from orchestrator import BrowserAgent

        agent = BrowserAgent(api_key="mock", llm_provider="openai")
        mock_browser = MagicMock()
        mock_page = MagicMock()
        mock_browser.page = mock_page

        # Mock: click 失败，但元素有 bounding_box
        mock_elem = MagicMock()
        mock_elem.first.bounding_box.return_value = {"x": 100, "y": 200, "width": 50, "height": 30}
        mock_browser._get_locator.return_value = mock_elem
        mock_browser.click.return_value = False

        agent._execute_action(mock_browser, ActionType.CLICK, "text=Submit", "")

        # 应该用 bbox 中心坐标点击
        mock_page.mouse.click.assert_called()


class TestExecuteActionType:
    """TYPE action 的错误处理"""

    def test_type_fails_when_element_not_found(self):
        """type() 返回 False 时应该抛出 RuntimeError"""
        from orchestrator import BrowserAgent

        agent = BrowserAgent(api_key="mock", llm_provider="openai")
        mock_browser = MagicMock()
        mock_browser.type.return_value = False

        with pytest.raises(RuntimeError) as exc_info:
            agent._execute_action(mock_browser, ActionType.TYPE, "#username", "myuser")

        assert "Type failed" in str(exc_info.value)


class TestExecuteActionSwitchTab:
    """SWITCH_TAB action 的索引转换"""

    def test_switch_tab_converts_1_indexed(self):
        """SWITCH_TAB value='2' 应该调用 browser.switch_to_page(1)（0-indexed）"""
        from orchestrator import BrowserAgent

        agent = BrowserAgent(api_key="mock", llm_provider="openai")
        mock_browser = MagicMock()

        agent._execute_action(mock_browser, ActionType.SWITCH_TAB, "", "2")

        # value='2' → idx=1 → switch_to_page(1)
        mock_browser.switch_to_page.assert_called_once_with(1)

    def test_switch_tab_first_tab(self):
        """SWITCH_TAB value='1' 应该切换到第一个标签页（idx=0）"""
        from orchestrator import BrowserAgent

        agent = BrowserAgent(api_key="mock", llm_provider="openai")
        mock_browser = MagicMock()

        agent._execute_action(mock_browser, ActionType.SWITCH_TAB, "", "1")

        mock_browser.switch_to_page.assert_called_once_with(0)

    def test_switch_tab_third_tab(self):
        """SWITCH_TAB value='3' 应该切换到第三个标签页（idx=2）"""
        from orchestrator import BrowserAgent

        agent = BrowserAgent(api_key="mock", llm_provider="openai")
        mock_browser = MagicMock()

        agent._execute_action(mock_browser, ActionType.SWITCH_TAB, "", "3")

        mock_browser.switch_to_page.assert_called_once_with(2)


class TestExecuteActionScroll:
    """SCROLL action"""

    def test_scroll_calls_browser_scroll(self):
        """SCROLL 应该调用 browser.scroll(value)"""
        from orchestrator import BrowserAgent

        agent = BrowserAgent(api_key="mock", llm_provider="openai")
        mock_browser = MagicMock()

        agent._execute_action(mock_browser, ActionType.SCROLL, "", "down500")

        mock_browser.scroll.assert_called_once_with("down500")


class TestExecuteActionWait:
    """WAIT action"""

    def test_wait_sleeps_for_seconds(self):
        """WAIT value='2.5' 应该 time.sleep(2.5)"""
        from orchestrator import BrowserAgent

        agent = BrowserAgent(api_key="mock", llm_provider="openai")
        mock_browser = MagicMock()

        with patch('time.sleep') as mock_sleep:
            agent._execute_action(mock_browser, ActionType.WAIT, "", "2.5")

            mock_sleep.assert_called_once_with(2.5)


class TestExecuteActionGoto:
    """GOTO action"""

    def test_goto_calls_browser_goto(self):
        """GOTO 应该调用 browser.goto(value)"""
        from orchestrator import BrowserAgent

        agent = BrowserAgent(api_key="mock", llm_provider="openai")
        mock_browser = MagicMock()

        agent._execute_action(mock_browser, ActionType.GOTO, "", "https://github.com")

        mock_browser.goto.assert_called_once_with("https://github.com")


class TestExecuteActionUnknown:
    """未知 action 应抛出 RuntimeError"""

    def test_unknown_action_raises(self):
        """未知 action type 应该抛出 RuntimeError"""
        from orchestrator import BrowserAgent

        agent = BrowserAgent(api_key="mock", llm_provider="openai")
        mock_browser = MagicMock()

        # 创建一个不存在的 ActionType
        unknown_action = 9999

        with pytest.raises(RuntimeError) as exc_info:
            agent._execute_action(mock_browser, unknown_action, "", "")

        assert "Unknown action" in str(exc_info.value)