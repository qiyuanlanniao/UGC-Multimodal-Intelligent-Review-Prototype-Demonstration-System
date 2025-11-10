# backend/config.py
"""
跨模态UGC审核系统配置
"""

# 跨模态权重配置
CROSS_MODAL_CONFIG = {
    "text_weight": 0.4,      # 文本模态权重
    "image_weight": 0.4,     # 图像模态权重
    "audio_weight": 0.2,     # 音频模态权重
    "consistency_threshold": 0.65,  # 跨模态一致性阈值
}

# 违规关键词库
VIOLATION_KEYWORDS = {
    '暴力': [],
    '色情': [],
    '辱骂': [],
    '诈骗': []
}

SEMANTIC_VIOLATION_LABELS = {
    "色情": "这是一段描述色情、淫秽、性交、裸露或带有性挑逗意图的文字，常见于视频、直播、推特、电报等平台上的成人内容或福利姬信息",
    "暴力": "这是一段描述殴打、虐待、自残、持械攻击等具体暴力行为的文字",
    "辱骂": "这是一段文字或对话，包含了侮辱、谩骂、诅咒他人或进行人身攻击的言论",
    "诈骗": "这是一段意图通过虚假承诺、仿冒身份等欺骗手段，诱导他人进行转账、投资或泄露个人信息，以造成金融损失的文字"
}


# 模型配置
MODEL_CONFIG = {
    "clip_model": "OFA-Sys/chinese-clip-vit-base-patch16",  # Chinese-CLIP
    "whisper_model": "tiny",  # Whisper最小模型
    "text_model": "nghuyong/ernie-3.0-base-zh"  # 备用文本模型
}

# 采样配置
VIDEO_CONFIG = {
    "frame_count": 3,  # 关键帧数量
    "frame_positions": [0.15, 0.5, 0.85],  # 帧位置（百分比）
    "audio_sample_rate": 16000
}

DEGRADATION_CONFIG = {
    "enable_fallback": True,
    "min_alignment_score": 0.01,  # 低于此值视为失败
    "fallback_confidence": 0.75
}
