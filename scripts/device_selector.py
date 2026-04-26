"""
device_selector.py — 运行时设备选择器
分析任务特征，自动给出 CPU/GPU 推荐，供刘总决策

逻辑：
  1. 检测 GPU 显存可用量
  2. 检测当前系统负载（CPU/内存/显存）
  3. 分析任务特征（步骤数、是否复杂网页、是否多标签页）
  4. 结合模型加载开销，给出推荐
"""

import sys
import os
import time

sys.path.insert(0, r"D:\OpenClaw\workspace\skills\playwright-omni\scripts")


def get_gpu_info():
    """获取GPU状态"""
    try:
        import torch
        if not torch.cuda.is_available():
            return {"available": False, "name": None, "free_gb": 0, "total_gb": 0}

        free_bytes, total_bytes = torch.cuda.mem_get_info()
        device_name = torch.cuda.get_device_name(0)
        return {
            "available": True,
            "name": device_name,
            "free_gb": round(free_bytes / 1024**3, 1),
            "total_gb": round(total_bytes / 1024**3, 1),
        }
    except Exception as e:
        return {"available": False, "error": str(e)}


def get_cpu_load():
    """获取CPU负载"""
    try:
        import psutil
        return {
            "percent": psutil.cpu_percent(interval=0.5),
            "count": psutil.cpu_count(),
            "memory_free_gb": round(psutil.virtual_memory().available / 1024**3, 1),
        }
    except:
        return {"percent": None, "count": os.cpu_count(), "memory_free_gb": None}


def get_concurrent_tasks():
    """检测当前是否有其他AI任务在跑"""
    try:
        import psutil
        ai_processes = []
        keywords = ["python", "node", "ollama", "torch", "cuda"]
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                cmdline = " ".join(proc.info["cmdline"] or [])
                if any(k in cmdline.lower() for k in keywords) and proc.info["pid"] != os.getpid():
                    ai_processes.append(proc.info["name"])
            except:
                pass
        return len(ai_processes)
    except:
        return 0


def estimate_task_complexity(url: str, goal: str) -> str:
    """根据URL和目标描述估算任务复杂度"""
    # 复杂度关键词
    complex_keywords = ["登录", "注册", "支付", "下单", "填写", "表单", "复杂", "多步", "多个"]
    simple_keywords = ["打开", "浏览", "查看", "截图", "搜索", "点击", "滚动"]
    multi_tab_keywords = ["新标签", "多标签", "tab", "切换"]

    goal_lower = goal.lower()
    url_lower = url.lower()

    if any(k in goal_lower for k in multi_tab_keywords):
        return "multi_tab"
    elif any(k in goal_lower for k in complex_keywords):
        return "complex"
    elif any(k in goal_lower for k in simple_keywords):
        return "simple"
    else:
        return "medium"


def recommend_device(url: str, goal: str, max_steps: int = 20) -> dict:
    """
    主分析函数
    返回推荐结果供刘总决策
    """
    gpu = get_gpu_info()
    cpu_load = get_cpu_load()
    concurrent = get_concurrent_tasks()
    complexity = estimate_task_complexity(url, goal)

    # ── 显存需求估算 ─────────────────────────────────
    YOLO_VRAM_GB = 4.0        # YOLO 固定占用
    BLIP2_VRAM_GB = 8.0       # BLIP2 float32
    BROWSER_BASE_VRAM_GB = 1.1  # Chromium 基础占用
    SAFETY_MARGIN_GB = 1.0    # 安全余量

    # GPU 显存总需求（当前所有模型常驻 + 浏览器基础）
    gpu_needed = YOLO_VRAM_GB + BLIP2_VRAM_GB + BROWSER_BASE_VRAM_GB + SAFETY_MARGIN_GB

    # ── 推理速度估算 ──────────────────────────────────
    CPU_STEP_SEC = 7      # CPU单步 ~7秒（BLIP2 5s + YOLO 0.5s + LLM 2s）
    GPU_STEP_SEC = 2      # GPU单步 ~2秒
    STEP_TIME_CPU = max_steps * CPU_STEP_SEC
    STEP_TIME_GPU = max_steps * GPU_STEP_SEC

    # ── 决策逻辑 ────────────────────────────────────
    reasons = []
    score = 0  # 正分=推荐GPU，负分=推荐CPU

    # GPU可用性
    if not gpu["available"]:
        reasons.append("GPU不可用（CUDA检测失败），强制CPU")
        return {
            "recommendation": "CPU",
            "confidence": "HIGH",
            "reasons": reasons,
            "estimated_time_cpu": STEP_TIME_CPU,
            "estimated_time_gpu": None,
            "vram_free": 0,
            "vram_needed": gpu_needed,
        }

    reasons.append(f"GPU: {gpu['name']}，空闲 {gpu['free_gb']} GB / {gpu['total_gb']} GB")

    # 显存是否足够
    if gpu["free_gb"] >= gpu_needed:
        reasons.append(f"显存充足（需要{gpu_needed:.0f}GB，可用{gpu['free_gb']}GB）")
        score += 3
    elif gpu["free_gb"] >= YOLO_VRAM_GB + BROWSER_BASE_VRAM_GB + SAFETY_MARGIN_GB:
        reasons.append(f"显存仅够YOLO（需要{YOLO_VRAM_GB+BROWSER_BASE_VRAM_GB+SAFETY_MARGIN_GB:.0f}GB，可用{gpu['free_gb']}GB）")
        score -= 2
    else:
        reasons.append(f"显存不足（需要{gpu_needed:.0f}GB，可用仅{gpu['free_gb']}GB）")
        score -= 5

    # 并发任务检测
    if concurrent > 0:
        reasons.append(f"检测到{concurrent}个并发AI任务，占用额外显存/CPU")
        score -= 3

    # 任务复杂度
    if complexity == "complex":
        reasons.append(f"任务复杂度: {complexity}，GPU加速效果更明显")
        score += 2
    elif complexity == "simple":
        reasons.append(f"任务复杂度: {complexity}，CPU也能快速完成")
        score -= 1

    # 步数影响
    if max_steps > 15:
        reasons.append(f"任务步数较多（{max_steps}步），GPU加速节省大量时间")
        score += 2
    elif max_steps <= 5:
        reasons.append(f"任务步数较少（{max_steps}步），CPU时间也可接受")
        score -= 1

    # CPU负载
    if cpu_load["percent"] and cpu_load["percent"] > 80:
        reasons.append(f"CPU负载较高（{cpu_load['percent']:.0f}%），GPU分流可减轻CPU压力")
        score += 1
    elif cpu_load["percent"] and cpu_load["percent"] < 50:
        reasons.append(f"CPU负载较低（{cpu_load['percent']:.0f}%），CPU模式压力不大")
        score -= 1

    # ── 综合决策 ──────────────────────────────────────
    if score >= 3:
        recommendation = "GPU"
        confidence = "HIGH"
    elif score >= 0:
        recommendation = "GPU"
        confidence = "MEDIUM"
    elif score >= -2:
        recommendation = "CPU"
        confidence = "MEDIUM"
    else:
        recommendation = "CPU"
        confidence = "HIGH"

    time_saved = STEP_TIME_CPU - STEP_TIME_GPU
    time_saved_min = time_saved / 60

    # 时间对比
    if recommendation == "GPU":
        reasons.append(f"GPU预计节省 {time_saved_min:.1f} 分钟（CPU {STEP_TIME_CPU/60:.1f}min vs GPU {STEP_TIME_GPU/60:.1f}min）")

    return {
        "recommendation": recommendation,
        "confidence": confidence,
        "score": score,
        "reasons": reasons,
        "estimated_time_cpu_sec": STEP_TIME_CPU,
        "estimated_time_gpu_sec": STEP_TIME_GPU,
        "estimated_time_cpu_min": round(STEP_TIME_CPU / 60, 1),
        "estimated_time_gpu_min": round(STEP_TIME_GPU / 60, 1),
        "time_saved_min": round(time_saved / 60, 1),
        "vram_free": gpu["free_gb"],
        "vram_total": gpu["total_gb"],
        "vram_needed_approx": gpu_needed,
        "complexity": complexity,
        "concurrent_ai_tasks": concurrent,
        "cpu_load_percent": cpu_load["percent"],
    }


def format_recommendation(result: dict, url: str, goal: str, max_steps: int) -> str:
    """格式化输出，供刘总决策"""
    lines = []
    lines.append("=" * 50)
    lines.append("🖥️  设备选择分析报告")
    lines.append("=" * 50)
    lines.append("")
    lines.append(f"📌 任务: {goal[:40]}{'...' if len(goal)>40 else ''}")
    lines.append(f"🔗 URL:  {url[:50]}{'...' if len(url)>50 else ''}")
    lines.append(f"📊 步数: {max_steps}")
    lines.append(f"🔬 复杂度: {result['complexity']}")
    lines.append("")
    lines.append("─" * 50)
    lines.append("📐 硬件状态")
    lines.append(f"   GPU: {result['vram_free']}GB / {result['vram_total']}GB 空闲")
    lines.append(f"   显存需求估算: {result['vram_needed_approx']:.0f} GB")
    if result.get("cpu_load_percent"):
        lines.append(f"   CPU负载: {result['cpu_load_percent']:.0f}%")
    if result["concurrent_ai_tasks"] > 0:
        lines.append(f"   并发AI任务: {result['concurrent_ai_tasks']} 个")
    lines.append("")
    lines.append("─" * 50)
    lines.append("⏱️  时间估算")
    lines.append(f"   CPU模式:  ~{result['estimated_time_cpu_min']:.1f} 分钟")
    if result["recommendation"] == "GPU":
        lines.append(f"   GPU模式:  ~{result['estimated_time_gpu_min']:.1f} 分钟")
        lines.append(f"   ⏱️ 节省时间: ~{result['time_saved_min']:.1f} 分钟")
    lines.append("")
    lines.append("─" * 50)
    lines.append("📋 决策理由")
    for i, reason in enumerate(result["reasons"], 1):
        lines.append(f"   {i}. {reason}")
    lines.append("")
    lines.append("─" * 50)
    emoji = "🚀" if result["recommendation"] == "GPU" else "💻"
    conf_bar = "●●●●" if result["confidence"] == "HIGH" else "●○○○"
    lines.append(f"🤖 推荐设备: {emoji} {result['recommendation']}  [{conf_bar} {result['confidence']}]")
    lines.append(f"   综合评分: {result['score']:+d}（>0偏GPU，<0偏CPU）")
    lines.append("")
    lines.append("=" * 50)
    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="设备选择分析器")
    parser.add_argument("--url", required=True, help="目标URL")
    parser.add_argument("--goal", required=True, help="任务描述")
    parser.add_argument("--max-steps", type=int, default=20, help="最大步数")
    args = parser.parse_args()

    result = recommend_device(args.url, args.goal, args.max_steps)
    report = format_recommendation(result, args.url, args.goal, args.max_steps)
    print(report)

    # 输出结构化结果（供程序调用）
    print(f"\n[RESULT] recommendation={result['recommendation']} confidence={result['confidence']} score={result['score']}")
    return result


if __name__ == "__main__":
    main()
