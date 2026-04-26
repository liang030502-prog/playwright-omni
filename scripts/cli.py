#!/usr/bin/env python
# cli.py — Playwright-Omni 命令行入口
# 用法: python cli.py --url https://github.com/login --goal "登录 GitHub" [--max-steps 20] [--headless] [--verbose]
"""
Playwright-Omni CLI

示例:
  python cli.py --url https://github.com/login --goal "登录 GitHub，用户名 myuser，密码 mypass"
  python cli.py --url https://example.com --goal "填表" --max-steps 30 --headless
  python cli.py --check                          # 仅预检，不执行
  python cli.py --list-providers                 # 列出支持的 LLM 提供者
"""

import sys as _sys
import os as _os
import json
import argparse
import traceback

# 路径：支持直接运行和包导入
_scripts_dir = _os.path.dirname(_os.path.abspath(__file__))
if _scripts_dir not in _sys.path:
    _sys.path.insert(0, _scripts_dir)

from api_config import (
    OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL,
    ANTHROPIC_API_KEY, ZHIPU_API_KEY, ARK_API_KEY,
    OLLAMA_BASE_URL, OLLAMA_MODEL,
)

PROVIDER_DEFAULT_MODEL = {
    "openai":   OPENAI_MODEL or "gpt-4o-mini",
    "anthropic": "claude-3-5-sonnet-20241022",
    "zhipu":    "glm-4v",
    "doubao":   "doubao-vl-32k",
    "ollama":   OLLAMA_MODEL or "qwen2.5:3b",
}

PROVIDER_API_KEY = {
    "openai":   OPENAI_API_KEY,
    "anthropic": ANTHROPIC_API_KEY,
    "zhipu":    ZHIPU_API_KEY,
    "doubao":   ARK_API_KEY,
    "ollama":   "ollama",  # 不需要真实 key
}


def run_check():
    """预检 — 委托给 standalone preflight_check.py"""
    import subprocess as _subprocess
    pf = _os.path.join(_scripts_dir, 'preflight_check.py')
    r = _subprocess.run([_sys.executable, '-X', 'utf8', pf], cwd=_scripts_dir)
    return r.returncode == 0

def list_providers():
    print("支持的 LLM 提供者：")
    print()
    print("  openai    - GPT-4o / GPT-4o-mini  (当前默认)")
    print("  anthropic - Claude-3.5-Sonnet")
    print("  zhipu     - GLM-4V（智谱）")
    print("  doubao    - Doubao-VL（字节）")
    print("  ollama    - 本地 qwen2.5:3b 等")
    print()
    print(f"当前配置:")
    print(f"  openai    → {OPENAI_BASE_URL} / {OPENAI_MODEL or 'gpt-4o-mini'}")
    print(f"  anthropic → {ANTHROPIC_API_KEY[:10] + '...' if ANTHROPIC_API_KEY else '未配置'}")
    print(f"  zhipu     → {ZHIPU_API_KEY[:10] + '...' if ZHIPU_API_KEY else '未配置'}")
    print(f"  doubao    → {ARK_API_KEY[:10] + '...' if ARK_API_KEY else '未配置'}")
    print(f"  ollama    → {OLLAMA_BASE_URL} / {OLLAMA_MODEL}")


def main():
    parser = argparse.ArgumentParser(
        description="Playwright-Omni — AI 浏览器自动化",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python cli.py --url https://github.com/login --goal "登录 GitHub，用户名 myuser，密码 mypass"
  python cli.py --check                        # 仅预检
  python cli.py --list-providers              # 列出支持的 LLM
        """,
    )
    parser.add_argument("--url", help="目标 URL")
    parser.add_argument("--goal", help="任务目标描述")
    parser.add_argument("--max-steps", type=int, default=20, help="最大步数（默认 20）")
    parser.add_argument("--headless", action="store_true", help="无头模式（不显示浏览器）")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    parser.add_argument("--provider", default="openai",
                        choices=["openai", "anthropic", "zhipu", "doubao", "ollama"],
                        help="LLM 提供者（默认 openai）")
    parser.add_argument("--model", help="指定模型（覆盖默认）")
    parser.add_argument("--output", help="结果输出 JSON 文件路径")
    parser.add_argument("--device", default="auto", choices=["cpu", "cuda", "auto"], help="设备模式（默认 auto）")
    parser.add_argument("--check", action="store_true", help="仅运行预检，不执行任务")
    parser.add_argument("--analyze-only", action="store_true", help="仅运行 device_selector 分析，不执行任务")
    parser.add_argument("--list-providers", action="store_true", help="列出支持的 LLM 提供者")
    parser.add_argument("--screenshot-dir", default=None, help="截图保存目录")
    # ── 浏览器接管模式 ─────────────────────────────────────
    parser.add_argument("--cdp-url", default=None,
                        help="CDP 接管模式：连接已运行的 Chrome，例如 http://localhost:9222")
    parser.add_argument("--user-data-dir", default=None,
                        help="UserDataDir 模式：用指定 Chrome profile 启动，例如 'C:\\Users\\...\\Chrome\\User Data'")

    args = parser.parse_args()

    if args.analyze_only:
        if not args.url or not args.goal:
            print("错误: --analyze-only 需要 --url 和 --goal")
            _sys.exit(1)
        from device_selector import recommend_device, format_recommendation
        result = recommend_device(args.url, args.goal, args.max_steps or 20)
        print(format_recommendation(result, args.url, args.goal, args.max_steps or 20))
        _sys.exit(0)

    if args.check:
        ok = run_check()
        _sys.exit(0 if ok else 1)

    if args.list_providers:
        list_providers()
        _sys.exit(0)

    if not args.url or not args.goal:
        parser.print_help()
        _sys.exit(1)

    # 预检
    print("[CLI] 开始预检...")
    if not run_check():
        print("[CLI] ❌ 预检失败，无法执行。请先修复上述问题。")
        _sys.exit(1)

    # 执行任务
    print(f"\n[CLI] 开始执行: {args.goal}")
    print(f"[CLI] URL: {args.url}")
    print(f"[CLI] LLM: {args.provider} / {args.model or PROVIDER_DEFAULT_MODEL.get(args.provider)}")
    print(f"[CLI] Max steps: {args.max_steps}")
    print()

    try:
        from orchestrator import run_browser_task

        result = run_browser_task(
            url=args.url,
            goal=args.goal,
            llm_provider=args.provider,
            api_key=PROVIDER_API_KEY.get(args.provider, ""),
            base_url=OPENAI_BASE_URL if args.provider == "openai" else None,
            model=args.model or PROVIDER_DEFAULT_MODEL.get(args.provider),
            device=args.device if args.device != "auto" else None,
            max_steps=args.max_steps,
            headless=args.headless,
            verbose=args.verbose,
            cdp_url=args.cdp_url,
            user_data_dir=args.user_data_dir,
            screenshot_dir=args.screenshot_dir,
        )

        print("\n" + "=" * 60)
        print("执行结果")
        print("=" * 60)
        print(f"  状态: {result.status}")
        print(f"  总步数: {result.total_steps}")
        print(f"  总耗时: {result.total_time_seconds:.1f}s")

        if result.steps:
            print("\n执行步骤:")
            for step in result.steps:
                icon = "✅" if step.success else "❌"
                print(f"  {icon} Step {step.step}: {step.action} → {step.target}")
                if step.error:
                    print(f"     错误: {step.error[:80]}")

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump({
                    "status": result.status,
                    "total_steps": result.total_steps,
                    "total_time_seconds": result.total_time_seconds,
                    "steps": [
                        {
                            "step": s.step,
                            "action": s.action,
                            "target": s.target,
                            "value": s.value,
                            "thought": s.thought,
                            "success": s.success,
                            "error": s.error,
                        }
                        for s in result.steps
                    ],
                }, f, ensure_ascii=False, indent=2)
            print(f"\n结果已保存: {args.output}")

        _sys.exit(0 if result.status == "success" else 1)

    except Exception as e:
        print(f"\n[CLI] ❌ 执行异常: {e}")
        if args.verbose:
            traceback.print_exc()
        _sys.exit(1)


if __name__ == "__main__":
    main()
