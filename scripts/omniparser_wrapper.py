# omniparser_wrapper.py — OmniParser 视觉解析层封装
# 职责：加载模型、解析截图、输出结构化 UI 元素
r"""
架构（Path C — BLIP2 替代 Florence2）：
  1. icon_detect   — YOLO 检测模型（OmniParser fine-tuned）
                      路径: D:\AI_Cache\omniparser_models\icon_detect\
  2. icon_caption  — BLIP2-FlanT5-large（Salesforce/blip2-flan-t5-xl）
                      通用 VLM，用于生成元素语义描述
                      下载时间: 约 10-15 分钟（今晚 12 点执行）

用法:
    from omniparser_wrapper import OmniParserWrapper
    
    parser = OmniParserWrapper()  # 首次调用加载模型（慢）
    result = parser.parse('screenshot.png')
    
    for elem in result.elements:
        print(elem.bbox, elem.description, elem.interactable)
"""

from __future__ import annotations

import os
import sys
import time
import json
import torch
import numpy as np
from PIL import Image
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Tuple, Union

# 模型路径
OMNIPARSER_BASE = r"D:\AI_Cache\omniparser_models"
ICON_DETECT_DIR = OMNIPARSER_BASE + r"\icon_detect\icon_detect"
ICON_CAPTION_DIR = OMNIPARSER_BASE + r"\icon_caption_florence\icon_caption\hub\models--Salesforce--blip2-flan-t5-xl\snapshots\0eb0d3b46c14c1f8c7680bca2693baafdb90bb28"


# ─────────────────────────────────────────────────────────
# 数据结构
# ─────────────────────────────────────────────────────────

@dataclass
class UIElement:
    """单个 UI 元素"""
    bbox: List[float]       # [x1, y1, x2, y2] 像素坐标
    description: str         # 语义描述
    interactable: bool      # 是否可交互
    score: float = 0.0      # 检测置信度


@dataclass
class OmniResult:
    """OmniParser 完整输出"""
    elements: List[UIElement]  # 检测到的所有元素
    image_size: Tuple[int, int]  # (width, height)
    parse_time_ms: float      # 解析耗时


# ─────────────────────────────────────────────────────────
# OmniParser 核心
# ─────────────────────────────────────────────────────────

class OmniParserWrapper:
    """
    OmniParser V2 推理封装
    
    模型加载策略：延迟加载（首次 parse 时加载，缓存在 self）
    支持 CPU 推理（无 GPU 时自动回退）
    """
    
    def __init__(
        self,
        detect_weights_dir: Optional[str] = None,
        caption_weights_dir: Optional[str] = None,
        device: Optional[str] = None,  # "cuda" / "cpu", None=自动
        confidence_threshold: float = 0.3,  # 过滤低置信度检测
    ):
        self.detect_weights_dir = detect_weights_dir or ICON_DETECT_DIR
        self.caption_weights_dir = caption_weights_dir or ICON_CAPTION_DIR
        self.confidence_threshold = confidence_threshold
        
        # 自动设备选择
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
        
        # 模型实例（延迟加载）
        self._detect_model = None
        self._caption_model = None
        self._caption_processor = None
        
        # 缓存
        self._last_parse_time = 0.0
    
    # ─────────────────────────────────────────────────────────
    # 模型加载
    # ─────────────────────────────────────────────────────────
    
    def _load_detect_model(self):
        """加载 YOLO 检测模型"""
        if self._detect_model is not None:
            return
        
        print(f"[OmniParser] Loading icon_detect model on {self.device}...")
        t0 = time.time()
        
        # YOLO 检测模型
        YOLO_PATH = self.detect_weights_dir
        
        # 动态导入 ultralytics（playwright 安装时附带）
        sys.path.insert(0, r"D:\OpenClaw\venv\Lib\site-packages")
        
        try:
            from ultralytics import YOLO
            # 加载 YOLOv8 模型
            model_file = os.path.join(YOLO_PATH, "model.pt")
            self._detect_model = YOLO(model_file)
            self._detect_model.to(self.device)
            print(f"[OmniParser] icon_detect loaded in {time.time()-t0:.1f}s")
        except ImportError:
            print("[OmniParser] ultralytics not found, using fallback YOLO loader...")
            self._detect_model = self._load_yolo_fallback(YOLO_PATH)
    
    def _load_yolo_fallback(self, weights_dir: str) -> Any:
        """YOLO 备用加载方式（直接用 PyTorch）"""
        import torch.nn as nn
        
        # 读取 YOLO 模型配置
        import yaml
        with open(os.path.join(weights_dir, "model.yaml"), "r") as f:
            cfg = yaml.safe_load(f)
        
        # 加载权重
        weights_file = os.path.join(weights_dir, "model.pt")
        checkpoint = torch.load(weights_file, map_location=self.device, weights_only=False)
        
        # 简单包装对象
        class YOLOWrapper:
            def __init__(self, ckpt, device):
                self.ckpt = ckpt
                self.device = device
                self.model = ckpt.get("model", ckpt)
            
            def to(self, device):
                self.model = self.model.to(device)
                self.device = device
                return self
            
            def __call__(self, source, imgsz=640, conf=0.25, verbose=False):
                # 简单推理接口
                results = self.model(
                    source,
                    imgsz=imgsz,
                    conf=conf,
                    verbose=verbose,
                    device=self.device,
                )
                return results
        
        return YOLOWrapper(checkpoint, self.device)
    
    def _load_caption_model(self):
        """加载 BLIP2-FlanT5-large 描述模型
        
        BLIP2 = CLIP Vision Encoder + Q-Former + FlanT5-Large
        模型: Salesforce/blip2-flan-t5-xl
        使用 HF_HOME/snapshots/xxx 路径直接加载，绕过网络模板查询
        """
        if self._caption_model is not None:
            return
        
        print(f"[OmniParser] Loading BLIP2 caption model on {self.device}...")
        t0 = time.time()
        
        try:
            from transformers import Blip2ForConditionalGeneration, Blip2Processor
            
            device = self.device
            cache_dir = self.caption_weights_dir  # D:\AI_Cache\...\snapshots\xxx
            
            self._caption_processor = Blip2Processor.from_pretrained(cache_dir)
            self._caption_model = Blip2ForConditionalGeneration.from_pretrained(
                cache_dir,
                torch_dtype=torch.float32 if device == "cpu" else torch.float16,
            )
            
            if device == "cuda":
                self._caption_model = self._caption_model.to(device)
            
            self._caption_model.eval()
            load_time = time.time() - t0
            print(f"[OmniParser] BLIP2 loaded in {load_time:.1f}s")
            
            # 估算模型大小
            try:
                param_count = sum(p.numel() for p in self._caption_model.parameters())
                print(f"[OmniParser] BLIP2 params: {param_count/1e9:.1f}B")
            except Exception:
                pass
            
        except Exception as e:
            print(f"[OmniParser] BLIP2 load failed: {e}")
            print("[OmniParser] Falling back to placeholder caption...")
            self._caption_model = None
            self._caption_processor = None
    
    def _ensure_models_loaded(self):
        """确保两个模型都已加载"""
        self._load_detect_model()
        self._load_caption_model()
    
    # ─────────────────────────────────────────────────────────
    # 核心推理
    # ─────────────────────────────────────────────────────────
    
    def parse(
        self,
        image: Union[str, Image.Image, np.ndarray],
        verbose: bool = False,
    ) -> OmniResult:
        """
        解析截图，输出结构化 UI 元素列表
        
        Args:
            image: 截图路径 / PIL Image / numpy array (RGB/BGR)
            verbose: 是否打印详细信息
        
        Returns:
            OmniResult: 包含 elements 列表和元数据
        """
        t0 = time.time()
        
        # 加载图片
        if isinstance(image, str):
            pil_img = Image.open(image).convert("RGB")
        elif isinstance(image, np.ndarray):
            pil_img = Image.fromarray(image)
        elif isinstance(image, Image.Image):
            pil_img = image
        else:
            raise TypeError(f"Unsupported image type: {type(image)}")
        
        img_w, img_h = pil_img.size
        
        # Step 1: YOLO 检测可交互区域
        boxes, scores, labels = self._detect(pil_img)
        
        # Step 2: BLIP2 描述每个区域（caption）
        elements = []
        for bbox, score in zip(boxes, scores):
            if score < self.confidence_threshold:
                continue
            
            # 裁剪区域图片
            x1, y1, x2, y2 = [int(v) for v in bbox]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(img_w, x2), min(img_h, y2)
            
            if x2 - x1 < 5 or y2 - y1 < 5:
                continue  # 太小，跳过
            
            cropped = pil_img.crop((x1, y1, x2, y2))
            
            # 描述
            description = self._caption(cropped, bbox)
            
            # 判断是否可交互（基于标签或描述关键词）
            interactable = self._is_interactable(description, labels)
            
            elements.append(UIElement(
                bbox=bbox,
                description=description,
                interactable=interactable,
                score=float(score),
            ))
        
        parse_time = (time.time() - t0) * 1000
        self._last_parse_time = parse_time
        
        if verbose:
            print(f"[OmniParser] Detected {len(elements)} elements in {parse_time:.0f}ms")
        
        return OmniResult(
            elements=elements,
            image_size=(img_w, img_h),
            parse_time_ms=parse_time,
        )
    
    def _detect(
        self,
        pil_img: Image.Image,
    ) -> Tuple[List[List[float]], List[float], List[str]]:
        """
        YOLO 检测，返回边界框、置信度、标签
        """
        self._load_detect_model()
        
        # 执行推理
        results = self._detect_model(
            pil_img,
            imgsz=640,
            conf=self.confidence_threshold,
            verbose=False,
            device=self.device,
        )
        
        boxes = []
        scores = []
        labels = []
        
        if results and len(results) > 0:
            r = results[0]
            if r.boxes is not None:
                for box in r.boxes:
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    conf = float(box.conf[0])
                    cls_id = int(box.cls[0])
                    
                    # OmniParser 的 YOLO 只检测 "icon/interactable" 一类
                    boxes.append([float(x1), float(y1), float(x2), float(y2)])
                    scores.append(conf)
                    labels.append(f"class_{cls_id}")
        
        return boxes, scores, labels
    
    def _caption(
        self,
        cropped: Image.Image,
        bbox: List[float],
    ) -> str:
        """
        BLIP2 生成元素描述
        
        BLIP2 接受 (image, text_prompt) → 生成描述文本
        Prompt 设计对结果影响很大，这里用简短指令。
        """
        if self._caption_model is None:
            # Fallback: 返回简单尺寸描述
            w, h = int(bbox[2]-bbox[0]), int(bbox[3]-bbox[1])
            return f"icon region ({w}x{h})"
        
        try:
            # 确保图片尺寸合理（BLIP2 对超大图会慢）
            w, h = cropped.size
            if w > 384 or h > 384:
                cropped = cropped.resize((384, 384), Image.LANCZOS)
            
            # BLIP2 text prompt for image captioning
            # "Question: describe this icon. Answer:" 是 BLIP2 标准 QA prompt
            prompt = "Question: what is this UI element? Answer:"
            
            inputs = self._caption_processor(
                images=cropped,
                return_tensors="pt",
            )
            
            if self.device == "cuda":
                inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # Generate with LLM
            generated_ids = self._caption_model.generate(
                **inputs,
                max_new_tokens=40,
                num_beams=3,
                do_sample=False,
            )
            
            # Decode
            generated_text = self._caption_processor.batch_decode(
                generated_ids,
                skip_special_tokens=True,
            )[0].strip()
            
            return generated_text if generated_text else f"icon ({int(bbox[2]-bbox[0])}x{int(bbox[3]-bbox[1])})"
        
        except Exception as e:
            # 任何错误都 fallback
            w, h = int(bbox[2]-bbox[0]), int(bbox[3]-bbox[1])
            return f"icon region ({w}x{h})"
    
    def _is_interactable(self, description: str, labels: List[str]) -> bool:
        """
        判断元素是否可交互
        基于描述中的关键词
        """
        description_lower = description.lower()
        
        interactable_keywords = [
            "button", "btn", "input", "field", "checkbox", "radio",
            "link", "menu", "tab", "icon", "search", "submit",
            "login", "sign", "click", "hover", "toggle", "switch",
            "dropdown", "select", "slider", "textbox",
        ]
        
        non_interactable_keywords = [
            "text", "label", "heading", "title", "paragraph",
            "image", "photo", "picture", "icon", "logo", "decor",
            "static",
        ]
        
        for kw in interactable_keywords:
            if kw in description_lower:
                # 排除明确非交互的
                for nk in non_interactable_keywords:
                    if nk in description_lower and kw not in ["icon"]:
                        return False
                return True
        
        return False
    
    # ─────────────────────────────────────────────────────────
    # 便捷方法
    # ─────────────────────────────────────────────────────────
    
    def parse_and_save(
        self,
        image_path: str,
        output_path: Optional[str] = None,
        draw_boxes: bool = True,
    ) -> OmniResult:
        """
        解析并可选地在图上画框保存
        """
        result = self.parse(image_path)
        
        if draw_boxes:
            self._draw_and_save(image_path, output_path or image_path, result)
        
        return result
    
    def _draw_and_save(
        self,
        input_path: str,
        output_path: str,
        result: OmniResult,
    ):
        """在图上画检测框并保存"""
        from PIL import ImageDraw, ImageFont
        
        img = Image.open(input_path).convert("RGB")
        draw = ImageDraw.Draw(img)
        
        img_w, img_h = result.image_size
        
        for elem in result.elements:
            x1, y1, x2, y2 = elem.bbox
            
            # 颜色：绿色=可交互，红色=不可交互
            color = (0, 255, 0) if elem.interactable else (255, 0, 0)
            
            # 画框
            draw.rectangle([x1, y1, x2, y2], outline=color, width=2)
            
            # 画标签
            label = elem.description[:30] + ("..." if len(elem.description) > 30 else "")
            draw.text((x1 + 4, y1 + 4), label, fill=color)
        
        img.save(output_path)
    
    def to_llm_prompt(
        self,
        result: OmniResult,
        user_goal: Optional[str] = None,
    ) -> str:
        """
        将解析结果格式化为 LLM 可读的自然语言描述
        """
        if not result.elements:
            return "页面上未检测到可交互元素。"
        
        lines = []
        if user_goal:
            lines.append(f"用户目标：{user_goal}\n")
        
        lines.append(f"页面尺寸：{result.image_size[0]}x{result.image_size[1]}")
        lines.append(f"检测到 {len(result.elements)} 个元素：\n")
        
        for i, elem in enumerate(result.elements):
            x1, y1, x2, y2 = [int(v) for v in elem.bbox]
            w, h = x2 - x1, y2 - y1
            label = "[可交互]" if elem.interactable else "[装饰]"
            lines.append(
                f"{i+1}. {label} 「{elem.description}」"
                f" 位置：({x1},{y1}) 大小：{w}x{h}px"
            )
        
        return "\n".join(lines)
    
    def find_element_by_description(
        self,
        result: OmniResult,
        description: str,
        exact: bool = False,
    ) -> Optional[UIElement]:
        """
        根据描述查找元素
        """
        description_lower = description.lower()
        
        for elem in result.elements:
            elem_desc_lower = elem.description.lower()
            
            if exact:
                if elem_desc_lower == description_lower:
                    return elem
            else:
                if description_lower in elem_desc_lower:
                    return elem
        
        return None
    
    def get_element_coords(
        self,
        elem: UIElement,
    ) -> Tuple[int, int, int, int]:
        """获取元素坐标 (x1, y1, x2, y2)"""
        return tuple(int(v) for v in elem.bbox)
    
    def get_element_center(
        self,
        elem: UIElement,
    ) -> Tuple[int, int]:
        """获取元素中心点"""
        x1, y1, x2, y2 = elem.bbox
        return int((x1 + x2) / 2), int((y1 + y2) / 2)
    
    @property
    def last_parse_time_ms(self) -> float:
        return self._last_parse_time
    
    def unload(self):
        """卸载模型，释放内存"""
        if self._detect_model is not None:
            del self._detect_model
            self._detect_model = None
        if self._caption_model is not None:
            del self._caption_model
            self._caption_model = None
        if self._caption_processor is not None:
            del self._caption_processor
            self._caption_processor = None
        
        if self.device == "cuda":
            torch.cuda.empty_cache()
        
        import gc
        gc.collect()
