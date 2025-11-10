# backend/main.py
"""
FastAPI路由层 - 跨模态UGC审核系统入口
"""
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
from pathlib import Path

from web_ocr import browser_manager
from models import model_manager
from processors import (
    text_processor, image_processor,
    audio_processor, video_processor
)

# 创建FastAPI应用
app = FastAPI(
    title="跨模态UGC智能审核系统",
    description="基于Chinese-CLIP的多模态内容安全审核API",
    version="2.0.0"
)

# CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 上传目录
UPLOAD_DIR = Path("upload")
UPLOAD_DIR.mkdir(exist_ok=True)


def check_ffmpeg():
    """检查ffmpeg是否在系统PATH中"""
    return shutil.which('ffmpeg') is not None


@app.on_event("startup")
async def startup_event():
    """应用启动时加载模型"""
    model_manager.load_models()
    browser_manager.initialize()
    print(f"🚀 系统启动完成！访问 http://localhost:8000")

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理资源"""
    browser_manager.shutdown()
    print("👋 系统已关闭。")


@app.post("/api/moderate")
async def moderate_content(
        content_type: str = Form(..., description="内容类型: text/image/audio/video"),
        text: str = Form(None, description="文本内容"),
        file: UploadFile = None
):
    """
    跨模态内容审核统一接口

    - **text**: 纯文本审核
    - **image**: 图像+OCR+CLIP视觉分析
    - **audio**: 音频转录+文本分析
    - **video**: 多关键帧+音频融合分析
    """
    try:
        # 文本审核
        if content_type == "text":
            if not text or len(text.strip()) < 2:
                return JSONResponse(
                    status_code=400,
                    content={"error": "文本内容长度必须大于2个字符"}
                )

            result = text_processor.process(text)
            result['modality'] = "文本单模态"
            return {"success": True, "result": result}

        # 文件审核
        if not file:
            return JSONResponse(status_code=400, content={"error": "文件不能为空"})

        # 保存临时文件
        file_path = UPLOAD_DIR / file.filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 根据类型调用对应处理器
        if content_type == "image":
            result = image_processor.process(str(file_path))
            result['modality'] = "图像+OCR跨模态"

        elif content_type == "audio":
            result = audio_processor.process(str(file_path))
            result['modality'] = "音频转文本跨模态"

        elif content_type == "video":
            result = video_processor.process(str(file_path))
            result['modality'] = "视频多帧+音频跨模态融合"

        else:
            os.unlink(file_path)
            return JSONResponse(status_code=400, content={"error": "不支持的内容类型"})

        # 清理临时文件
        os.unlink(file_path)
        return {"success": True, "result": result}

    except Exception as e:
        # 错误处理
        if 'file_path' in locals() and os.path.exists(file_path):
            try:
                os.unlink(file_path)
            except:
                pass

        import traceback
        print(traceback.format_exc())

        return JSONResponse(
            status_code=500,
            content={
                "error": f"审核异常: {str(e)}",
                "detail": "请检查文件格式或稍后重试"
            }
        )


@app.get("/api/health")
async def health_check():
    """增强健康检查接口"""
    models = model_manager.load_models()
    status = model_manager.get_status()

    return {
        "status": "healthy" if any(status.values()) else "degraded",
        "timestamp": health_check.__name__,
        "models": {
            "clip": {
                "ready": model_manager.is_ready('clip'),
                "processor": model_manager.get_model('clip_processor') is not None
            },
            "whisper": {
                "ready": model_manager.is_ready('whisper'),
                "model": model_manager.get_model('whisper') is not None
            }
        },
        "dependencies": {
            "ffmpeg": check_ffmpeg(),
            "cv2": True,  # 已在导入时检查
            "librosa": True,
            "easyocr": True
        },
        "mode": "production" if all(status.values()) else "simulation"
    }


@app.get("/")
async def root():
    """根路径重定向"""
    return {
        "message": "跨模态UGC智能审核系统API",
        "endpoints": {
            "moderate": "/api/moderate",
            "health": "/api/health",
            "docs": "/docs"
        }
    }


# 静态文件服务（前端）
app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")

# uvicorn main:app --host 0.0.0.0 --port 8000 --reload
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)