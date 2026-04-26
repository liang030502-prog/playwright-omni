import sys, os
sys.path.insert(0, r'D:\OpenClaw\workspace\skills\playwright-omni\scripts')
os.environ['TRANSFORMERS_CACHE'] = r'D:\AI_Cache'
os.environ['HF_HOME'] = r'D:\AI_Cache\omniparser_models\icon_caption_florence\icon_caption'

from orchestrator import run_browser_task
from api_config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL

# 赛道1: Innovation - 雀巢Z世代产品创新
print('=== 赛道1: Innovation - 搜索雀巢创新案例 ===')
result = run_browser_task(
    url='https://duckduckgo.com/?q=Nestl%C3%A9+innovation+Gen+Z+product+strategy+2025+2026',
    goal='找到雀巢针对Z世代的产品创新策略和案例，包括新产品研发方向',
    llm_provider='openai',
    api_key=OPENAI_API_KEY,
    base_url=OPENAI_BASE_URL,
    model=OPENAI_MODEL,
    device='cuda',
    max_steps=6,
    headless=True,
)
print(f'Status: {result.status}, Steps: {result.total_steps}')
for s in result.steps:
    if s.success and s.thought:
        print(f'  Step {s.step}: {s.thought[:150]}')
if result.error_message:
    print(f'Error: {result.error_message}')
