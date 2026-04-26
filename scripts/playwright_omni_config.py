# playwright_omni_config.py — API 配置脚本
# 用法: python playwright_omni_config.py
"""
配置 GPT-4o API 凭证（OpenAI 兼容接口）
API Key:  sk_CEWSOjLCO7XP4d1HMyZZj-P6i2YsAYFJyj2sMfV6Q2Q
Base URL: https://api.jiekou.ai/openai
"""

import os
import sys
from pathlib import Path

# ── 凭证 ──────────────────────────────────────────────
OPENAI_API_KEY = "sk_CEWSOjLCO7XP4d1HMyZZj-P6i2YsAYFJyj2sMfV6Q2Q"
OPENAI_BASE_URL = "https://api.jiekou.ai/openai"
MODEL_NAME      = "gpt-4o"          # 可改为 gpt-4o-mini 加快速度

# ── 写入环境变量（当前进程）──────────────────────────
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
os.environ["OPENAI_BASE_URL"] = OPENAI_BASE_URL   # playwright-omni 暂不支持，读代码中的 base_url

# ── 同时写入配置文件，供后续脚本 import ──────────────
CONFIG_PATH = Path(__file__).parent / "api_config.py"
CONFIG_PATH.write_text(
    f"# ── Playwright-Omni API 配置 ──────────────────────────────\n"
    f"# 上次更新: 2026-04-19\n\n"
    f"OPENAI_API_KEY   = {OPENAI_API_KEY!r}\n"
    f"OPENAI_BASE_URL  = {OPENAI_BASE_URL!r}\n"
    f"OPENAI_MODEL     = {MODEL_NAME!r}\n\n"
    f"# 使用方法（在 orchestrator / vision_decision 之前 import）:\n"
    f"#   from api_config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL\n"
    f"#   agent = BrowserAgent(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL, ...)\n"
)
print(f"[Config] 写入 {CONFIG_PATH}")

# ── 验证连通性 ────────────────────────────────────────
print("[Config] 验证 API 连通性...")
try:
    from openai import OpenAI
    client = OpenAI(
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,
        timeout=30.0,
    )
    # 简单 chat 测试
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": "Hello, reply with just one word."}],
        max_tokens=10,
        temperature=0.1,
    )
    reply = response.choices[0].message.content
    print(f"[Config] ✅ API 连通成功！模型回复: {reply!r}")
    print(f"[Config] 已配置: base_url={OPENAI_BASE_URL}, model={MODEL_NAME}")
except Exception as e:
    print(f"[Config] ❌ API 验证失败: {e}")
    print(f"[Config] 请检查: 1) 网络  2) API Key  3) Base URL 是否正确")
    sys.exit(1)
