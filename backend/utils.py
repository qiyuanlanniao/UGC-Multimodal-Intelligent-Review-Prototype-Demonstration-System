# backend/utils.py
"""
通用工具函数（防弹版）
"""
import torch
import numpy as np
import re
from typing import Dict, Optional


def sanitize_text(text: str) -> str:
    """
    强力清理文本，只保留中文字符、英文字母、数字和空格。
    """
    if not text:
        return ""
    sanitized = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', ' ', text)
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    return sanitized


def extract_cross_modal_features(
        text: str = None,
        image_path: str = None,
        clip_model=None,
        clip_processor=None
) -> Dict:
    """
    安全提取跨模态联合表征特征。
    包含最终修复：用try-except隔离模型调用，处理模型对特定文本的内部崩溃。
    """
    features = {
        "text_embed": None,
        "image_embed": None,
        "alignment_score": 0.0,
        "semantic_gap": 0.0
    }

    if not clip_model or not clip_processor:
        print("⚠️ 模型未加载，跳过特征提取")
        return features

    # 1. 提取文本特征
    if text:
        clean_text = sanitize_text(text)
        print(f"🧼 文本清洗: '{text[:40].strip()}' -> '{clean_text[:40]}'")

        if len(clean_text) > 1:
            try:
                text_inputs = clip_processor(
                    text=clean_text[:512], return_tensors="pt", padding=True
                )

                # --- 防弹修复：将模型调用本身隔离在try-except块中 ---
                # 这是因为即使tokenizer输出有效，模型内部也可能因词汇表问题而失败。
                try:
                    with torch.no_grad():
                        text_embed = clip_model.get_text_features(**text_inputs)
                        if text_embed is not None:
                            features['text_embed'] = torch.nn.functional.normalize(text_embed, dim=-1)
                            print(f"✅ 文本特征提取成功")
                        else:
                            print("❌ 模型返回了None，即使输入看起来有效")
                except Exception as model_error:
                    print(f"❌ 模型在处理文本 '{clean_text[:40]}' 时内部崩溃: {model_error}")
                    # 崩溃后，text_embed 保持为 None，流程可以安全继续

            except Exception as e:
                print(f"❌ 文本特征提取的预处理或tokenize步骤失败: {e}")

    # 2. 提取图像特征 (此部分逻辑不变)
    if image_path:
        try:
            from PIL import Image
            image = Image.open(image_path).convert("RGB")
            image_inputs = clip_processor(
                images=image, return_tensors="pt"
            )
            with torch.no_grad():
                image_embed = clip_model.get_image_features(**image_inputs)
                if image_embed is not None:
                    features['image_embed'] = torch.nn.functional.normalize(image_embed, dim=-1)
        except Exception as e:
            print(f"❌ 图像特征提取失败: {e}")

    # 3. 计算对齐分数 (此部分逻辑不变)
    if features['text_embed'] is not None and features['image_embed'] is not None:
        similarity = torch.cosine_similarity(features['text_embed'], features['image_embed'], dim=-1)
        features['alignment_score'] = similarity.item()
        features['semantic_gap'] = 1 - features['alignment_score']
        print(f"✅ 图文对齐分数: {features['alignment_score']:.3f}")

    return features


def mock_moderation_result(content_type: str = "text") -> Dict:
    """生成模拟审核结果"""
    import random
    if content_type == "text":
        return {"violation": random.random() > 0.7, "type": random.choice(['暴力', '色情', '政治', '诈骗', '正常']),
                "confidence": round(random.uniform(0.7, 0.95), 3),
                "features": {"text_embed": None, "alignment_score": 0.0}, "is_mock": True}
    elif content_type == "image":
        return {"violation": random.random() > 0.7, "type": random.choice(['色情', '暴力', '正常', '武器', '血腥']),
                "confidence": round(random.uniform(0.6, 0.9), 3), "ocr_text": "模拟OCR结果",
                "features": {"image_embed": None, "alignment_score": 0.0}, "is_mock": True}