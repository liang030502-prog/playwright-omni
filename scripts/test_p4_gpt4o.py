"""
P4: LLM 决策层测试
使用真实 GPT-4o (jiekou.ai 代理) 进行端到端验证
"""
import os, sys, glob
sys.path.insert(0, os.path.dirname(__file__))

from playwright_omni_config import OPENAI_API_KEY, OPENAI_BASE_URL, MODEL_NAME
from vision_decision import VisionDecision
from omniparser_wrapper import OmniParserWrapper, OmniResult, UIElement

print(f"[P4] API: {OPENAI_BASE_URL}")
print(f"[P4] Model: {MODEL_NAME}")
print(f"[P4] Key: {OPENAI_API_KEY[:12]}...")

# 使用已有的截图
screenshots = sorted(glob.glob(r"D:\AI_Cache\omniparser_models\p5_test\step_*.png"))
if screenshots:
    test_screenshot = screenshots[-1]
    print(f"[P4] 使用截图: {test_screenshot}")
else:
    print("[P4] 无截图，使用模拟 OmniResult")
    test_screenshot = None

# 加载 OmniParser（YOLO 已就绪，BLIP2 未下载会 fallback）
omni = OmniParserWrapper(device="cpu")

if test_screenshot:
    print("[P4] 解析截图...")
    result = omni.parse(test_screenshot)
    print(f"[P4] 检测到 {len(result.elements)} 个元素")
    for e in result.elements[:5]:
        print(f"  - {e.description} @{[round(x,1) for x in e.bbox]} [交互={e.interactable}]")
else:
    result = OmniResult(
        elements=[
            UIElement(bbox=[100,200,200,250], description="Sign in 按钮", interactable=True, score=0.95),
            UIElement(bbox=[100,250,300,300], description="Username 输入框", interactable=True, score=0.90),
            UIElement(bbox=[100,310,300,360], description="Password 输入框", interactable=True, score=0.90),
            UIElement(bbox=[400,200,500,250], description="Logo 图片", interactable=False, score=0.80),
        ],
        image_size=(1280, 720),
        parse_time_ms=500,
    )

# GPT-4o 决策
llm = VisionDecision(
    provider="openai",
    api_key=OPENAI_API_KEY,
    base_url=OPENAI_BASE_URL,
)

print("\n[P4] GPT-4o 决策测试（目标：登录 GitHub）...")
decision = llm.decide(
    omni_result=result,
    user_goal="登录 GitHub，用户名 myuser，密码 mypass",
)

print(f"[P4] 决策结果:")
print(f"  THOUGHT: {decision.thought}")
print(f"  ACTION:  {decision.action.value}")
print(f"  TARGET:  {decision.target}")
print(f"  VALUE:   {decision.value}")
print(f"  原始:\n{decision.raw_response}")

print("\n[P4] ✅ GPT-4o 决策层测试通过！" if decision.action.value != "FAIL" else "\n[P4] ❌ 失败")
