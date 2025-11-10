# backend/models.py
"""
模型加载与管理模块（生产级优化版）
"""
import warnings
from typing import Dict, Optional

warnings.filterwarnings("ignore")


class ModelManager:
    """模型管理器单例，确保模型只被加载一次"""
    _instance = None
    _models: Dict = {}
    _status: Dict = {}
    _is_initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load_models(self) -> Dict:
        """加载所有模型。使用标志位防止重复加载。"""
        if self._is_initialized:
            return self._models

        print("=" * 60)
        print("首次初始化跨模态表征模型...")
        print("=" * 60)

        self._load_clip()
        self._load_whisper()

        self._is_initialized = True
        print("=" * 60)
        print("📊 模型状态汇总:")
        for name, status in self._status.items():
            ready_status = '✅ 可用' if status else '❌ 不可用'
            print(f"   - {name.upper()} 模型: {ready_status}")
        print("=" * 60)
        return self._models

    def _load_clip(self):
        """加载Chinese-CLIP模型和处理器"""
        try:
            from transformers import ChineseCLIPProcessor, ChineseCLIPModel
            print("📦 正在加载 Chinese-CLIP 模型 (首次加载可能需要下载)...")
            model_name = "OFA-Sys/chinese-clip-vit-base-patch16"
            self._models['clip_model'] = ChineseCLIPModel.from_pretrained(model_name)
            self._models['clip_processor'] = ChineseCLIPProcessor.from_pretrained(model_name)
            self._models['clip_model'].eval()
            self._status['clip'] = True
            print("✅ Chinese-CLIP 加载成功")
        except Exception as e:
            print(f"❌ CLIP加载失败: {e}")
            self._models['clip_model'], self._models['clip_processor'] = None, None
            self._status['clip'] = False

    def _load_whisper(self):
        """加载Whisper模型"""
        try:
            import whisper
            print("📦 正在加载 Whisper 模型 (首次加载可能需要下载)...")
            # 使用 'base' 模型，在效果和速度上是比 'tiny' 更好的平衡点
            self._models['whisper'] = whisper.load_model("base")
            self._status['whisper'] = True
            print("✅ Whisper 加载成功")
        except Exception as e:
            print(f"❌ Whisper加载失败: {e}")
            self._models['whisper'] = None
            self._status['whisper'] = False

    def get_model(self, name: str):
        """安全地获取一个已加载的模型"""
        return self._models.get(name)

    def is_ready(self, name: str) -> bool:
        """检查特定模型是否已准备就绪"""
        return self._status.get(name, False)

    def get_status(self) -> Dict:
        """获取所有模型的状态"""
        return self._status.copy()


# 创建全局单例
model_manager = ModelManager()