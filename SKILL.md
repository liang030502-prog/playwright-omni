---
name: playwright-omni
description: >
  有头模式浏览器自动化 — Playwright + OmniParser YOLO + BLIP2 + 多模态LLM。
  AI 驱动的网页操作：截图 → YOLO检测 → BLIP2 caption → LLM决策 → 执行。
  用于：自动填表、网页导航、视觉验证、复杂表单、爬虫等。

  触发词：帮我操作浏览器 / 浏览器自动化 / 自动填表 / 网页任务
---

# Playwright-Omni 🌐

## 架构

```
用户 → BrowserAgent (编排层)
              ↓
   ┌──────────┴──────────┐
   ↓                      ↓
Playwright            OmniParser Wrapper
(执行层)              (视觉AI层)
   ↓                      ↓
有头Chrome ← 截图 → YOLO检测 (图标区域)
                          ↓
                    BLIP2-FlanT5-XL (caption)
                    Salesforce/blip2-flan-t5-xl
                    9.96 + 5.81 GB ✅ 已下载
                          ↓
                    结构化UI元素 + 语义描述
                          ↓
                    GPT-4o-mini (jiekou.ai) ✅
```

## 核心组件

| 模块 | 职责 | 路径 |
|------|------|------|
| `BrowserSession` | 浏览器生命周期、截图、元素操作 | `scripts/playwright_headful.py` |
| `OmniParserWrapper` | YOLO检测可交互区域 + BLIP2 caption | `scripts/omniparser_wrapper.py` |
| `VisionDecision` | LLM根据解析结果决定下一步操作 | `scripts/vision_decision.py` |
| `BrowserAgent` | 串联三者，形成完整AI自动化循环 | `scripts/orchestrator.py` |
| `device_selector` | 运行时自动分析CPU/GPU推荐 | `scripts/device_selector.py` |

## 安装状态

| 组件 | 状态 | 路径 |
|------|------|------|
| Playwright 1.58.0 | ✅ | `D:\OpenClaw\browsers\chromium-1208` |
| YOLO (icon_detect) | ✅ 38 MB | `D:\AI_Cache\omniparser_models/icon_detect/icon_detect/model.pt` |
| BLIP2-FlanT5-XL | ✅ 15.77 GB | `D:\AI_Cache\omniparser_models/icon_caption_florence/icon_caption/` |
| GPT-4o-mini (jiekou.ai) | ✅ 已配置 | `scripts/api_config.py` |
| RTX 4060 Ti 16GB | ✅ 可用 | — |

## LLM 提供者配置

| 提供者 | 默认模型 | API Key 状态 |
|--------|---------|-------------|
| **openai** (当前) | `gpt-4o-mini` | ✅ 已配置 |
| anthropic | `claude-3-5-sonnet` | ❌ 未配置 |
| zhipu | `glm-4v` | ❌ 未配置 |
| doubao | `doubao-vl-32k` | ❌ 未配置 |
| ollama | `qwen2.5:3b` | ⚠️ 本地需启动 |

## 快速开始

### 方式一：CLI（推荐）

```bash
# 预检（不执行任务）
python scripts/preflight_check.py

# 执行任务
python scripts/cli.py --url https://github.com/login --goal "登录 GitHub，用户名 myuser，密码 mypass"

# 带参数
python scripts/cli.py --url https://example.com --goal "填表" --max-steps 30 --headless --verbose

# Windows 快速启动
run.bat "https://github.com/login" "登录 GitHub，用户名 myuser，密码 mypass"
```

### 方式二：Python API

```python
import sys
sys.path.insert(0, r'D:\OpenClaw\workspace\skills\playwright-omni\scripts')

from orchestrator import run_browser_task

result = run_browser_task(
    url="https://github.com/login",
    goal="登录 GitHub，用户名 myuser，密码 mypass",
    llm_provider="openai",
    api_key="sk_71klFm30nktSl_WgkUbd94TJq3jSzLuYEYBcbqbgk5k",
    base_url="https://api.jiekou.ai/openai",
    model="gpt-4o-mini",
    device="auto",   # "cuda" / "cpu" / "auto"
    max_steps=20,
    headless=False,
)
print(result.summary())
```

### 方式三：OpenClaw Skill 触发词

触发后，device_selector 自动分析任务并输出推荐，等刘总决策后再执行。

```
刘总：帮我打开 GitHub 并登录
刘总：自动填表
刘总：浏览器任务
```

## CLI 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--url` | 目标 URL | 必填 |
| `--goal` | 任务目标描述 | 必填 |
| `--max-steps` | 最大步数 | 20 |
| `--headless` | 无头模式（不显示浏览器） | False |
| `--provider` | LLM 提供者 | openai |
| `--model` | 指定模型 | gpt-4o-mini |
| `--device` | 设备模式：`cuda` / `cpu` / `auto` | auto |
| `--output` | 结果输出 JSON 路径 | — |
| `--check` | 仅预检，不执行 | False |
| `--list-providers` | 列出支持的 LLM | False |
| `--analyze-only` | 仅运行 device_selector 分析，不执行任务 | False |

## VRAM 使用

| 状态 | VRAM 占用 |
|------|-----------|
| 系统空闲 | ~1.1 GB |
| YOLO 推理中 | ~4 GB |
| BLIP2 caption 推理中（GPU） | ~8 GB |
| **GPU总占用（推理时）** | ~13 GB |
| **RTX 4060 Ti 16GB 余量** | ~3 GB 可用 |

## CPU vs GPU 模式

**device_selector.py** 会在任务开始前自动分析，输出建议等刘总决策。

| 模式 | BLIP2推理速度 | 显存 | 适用场景 |
|------|-------------|------|---------|
| CPU (`torch.float32`) | ~2-5秒/图 | 0 GB | 显存紧张/后台任务 |
| GPU (`torch.float16`) | ~0.3-1秒/图 | ~8 GB | 步数多/复杂任务 |

**自动选择逻辑**：综合 GPU显存空闲量 + 并发任务数 + 任务复杂度 + 步数，给出推荐。

```python
from device_selector import recommend_device, format_recommendation

result = recommend_device(url="https://github.com/login", goal="登录GitHub", max_steps=15)
print(format_recommendation(result, url, goal, max_steps))
# → 输出推荐设备，等待刘总决策
```

## 文件结构

```
D:\OpenClaw\workspace\skills\playwright-omni\
├── SKILL.md                      ← 本文件
├── README.md                      ← 项目说明
├── requirements.txt               ← 依赖列表
├── run.bat                        ← Windows 快速启动
└── scripts\
      ├── __init__.py             ← 包导出
      ├── api_config.py            ← API 凭证配置（含 TRANSFORMERS_CACHE）⚠️
      ├── cli.py                   ← CLI 入口
      ├── preflight_check.py       ← 独立预检
      ├── device_selector.py        ← 运行时 CPU/GPU 自动分析 (P6 新增)
      ├── playwright_headful.py    ← 浏览器执行层
      ├── omniparser_wrapper.py    ← 视觉解析层 (YOLO + BLIP2)
      ├── vision_decision.py       ← LLM 决策层
      └── orchestrator.py         ← 编排层 + run_browser_task

D:\AI_Cache\omniparser_models\
├── icon_detect\icon_detect\model.pt              ✅ YOLO 权重
└── icon_caption_florence\icon_caption\
      ├── model-00001-of-00002.safetensors        ✅ 9.96 GB
      ├── model-00002-of-00002.safetensors        ✅ 5.81 GB
      ├── model.safetensors                        ✅ Florence caption
      ├── tokenizer.json / tokenizer_config.json  ✅
      └── hub\models--Salesforce--blip2-flan-t5-xl\  ✅ symlink
```

## Phase 完成状态

| Phase | 内容 | 状态 | 日期 |
|-------|------|------|------|
| 1 | 环境准备 | ✅ 完成 | 2026-04-18 |
| 2 | 执行层 + 视觉层 + 决策层 + 编排层 | ✅ 完成 | 2026-04-18 |
| 3 | 模型推理调通（YOLO ✅ / BLIP2 ✅） | ✅ 完成 | 2026-04-20 |
| 4 | LLM 决策层调通（GPT-4o-mini ✅） | ✅ 完成 | 2026-04-20 |
| 5 | 端到端自动化循环 | ✅ 完成 | 2026-04-20 |
| 6 | Skill 封装 + CLI | ✅ 完成 | 2026-04-20 |
| 7a | 错误重试机制 | ✅ 完成 | 2026-04-20 |
| 7b | 基础日志模块 | ✅ 完成 | 2026-04-20 |
| 7c | device_selector 集成 | ✅ 完成 | 2026-04-20 |
| 7d | TRANSFORMERS_CACHE 显式设置 | ✅ 完成 | 2026-04-20 |
| 7e | 端到端真实网页测试 | ✅ 完成 | 2026-04-21 |
| 7f | GPU模式CUDA验证 | ✅ 完成 | 2026-04-21 |

## 已知问题 / 限制

1. **显存占用高**：YOLO + BLIP2 同时加载约 13 GB，RTX 4060 Ti 16GB 够用但余量小
2. **无多标签页原生支持**：`SWITCH_TAB` 操作需要额外实现
3. **BLIP2 推理速度**：CPU 模式下较慢，建议 GPU 运行
4. **API Key 明文存储**：`api_config.py` 包含明文 Key，仅本地使用

## 更新日志

- **2026-04-20**: BLIP2 下载完成（hf-mirror.com 9.96 + 5.81 GB）；P4 LLM 决策验证通过；P6 CLI + 预检脚本完成
- **2026-04-18**: 项目初始化，YOLO + Playwright 完成，P1-P2 完成
