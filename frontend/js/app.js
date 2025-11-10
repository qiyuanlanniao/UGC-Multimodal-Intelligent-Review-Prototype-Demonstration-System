// frontend/js/app.js
import { UIController } from './ui.js';
import { APIService } from './api.js';
import { CONFIG } from './config.js';

// 全局应用实例
class ModerationApp {
    constructor() {
        this.ui = new UIController();
        this.init();
    }

    /**
     * 初始化应用
     */
    init() {
        console.log('🚀 启动跨模态审核应用...');

        // 绑定所有事件
        this.ui.bindModeSwitch();
        this.ui.bindFileUploads();
        this.bindModerationButton();

        // 检查后端健康状态
        this.checkBackendHealth();

        console.log('✅ 应用初始化完成');
    }

    /**
     * 绑定审核按钮事件
     */
    bindModerationButton() {
        const moderateBtn = document.getElementById('moderate-btn');
        if (!moderateBtn) {
            console.error('❌ 审核按钮不存在');
            return;
        }

        moderateBtn.addEventListener('click', () => this.startModeration());
    }

    /**
     * 启动审核流程
     */
    async startModeration() {
        const mode = this.ui.currentMode;

        console.log(`🎯 开始审核: ${mode} 模式`);

        // 验证输入
        if (!this.validateInput(mode)) {
            alert('⚠️ 请先输入内容或上传文件！');
            return;
        }

        // 设置处理状态
        this.ui.setProcessingState(true);
        this.ui.updateLoadingProgress(mode);

        try {
            // 准备内容
            const content = await this.prepareContent(mode);

            // 调用API
            const result = await APIService.moderate(mode, content);

            if (result.success) {
                console.log('✅ 审核成功:', result.data);
                this.ui.displayResults(result.data, mode);
            }
        } catch (error) {
            console.error('❌ 审核失败:', error);
            this.ui.showError(error.message);
        } finally {
            // 恢复UI状态
            this.ui.setProcessingState(false);
        }
    }

    /**
     * 验证输入内容
     */
    validateInput(mode) {
        if (mode === 'text') {
            const textInput = document.getElementById('text-input');
            return textInput && textInput.value.trim().length > 0;
        } else {
            const fileInput = document.getElementById(`${mode}-file`);
            return fileInput && fileInput.files.length > 0;
        }
    }

    /**
     * 准备审核内容
     */
    async prepareContent(mode) {
        if (mode === 'text') {
            return document.getElementById('text-input').value;
        } else {
            const fileInput = document.getElementById(`${mode}-file`);
            const file = fileInput.files[0];

            // 视频文件大小检查
            if (mode === 'video' && file.size > CONFIG.VIDEO.MAX_SIZE) {
                throw new Error(`视频文件过大（${(file.size/1024/1024).toFixed(1)}MB），请限制在50MB以内`);
            }

            return file;
        }
    }

    /**
     * 检查后端健康状态
     */
    async checkBackendHealth() {
        try {
            const health = await APIService.healthCheck();
            if (health.status === 'healthy') {
                console.log('✅ 后端服务正常');
                console.log('📊 模型状态:', health.models);
            } else {
                console.warn('⚠️ 后端服务异常:', health);
            }
        } catch (e) {
            console.warn('⚠️ 无法连接到后端服务');
        }
    }
}

// 启动应用
document.addEventListener('DOMContentLoaded', () => {
    window.moderationApp = new ModerationApp();
});