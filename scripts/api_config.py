# api_config.py — Playwright-Omni API 配置
# 上次更新: 2026-04-20
# 使用 jiekou.ai GPT-4o-mini 代理

import os

# ── HuggingFace 缓存路径（保护 C 盘）─────────────────
HF_CACHE = r"D:\AI_Cache\omniparser_models\icon_caption_florence\icon_caption"
os.environ["HF_HOME"] = HF_CACHE
os.environ["TRANSFORMERS_CACHE"] = HF_CACHE

# ── OpenAI (jiekou.ai 代理) ──────────────────────────
OPENAI_API_KEY   = "sk_71klFm30nktSl_WgkUbd94TJq3jSzLuYEYBcbqbgk5k"
OPENAI_BASE_URL  = "https://api.jiekou.ai/openai"
OPENAI_MODEL     = "gpt-4o-mini"

# ── Anthropic (可选) ────────────────────────────────
ANTHROPIC_API_KEY = ""

# ── 智谱 (可选) ──────────────────────────────────────
ZHIPU_API_KEY = ""

# ── 豆包 (可选) ──────────────────────────────────────
ARK_API_KEY = ""

# ── Ollama 本地 (可选) ──────────────────────────────
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5:3b"

# ── 设备模式 ─────────────────────────────────────────
# device="auto" | "cpu" | "cuda"
# 默认为 "auto"（自动分析），见 device_selector.py
DEVICE_MODE = "auto"
