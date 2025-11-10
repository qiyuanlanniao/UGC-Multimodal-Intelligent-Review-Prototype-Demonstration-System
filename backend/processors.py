# backend/processors.py
"""
内容审核处理器 - 生产级实现 (PaddleOCR
"""
import os
import tempfile
import random
from pathlib import Path
from typing import Dict, List
import cv2
import librosa
import numpy as np
import torch

from web_ocr import browser_manager

from config import VIOLATION_KEYWORDS, CROSS_MODAL_CONFIG, VIDEO_CONFIG, SEMANTIC_VIOLATION_LABELS
from utils import extract_cross_modal_features, mock_moderation_result
from models import model_manager
import subprocess
import shutil


class TextProcessor:
    """文本审核处理器 - [V3] 关键词 + 优化版CLIP语义匹配 + 健壮逻辑"""

    @staticmethod
    def process(text: str) -> Dict:
        if not text or len(text.strip()) < 2:
            return {"violation": False, "type": "正常", "confidence": 0.0, "method": "空文本"}

        # --- 阶段一: 关键词匹配 (最高优先级) ---
        text_lower = text.lower()
        for vtype, keywords in VIOLATION_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    confidence = min(0.85 + text_lower.count(keyword) * 0.1, 0.98)
                    result = {
                        "violation": True, "type": vtype, "confidence": round(confidence, 3),
                        "matched_keyword": keyword, "method": "关键词匹配"
                    }
                    print(f"✅ 关键词命中: '{keyword}' -> {vtype}")
                    # 关键词命中后，依然提取特征并返回
                    models = model_manager.load_models()
                    result['features'] = extract_cross_modal_features(text=text, clip_model=models.get('clip_model'),
                                                                      clip_processor=models.get('clip_processor'))
                    return result

        # --- 阶段二: CLIP 语义相似度匹配 (若关键词未命中) ---
        print("🔍 关键词未命中，启动CLIP语义相似度分析...")
        models = model_manager.load_models()
        clip_model = models.get('clip_model')
        clip_processor = models.get('clip_processor')

        features = extract_cross_modal_features(text=text, clip_model=clip_model, clip_processor=clip_processor)

        if clip_model and features['text_embed'] is not None:
            try:
                labels = list(SEMANTIC_VIOLATION_LABELS.values())
                label_types = list(SEMANTIC_VIOLATION_LABELS.keys())

                inputs = clip_processor(text=labels, return_tensors="pt", padding=True)
                with torch.no_grad():
                    label_embeds = clip_model.get_text_features(**inputs)
                    label_embeds = torch.nn.functional.normalize(label_embeds, dim=-1)
                    probs = torch.cosine_similarity(features['text_embed'], label_embeds)

                max_prob, max_idx = probs.max(dim=0)
                confidence = max_prob.item()

                semantic_threshold = 0.26  # 可以微调这个阈值

                if confidence > semantic_threshold:
                    matched_type = label_types[max_idx.item()]
                    scaled_confidence = (confidence - semantic_threshold) / (1 - semantic_threshold)

                    result = {
                        "violation": True,
                        "type": matched_type,
                        "confidence": round(min(scaled_confidence * 0.8, 0.9), 3),
                        "method": "CLIP语义匹配",
                        "semantic_score": round(confidence, 3)
                    }
                    print(f"✅ CLIP语义命中: '{text[:30]}...' 最匹配 -> {matched_type} (相似度: {confidence:.3f})")
                    result['features'] = features
                    return result

            except Exception as e:
                print(f"⚠️ CLIP语义分析失败: {e}")

        # --- 阶段三: 最终判定 (若以上全未命中) ---
        print("✅ 所有检查通过，内容判定为安全。")
        result = {"violation": False, "type": "正常", "confidence": 0.95, "method": "安全文本"}
        result['features'] = features
        return result


class ImageProcessor:
    """图像审核处理器 - 使用高精度的Web OCR（已修复路径问题）"""

    @staticmethod
    def process(image_path: str) -> Dict:
        # --- 核心修复：将传入的任何路径都转换为绝对路径 ---
        # Selenium的 .send_keys 需要一个绝对路径才能正确定位和上传文件。
        # os.path.abspath() 会将 "upload\image.png" 这样的相对路径
        # 转换为 "D:\your_project_folder\backend\upload\image.png" 这样的绝对路径。
        absolute_image_path = os.path.abspath(image_path)

        # 增加一个健壮性检查，确保文件确实存在
        if not os.path.exists(absolute_image_path):
            print(f"❌ 错误：图片文件在转换路径后未找到: {absolute_image_path}")
            return {"error": f"图片文件未找到: {absolute_image_path}", "method": "路径错误"}
        # --- 修复结束 ---

        print(f"🔎 使用Web OCR进行高精度文本识别 (路径: {absolute_image_path})...")
        # 将转换后的绝对路径传递给浏览器管理器
        ocr_text = browser_manager.recognize_text(absolute_image_path)

        if ocr_text:
            print(f"✅ OCR成功 (Web): {ocr_text[:50]}...")
        else:
            print("⚠️ OCR未检测到文本 (Web)")

        # ↓↓↓ 后续的审核逻辑完全复用，无任何改动 ↓↓↓

        # 2. OCR文本审核（高优先级）
        if len(ocr_text) > 2:
            ocr_detection = TextProcessor.process(ocr_text)
            if ocr_detection['violation']:
                models = model_manager.load_models()
                features = extract_cross_modal_features(text=ocr_text,
                                                        image_path=absolute_image_path,
                                                        clip_model=models.get('clip_model'),
                                                        clip_processor=models.get('clip_processor'))
                return {"violation": True, "type": f"OCR-{ocr_detection['type']}",
                        "confidence": ocr_detection['confidence'], "ocr_text": ocr_text[:100], "features": features,
                        "method": "Web OCR优先"}

        # 3. CLIP视觉分析
        from PIL import Image
        models = model_manager.load_models()
        clip_detection = None
        if models.get('clip_model') and models.get('clip_processor'):
            try:
                image = Image.open(absolute_image_path).convert("RGB")
                label_texts = ["这张图片包含色情内容或裸露", "这张图片包含暴力或血腥画面", "这张图片是正常的人物照片",
                               "这张图片是正常风景或物品", "这张图片包含武器或危险物品", "这张图片包含血腥或恐怖画面"]
                inputs = models['clip_processor'](text=label_texts, images=image, return_tensors="pt", padding=True)
                with torch.no_grad():
                    outputs = models['clip_model'](**inputs)
                    probs = outputs.logits_per_image.softmax(dim=1)[0]
                max_prob, max_idx = probs.max(dim=0)
                confidence = max_prob.item()
                violation_labels = [0, 1, 4, 5]
                is_violation = max_idx.item() in violation_labels and confidence > 0.55
                features = extract_cross_modal_features(text=ocr_text,
                                                        image_path=absolute_image_path,
                                                        clip_model=models.get('clip_model'),
                                                        clip_processor=models.get('clip_processor'))
                clip_detection = {"violation": is_violation,
                                  "type": ["色情", "暴力", "正常", "正常", "武器", "血腥"][max_idx.item()],
                                  "confidence": round(confidence, 3), "features": features, "method": "CLIP视觉",
                                  "视觉匹配": label_texts[max_idx.item()][:15] + "..."}
                if is_violation:
                    print(f"✅ CLIP视觉命中: {clip_detection['type']} ({confidence:.3f})")
                else:
                    print(f"✅ CLIP视觉正常: {clip_detection['type']} ({confidence:.3f})")
            except Exception as e:
                print(f"⚠️ CLIP视觉分析失败: {e}")

        # 4. 优先返回CLIP结果
        if clip_detection:
            clip_detection['ocr_text'] = ocr_text[:100]
            return clip_detection

        # 5. 最终降级
        print("⚠️ 所有方法失败，使用模拟结果")
        features = extract_cross_modal_features(text=ocr_text,image_path=absolute_image_path,
                                                clip_model=models.get('clip_model'),
                                                clip_processor=models.get('clip_processor'))
        result = mock_moderation_result("image")
        result['ocr_text'] = ocr_text[:100] if ocr_text else "无文本内容"
        result['features'] = features
        result['method'] = "模拟降级"
        return result


class AudioProcessor:
    """音频审核处理器 - Whisper转录 + 文本分析"""

    # ... (This class remains completely unchanged)
    @staticmethod
    def process(audio_path: str) -> Dict:
        transcript = ""
        models = model_manager.load_models()
        if models.get('whisper'):
            try:
                result = models['whisper'].transcribe(audio_path, language='zh')
                transcript = result.get('text', '').strip()
                if transcript:
                    print(f"✅ Whisper转录成功: {transcript[:50]}...")
                else:
                    print("⚠️ Whisper未检测到语音")
            except Exception as e:
                print(f"⚠️ Whisper转录失败: {e}")
        text_result = TextProcessor.process(transcript)
        features = {"transcript": transcript[:200] if transcript else "无转录", "audio_duration": 0,
                    "speech_speed": "unknown"}
        try:
            y, sr = librosa.load(audio_path)
            features['audio_duration'] = len(y) / sr
            if len(transcript) > 0 and features['audio_duration'] > 0:
                char_per_sec = len(transcript) / features['audio_duration']
                if char_per_sec > 8:
                    features['speech_speed'] = "fast"
                elif char_per_sec > 4:
                    features['speech_speed'] = "normal"
                else:
                    features['speech_speed'] = "slow"
        except Exception as e:
            print(f"⚠️ 音频特征提取失败: {e}")
        return {"violation": text_result['violation'], "type": text_result['type'],
                "confidence": text_result['confidence'], "transcript": transcript[:200], "features": features,
                "method": f"Whisper+{text_result['method']}"}


class VideoProcessor:
    """视频审核处理器 - [已增强] 增加自动转码，确保Web兼容性和处理稳定性"""

    @staticmethod
    def _transcode_to_h264(source_path: str) -> (str, bool):
        """
        将视频文件转码为 H.264/AAC 编码的 MP4。
        这是保证Web和处理库（如cv2）兼容性的关键步骤。
        返回 (处理后的文件路径, 是否创建了新文件)
        """
        if not shutil.which('ffmpeg'):
            print("⚠️ ffmpeg 未找到，跳过视频转码。如果处理失败，请安装ffmpeg。")
            return source_path, False

        # 检查文件扩展名，如果已经是 .mp4，可以考虑跳过（但编码可能不兼容）
        # 为了稳定性，我们统一处理所有传入的视频

        target_path = tempfile.mktemp(suffix='.mp4')
        print(f"🔧 正在将视频转码为Web兼容格式 (H.264/AAC)...")

        try:
            # -c:v libx264: 使用 H.264 视频编码器
            # -c:a aac: 使用 AAC 音频编码器
            # -pix_fmt yuv420p: 保证像素格式的最大兼容性
            # -y: 如果目标文件已存在则覆盖
            command = [
                'ffmpeg', '-i', source_path, '-c:v', 'libx264',
                '-c:a', 'aac', '-pix_fmt', 'yuv420p', '-y', target_path
            ]
            result = subprocess.run(
                command, capture_output=True, text=True, check=True, timeout=120
            )
            print(f"✅ 视频转码成功，新文件位于: {target_path}")
            return target_path, True
        except subprocess.CalledProcessError as e:
            print(f"❌ 视频转码失败: {e.stderr[:500]}...")
            print("...将尝试使用原始文件进行处理。")
            if os.path.exists(target_path): os.unlink(target_path)
            return source_path, False
        except Exception as e:
            print(f"❌ 转码过程中发生未知错误: {e}")
            if os.path.exists(target_path): os.unlink(target_path)
            return source_path, False

    @staticmethod
    def process(video_path: str) -> Dict:
        path_to_process = video_path
        was_transcoded = False

        try:
            # --- 核心步骤 1: 视频转码 ---
            path_to_process, was_transcoded = VideoProcessor._transcode_to_h264(video_path)

            # --- 核心步骤 2: 使用转码后（或原始）的文件进行所有后续处理 ---
            results = {"frames": [], "audio": {}, "cross_modal_fusion": {}}
            audio_path = tempfile.mktemp(suffix='.wav')

            try:
                print("🎵 提取音频...")
                # 使用 path_to_process
                subprocess.run(
                    ['ffmpeg', '-i', path_to_process, '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', '-y',
                     audio_path], capture_output=True, check=True, timeout=30)
                if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
                    results['audio'] = AudioProcessor.process(audio_path)
                    print(f"✅ 音频处理完成: {results['audio']['type']}")
                else:
                    raise Exception("音频文件为空")
            except Exception as e:
                print(f"⚠️ 音频提取失败: {str(e)[:100]}...，使用模拟结果")
                results['audio'] = {"violation": False, "type": "正常", "confidence": 0.0, "transcript": "音频提取失败"}
            finally:
                if os.path.exists(audio_path):
                    try:
                        os.unlink(audio_path)
                    except:
                        pass

            print("🎬 提取关键帧...")
            # 使用 path_to_process
            cap = cv2.VideoCapture(path_to_process)
            if not cap.isOpened(): raise Exception(f"无法打开视频文件: {path_to_process}")

            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            duration = total_frames / fps if fps > 0 else 1
            frame_positions = VIDEO_CONFIG["frame_positions"]
            frame_indices = [int(total_frames * pos) for pos in frame_positions]
            texts_from_frames = []

            for i, frame_idx in enumerate(frame_indices):
                try:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                    ret, frame = cap.read()
                    if ret:
                        print(f"  📸 处理第{i + 1}帧 (位置: {frame_positions[i] * 100:.0f}%)")
                        frame_path = tempfile.mktemp(suffix='.jpg')
                        cv2.imwrite(frame_path, frame)
                        frame_result = ImageProcessor.process(frame_path)
                        results['frames'].append(
                            {"timestamp": round(frame_positions[i] * duration, 1), "result": frame_result})
                        if frame_result.get('ocr_text') and 'error' not in frame_result:
                            texts_from_frames.append(frame_result['ocr_text'])
                        if os.path.exists(frame_path):
                            try:
                                os.unlink(frame_path)
                            except:
                                pass
                    else:
                        print(f"⚠️ 无法读取第{frame_idx}帧")
                except Exception as e:
                    print(f"⚠️ 处理帧{i}失败: {e}")
                    results['frames'].append({"timestamp": round(frame_positions[i] * duration, 1),
                                              "result": mock_moderation_result("image")})

            cap.release()
            print(f"✅ 帧处理完成: {len(results['frames'])} 帧")

            if texts_from_frames:
                combined_text = " ".join(texts_from_frames)
                context_result = text_processor.process(combined_text)
                if context_result['violation']:
                    results['cross_modal_fusion']['temporal_context'] = {"violation": True, "type": "跨帧关联违规",
                                                                         "confidence": context_result['confidence']}

            print("⚖️ 执行多模态融合...")
            final_result = {}
            modalities = []
            if results['audio'].get('violation'):
                modalities.append(
                    {'type': f"音频-{results['audio']['type']}", 'confidence': results['audio']['confidence'],
                     'weight': CROSS_MODAL_CONFIG['audio_weight']})

            violation_frames = [f for f in results['frames'] if
                                'error' not in f['result'] and f['result'].get('violation', False)]
            if violation_frames:
                max_conf_frame = max(violation_frames, key=lambda x: x['result']['confidence'])
                modalities.append({'type': f"图像-{max_conf_frame['result']['type']}",
                                   'confidence': max_conf_frame['result']['confidence'],
                                   'weight': CROSS_MODAL_CONFIG['image_weight']})

            if results['cross_modal_fusion'].get('temporal_context', {}).get('violation'):
                context = results['cross_modal_fusion']['temporal_context']
                modalities.append({'type': context['type'], 'confidence': context['confidence'], 'weight': 0.3})

            if modalities:
                total_score = sum(m['confidence'] * m['weight'] for m in modalities)
                total_weight = sum(m['weight'] for m in modalities)
                dominant_modality = max(modalities, key=lambda m: m['confidence'])
                dominant_type = dominant_modality['type'].split('-')[-1]
                final_result = {"violation": True, "type": dominant_type,
                                "confidence": min(round(total_score / total_weight, 3), 1.0)}
                print(f"✅ 融合结果: 违规={True}, 主要类型='{dominant_type}', 置信度={final_result['confidence']}")
            else:
                valid_confs = [f['result'].get('confidence', 0) for f in results['frames'] if
                               'error' not in f['result']]
                avg_confidence = sum(valid_confs) / len(valid_confs) if valid_confs else 0.85
                final_result = {"violation": False, "type": "正常", "confidence": round(avg_confidence, 3)}
                print(f"✅ 融合结果: 违规={False}, 置信度={final_result['confidence']}")

            final_result['frames'] = results['frames']
            final_result['audio_transcript'] = results.get('audio', {}).get('transcript', '无音频')
            final_result['method'] = "视频多模态融合"
            return final_result

        except Exception as e:
            print(f"❌ 视频处理失败: {str(e)[:100]}...")
            import traceback
            print(traceback.format_exc())
            return {"error": f"视频处理失败: {str(e)}", "violation": True, "type": "处理异常", "confidence": 1.0,
                    "frames": [], "method": "异常降级"}
        finally:
            # --- 核心步骤 3: 清理转码后产生的临时文件 ---
            if was_transcoded and os.path.exists(path_to_process):
                try:
                    os.unlink(path_to_process)
                    print(f"🧹 已清理临时转码文件: {path_to_process}")
                except OSError as e:
                    print(f"⚠️ 清理临时转码文件失败: {e}")


# 导出处理器实例
text_processor = TextProcessor()
image_processor = ImageProcessor()
audio_processor = AudioProcessor()
video_processor = VideoProcessor()
