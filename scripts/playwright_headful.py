# playwright_headful.py — Playwright 有头模式基础执行层
# 职责：浏览器生命周期管理、截图、元素操作（不含AI决策）
r"""
用法示例:
    from playwright_headful import BrowserSession

    with BrowserSession() as browser:
        browser.goto('https://example.com')
        browser.screenshot('output.png')
        browser.click('text=Submit')
        browser.type('id=username', 'myuser')

CDP 接管模式:
    config = BrowserConfig(cdp_url="http://localhost:9222")
    with BrowserSession(config) as browser:
        browser.goto('https://example.com')  # 复用已有 Chrome

User Data Dir 模式:
    config = BrowserConfig(
        user_data_dir=r"C:\\Users\\Administrator\\AppData\\Local\\Google\\Chrome\\User Data"
    )
    with BrowserSession(config) as browser:
        browser.goto('https://example.com')  # 使用你的 Chrome profile
"""

from __future__ import annotations

import os
import sys
import time
import json
from pathlib import Path
from typing import Optional, Union, List, Dict, Any
from dataclasses import dataclass, field

# Playwright 路径固定，不走 venv 自动搜索
_PW_PATH = os.environ.get('PLAYWRIGHT_PATH', r'D:\OpenClaw\venv\Lib\site-packages\playwright')
_PW_PATH = os.path.normpath(_PW_PATH)
if _PW_PATH not in sys.path:
    sys.path.insert(0, _PW_PATH)

from playwright.sync_api import (
    sync_playwright,
    Browser as BrowserBase,
    BrowserContext,
    Page,
    TimeoutError as PWTimeoutError,
)

# ChromiumBrowser 不是公开 API，使用 Browser 基类
ChromiumBrowser = BrowserBase


@dataclass
class BrowserConfig:
    """浏览器启动配置"""
    headless: bool = False
    viewport_width: int = 1280
    viewport_height: int = 900
    user_agent: Optional[str] = None
    proxy: Optional[Dict] = None  # {"server": "http://proxy:8080"}
    ignore_https_errors: bool = True
    # 有头模式特有参数
    start_maximized: bool = True
    no_viewport: bool = False  # 有头模式默认 True（跟随真实窗口）
    # 启动参数
    args: List[str] = field(default_factory=lambda: [
        '--disable-extensions',
        '--no-sandbox',
        '--disable-dev-shm-usage',
        '--disable-blink-features=AutomationControlled',
    ])
    chromium_channel: str = "chromium"  # 使用 playwright 安装的 chromium
    # ── CDP 接管模式 ─────────────────────────────────────
    # 设置 cdp_url 即可启用，例如 "http://localhost:9222"
    cdp_url: Optional[str] = None
    # ── User Data Dir 模式 ───────────────────────────────
    # 例如 r"C:\\Users\\Administrator\\AppData\\Local\\Google\\Chrome\\User Data"
    user_data_dir: Optional[str] = None


class BrowserSession:
    """
    浏览器会话管理器
    用法:
        with BrowserSession() as browser:
            browser.goto('https://example.com')
            browser.screenshot('out.png')

    支持嵌套（不建议，资源浪费）:
        outer = BrowserSession()
        outer.__enter__()
        outer.goto('https://a.com')
        inner = BrowserSession()
        inner.__enter__()  # 共享同一 playwright 实例，但会创建新 context/page
    """

    _playwright = None  # 全局单例 playwright instance
    _active_sessions: List["BrowserSession"] = []

    def __init__(self, config: Optional[BrowserConfig] = None):
        self.config = config or BrowserConfig()
        self.browser: Optional[ChromiumBrowser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._opened_pages: List[Page] = []
        self._closed = False

    def __enter__(self) -> "BrowserSession":
        self._ensure_browser()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _ensure_browser(self):
        """延迟初始化浏览器（支持三种模式）"""
        if self.browser is not None:
            return

        # 全局 playwright 单例
        if BrowserSession._playwright is None:
            BrowserSession._playwright = sync_playwright().start()

        # ── 模式 1：CDP 接管（连接已运行的 Chrome）───────────
        if self.config.cdp_url:
            try:
                self.browser = BrowserSession._playwright.chromium.connect_over_cdp(
                    self.config.cdp_url
                )
                if self.browser.contexts:
                    self.context = self.browser.contexts[0]
                else:
                    self.context = self.browser.new_context()
                if self.context.pages:
                    self.page = self.context.pages[0]
                else:
                    self.page = self.context.new_page()
                self._opened_pages.append(self.page)
                BrowserSession._active_sessions.append(self)
                return
            except Exception as e:
                raise RuntimeError(f"[CDP] 连接失败 {self.config.cdp_url}: {e}") from e

        # ── 模式 2：User Data Dir（以指定 profile 启动）───────
        if self.config.user_data_dir:
            launch_opts: Dict[str, Any] = {
                "headless": self.config.headless,
                "args": self.config.args,
                "channel": self.config.chromium_channel,
            }
            try:
                self.browser = BrowserSession._playwright.chromium.launch(**launch_opts)
            except Exception as e:
                raise RuntimeError(
                    f"[UserDataDir] 启动 Chromium 失败: {e}\n"
                    f"Path: {self.config.user_data_dir}\n"
                    f"确保关闭所有 Chrome 窗口后再试。"
                ) from e
            context_opts: Dict[str, Any] = {
                "viewport": {
                    "width": self.config.viewport_width,
                    "height": self.config.viewport_height,
                },
                "ignore_https_errors": self.config.ignore_https_errors,
            }
            if self.config.user_agent:
                context_opts["user_agent"] = self.config.user_agent
            if self.config.proxy:
                context_opts["proxy"] = self.config.proxy
            self.context = self.browser.new_context(**context_opts)
            self.page = self.context.new_page()
            self._opened_pages.append(self.page)
            BrowserSession._active_sessions.append(self)
            return

        # ── 模式 3：默认 Playwright 新建浏览器 ──────────────────
        launch_opts: Dict[str, Any] = {
            "headless": self.config.headless,
            "args": self.config.args,
            "channel": self.config.chromium_channel,
        }

        try:
            self.browser = BrowserSession._playwright.chromium.launch(
                **launch_opts
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to launch Chromium: {e}\n"
                f"Playwright browser path: D:\\OpenClaw\\browsers\\chromium-1208\\chrome-win64\\chrome.exe\n"
                f"Verify browser is installed: python -m playwright install chromium"
            ) from e

        context_opts: Dict[str, Any] = {
            "viewport": {
                "width": self.config.viewport_width,
                "height": self.config.viewport_height,
            },
            "ignore_https_errors": self.config.ignore_https_errors,
        }

        if self.config.user_agent:
            context_opts["user_agent"] = self.config.user_agent

        if self.config.proxy:
            context_opts["proxy"] = self.config.proxy

        self.context = self.browser.new_context(**context_opts)

        self.page = self.context.new_page()
        self._opened_pages.append(self.page)

        BrowserSession._active_sessions.append(self)

    # ─────────────────────────────────────────────────────────
    # 导航
    # ─────────────────────────────────────────────────────────

    def goto(self, url: str, timeout: float = 30000, wait_until: str = "load") -> Page:
        """
        导航到 URL

        Args:
            url: 目标 URL
            timeout: 超时时间（毫秒）
            wait_until: 等待条件
                - "load": 默认，等待 load 事件
                - "domcontentloaded": 等待 DOMContentLoaded
                - "networkidle": 等待网络空闲（动态页面推荐）
                - "commit": 导航提交即返回
        """
        self._ensure_browser()
        assert self.page, "Page not initialized"

        response = self.page.goto(url, timeout=timeout, wait_until=wait_until)

        # 等待页面稳定（可选）
        try:
            self.page.wait_for_load_state("networkidle", timeout=10000)
        except PWTimeoutError:
            pass  # 网络空闲超时没关系，页面可能持续有请求

        return self.page

    def back(self):
        """后退一页"""
        self.page.go_back()
        self._wait_page_stable()

    def forward(self):
        """前进一页"""
        self.page.go_forward()
        self._wait_page_stable()

    def reload(self, timeout: float = 30000):
        """刷新当前页"""
        self.page.reload(timeout=timeout)
        self._wait_page_stable()

    # ─────────────────────────────────────────────────────────
    # 截图
    # ─────────────────────────────────────────────────────────

    def screenshot(
        self,
        path: Optional[str] = None,
        full_page: bool = False,
        timeout: float = 30000,
        type: Optional[str] = None,  # "png" | "jpeg"
        quality: Optional[int] = None,
        omit_background: bool = False,
    ) -> bytes:
        """
        截图

        Args:
            path: 保存路径（相对路径基于 cwd），None 则只返回 bytes
            full_page: 是否截取整个可滚动页面
            type: 图片格式 ("png"/"jpeg")，None 则根据路径扩展名推断
            quality: JPEG 质量 (0-100)
            omit_background: PNG 背景透明（实验性）

        Returns:
            bytes: 图片数据（即使指定了 path 也会返回）
        """
        self._ensure_browser()
        assert self.page, "Page not initialized"

        opts: Dict[str, Any] = {
            "full_page": full_page,
            "timeout": timeout,
            "omit_background": omit_background,
        }
        if path:
            opts["path"] = path
        if type:
            opts["type"] = type
        if quality is not None:
            opts["quality"] = quality

        return self.page.screenshot(**opts)

    # ─────────────────────────────────────────────────────────
    # 元素定位 & 操作
    # ─────────────────────────────────────────────────────────

    def click(
        self,
        selector: str,
        timeout: float = 30000,
        button: str = "left",
        click_count: int = 1,
        modifiers: Optional[List[str]] = None,
        force: bool = False,
        position: Optional[Dict[str, int]] = None,
    ) -> None:
        """点击元素"""
        self._ensure_browser()
        assert self.page, "Page not initialized"

        self.page.click(
            selector,
            timeout=timeout,
            button=button,
            click_count=click_count,
            modifiers=modifiers,
            force=force,
            position=position,
        )

    def dblclick(
        self,
        selector: str,
        timeout: float = 30000,
        button: str = "left",
        modifiers: Optional[List[str]] = None,
        force: bool = False,
        position: Optional[Dict[str, int]] = None,
    ) -> None:
        """双击元素"""
        self._ensure_browser()
        assert self.page, "Page not initialized"

        self.page.dblclick(
            selector,
            timeout=timeout,
            button=button,
            modifiers=modifiers,
            force=force,
            position=position,
        )

    def rightclick(self, selector: str, timeout: float = 30000) -> None:
        """右键点击元素"""
        self.click(selector, timeout=timeout, button="right")

    def type(
        self,
        selector: str,
        text: str,
        delay: float = 0,
        timeout: float = 30000,
        clear: bool = True,
    ) -> None:
        """输入文本（逐字符打字效果）"""
        self._ensure_browser()
        assert self.page, "Page not initialized"

        if clear:
            self.page.fill(selector, "", timeout=timeout)
        self.page.type(selector, text, delay=delay, timeout=timeout)

    def fill(
        self,
        selector: str,
        value: str,
        timeout: float = 30000,
    ) -> None:
        """填充表单字段（直接赋值，不触发输入事件）"""
        self._ensure_browser()
        assert self.page, "Page not initialized"

        self.page.fill(selector, value, timeout=timeout)

    def press(
        self,
        selector: str,
        key: str,
        delay: float = 0,
        timeout: float = 30000,
    ) -> None:
        """按下键盘按键"""
        self._ensure_browser()
        assert self.page, "Page not initialized"

        self.page.press(selector, key, delay=delay, timeout=timeout)

    def hover(self, selector: str, timeout: float = 30000) -> None:
        """鼠标悬停"""
        self._ensure_browser()
        assert self.page, "Page not initialized"
        self.page.hover(selector, timeout=timeout)

    def select_option(
        self,
        selector: str,
        value: Optional[Union[str, List[str]]] = None,
        label: Optional[Union[str, List[str]]] = None,
        index: Optional[Union[int, List[int]]] = None,
        timeout: float = 30000,
        force: bool = False,
    ) -> List[str]:
        """下拉框选择"""
        self._ensure_browser()
        assert self.page, "Page not initialized"

        return self.page.select_option(
            selector,
            value=value,
            label=label,
            index=index,
            timeout=timeout,
            force=force,
        )

    def check(self, selector: str, timeout: float = 30000) -> None:
        """勾选复选框/单选框"""
        self._ensure_browser()
        assert self.page, "Page not initialized"
        self.page.check(selector, timeout=timeout)

    def uncheck(self, selector: str, timeout: float = 30000) -> None:
        """取消勾选"""
        self._ensure_browser()
        assert self.page, "Page not initialized"
        self.page.uncheck(selector, timeout=timeout)

    def set_checked(self, selector: str, checked: bool, timeout: float = 30000) -> None:
        """设置复选框/单选框状态"""
        self._ensure_browser()
        assert self.page, "Page not initialized"
        self.page.set_checked(selector, checked, timeout=timeout)

    # ─────────────────────────────────────────────────────────
    # JavaScript
    # ─────────────────────────────────────────────────────────

    def evaluate(self, expression: str, *args, timeout: float = 30000) -> Any:
        """执行 JavaScript 表达式"""
        self._ensure_browser()
        assert self.page, "Page not initialized"
        return self.page.evaluate(expression, *args, timeout=timeout)

    def evaluate_async(self, expression: str, *args, timeout: float = 30000) -> Any:
        """执行异步 JavaScript 表达式"""
        self._ensure_browser()
        assert self.page, "Page not initialized"
        return self.page.evaluate_async(expression, *args, timeout=timeout)

    # ─────────────────────────────────────────────────────────
    # 等待
    # ─────────────────────────────────────────────────────────

    def wait_for_selector(
        self,
        selector: str,
        state: str = "visible",
        timeout: float = 30000,
    ) -> Optional[Any]:
        """
        等待元素出现

        Args:
            selector: CSS 选择器 / xpath
            state: "attached" | "detached" | "visible" | "hidden"
            timeout: 超时（毫秒）
        """
        self._ensure_browser()
        assert self.page, "Page not initialized"

        try:
            return self.page.wait_for_selector(selector, state=state, timeout=timeout)
        except PWTimeoutError:
            return None

    def wait_for_load_state(
        self,
        state: str = "load",
        timeout: float = 30000,
    ) -> None:
        """等待页面状态"""
        self._ensure_browser()
        assert self.page, "Page not initialized"
        self.page.wait_for_load_state(state, timeout=timeout)

    def wait_for_navigation(
        self,
        timeout: float = 30000,
        wait_until: str = "load",
        expected_url: Optional[str] = None,
    ) -> Optional[Any]:
        """等待导航完成"""
        self._ensure_browser()
        assert self.page, "Page not initialized"

        if expected_url:
            return self.page.wait_for_url(expected_url, timeout=timeout)

        return self.page.wait_for_load_state(wait_until, timeout=timeout)

    def sleep(self, seconds: float) -> None:
        """强制等待（秒）"""
        time.sleep(seconds)

    def _wait_page_stable(self, timeout: float = 10000) -> None:
        """等待页面稳定（网络空闲或超时）"""
        try:
            self.page.wait_for_load_state("networkidle", timeout=timeout)
        except PWTimeoutError:
            pass

    # ─────────────────────────────────────────────────────────
    # 页面 / Frame
    # ─────────────────────────────────────────────────────────

    @property
    def url(self) -> str:
        """当前页面 URL"""
        self._ensure_browser()
        assert self.page, "Page not initialized"
        return self.page.url

    @property
    def title(self) -> str:
        """当前页面标题"""
        self._ensure_browser()
        assert self.page, "Page not initialized"
        return self.page.title()

    def get_cookies(self) -> List[Dict]:
        """获取当前页面 cookies"""
        self._ensure_browser()
        assert self.context, "Context not initialized"
        return self.context.cookies()

    def set_cookies(cookies: List[Dict]) -> None:
        """设置 cookies"""
        self._ensure_browser()
        assert self.context, "Context not initialized"
        self.context.add_cookies(cookies)

    def clear_cookies(self) -> None:
        """清除所有 cookies"""
        self._ensure_browser()
        assert self.context, "Context not initialized"
        self.context.clear_cookies()

    def new_page(self) -> Page:
        """创建新页面（Tab）"""
        self._ensure_browser()
        assert self.context, "Context not initialized"
        page = self.context.new_page()
        self._opened_pages.append(page)
        return page

    def switch_to_page(self, page: Page) -> None:
        """切换到指定页面"""
        self._ensure_browser()
        assert page in self._opened_pages, "Page not managed by this session"
        self.page = page

    def switch_to_frame(self, frame_index: int = 0) -> None:
        """切换到 iframe（默认第一个）"""
        self._ensure_browser()
        assert self.page, "Page not initialized"
        frames = self.page.frames
        if 0 <= frame_index < len(frames):
            self.page = frames[frame_index]  # type: ignore

    def close_page(self, page: Optional[Page] = None) -> None:
        """关闭页面（Tab）"""
        self._ensure_browser()
        if page is None:
            page = self.page
        if page and page in self._opened_pages:
            page.close()
            self._opened_pages.remove(page)
            if page == self.page and self._opened_pages:
                self.page = self._opened_pages[-1]

    # ─────────────────────────────────────────────────────────
    # 滚动
    # ─────────────────────────────────────────────────────────

    def scroll_to_element(self, selector: str, timeout: float = 30000) -> None:
        """滚动到元素可见"""
        self._ensure_browser()
        assert self.page, "Page not initialized"
        self.page.evaluate(
            "selector => document.querySelector(selector).scrollIntoView()",
            selector,
        )

    def scroll_by(self, x: int = 0, y: int = 500) -> None:
        """按像素滚动"""
        self._ensure_browser()
        assert self.page, "Page not initialized"
        self.page.evaluate(f"window.scrollBy({x}, {y})")

    def scroll_to_top(self) -> None:
        """滚动到页面顶部"""
        self._ensure_browser()
        assert self.page, "Page not initialized"
        self.page.evaluate("window.scrollTo(0, 0)")

    def scroll_to_bottom(self) -> None:
        """滚动到页面底部"""
        self._ensure_browser()
        assert self.page, "Page not initialized"
        self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

    # ─────────────────────────────────────────────────────────
    # 弹窗 / 对话框
    # ─────────────────────────────────────────────────────────

    def handle_dialog(self, action: str = "accept", prompt_text: Optional[str] = None) -> None:
        """
        处理 JS 弹窗（alert/confirm/prompt）

        Args:
            action: "accept" | "dismiss"
            prompt_text: prompt 时输入的文本
        """
        self._ensure_browser()
        assert self.page, "Page not initialized"

        def handler(dialog):
            if action == "accept":
                if prompt_text:
                    dialog.accept(prompt_text)
                else:
                    dialog.accept()
            else:
                dialog.dismiss()

        self.page.on("dialog", handler)

    # ─────────────────────────────────────────────────────────
    # 下载
    # ─────────────────────────────────────────────────────────

    def download(
        self,
        selector: str,
        save_path: Optional[str] = None,
        timeout: float = 60000,
    ) -> Optional[str]:
        """
        点击下载链接并等待下载完成

        Args:
            selector: 下载按钮/链接选择器
            save_path: 保存路径（默认当前目录）
            timeout: 超时

        Returns:
            下载文件路径，失败返回 None
        """
        self._ensure_browser()
        assert self.page, "Page not initialized"

        with self.page.expect_download(timeout=timeout) as download_info:
            self.page.click(selector, timeout=timeout)
        download = download_info.value
        path = save_path or os.path.join(os.getcwd(), download.suggested_filename)
        download.save_as(path)
        return path

    # ─────────────────────────────────────────────────────────
    # 工具方法
    # ─────────────────────────────────────────────────────────

    def get_element_text(self, selector: str, timeout: float = 30000) -> str:
        """获取元素文本内容"""
        self._ensure_browser()
        assert self.page, "Page not initialized"
        return self.page.text_content(selector, timeout=timeout) or ""

    def get_element_attribute(
        self,
        selector: str,
        attr: str,
        timeout: float = 30000,
    ) -> Optional[str]:
        """获取元素属性值"""
        self._ensure_browser()
        assert self.page, "Page not initialized"
        return self.page.get_attribute(selector, attr, timeout=timeout)

    def is_visible(self, selector: str, timeout: float = 30000) -> bool:
        """元素是否可见"""
        self._ensure_browser()
        assert self.page, "Page not initialized"
        try:
            self.page.wait_for_selector(selector, state="visible", timeout=timeout)
            return True
        except PWTimeoutError:
            return False

    def is_disabled(self, selector: str, timeout: float = 30000) -> bool:
        """元素是否禁用"""
        self._ensure_browser()
        assert self.page, "Page not initialized"
        return self.page.is_disabled(selector, timeout=timeout)

    # ─────────────────────────────────────────────────────────
    # 批量操作
    # ─────────────────────────────────────────────────────────

    def fill_form(self, data: Dict[str, str], timeout: float = 30000) -> None:
        """
        批量填写表单（支持字典）

        data = {
            "#username": "myuser",
            "#password": "mypass",
            "input[name=remember]": True,   # checkbox
            "#country": "US",               # select
        }
        """
        self._ensure_browser()
        assert self.page, "Page not initialized"

        for selector, value in data.items():
            if value is True:
                self.check(selector, timeout=timeout)
            elif value is False:
                self.uncheck(selector, timeout=timeout)
            elif isinstance(value, bool):
                self.set_checked(selector, value, timeout=timeout)
            elif isinstance(value, list):
                # multi-select
                self.select_option(selector, value=value, timeout=timeout)
            else:
                self.fill(selector, str(value), timeout=timeout)

    # ─────────────────────────────────────────────────────────
    # 生命周期
    # ─────────────────────────────────────────────────────────

    def close(self) -> None:
        """关闭浏览器会话"""
        if self._closed:
            return
        self._closed = True

        for page in self._opened_pages:
            try:
                page.close()
            except Exception:
                pass
        self._opened_pages.clear()

        if self.context:
            try:
                self.context.close()
            except Exception:
                pass
            self.context = None

        if self in BrowserSession._active_sessions:
            BrowserSession._active_sessions.remove(self)

        # 如果没有其他活跃 session，清理 playwright 单例
        if not BrowserSession._active_sessions:
            self.cleanup()

    def cleanup(self) -> None:
        """清理全局 playwright 单例"""
        if BrowserSession._playwright is not None:
            try:
                BrowserSession._playwright.stop()
            except Exception:
                pass
            BrowserSession._playwright = None
