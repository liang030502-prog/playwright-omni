"""
env_diag.py — Playwright-Omni 环境诊断
运行方式: D:\OpenClaw\venv\Scripts\python.exe -X utf8 env_diag.py
"""
import sys
import os

print("=" * 60)
print("Playwright-Omni 环境诊断")
print("=" * 60)
print(f"Python: {sys.version.split()[0]}")
print(f"Executable: {sys.executable}")
print(f"VIRTUAL_ENV: {os.environ.get('VIRTUAL_ENV', '(未设置)')}")
print()

# 检查关键包
packages = {
    "openai": "openai",
    "torch": "torch",
    "transformers": "transformers",
    "playwright": "playwright",
    "PIL": "PIL",
    "numpy": "numpy",
    "ultralytics": "ultralytics",
}

print("[包检查]")
for name, import_name in packages.items():
    try:
        mod = __import__(import_name)
        ver = getattr(mod, "__version__", "(未知版本)")
        print(f"  ✅ {name}: {ver}")
    except ImportError:
        print(f"  ❌ {name}: 未安装")
    except Exception as e:
        print(f"  ⚠️  {name}: {e}")

print()

# 检查 playwright 路径
print("[Playwright 路径]")
pw_abs = r"D:\OpenClaw\venv\Lib\site-packages\playwright"
print(f"  预期路径: {pw_abs}")
print(f"  存在: {os.path.exists(pw_abs)}")

# 检查 BLIP2 模型
print()
print("[BLIP2 模型]")
blip_path = r"D:\AI_Cache\omniparser_models\icon_caption_florence\icon_caption"
print(f"  HF_CACHE: {blip_path}")
print(f"  存在: {os.path.exists(blip_path)}")
snapshots = os.path.join(blip_path, "hub", "models--Salesforce--blip2-flan-t5-xl", "snapshots")
if os.path.exists(snapshots):
    print(f"  Snapshots: {os.listdir(snapshots)}")

# 检查 YOLO 模型
print()
print("[YOLO 模型]")
yolo_path = r"D:\AI_Cache\omniparser_models\icon_detect\icon_detect"
print(f"  YOLO路径: {yolo_path}")
print(f"  存在: {os.path.exists(yolo_path)}")
model_file = os.path.join(yolo_path, "model.pt")
print(f"  model.pt 存在: {os.path.exists(model_file)}")

# 检查 Chromium
print()
print("[Chromium]")
chromium_path = r"D:\OpenClaw\browsers\chromium-1208\chrome-win64\chrome.exe"
print(f"  Chromium: {chromium_path}")
print(f"  存在: {os.path.exists(chromium_path)}")

print()
print("=" * 60)
print("如需安装缺失包，运行:")
print("  D:\\OpenClaw\\tools\\safe-pip.bat install openai")
print("  D:\\OpenClaw\\tools\\safe-pip.bat install torch --index-url https://download.pytorch.org/whl/cpu")
print("=" * 60)
