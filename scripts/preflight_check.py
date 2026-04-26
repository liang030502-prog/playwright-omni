"""
preflight_check.py - Playwright-Omni 独立预检脚本
无需运行任务，快速验证所有组件是否就绪

用法:
    D:/OpenClaw/venv/Scripts/python.exe -X utf8 preflight_check.py
"""

import sys
import os
import time

# 路径设置（必须最先）
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
AI_CACHE = r"D:\AI_Cache\omniparser_models\icon_caption_florence\icon_caption"
os.environ["HF_HOME"] = AI_CACHE
os.environ["TRANSFORMERS_CACHE"] = AI_CACHE

# playwright_headful.py 的固定路径（与 playwright_headful.py 保持一致）
_PW_PATH = r"D:\OpenClaw\venv\Lib\site-packages\playwright"
for _p in [_PW_PATH, SCRIPTS_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _check_import(module_name, import_stmt):
    """尝试导入，返回 (success, message)"""
    try:
        exec(import_stmt, {"__name__": "__main__"})
        return True, ""
    except ImportError as e:
        return False, f"未安装 ({e})"
    except Exception as e:
        return False, str(e)[:80]


def check_api():
    """1. API Key 验证"""
    print("\n[1/8] API Key (jiekou.ai GPT-4o-mini)")
    ok, err = _check_import("openai", "from openai import OpenAI")
    if not ok:
        print(f"  X openai 未安装或导入失败: {err}")
        return False
    try:
        from openai import OpenAI
        client = OpenAI(
            api_key="sk_71klFm30nktSl_WgkUbd94TJq3jSzLuYEYBcbqbgk5k",
            base_url="https://api.jiekou.ai/openai",
            timeout=30,
        )
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=5,
        )
        print(f"  OK 连通正常 | 模型: {r.model} | 回复: {r.choices[0].message.content}")
        return True
    except Exception as e:
        print(f"  X API 失败: {e}")
        return False


def check_playwright():
    """2. Playwright + Chromium"""
    print("\n[2/8] Playwright + Chromium")
    ok, err = _check_import("playwright", "from playwright_headful import BrowserSession, BrowserConfig")
    if not ok:
        print(f"  X playwright 导入失败: {err}")
        return False
    try:
        from playwright_headful import BrowserSession, BrowserConfig
        with BrowserSession() as browser:
            browser.goto("about:blank")
        print("  OK Playwright + Chromium 正常")
        return True
    except Exception as e:
        print(f"  X Playwright 失败: {e}")
        return False


def check_yolo():
    """3. OmniParser YOLO"""
    print("\n[3/8] OmniParser YOLO")
    ok, err = _check_import("torch", "import torch; from omniparser_wrapper import OmniParserWrapper")
    if not ok:
        print(f"  X torch/ultralytics 导入失败: {err}")
        return False
    try:
        from omniparser_wrapper import OmniParserWrapper
        parser = OmniParserWrapper(device="cpu")  # 强制 CPU 避免 CUDA 问题
        parser._load_detect_model()
        print("  OK OmniParser 加载成功")
        return True
    except FileNotFoundError as e:
        print(f"  ! 模型文件缺失: {e}")
        return False
    except Exception as e:
        print(f"  X OmniParser 失败: {e}")
        return False


def check_blip2():
    """4. BLIP2-FlanT5-XL 模型"""
    print("\n[4/8] BLIP2-FlanT5-XL 模型")
    ok, err = _check_import("torch", "import torch; from transformers import Blip2Processor")
    if not ok:
        print(f"  X torch/transformers 导入失败: {err}")
        return False
    try:
        import torch
        from transformers import Blip2Processor, Blip2ForConditionalGeneration

        t0 = time.time()
        cache_dir = AI_CACHE + r"\hub\models--Salesforce--blip2-flan-t5-xl\snapshots\0eb0d3b46c14c1f8c7680bca2693baafdb90bb28"
        proc = Blip2Processor.from_pretrained(cache_dir, local_files_only=True)
        model = Blip2ForConditionalGeneration.from_pretrained(
            cache_dir,
            local_files_only=True,
            torch_dtype=torch.float32,
        )
        elapsed = time.time() - t0

        # 简单推理测试
        from PIL import Image
        import numpy as np
        img = Image.fromarray(np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8))
        inputs = proc(images=img, return_tensors="pt")
        out = model.generate(**inputs, max_new_tokens=10)
        caption = proc.decode(out[0], skip_special_tokens=True)

        print(f"  OK 模型加载成功（{elapsed:.1f}s）")
        print(f"  OK 推理测试通过: {caption[:60]}")
        return True
    except FileNotFoundError as e:
        print(f"  ! BLIP2 模型文件缺失: {e}")
        return False
    except Exception as e:
        print(f"  X BLIP2 失败: {e}")
        return False


def check_llm_decision():
    """5. LLM 决策层"""
    print("\n[5/8] LLM 决策层")
    ok, err = _check_import("openai", "from openai import OpenAI")
    if not ok:
        print(f"  X openai 导入失败: {err}")
        return False
    try:
        from vision_decision import VisionDecision
        from omniparser_wrapper import OmniResult, UIElement

        mock_elements = [
            UIElement(description="Sign in button", bbox=[200, 300, 400, 360], interactable=True),
            UIElement(description="Username field", bbox=[200, 200, 500, 260], interactable=True),
        ]
        omni = OmniResult(elements=mock_elements, image_size=(1920, 1080), parse_time_ms=5.0)

        llm = VisionDecision(
            provider="openai",
            api_key="sk_71klFm30nktSl_WgkUbd94TJq3jSzLuYEYBcbqbgk5k",
            base_url="https://api.jiekou.ai/openai",
            model="gpt-4o-mini",
        )

        t0 = time.time()
        decision = llm.decide(omni, user_goal="登录 GitHub")
        elapsed = time.time() - t0

        print(f"  OK LLM 决策成功（{elapsed:.1f}s）")
        print(f"     Action: {decision.action.value} | Target: {decision.target}")
        return True
    except Exception as e:
        print(f"  X LLM 决策失败: {e}")
        return False


def check_disk():
    """6. 磁盘空间"""
    print("\n[6/8] 磁盘空间")
    try:
        import shutil
        d_free = shutil.disk_usage("D:").free / 1024**3
        print(f"  D: 空闲: {d_free:.1f} GB")
        if d_free < 5:
            print(f"  ! 磁盘空间不足，建议清理")
            return False
        print(f"  OK 磁盘空间充足")
        return True
    except Exception as e:
        print(f"  X 磁盘检查失败: {e}")
        return False


def check_cdp_mode():
    """7. CDP 接管模式（可选）"""
    print("\n[7/8] CDP 接管模式")
    try:
        from playwright_headful import BrowserConfig
        config = BrowserConfig(cdp_url="http://localhost:9222")
        print(f"  OK BrowserConfig 接受 cdp_url 参数: {config.cdp_url}")
        return True
    except Exception as e:
        print(f"  X CDP 配置失败: {e}")
        return False


def check_userdata_mode():
    """8. UserDataDir 模式（可选）"""
    print("\n[8/8] UserDataDir 模式")
    try:
        from playwright_headful import BrowserConfig
        config = BrowserConfig(user_data_dir=r"C:\Users\Administrator\AppData\Local\Google\Chrome\User Data")
        print("  OK BrowserConfig 接受 user_data_dir 参数")
        return True
    except Exception as e:
        print(f"  X UserDataDir 配置失败: {e}")
        return False


def main():
    print("=" * 60)
    print("Playwright-Omni 预检脚本")
    print("=" * 60)
    print(f"Python: {sys.version.split()[0]}")
    print(f"Python 可执行文件: {sys.executable}")
    print(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"sys.path[0]: {sys.path[0]}")
    print(f"HF_HOME: {os.environ.get('HF_HOME', '(未设置)')}")

    checks = [
        ("API Key", check_api),
        ("Playwright", check_playwright),
        ("OmniParser YOLO", check_yolo),
        ("BLIP2 模型", check_blip2),
        ("LLM 决策", check_llm_decision),
        ("磁盘空间", check_disk),
        ("CDP 接管模式", check_cdp_mode),
        ("UserDataDir 模式", check_userdata_mode),
    ]

    results = []
    for name, fn in checks:
        try:
            ok = fn()
            results.append((name, ok))
        except Exception as e:
            print(f"  X {name} 异常: {e}")
            results.append((name, False))

    # Summary
    print("\n" + "=" * 60)
    print("汇总")
    print("=" * 60)
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    for name, ok in results:
        icon = "OK" if ok else "X"
        print(f"  [{icon}] {name}")

    print(f"\n通过: {passed}/{total}")
    if passed == total:
        print("\n🎉 所有组件就绪！")
        print("运行示例:")
        print('  python cli.py --url https://github.com/login --goal "登录 GitHub，用户名 myuser，密码 mypass"')
    else:
        print(f"\n⚠️  {total - passed} 项异常，请修复后再试。")
        print()
        print("快速修复（运行）:")
        print("  D:\\OpenClaw\\workspace\\skills\\playwright-omni\\scripts\\fix_env.bat")

    return passed == total


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
