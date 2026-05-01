# vision_decision.py — LLM 决策层
# 职责：基于 OmniParser 的结构化输出，让 LLM 决定下一步操作
"""
支持的 LLM 提供者:
  - openai:   GPT-4o / GPT-4o-mini（默认）
  - anthropic: Claude-3.5-Sonnet / Claude-3-Opus
  - zhipu:    GLM-4V（智谱）
  - doubao:   Doubao-VL（字节）
  - ollama:   本地 Ollama（qwen2.5:3b 等）

用法:
    from vision_decision import VisionDecision
    
    llm = VisionDecision(provider="openai", api_key="sk-...")
    decision = llm.decide(
        omni_result=parse_result,
        user_goal="登录 GitHub",
        conversation_history=[...],
    )
    print(decision.action, decision.target, decision.value)
"""

from __future__ import annotations

import os
import sys
import json
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Literal
from enum import Enum

import importlib

# ─────────────────────────────────────────────────────────
# 数据结构
# ─────────────────────────────────────────────────────────

class ActionType(Enum):
    CLICK = "CLICK"
    TYPE = "TYPE"
    SCROLL = "SCROLL"
    WAIT = "WAIT"
    GOTO = "GOTO"
    SWITCH_TAB = "SWITCH_TAB"
    DONE = "DONE"
    FAIL = "FAIL"
    # ── browser-harness 兼容新增 ──────────────────────────────
    COORD_CLICK = "COORD_CLICK"   # 坐标点击 fallback when selector fails
    JS_EXEC = "JS_EXEC"           # 执行 JavaScript
    HTTP_GET = "HTTP_GET"       # 纯 HTTP 请求（无浏览器）


@dataclass
class LLMDecision:
    """LLM 决策结果"""
    action: ActionType
    target: str = ""           # 目标描述或坐标
    value: str = ""            # TYPE 时输入的文本
    thought: str = ""          # LLM 的思考过程
    confidence: float = 0.0   # 置信度
    raw_response: str = ""     # 原始 LLM 输出


@dataclass
class ConversationMessage:
    role: str        # "user" / "assistant" / "system"
    content: str


# ─────────────────────────────────────────────────────────
# LLM 客户端抽象
# ─────────────────────────────────────────────────────────

class LLMClient:
    """LLM 客户端基类"""
    
    def chat(self, messages: List[Dict], **kwargs) -> str:
        raise NotImplementedError


class OpenAIClient(LLMClient):
    def __init__(self, api_key: str, model: str = "gpt-4o", **kwargs):
        self.api_key = api_key
        self.model = model
        # Separate OpenAI init params from chat params
        _init_keys = ("base_url", "timeout", "max_retries", "default_headers", "http_headers", "http_client")
        self._init_kwargs = {k: v for k, v in kwargs.items() if k in _init_keys}
        self._chat_extra = {k: v for k, v in kwargs.items() if k not in _init_keys}

        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=api_key, **self._init_kwargs)
        except ImportError:
            raise ImportError(
                "openai package not installed. Run: pip install openai"
            )

    def chat(self, messages: List[Dict], **kwargs) -> str:
        merged = {**self._chat_extra, **kwargs}
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=merged.pop("temperature", 0.1),
            max_tokens=merged.pop("max_tokens", 500),
        )
        return response.choices[0].message.content


class AnthropicClient(LLMClient):
    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022", **kwargs):
        self.api_key = api_key
        self.model = model
        
        try:
            from anthropic import Anthropic
            self.client = Anthropic(api_key=api_key, **kwargs)
        except ImportError:
            raise ImportError(
                "anthropic package not installed. Run: pip install anthropic"
            )
    
    def chat(self, messages: List[Dict], **kwargs) -> str:
        # Anthropic 需要 system 和 user 分开
        system_msg = ""
        filtered_messages = []
        for m in messages:
            if m["role"] == "system":
                system_msg = m["content"]
            else:
                filtered_messages.append(m)
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=kwargs.get("max_tokens", 500),
            system=system_msg,
            messages=filtered_messages,
            temperature=kwargs.get("temperature", 0.1),
        )
        return response.content[0].text


class ZhipuClient(LLMClient):
    """智谱 GLM-4V"""
    def __init__(self, api_key: str, model: str = "glm-4v", **kwargs):
        self.api_key = api_key
        self.model = model
        
        try:
            from zhipuai import ZhipuAI
            self.client = ZhipuAI(api_key=api_key)
        except ImportError:
            raise ImportError("zhipuai package not installed. Run: pip install zhipuai")
    
    def chat(self, messages: List[Dict], **kwargs) -> str:
        # 取第一条 user 消息作为 content
        user_content = next((m["content"] for m in messages if m["role"] == "user"), "")
        system_msg = next((m["content"] for m in messages if m["role"] == "system"), "")
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_content},
            ],
            temperature=kwargs.get("temperature", 0.1),
        )
        return response.choices[0].message.content


class DoubaoClient(LLMClient):
    """字节豆包 VL"""
    def __init__(self, api_key: str, model: str = "doubao-vl-32k", **kwargs):
        self.api_key = api_key
        self.model = model
        
        # 豆包用的是火山引擎，openai 兼容接口
        try:
            from openai import OpenAI
            self.client = OpenAI(
                api_key=api_key,
                base_url="https://ark.cn-beijing.volces.com/api/v3",
            )
        except ImportError:
            raise ImportError("openai package not installed.")
    
    def chat(self, messages: List[Dict], **kwargs) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=kwargs.get("temperature", 0.1),
            max_tokens=kwargs.get("max_tokens", 500),
        )
        return response.choices[0].message.content


class OllamaClient(LLMClient):
    """本地 Ollama"""
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "qwen2.5:3b", **kwargs):
        self.base_url = base_url
        self.model = model
        
        try:
            import openai as _openai
            self.client = _openai.OpenAI(base_url=f"{base_url}/v1", api_key="ollama")
        except ImportError:
            raise ImportError("openai package needed for Ollama")
    
    def chat(self, messages: List[Dict], **kwargs) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=kwargs.get("temperature", 0.1),
            max_tokens=kwargs.get("max_tokens", 500),
        )
        return response.choices[0].message.content


# ─────────────────────────────────────────────────────────
# VisionDecision 主类
# ─────────────────────────────────────────────────────────

# 默认 system prompt
DEFAULT_SYSTEM_PROMPT = """你是一个浏览器自动化助手。你的任务是根据页面截图解析结果和用户目标，决定下一步应该执行什么操作。

页面截图被 OmniParser 解析成了结构化元素，每个元素包含：
- description: 元素的语义描述（如"提交按钮"、"搜索输入框"）
- bbox: 元素的像素坐标 [x1, y1, x2, y2]
- interactable: 是否可交互（可点击/输入）

**你必须严格遵循以下输出格式，不要输出任何其他内容：**

```
THOUGHT: <1-2句话解释你的推理过程>
ACTION: <操作类型>
TARGET: <目标元素的描述或坐标>
VALUE: <如果 ACTION 是 TYPE，输入的文本内容>
```

**操作类型（必须大写）：**
- CLICK: 点击元素
- TYPE: 向输入框输入文本
- SCROLL: 滚动页面（VALUE=up/down/down500/top/bottom）
- WAIT: 等待某个条件（VALUE=秒数）
- GOTO: 导航到新 URL（VALUE=URL）
- SWITCH_TAB: 切换标签页（VALUE=标签页序号）
- DONE: 任务已完成
- FAIL: 无法完成任务（VALUE=失败原因）

**决策规则：**
1. 优先选择与用户目标最相关的可交互元素
2. 描述要精确，让执行层能找到对应元素
3. 如果用户目标已达成，输出 DONE
4. 如果页面加载失败或找不到目标元素，输出 FAIL
5. 不要猜测不可交互的装饰元素

**重要：只输出上述格式，不要有多余文字。**"""


class VisionDecision:
    """
    LLM 决策引擎
    
    用法:
        llm = VisionDecision(provider="openai", api_key="sk-...")
        
        decision = llm.decide(
            omni_result=parse_result,
            user_goal="登录 GitHub",
            screenshot_path="page.png",
        )
        
        if decision.action == "CLICK":
            browser.click(decision.target)
    """
    
    PROVIDER_CLIENTS = {
        "openai": OpenAIClient,
        "anthropic": AnthropicClient,
        "zhipu": ZhipuClient,
        "doubao": DoubaoClient,
        "ollama": OllamaClient,
    }
    
    def __init__(
        self,
        provider: str = "openai",
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        max_history: int = 5,
        **llm_kwargs,
    ):
        """
        Args:
            provider: LLM 提供者 (openai/anthropic/zhipu/doubao/ollama)
            api_key: API Key，None 则从环境变量读取
            model: 模型名称，None 则使用提供者默认值
            system_prompt: 自定义 system prompt
            max_history: 保留多少条历史对话
            **llm_kwargs: 额外参数传给 LLM 客户端
        """
        self.provider = provider.lower()
        if self.provider not in self.PROVIDER_CLIENTS:
            raise ValueError(
                f"Unknown provider: {provider}. "
                f"Supported: {list(self.PROVIDER_CLIENTS.keys())}"
            )
        
        # 获取 API key
        if api_key is None:
            env_vars = {
                "openai": "OPENAI_API_KEY",
                "anthropic": "ANTHROPIC_API_KEY",
                "zhipu": "ZHIPU_API_KEY",
                "doubao": "ARK_API_KEY",
            }
            env_key = env_vars.get(self.provider, "")
            api_key = os.environ.get(env_key, "")
        
        if not api_key:
            print(f"[Warning] No API key for {self.provider}, using mock mode")
            self._mock_mode = True
            self._client = None
        else:
            self._mock_mode = False
            client_class = self.PROVIDER_CLIENTS[self.provider]
            # 只传 model（避免 None 覆盖默认值）
            init_kwargs = {"api_key": api_key}
            if model is not None:
                init_kwargs["model"] = model
            self._client = client_class(**init_kwargs, **llm_kwargs)
        
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        self.max_history = max_history
        self._conversation_history: List[ConversationMessage] = []
    
    def decide(
        self,
        omni_result,  # OmniResult from omniparser_wrapper
        user_goal: str,
        screenshot_path: Optional[str] = None,
        conversation_history: Optional[List[ConversationMessage]] = None,
        force_json: bool = False,
    ) -> LLMDecision:
        """
        让 LLM 根据 OmniParser 结果决定下一步操作
        
        Args:
            omni_result: OmniParser.parse() 返回的 OmniResult
            user_goal: 用户目标描述
            screenshot_path: 截图路径（用于多模态模型）
            conversation_history: 对话历史
            force_json: 是否强制 JSON 输出模式（某些模型）
        
        Returns:
            LLMDecision: 决策结果
        """
        # 构建 prompt
        elements_text = self._format_elements(omni_result)
        
        user_message = f"""## 用户目标
{user_goal}

## 页面元素列表
{elements_text}

## 输出你的决策："""
        
        # 构建消息列表
        messages = [
            {"role": "system", "content": self.system_prompt},
        ]
        
        # 加入历史对话
        history = conversation_history or self._conversation_history[-self.max_history:]
        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})
        
        messages.append({"role": "user", "content": user_message})
        
        if self._mock_mode:
            return self._mock_decide(omni_result, user_goal)
        
        # 调用 LLM
        try:
            raw = self._client.chat(messages)
            return self._parse_response(raw)
        except Exception as e:
            print(f"[VisionDecision] LLM call failed: {e}")
            return LLMDecision(
                action=ActionType.FAIL,
                value=f"LLM 调用失败: {e}",
                raw_response=str(e),
            )
    
    def _format_elements(self, omni_result) -> str:
        """将 OmniResult 格式化为可读文本"""
        if not omni_result.elements:
            return "（页面上未检测到可交互元素）"
        
        lines = []
        for i, elem in enumerate(omni_result.elements):
            x1, y1, x2, y2 = [int(v) for v in elem.bbox]
            w, h = x2 - x1, y2 - y1
            label = "[可交互]" if elem.interactable else "[装饰]"
            lines.append(
                f"- [{i+1}] {label} 「{elem.description}」"
                f" @({x1},{y1},{x2},{y2}) {w}x{h}px"
            )
        
        return "\n".join(lines)
    
    def _parse_response(self, raw: str) -> LLMDecision:
        """解析 LLM 原始输出"""
        raw = raw.strip()
        
        thought = ""
        action_str = "FAIL"
        target = ""
        value = ""
        
        # 解析行
        for line in raw.split("\n"):
            line = line.strip()
            if not line:
                continue
            
            if line.startswith("THOUGHT:"):
                thought = line[8:].strip()
            elif line.startswith("ACTION:"):
                action_str = line[7:].strip().upper()
            elif line.startswith("TARGET:"):
                target = line[7:].strip()
            elif line.startswith("VALUE:"):
                value = line[6:].strip()
        
        # 映射到 ActionType
        try:
            action = ActionType[action_str]
        except KeyError:
            action = ActionType.FAIL
        
        return LLMDecision(
            action=action,
            target=target,
            value=value,
            thought=thought,
            confidence=1.0,
            raw_response=raw,
        )
    
    def _mock_decide(self, omni_result, user_goal: str) -> LLMDecision:
        """模拟决策（无 API Key 时使用）"""
        # 找第一个可交互元素
        for elem in omni_result.elements:
            if elem.interactable:
                return LLMDecision(
                    action=ActionType.CLICK,
                    target=elem.description,
                    thought=f"[Mock] 模拟决策：点击「{elem.description}」",
                    confidence=0.5,
                    raw_response="[mock mode]",
                )
        
        return LLMDecision(
            action=ActionType.DONE,
            thought="[Mock] 未找到可交互元素，模拟完成",
            confidence=0.5,
            raw_response="[mock mode]",
        )
    
    def add_to_history(self, message: ConversationMessage):
        """添加到对话历史"""
        self._conversation_history.append(message)
        if len(self._conversation_history) > self.max_history * 2:
            self._conversation_history = self._conversation_history[-self.max_history * 2:]
    
    def clear_history(self):
        """清空对话历史"""
        self._conversation_history.clear()
    
    @property
    def is_mock(self) -> bool:
        return self._mock_mode


def format_elements_for_llm(omni_result) -> str:
    """便捷函数：格式化元素列表"""
    if not hasattr(omni_result, 'elements'):
        return "（无元素数据）"
    
    lines = []
    for i, elem in enumerate(omni_result.elements):
        x1, y1, x2, y2 = [int(v) for v in elem.bbox]
        label = "[可交互]" if elem.interactable else "[装饰]"
        lines.append(f"{i+1}. {label} 「{elem.description}」 @({x1},{y1},{x2},{y2})")
    
    return "\n".join(lines) if lines else "（无元素）"
