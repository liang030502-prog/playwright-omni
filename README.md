# Playwright-Omni 🌐

> AI 驱动的有头模式浏览器自动化 — Playwright + OmniParser + 多模态 LLM

**状态：** 147 tests passing | Python 3.13 | Windows

---

## 项目简介

Playwright-Omni 是一个有头模式浏览器自动化框架，通过视觉 AI + 多模态大模型实现网页智能操作：

- **输入任务描述**（如"打开 GitHub，搜索 playwright"）
- **截图 + OmniParser 视觉解析**（YOLO 检测图标区域 + BLIP2 描述）
- **LLM 决策**（GPT-4o-mini / Claude / Ollama）
- **Playwright 执行**（点击、输入、滚动、标签页切换等）

适用于：自动填表、网页导航、视觉验证、复杂表单、爬虫、UI 测试。

---

## 架构

```
用户任务描述
    ↓
BrowserAgent (orchestrator.py — 编排层)
    ↓
┌─────────────────┬──────────────────┐
↓                  ↓
Playwright       OmniParser Wrapper
有头Chrome        视觉AI层
执行操作          ↓
    ↓           YOLO 检测可交互区域
截图 ──────────→ BLIP2-FlanT5-XL Caption
    ↓           结构化 UI 元素 + 语义描述
    ↓                  ↓
    └──── GPT-4o-mini ←┘
    LLM 决策 → 返回下一步 Action
    ↓
执行 Action (CLICK / TYPE / SCROLL / GOTO / SWITCH_TAB / ...)
```

---

## 目录结构

```
playwright-omni/
├── scripts/
│   ├── orchestrator.py         # BrowserAgent 核心编排
│   ├── playwright_headful.py    # BrowserSession 浏览器生命周期
│   ├── vision_decision.py      # LLM 决策 (VisionDecision)
│   ├── omniparser_wrapper.py   # OmniParser (YOLO + BLIP2)
│   ├── bh_tools.py             # 工具集: HTTP/keyboard/tab/dialog/download
│   ├── device_selector.py      # CPU/GPU 设备选择
│   ├── api_config.py           # API 配置
│   ├── preflight_check.py      # 环境预检
│   ├── cli.py                   # 命令行入口
│   ├── env_diag.py             # 环境诊断
│   └── run_search_tasks.py      # 批量任务运行
├── tests/                      # pytest 测试套件 (147 tests)
├── SKILL.md                    # OpenClaw Skill 元数据
├── CONTRIBUTING.md             # 贡献指南
├── README.md                   # 本文件
├── requirements.txt             # Python 依赖
├── run.bat                     # Windows 快速启动
└── run_multi.bat               # 多任务并行
```

---

## 快速开始

### 环境要求

- Python 3.12+
- Windows 10/11 (已配置)
- D:\OpenClaw\venv (已配置)
- Chromium (已安装)

### 安装依赖

```bash
pip install -r requirements.txt
playwright install chromium
```

### 运行自动化任务

```bash
# 单任务
python scripts/run_search_tasks.py

# 或直接运行 agent
python scripts/cli.py --task "打开 GitHub 首页"
```

### 运行测试

```bash
# 所有测试
pytest

# 单模块
pytest tests/test_orchestrator_action_exec.py -v

# 带详细输出
pytest tests/ -v --tb=short
```

---

## 核心模块

### `BrowserAgent` (orchestrator.py)

```python
from orchestrator import BrowserAgent

agent = BrowserAgent(
    api_key="sk-...",
    llm_provider="openai"   # openai | anthropic | zhipu | ollama
)
result = agent.run("打开 GitHub，搜索 playwright")
print(result.summary)
```

支持的 ActionType：

| Action | 说明 |
|--------|------|
| `CLICK` | 点击元素 |
| `TYPE` | 输入文本 |
| `SCROLL` | 滚动页面 |
| `WAIT` | 等待秒数 |
| `GOTO` | 导航 URL |
| `SWITCH_TAB` | 切换标签页 |
| `COORD_CLICK` | 坐标点击（fallback） |
| `JS_EXEC` | 执行 JavaScript |
| `HTTP_GET` | 纯 HTTP 请求 |
| `DONE` | 任务完成 |
| `FAIL` | 任务失败 |

### `OmniParserWrapper` (omniparser_wrapper.py)

```python
from omniparser_wrapper import OmniParserWrapper

parser = OmniParserWrapper(device="cuda")
result = parser.parse("screenshot.png")

for elem in result.elements:
    print(elem.bbox, elem.description, elem.interactable)
```

### `bh_tools.py` — 工具集

```python
from bh_tools import (
    http_get,           # 纯 HTTP GET（无浏览器）
    dispatch_key,       # 键盘事件（DOM 级别）
    is_internal_url,     # 判断 chrome:// URL
    prepare_upload,      # 文件上传
    DialogHandler,       # 自动处理弹窗
    DownloadHandler,     # 自动下载管理
    SelfHealingToolWriter,  # Self-healing 工具写入
)
```

---

## 环境预检

```bash
python scripts/preflight_check.py
```

检查项：
- ✅ Python 版本
- ✅ Playwright / Chromium
- ✅ OpenAI API Key
- ✅ OmniParser 模型路径
- ✅ YOLO 模型
- ✅ BLIP2 模型
- ✅ Ollama 连接（可选）

---

## LLM 提供者

| 提供者 | 模型 | 状态 |
|--------|------|------|
| **openai** | `gpt-4o-mini` | ✅ 已配置 |
| anthropic | `claude-3-5-sonnet` | ❌ 需配置 |
| zhipu | `glm-4v` | ❌ 需配置 |
| ollama | `qwen2.5:3b` | ⚠️ 本地 |

配置位置：`scripts/api_config.py`

---

## 测试覆盖

| 模块 | 测试文件 | 状态 |
|------|---------|------|
| orchestrator | `test_orchestrator*.py` | ✅ |
| vision_decision | `test_vision_decision.py` | ✅ |
| omniparser_wrapper | `test_omniparser_wrapper.py` | ✅ |
| bh_tools | `test_bh_tools_validation.py` | ✅ |
| device_selector | `test_device_selector.py` | ✅ |
| api_config | `test_api_config.py` | ✅ |
| preflight | `test_preflight.py` | ✅ |
| dialog/download | `test_bh_dialog.py`, `test_bh_download.py` | ✅ |
| self-healing | `test_bh_self_healing.py` | ✅ |

**总计：147 tests passing**

---

## CI/CD

GitHub Actions 配置：`.github/workflows/test.yml`

每次 push 自动运行：
```yaml
- pip install -r requirements.txt
- pytest tests/ --tb=short
```

---

## 开发指南

详见 [CONTRIBUTING.md](CONTRIBUTING.md)：

- 分支策略（`feature/*`, `fix/*`, `refactor/*`）
- Commit 规范（Conventional Commits）
- PR 工作流
- TDD 测试规范

---

## License

MIT