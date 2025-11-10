// frontend/js/api.js
import { CONFIG } from './config.js';

export class APIService {
    /**
     * 跨模态内容审核
     * @param {string} contentType - 内容类型: text/image/audio/video
     * @param {string|File} content - 文本内容或文件对象
     * @returns {Promise} 审核结果
     */
    static async moderate(contentType, content) {
        const formData = new FormData();
        formData.append('content_type', contentType);

        if (contentType === 'text') {
            formData.append('text', content);
        } else {
            formData.append('file', content);
        }

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), CONFIG.API.TIMEOUT);

        try {
            const response = await fetch(CONFIG.API.ENDPOINTS.MODERATE, {
                method: 'POST',
                body: formData,
                signal: controller.signal
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                throw new Error(`HTTP错误: ${response.status}`);
            }

            const data = await response.json();

            if (data.success) {
                return { success: true, data: data.result };
            } else {
                throw new Error(data.error || '审核失败');
            }
        } catch (error) {
            if (error.name === 'AbortError') {
                throw new Error('请求超时，请检查网络或文件大小');
            }
            throw error;
        }
    }

    /**
     * 健康检查
     */
    static async healthCheck() {
        try {
            const response = await fetch(CONFIG.API.ENDPOINTS.HEALTH);
            return await response.json();
        } catch (e) {
            return { status: 'unhealthy', error: e.message };
        }
    }
}