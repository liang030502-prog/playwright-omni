import sys, os
sys.path.insert(0, r"D:\OpenClaw\workspace\skills\playwright-omni\scripts")
os.environ["TRANSFORMERS_CACHE"] = r"D:\AI_Cache"
os.environ["HF_HOME"] = r"D:\AI_Cache\omniparser_models\icon_caption_florence\icon_caption"
os.environ["PYTHONIOENCODING"] = "utf-8"

from orchestrator import run_browser_task
from api_config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL

tasks = [
    ("赛题5:宠物友好工作环境", "https://duckduckgo.com/?q=Nestl%C3%A9+pet+friendly+workplace+policy+office+2025", "找到雀巢宠物友好型工作环境相关信息"),
    ("赛题5-2:雀巢Purina", "https://duckduckgo.com/?q=Nestl%C3%A9+Purina+pet+care+strategy+2025+2026", "找到Purina宠物护理品牌相关信息"),
    ("赛题6:Health Science", "https://duckduckgo.com/?q=Nestl%C3%A9+Health+Science+nutrition+strategy+2025+2026", "找到Nestlé Health Science营养改善相关信息"),
    ("赛题6-2:特医食品", "https://duckduckgo.com/?q=Nestl%C3%A9+Health+Science+medical+nutrition+supplements+2025", "找到雀巢特医食品和营养补充剂相关信息"),
]

for name, url, goal in tasks:
    print(f"\n=== {name} ===")
    try:
        result = run_browser_task(url=url, goal=goal, llm_provider="openai", api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL, model=OPENAI_MODEL, device="cuda", max_steps=5, headless=True)
        print(f"Status: {result.status} | Steps: {result.total_steps}")
        for s in result.steps:
            if s.success and s.thought:
                print(f"  Step{s.step}: {s.thought[:400]}")
        if result.error_message:
            print(f"  Error: {result.error_message}")
    except Exception as e:
        print(f"Exception: {e}")