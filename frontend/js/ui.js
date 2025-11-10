// frontend/js/ui.js
import { CONFIG } from './config.js';

export class UIController {
    constructor() {
        this.elements = this.initializeElements();
        this.currentMode = 'text';
        this.isProcessing = false;
    }

    /**
     * 初始化DOM元素引用
     */
    initializeElements() {
        const ids = [
            'moderate-btn', 'btn-text', 'loading', 'result-container',
            'placeholder', 'risk-badge', 'result-details', 'text-input'
        ];

        const elements = {};
        ids.forEach(id => {
            elements[id] = document.getElementById(id);
        });

        // 模式标签和面板
        elements.modeTabs = document.querySelectorAll('.mode-tab');
        elements.panels = document.querySelectorAll('.panel');

        // 文件上传元素
        elements.uploads = {
            image: { zone: 'image-upload', file: 'image-file', preview: 'image-preview' },
            audio: { zone: 'audio-upload', file: 'audio-file', preview: 'audio-preview' },
            video: { zone: 'video-upload', file: 'video-file', preview: 'video-preview' }
        };

        return elements;
    }

    /**
     * 绑定模式切换事件
     */
    bindModeSwitch() {
        this.elements.modeTabs.forEach(tab => {
            tab.addEventListener('click', (e) => {
                const targetMode = e.target.dataset.mode;
                this.switchMode(targetMode);
            });
        });
    }

    /**
     * 切换审核模式
     */
    switchMode(mode) {
        this.currentMode = mode;

        // 移除所有激活状态
        this.elements.modeTabs.forEach(t => t.classList.remove('active'));
        this.elements.panels.forEach(p => p.classList.remove('active'));

        // 激活当前标签和面板
        document.querySelector(`[data-mode="${mode}"]`).classList.add('active');
        document.getElementById(`${mode}-panel`).classList.add('active');

        this.resetResults();
        console.log(`✅ 切换到模式: ${mode}`);
    }

    /**
     * 绑定文件上传事件
     */
    bindFileUploads() {
        Object.keys(this.elements.uploads).forEach(type => {
            const config = this.elements.uploads[type];
            const zone = document.getElementById(config.zone);
            const fileInput = document.getElementById(config.file);
            const preview = document.getElementById(config.preview);

            if (!zone || !fileInput || !preview) {
                console.error(`❌ 上传组件初始化失败: ${type}`);
                return;
            }

            // 点击上传
            zone.addEventListener('click', () => fileInput.click());

            // 拖拽事件
            zone.addEventListener('dragover', e => {
                e.preventDefault();
                zone.classList.add('dragover');
            });

            zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));

            zone.addEventListener('drop', e => {
                e.preventDefault();
                zone.classList.remove('dragover');
                fileInput.files = e.dataTransfer.files;
                this.handleFile(e.dataTransfer.files[0], preview);
            });

            fileInput.addEventListener('change', e => this.handleFile(e.target.files[0], preview));
        });
    }

    /**
     * 处理文件选择和预览 (代码已精简)
     */
    handleFile(file, previewElement) {
        if (!file) return;

        console.log(`📄 选择文件: ${file.name} (${(file.size / 1024 / 1024).toFixed(2)}MB)`);

        // --- 核心优化：直接将 createObjectURL 的结果赋值给 src ---
        previewElement.src = URL.createObjectURL(file);
        previewElement.classList.add('show');
    }

    /**
     * 更新加载状态
     */
    updateLoadingProgress(mode) {
        const loadingDetail = document.getElementById('loading-detail');
        if (!loadingDetail) return;

        const steps = CONFIG.UI.LOADING_STEPS[mode];
        let i = 0;

        loadingDetail.textContent = steps[0];
        const interval = setInterval(() => {
            i = (i + 1) % steps.length;
            loadingDetail.textContent = steps[i];
        }, 800);

        setTimeout(() => clearInterval(interval), 8000);
    }

    /**
     * 设置处理状态（禁用按钮、显示加载动画）
     */
    setProcessingState(isProcessing) {
        this.isProcessing = isProcessing;

        const btn = this.elements['moderate-btn'];
        const btnText = this.elements['btn-text'];
        const loading = this.elements['loading'];
        const placeholder = this.elements['placeholder'];
        const resultContainer = this.elements['result-container'];

        btn.disabled = isProcessing;

        if (isProcessing) {
            loading.classList.add('show');
            if (placeholder) placeholder.style.display = 'none';
            if (resultContainer) resultContainer.classList.remove('show');
            if (btnText) btnText.textContent = '分析中...';
        } else {
            loading.classList.remove('show');
            if (btnText) btnText.textContent = '🔍 启动跨模态智能审核';
        }
    }

    /**
     * 显示审核结果
     */
    displayResults(result, mode) {
        const riskBadge = this.elements['risk-badge'];
        const resultDetails = this.elements['result-details'];
        const resultContainer = this.elements['result-container'];

        if (!riskBadge || !resultDetails || !resultContainer) {
            console.error('❌ 结果展示元素缺失');
            return;
        }

        // --- 核心修复：重构风险等级判断逻辑 ---
        let riskLevel;

        if (result.violation) {
            // 首先判断为违规，然后再根据置信度划分等级
            if (result.confidence >= CONFIG.UI.RISK_LEVELS.DANGER.threshold) {
                riskLevel = CONFIG.UI.RISK_LEVELS.DANGER;
            } else if (result.confidence >= CONFIG.UI.RISK_LEVELS.WARNING.threshold) {
                riskLevel = CONFIG.UI.RISK_LEVELS.WARNING;
            } else {
                // 这是新增的关键逻辑：
                // 只要是违规，就算置信度低于WARNING阈值，也至少是“中度风险”
                riskLevel = CONFIG.UI.RISK_LEVELS.WARNING;
            }
        } else {
            // 只有在 violation 明确为 false 时，才判定为安全
            riskLevel = CONFIG.UI.RISK_LEVELS.SAFE;
        }
        // --- 修复结束 ---

        riskBadge.className = `risk-badge ${riskLevel.class}`;
        // 注意：这里的 textContent 模板字符串可能需要根据 riskLevel 的定义调整
        // 我们的 config.js 中，text不包含置信度，所以直接赋值
        riskBadge.textContent = riskLevel.text;

        // 渲染结果详情 (这部分逻辑不变)
        resultDetails.innerHTML = this.renderResultHTML(result, mode);
        resultContainer.classList.add('show');
    }

    /**
     * 渲染结果HTML
     */
    renderResultHTML(data, mode) {
        let html = `<div class="result-section">
            <div class="section-title">📋 基础信息</div>
            <div class="detail-grid">
                <div class="detail-item">
                    <div class="detail-label">检测模式</div>
                    <div class="detail-value">${data.modality || '-'}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">置信度</div>
                    <div class="detail-value">${(data.confidence * 100).toFixed(1)}%</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">违规类型</div>
                    <div class="detail-value">${data.type || '-'}</div>
                </div>
            </div>
        </div>`;

        // 跨模态一致性分析（图文模式）
        if ((mode === 'image' || mode === 'video') && data.features?.alignment_score !== undefined) {
            const consistency = this.getConsistencyInfo(data.features.alignment_score);
            html += `<div class="result-section">
                <div class="section-title">🔄 跨模态一致性分析</div>
                <div class="consistency-indicator ${consistency.class}">
                    <span>${consistency.icon}</span>
                    <div>
                        <div style="font-weight: 600; margin-bottom: 4px;">${consistency.title}</div>
                        <div class="detail-label">对齐分数: ${(data.features.alignment_score * 100).toFixed(1)}%</div>
                    </div>
                </div>
            </div>`;
        }

        // 视频时间轴
        if (mode === 'video' && data.frames?.length > 0) {
            html += `<div class="result-section">
                <div class="section-title">🎬 视频关键帧分析</div>
                <div class="timeline">`;

            data.frames.forEach(frame => {
                const isViolation = frame.result.violation;
                const badgeClass = isViolation ? 'badge-danger' : 'badge-safe';
                const badgeText = isViolation ? '违规' : '正常';

                html += `<div class="timeline-item">
                    <div class="timestamp">⏱️ ${frame.timestamp}秒</div>
                    <div class="detail-value">
                        ${frame.result.type}
                        <span class="badge ${badgeClass}">${badgeText} ${frame.result.confidence}</span>
                    </div>
                </div>`;
            });

            html += `</div></div>`;
        }

        return html;
    }

    /**
     * 获取一致性信息
     */
    getConsistencyInfo(score) {
        if (score > 0.7) {
            return { class: 'consistency-high', icon: '✅', title: '高一致性' };
        } else if (score > 0.4) {
            return { class: 'consistency-medium', icon: '⚠️', title: '中等一致性' };
        } else {
            return { class: 'consistency-low', icon: '🚨', title: '低一致性' };
        }
    }

    /**
     * 显示错误信息
     */
    showError(message) {
        const riskBadge = this.elements['risk-badge'];
        const resultDetails = this.elements['result-details'];
        const resultContainer = this.elements['result-container'];

        if (riskBadge) {
            riskBadge.className = 'risk-badge risk-danger';
            riskBadge.textContent = '❌ 处理失败';
        }

        if (resultDetails) {
            resultDetails.innerHTML = `<div class="result-section"><div class="error-message">${message}</div></div>`;
        }

        if (resultContainer) {
            resultContainer.classList.add('show');
        }
    }

    /**
     * 重置结果展示
     */
    resetResults() {
        const resultContainer = this.elements['result-container'];
        const placeholder = this.elements['placeholder'];

        if (resultContainer) resultContainer.classList.remove('show');
        if (placeholder) placeholder.style.display = 'block';
    }
}