// frontend/js/config.js
export const CONFIG = {
    API: {
        BASE_URL: '',  // 空字符串使用当前域名
        ENDPOINTS: {
            MODERATE: '/api/moderate',
            HEALTH: '/api/health'
        },
        TIMEOUT: 120000  // 2分钟超时（视频处理）
    },

    UI: {
        LOADING_STEPS: {
            text: ['加载分词器...', '提取文本特征...', '语义分析...', '生成跨模态表征...'],
            image: ['加载图像...', 'OCR文本提取...', 'CLIP视觉编码...', '跨模态对齐...'],
            audio: ['加载音频...', 'Whisper转录...', '文本语义分析...', '时序特征提取...'],
            video: ['加载视频...', '提取音频轨道...', '关键帧采样...', '多模态融合...']
        },

        RISK_LEVELS: {
            SAFE: { threshold: 0, class: 'risk-safe', text: '✅ 内容正常' },
            WARNING: { threshold: 0.6, class: 'risk-warning', text: '⚠️ 中度风险' },
            DANGER: { threshold: 0.8, class: 'risk-danger', text: '🚨 高风险违规' }
        }
    },

    VIDEO: {
        MAX_SIZE: 50 * 1024 * 1024,  // 50MB限制
        FRAME_COUNT: 3
    }
};