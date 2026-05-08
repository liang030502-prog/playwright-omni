# orchestrator.py — Playwright + OmniParser + LLM 编排层
# 职责：串联执行层、视觉层、决策层，形成完整自动化循环
"""
主循环：
  while not done:
      1. Playwright 截图
      2. OmniParser 解析 → 结构化元素
      3. LLM 决策 → 下一步操作
      4. Playwright 执行 → 验证结果
      5. 判断是否完成

用法:
    from orchestrator import BrowserAgent
    
    agent = BrowserAgent(
        llm_provider="openai",
        api_key="sk-...",
    )
    
    result = agent.run(
        url="https://github.com/login",
        goal="登录 GitHub，用户名 myuser，密码 mypass",
        max_steps=20,
    )
    
    print(result)
"""

from __future__ import annotations

import os
import sys
import json
import time
import traceback
import logging as _logging
from pathlib import Path as _Path
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Literal, Callable
from pathlib import Path

# 本地模块（支持直接运行和包导入两种方式）
try:
    from .playwright_headful import BrowserSession, BrowserConfig
    from .omniparser_wrapper import OmniParserWrapper, OmniResult, UIElement
    from .vision_decision import VisionDecision, LLMDecision, ActionType, ConversationMessage
except ImportError:
    # 直接运行时
    import sys, os
    _scripts_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, _scripts_dir)
    from playwright_headful import BrowserSession, BrowserConfig
    from omniparser_wrapper import OmniParserWrapper, OmniResult, UIElement
    from vision_decision import VisionDecision, LLMDecision, ActionType, ConversationMessage


# ─────────────────────────────────────────────────────────
# 结果数据结构
# ─────────────────────────────────────────────────────────

@dataclass
class StepRecord:
    """单步执行记录"""
    step: int
    action: str
    target: str
    value: str
    thought: str
    omni_elements_count: int
    omni_time_ms: float
    decision_time_ms: float
    success: bool
    error: str = ""


@dataclass
class AgentResult:
    """完整运行结果"""
    status: Literal["success", "max_steps", "error", "failed"] = "error"
    total_steps: int = 0
    total_time_seconds: float = 0.0
    steps: List[StepRecord] = field(default_factory=list)
    final_url: str = ""
    error_message: str = ""
    screenshot_dir: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "status": self.status,
            "total_steps": self.total_steps,
            "total_time_seconds": round(self.total_time_seconds, 2),
            "steps": [asdict(s) for s in self.steps],
            "final_url": self.final_url,
            "error_message": self.error_message,
        }
    
    def summary(self) -> str:
        lines = [
            f"[BrowserAgent] Status: {self.status}",
            f"  Steps: {self.total_steps}",
            f"  Time: {self.total_time_seconds:.1f}s",
        ]
        if self.error_message:
            lines.append(f"  Error: {self.error_message}")
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────
# 截图管理
# ─────────────────────────────────────────────────────────

class ScreenshotManager:
    """截图管理器"""
    
    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = output_dir or os.path.join(
            os.getcwd(), "browser_agent_screenshots"
        )
        self.screenshots: List[str] = []
        os.makedirs(self.output_dir, exist_ok=True)
    
    def capture(
        self,
        page,
        step: int,
        label: str = "",
        full_page: bool = False,
    ) -> str:
        """截图并返回路径"""
        filename = f"step_{step:03d}"
        if label:
            filename += f"_{label}"
        filename += ".png"
        
        path = os.path.join(self.output_dir, filename)
        page.screenshot(path=path, full_page=full_page)
        self.screenshots.append(path)
        return path
    
    def cleanup(self):
        """删除所有截图"""
        for p in self.screenshots:
            try:
                os.remove(p)
            except Exception:
                pass
        self.screenshots.clear()


# ─────────────────────────────────────────────────────────
# BrowserAgent 主类
# ─────────────────────────────────────────────────────────


from bh_tools import setup_download_listener, setup_dialog_listener
class BrowserAgent:
    """
    浏览器自动化 Agent
    
    整合 Playwright（有头浏览器）+ OmniParser（视觉解析）+ LLM（决策）
    形成完整的 AI 驱动的浏览器自动化循环。
    
    用法:
        agent = BrowserAgent(
            llm_provider="openai",
            api_key="sk-...",
        )
        result = agent.run("https://github.com", "登录 GitHub")
    """
    
    def __init__(
        self,
        llm_provider: str = "openai",
        api_key: Optional[str] = None,
        vision_model: Optional[str] = None,
        base_url: Optional[str] = None,      # ⬅️ 新增：自定义 API 代理地址
        device: Optional[str] = None,         # ⬅️ "cuda" / "cpu" / None=auto（见 device_selector.py）
        browser_config: Optional[BrowserConfig] = None,
        omni_config: Optional[Dict] = None,
        screenshot_dir: Optional[str] = None,
        max_steps: int = 20,
        save_screenshots: bool = True,
        debug: bool = False,
        max_retries: int = 2,        # ⬅️ 每个action最多重试次数
        # LLM 额外参数
        llm_temperature: float = 0.1,
        llm_max_tokens: int = 500,
        **llm_kwargs,
    ):
        """
        Args:
            llm_provider: LLM 提供者 (openai/anthropic/zhipu/doubao/ollama)
            api_key: API Key
            vision_model: 视觉模型名称
            browser_config: Playwright 浏览器配置
            omni_config: OmniParser 配置
            screenshot_dir: 截图保存目录
            max_steps: 最大步数，防止死循环
            save_screenshots: 是否保存截图
            debug: 调试模式，打印更多信息
            max_retries: 每个action失败后重试次数（默认2）
        """
        self.llm_provider = llm_provider
        self._api_key = api_key  # stored for _get_api_key()
        self.vision_model = vision_model
        if base_url:
            llm_kwargs["base_url"] = base_url  # 注入自定义代理地址
        self.browser_config = browser_config or BrowserConfig(headless=False)
        self.omni_config = omni_config or {}
        self.screenshot_dir = screenshot_dir
        self.max_steps = max_steps
        self.save_screenshots = save_screenshots
        self.debug = debug
        self.llm_temperature = llm_temperature
        self.llm_max_tokens = llm_max_tokens
        self.llm_kwargs = llm_kwargs
        self.device = device
        
        # 运行时实例
        self._browser: Optional[BrowserSession] = None
        self._omni: Optional[OmniParserWrapper] = None
        self._llm: Optional[VisionDecision] = None
        # 日志
        self._log_file: Optional[str] = None
        self._setup_logging()

        # 重试配置
        self._max_retries = max_retries

        # 运行状态
        self._current_step = 0
        self._steps: List[StepRecord] = []
        self._conversation_history: List[ConversationMessage] = []
        self._start_time = 0.0
        self._running = False
        
        # 钩子函数
        self.on_step_complete: Optional[Callable[[StepRecord], None]] = None
        self.on_error: Optional[Callable[[Exception], None]] = None
    
    def _ensure_browser(self) -> BrowserSession:
        if self._browser is None:
            self._browser = BrowserSession(self.browser_config, download_handler=self._download_handler, dialog_handler=self._dialog_handler)
            self._browser.__enter__()
        return self._browser
    
    def _ensure_omni(self) -> OmniParserWrapper:
        if self._omni is None:
            cfg = dict(self.omni_config)
            if self.device is not None:
                cfg["device"] = self.device
            self._omni = OmniParserWrapper(**cfg)
        return self._omni
    
    def _ensure_llm(self) -> VisionDecision:
        if self._llm is None:
            self._llm = VisionDecision(
                provider=self.llm_provider,
                api_key=self._get_api_key(),
                model=self.vision_model,
                temperature=self.llm_temperature,
                max_tokens=self.llm_max_tokens,
                **self.llm_kwargs,
            )
        return self._llm
    
    def _get_api_key(self) -> Optional[str]:
        """从参数或环境变量获取 API Key"""
        if self._api_key:
            return self._api_key
        
        env_vars = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "zhipu": "ZHIPU_API_KEY",
            "doubao": "ARK_API_KEY",
        }
        return os.environ.get(env_vars.get(self.llm_provider, ""), None)
    
    # ─────────────────────────────────────────────────────────
    # 核心运行
    # ─────────────────────────────────────────────────────────
    
    def run(
        self,
        url: str,
        goal: str,
        initial_actions: Optional[List[Dict]] = None,
    ) -> AgentResult:
        """
        运行自动化任务
        
        Args:
            url: 起始 URL
            goal: 用户目标（如"登录 GitHub，用户名 myuser，密码 mypass"）
            initial_actions: 初始动作列表（跳过 LLM 决策，直接执行）
                [{"action": "CLICK", "target": "text=登录"}]
        
        Returns:
            AgentResult: 运行结果
        """
        self._start_time = time.time()
        self._current_step = 0
        self._steps = []
        self._conversation_history = []
        self._running = True
        
        # 初始化截图管理器
        if self.save_screenshots:
            self._screenshot_mgr = ScreenshotManager(self.screenshot_dir)
        
        result = AgentResult()
        
        try:
            # 初始化组件
            browser = self._ensure_browser()
            omni = self._ensure_omni()
            llm = self._ensure_llm()
            
            # 导航到起始 URL
            if self.debug:
                print(f"[BrowserAgent] Navigating to {url}")
            browser.goto(url, wait_until="networkidle")
            
            # 执行初始动作（如果有）
            if initial_actions:
                for act in initial_actions:
                    self._execute_action(browser, act["action"], act.get("target", ""), act.get("value", ""))
                    self._current_step += 1
            
            # 主循环
            while self._current_step < self.max_steps and self._running:
                step_result = self._run_one_step(browser, omni, llm, goal)
                self._steps.append(step_result)
                self._current_step += 1
                
                # 钩子回调
                if self.on_step_complete:
                    self.on_step_complete(step_result)
                
                # 判断是否完成
                if step_result.action == "DONE":
                    result.status = "success"
                    break
                elif step_result.action == "FAIL":
                    result.status = "failed"
                    result.error_message = step_result.error or step_result.value
                    break
            
            if result.status == "error" and self._current_step >= self.max_steps:
                result.status = "max_steps"
                result.error_message = f"达到最大步数限制 ({self.max_steps})"
            
            result.total_steps = self._current_step
            result.total_time_seconds = time.time() - self._start_time
            result.steps = self._steps
            result.final_url = browser.get_url()
            result.screenshot_dir = self.screenshot_dir if self.save_screenshots else None
            
            return result
            
        except Exception as e:
            tb = traceback.format_exc()
            if self.debug:
                print(f"[BrowserAgent] Exception: {tb}")
            
            result.status = "error"
            result.error_message = f"{type(e).__name__}: {e}"
            result.total_steps = self._current_step
            result.total_time_seconds = time.time() - self._start_time
            result.steps = self._steps
            
            if self.on_error:
                self.on_error(e)
            
            return result
        
        finally:
            self._running = False
    
    def _run_one_step(
        self,
        browser: BrowserSession,
        omni: OmniParserWrapper,
        llm: VisionDecision,
        goal: str,
    ) -> StepRecord:
        """执行单步：截图 → OmniParser → LLM决策 → 执行"""
        
        t0 = time.time()
        
        # Step 1: 截图
        if self.save_screenshots and self._screenshot_mgr:
            screenshot_path = self._screenshot_mgr.capture(
                browser.page, self._current_step, label="before"
            )
        else:
            screenshot_path = None
        
        # Step 2: OmniParser 解析
        t_omni = time.time()
        if screenshot_path:
            omni_result = omni.parse(screenshot_path)
        else:
            # 临时截图
            import tempfile
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            tmp.close()
            browser.screenshot(tmp.name)
            omni_result = omni.parse(tmp.name)
            try:
                os.unlink(tmp.name)
            except Exception:
                pass
        omni_time_ms = (time.time() - t_omni) * 1000
        
        # Step 3: LLM 决策
        t_decision = time.time()
        decision = llm.decide(
            omni_result=omni_result,
            user_goal=goal,
            screenshot_path=screenshot_path,
            conversation_history=self._conversation_history,
        )
        decision_time_ms = (time.time() - t_decision) * 1000
        
        # 记录对话历史
        self._conversation_history.append(
            ConversationMessage(
                role="assistant",
                content=f"THOUGHT: {decision.thought}\n"
                        f"ACTION: {decision.action.value}\n"
                        f"TARGET: {decision.target}\n"
                        f"VALUE: {decision.value}"
            )
        )
        self._conversation_history.append(
            ConversationMessage(
                role="user",
                content=f"执行结果: {'成功' if decision.action != ActionType.FAIL else '失败'}"
            )
        )
        
        # Step 4: 执行（含重试）
        success = True
        error_msg = ""
        action_tried = 0
        for attempt in range(self._max_retries):
            action_tried = attempt + 1
            try:
                self._execute_action(browser, decision.action, decision.target, decision.value)
                success = True
                error_msg = ""
                if attempt > 0:
                    self._log("info", f"[Step {self._current_step}] ACTION retry OK after {attempt} failures")
                break
            except Exception as e:
                success = False
                error_msg = str(e)
                self._log("warning", f"[Step {self._current_step}] ACTION attempt {attempt+1} failed: {error_msg}")
                if attempt < self._max_retries - 1:
                    wait = (attempt + 1) * 2
                    self._log("info", f"[Step {self._current_step}] Retry in {wait}s...")
                    time.sleep(wait)
        if success and action_tried > 1:
            self._log("info", f"[Step {self._current_step}] Succeeded on attempt {action_tried}")
        
        if self.debug:
            print(
                f"[Step {self._current_step}] "
                f"{decision.action.value} | {decision.target} | "
                f"omni={omni_time_ms:.0f}ms | decision={decision_time_ms:.0f}ms | "
                f"{'OK' if success else 'FAIL: '+error_msg}"
            )
        
        return StepRecord(
            step=self._current_step,
            action=decision.action.value,
            target=decision.target,
            value=decision.value,
            thought=decision.thought,
            omni_elements_count=len(omni_result.elements),
            omni_time_ms=omni_time_ms,
            decision_time_ms=decision_time_ms,
            success=success,
            error=error_msg,
        )
    
    def _execute_action(
        self,
        browser: BrowserSession,
        action: ActionType,
        target: str,
        value: str,
    ):
        """将决策转换为 Playwright 操作"""
        
        if action == ActionType.CLICK:
            ok = browser.click(target, timeout=10000)
            if not ok:
                # 尝试用坐标点击
                elem = browser._get_locator(target)
                try:
                    bbox = elem.first.bounding_box()
                    if bbox:
                        x = bbox["x"] + bbox["width"] / 2
                        y = bbox["y"] + bbox["height"] / 2
                        browser.page.mouse.click(x, y)
                except Exception as e:
                    raise RuntimeError(f"Click failed: {e}")
        
        elif action == ActionType.TYPE:
            ok = browser.type(target, value, timeout=10000)
            if not ok:
                raise RuntimeError(f"Type failed: could not find element '{target}'")
        
        elif action == ActionType.SCROLL:
            browser.scroll(value)
        
        elif action == ActionType.WAIT:
            import time as time_module
            time_module.sleep(float(value))
        
        elif action == ActionType.GOTO:
            browser.goto(value)
        
        elif action == ActionType.SWITCH_TAB:
            idx = int(value) - 1  # 用户看到的是 1-indexed
            browser.switch_to_page(idx)
        
        elif action == ActionType.DONE:
            pass  # 不需要执行
        
        elif action == ActionType.FAIL:
            raise RuntimeError(f"LLM decided FAIL: {value}")
        # ── browser-harness 兼容新增 action types ──────────────────
        elif action == ActionType.COORD_CLICK:
            # target 格式: "x,y" 或 "x,y,button"
            parts = target.split(",")
            x = float(parts[0])
            y = float(parts[1]) if len(parts) > 1 else float(parts[0])
            button = parts[2].strip() if len(parts) > 2 else "left"
            browser.page.mouse.click(x, y, button=button)
        elif action == ActionType.JS_EXEC:
            # 执行 JavaScript
            result = browser.page.evaluate(target)
            if self.debug:
                print(f"[JS_EXEC] result: {result}")
        elif action == ActionType.HTTP_GET:
            # 纯 HTTP 请求（通过 bh_tools.http_get）
            from bh_tools import http_get
            try:
                html = http_get(target)
                if self.debug:
                    print(f"[HTTP_GET] {target}: {len(html)} bytes")
            except Exception as e:
                raise RuntimeError(f"http_get failed: {e}")
        else:
            raise RuntimeError(f"Unknown action: {action}")
    
    # ─────────────────────────────────────────────────────────
    # 生命周期
    # ─────────────────────────────────────────────────────────
    
    def stop(self):
        """停止运行"""
        self._running = False
    
    def close(self):
        """关闭所有资源"""
        self._running = False
        
        if self._browser:
            try:
                self._browser.close()
            except Exception:
                pass
            self._browser = None
        
        if self._omni:
            try:
                self._omni.unload()
            except Exception:
                pass
            self._omni = None
        
        self._llm = None
    
    def __enter__(self) -> "BrowserAgent":
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def _setup_logging(self):
        log_dir = _Path(r"D:\OpenClaw\logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_name = f"playwright_omni_{int(time.time())}.log"
        self._log_file = str(log_dir / log_name)
        _logging.basicConfig(
            level=_logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[
                _logging.FileHandler(self._log_file, encoding="utf-8"),
                _logging.StreamHandler(sys.stdout),
            ],
        )
        self._logger = _logging.getLogger("PlaywrightOmni")
        self._log_file_written = str(log_dir / log_name)

    def _log(self, level: str, msg: str):
        if hasattr(self, "_logger"):
            getattr(self._logger, level)(msg)

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


# ─────────────────────────────────────────────────────────
# 便捷入口
# ─────────────────────────────────────────────────────────

def run_browser_task(
    url: str,
    goal: str,
    llm_provider: str = "openai",
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,      # ⬅️ 新增
    model: Optional[str] = None,         # ⬅️ 新增
    device: Optional[str] = None,        # ⬅️ "cuda" / "cpu" / None=auto
    max_steps: int = 20,
    headless: bool = False,
    debug: bool = True,
    max_retries: int = 2,
    screenshot_dir: Optional[str] = None,
    cdp_url: Optional[str] = None,       # ⬅️ CDP 接管模式
    user_data_dir: Optional[str] = None,  # ⬅️ UserDataDir 模式
    **kwargs,
) -> AgentResult:
    """
    一行命令运行浏览器自动化任务

    用法:
        result = run_browser_task(
            url="https://github.com/login",
            goal="登录 GitHub，用户名 myuser，密码 mypass",
            llm_provider="openai",
            api_key="sk-...",
        )
        print(result.summary())
    """
    config = BrowserConfig(
        headless=headless,
        cdp_url=cdp_url,
        user_data_dir=user_data_dir,
    )
    
    agent = BrowserAgent(
        llm_provider=llm_provider,
        api_key=api_key,
        base_url=base_url,
        vision_model=model,
        browser_config=config,
        device=device,
        max_steps=max_steps,
        max_retries=max_retries,
        save_screenshots=screenshot_dir is not None,
        screenshot_dir=screenshot_dir,
        debug=debug,
        **kwargs,
    )
    
    try:
        result = agent.run(url=url, goal=goal)
        return result
    finally:
        agent.close()
