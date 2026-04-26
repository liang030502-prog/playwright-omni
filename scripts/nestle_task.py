import sys, os
sys.path.insert(0, r'D:\OpenClaw\workspace\skills\playwright-omni\scripts')
os.environ['TRANSFORMERS_CACHE'] = r'D:\AI_Cache'
os.environ['HF_HOME'] = r'D:\AI_Cache\omniparser_models\icon_caption_florence\icon_caption'

from orchestrator import run_browser_task
from api_config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL

# Try DuckDuckGo instead of Google (less likely to block)
print('=== Test: DuckDuckGo Search ===')
result = run_browser_task(
    url='https://duckduckgo.com/?q=Nestl%C3%A9+CEO+Challenge+2026+topics+challenges',
    goal='在搜索结果中找到 Nestlé CEO Challenge 2026 相关的链接和赛题信息',
    llm_provider='openai',
    api_key=OPENAI_API_KEY,
    base_url=OPENAI_BASE_URL,
    model=OPENAI_MODEL,
    device='cuda',
    max_steps=8,
    headless=True,
)
print(f'Status: {result.status}')
print(f'Steps: {result.total_steps}')
for s in result.steps:
    print(f'  Step {s.step}: {s.action} {s.target} -> {s.success}')
    if s.thought:
        print(f'    Thought: {s.thought[:200]}')
if result.error_message:
    print(f'Error: {result.error_message}')
