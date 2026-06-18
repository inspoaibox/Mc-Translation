// 管理后台主逻辑
const token = localStorage.getItem('token');

if (!token) {
    window.location.href = '/admin/login';
    throw new Error('No token'); // 阻止后续代码执行
}

// 请求头
const headers = {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
};

let apiDocsBaseUrl = '';

const CAUSAL_LM_MODELS = [
    {
        value: 'qwen3_1_7b',
        label: 'Qwen3 1.7B',
        modelName: 'Qwen/Qwen3-1.7B',
        size: '~3.5GB',
        badge: '通用大模型',
        note: 'Qwen3 小型推理/指令模型，适合通用文本翻译'
    },
    {
        value: 'gemma3_1b',
        label: 'Gemma 3 1B',
        modelName: 'google/gemma-3-1b-it',
        size: '~2GB',
        badge: '需授权',
        note: 'Google Gemma 3 指令模型，下载可能需要 HuggingFace 授权'
    },
    {
        value: 'qwen2_5_0_5b',
        label: 'Qwen2.5 0.5B',
        modelName: 'Qwen/Qwen2.5-0.5B-Instruct',
        size: '~1GB',
        badge: '轻量',
        note: '轻量指令模型，资源占用更低'
    }
];

function revealAdmin() {
    document.documentElement.classList.remove('auth-pending');
    document.documentElement.classList.add('auth-ready');
}

async function verifyAdminSession() {
    try {
        const response = await fetch('/admin/settings', { headers });
        if (!response.ok) {
            throw new Error('Invalid admin session');
        }
        return true;
    } catch (error) {
        localStorage.removeItem('token');
        window.location.replace('/admin/login');
        return false;
    }
}

// 页面导航
document.addEventListener('DOMContentLoaded', async () => {
    const verified = await verifyAdminSession();
    if (!verified) return;

    revealAdmin();

    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', async (e) => {
            e.preventDefault();

            const page = item.dataset.page;

            // 更新活动状态
            document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
            item.classList.add('active');

            // 显示加载中
            const contentArea = document.getElementById('content-area');
            contentArea.innerHTML = '<div style="text-align: center; padding: 3rem;"><p>加载中...</p></div>';

            // 加载页面
            try {
                await loadPage(page);
            } catch (error) {
                console.error('加载页面失败:', error);
                contentArea.innerHTML = '<div style="text-align: center; padding: 3rem;"><p style="color: red;">加载失败，请重试</p></div>';
            }
        });
    });

    // 默认加载仪表盘
    loadPage('dashboard');
});

// 退出登录
function logout() {
    localStorage.removeItem('token');
    window.location.href = '/admin/login';
}

// 加载页面
async function loadPage(page) {
    const contentArea = document.getElementById('content-area');
    const pageTitle = document.getElementById('page-title');

    switch(page) {
        case 'dashboard':
            pageTitle.textContent = '仪表盘';
            await loadDashboard();
            break;
        case 'api-keys':
            pageTitle.textContent = 'API 密钥管理';
            await loadAPIKeys();
            break;
        case 'models':
            pageTitle.textContent = '模型管理';
            await loadModels();
            break;
        case 'translator':
            pageTitle.textContent = '在线翻译测试';
            await loadTranslator();
            break;
        case 'logs':
            pageTitle.textContent = '调用日志';
            await loadLogs();
            break;
        case 'settings':
            pageTitle.textContent = '系统设置';
            await loadSettings();
            break;
        case 'docs':
            pageTitle.textContent = 'API 文档';
            await loadDocs();
            break;
    }
}

// 仪表盘
async function loadDashboard() {
    const contentArea = document.getElementById('content-area');

    try {
        const [statsResponse, modelsResponse] = await Promise.all([
            fetch('/admin/stats', { headers }),
            fetch('/admin/models/status', { headers })
        ]);

        if (!statsResponse.ok) {
            throw new Error('获取统计失败');
        }

        const stats = await statsResponse.json();
        const modelStatus = modelsResponse.ok ? await modelsResponse.json() : null;
        const modelStatusHTML = modelStatus
            ? Object.entries(modelStatus).map(([name, info]) => `
                <p>${info.loaded ? '✅' : '⚠'} ${name}: ${info.loaded ? '可用' : '未就绪'}${info.has_downloads ? '' : '（未下载模型/语言包）'}</p>
            `).join('')
            : '<p>⚠ 模型状态暂时不可用</p>';
        const modelStatsHTML = Object.keys(stats.by_model || {}).length
            ? Object.entries(stats.by_model).map(([name, count]) => `<p>${name}: ${count} 次</p>`).join('')
            : '<p style="color: #666;">暂无模型调用数据</p>';

        contentArea.innerHTML = `
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-label">总翻译次数</div>
                    <div class="stat-value">${stats.total_translations || 0}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">成功率</div>
                    <div class="stat-value">${stats.success_rate || 0}%</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">活跃 API Key</div>
                    <div class="stat-value">${stats.active_keys || 0}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">平均响应时间</div>
                    <div class="stat-value">${stats.avg_response_time || 0}ms</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">总字符数</div>
                    <div class="stat-value">${stats.total_chars || 0}</div>
                </div>
            </div>

            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">系统状态</h3>
                </div>
                ${modelStatusHTML}
                <p>📊 数据库连接正常</p>
                <p>🔧 系统运行中</p>
            </div>

            <div class="card" style="margin-top: 1.5rem;">
                <div class="card-header">
                    <h3 class="card-title">模型调用分布</h3>
                </div>
                ${modelStatsHTML}
            </div>
        `;
    } catch (error) {
        console.error('加载仪表盘失败:', error);
        contentArea.innerHTML = `
            <div class="card">
                <h3>暂无数据</h3>
                <p>统计数据加载中或服务暂时不可用</p>
            </div>
        `;
    }
}

// API 密钥管理
async function loadAPIKeys() {
    const contentArea = document.getElementById('content-area');

    try {
        const response = await fetch('/admin/api-keys', { headers });

        if (!response.ok) {
            throw new Error('获取密钥列表失败');
        }

        const keys = await response.json();

        let keysHTML = keys.map(key => {
            const keyValue = escapeHTML(key.key);
            const copyValue = escapeJSString(key.key);
            const statusText = key.is_active ? '✓ 活跃' : '✗ 禁用';
            const statusClass = key.is_active ? 'badge-success' : 'badge-danger';
            const actionHTML = key.is_active
                ? `<button class="btn btn-danger btn-sm" onclick="deleteKey(${key.id})">吊销</button>`
                : '<button class="btn btn-sm" disabled style="background: #94a3b8; color: white; cursor: not-allowed;">已吊销</button>';

            return `
                <tr>
                    <td>${escapeHTML(key.name)}</td>
                    <td>
                        <div class="api-key-copy-row">
                            <code>${keyValue}</code>
                            <button type="button" class="btn btn-sm api-key-copy-btn" onclick="copyToClipboard('${copyValue}', this)">复制</button>
                        </div>
                    </td>
                    <td><span class="badge ${statusClass}">${statusText}</span></td>
                    <td>${escapeHTML(key.rate_limit)}/周期</td>
                    <td>${escapeHTML(key.created_at)}</td>
                    <td>${actionHTML}</td>
                </tr>
            `;
        }).join('');

        document.getElementById('content-area').innerHTML = `
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">API 密钥列表</h3>
                    <button class="btn btn-success" onclick="createAPIKey()">+ 创建密钥</button>
                </div>
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>名称</th>
                                <th>密钥</th>
                                <th>状态</th>
                                <th>速率限制</th>
                                <th>创建时间</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody>${keysHTML}</tbody>
                    </table>
                </div>
            </div>
        `;
    } catch (error) {
        console.error('加载 API 密钥失败:', error);
        contentArea.innerHTML = `
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">API 密钥列表</h3>
                    <button class="btn btn-success" onclick="createAPIKey()">+ 创建密钥</button>
                </div>
                <p style="padding: 1rem; color: #666;">暂无数据或加载失败，请刷新重试</p>
            </div>
        `;
    }
}

// 创建 API Key
async function createAPIKey() {
    const contentArea = document.getElementById('content-area');
    let defaultRateLimit = 100;
    let defaultRateLimitPeriod = 3600;

    try {
        const settingsResponse = await fetch('/admin/settings', { headers });
        if (settingsResponse.ok) {
            const settings = await settingsResponse.json();
            defaultRateLimit = settings.api_rate_limit || defaultRateLimit;
            defaultRateLimitPeriod = settings.api_rate_limit_period || defaultRateLimitPeriod;
        }
    } catch (error) {
        console.warn('读取默认速率限制失败:', error);
    }

    // 显示创建表单
    contentArea.innerHTML = `
        <div class="card">
            <div class="card-header">
                <h3 class="card-title">创建 API 密钥</h3>
                <button class="btn" onclick="loadAPIKeys()" style="padding: 0.5rem 1rem; background: #64748b; color: white; border: none; border-radius: 0.375rem; cursor: pointer;">← 返回</button>
            </div>

            <div style="padding: 2rem; max-width: 600px;">
                <form id="create-key-form" onsubmit="submitCreateAPIKey(event)">
                    <div style="margin-bottom: 1.5rem;">
                        <label style="display: block; margin-bottom: 0.5rem; font-weight: 500;">密钥名称 <span style="color: red;">*</span></label>
                        <input type="text" id="key-name" required placeholder="例如：测试密钥、生产环境"
                               style="width: 100%; padding: 0.75rem; border: 2px solid var(--border-color); border-radius: 0.5rem; font-size: 1rem;">
                    </div>

                    <div style="margin-bottom: 1.5rem;">
                        <label style="display: block; margin-bottom: 0.5rem; font-weight: 500;">描述（可选）</label>
                        <textarea id="key-description" rows="3" placeholder="密钥用途说明..."
                                  style="width: 100%; padding: 0.75rem; border: 2px solid var(--border-color); border-radius: 0.5rem; font-size: 1rem;"></textarea>
                    </div>

                    <div style="margin-bottom: 1.5rem;">
                        <label style="display: block; margin-bottom: 0.5rem; font-weight: 500;">速率限制（请求/周期）</label>
                        <input type="number" id="key-rate-limit" value="${defaultRateLimit}" min="1" max="10000"
                               style="width: 100%; padding: 0.75rem; border: 2px solid var(--border-color); border-radius: 0.5rem; font-size: 1rem;">
                        <p style="color: #64748b; font-size: 0.875rem; margin-top: 0.5rem;">当前系统限流周期：${defaultRateLimitPeriod} 秒</p>
                    </div>

                    <div style="display: flex; gap: 1rem;">
                        <button type="submit" class="btn btn-primary" style="padding: 0.75rem 2rem; background: var(--primary-color); color: white; border: none; border-radius: 0.5rem; cursor: pointer; font-size: 1rem;">
                            创建密钥
                        </button>
                        <button type="button" onclick="loadAPIKeys()" class="btn" style="padding: 0.75rem 2rem; background: #e5e7eb; color: #374151; border: none; border-radius: 0.5rem; cursor: pointer; font-size: 1rem;">
                            取消
                        </button>
                    </div>
                </form>
            </div>
        </div>
    `;
}

// 提交创建 API Key
async function submitCreateAPIKey(event) {
    event.preventDefault();

    const name = document.getElementById('key-name').value.trim();
    const description = document.getElementById('key-description').value.trim();
    const rateLimit = parseInt(document.getElementById('key-rate-limit').value) || 100;

    const submitBtn = event.target.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    submitBtn.textContent = '创建中...';

    try {
        const response = await fetch('/admin/api-keys', {
            method: 'POST',
            headers,
            body: JSON.stringify({
                name,
                description,
                rate_limit: rateLimit,
                expires_days: null
            })
        });

        if (!response.ok) {
            throw new Error('创建失败');
        }

        const result = await response.json();
        const resultKey = result.key || '';
        const safeResultKey = escapeHTML(resultKey);
        const copyResultKey = escapeJSString(resultKey);
        const safeName = escapeHTML(name);
        const safeDescription = escapeHTML(description);

        // 显示成功页面，包含新密钥
        document.getElementById('content-area').innerHTML = `
            <div class="card" style="max-width: 800px; margin: 0 auto;">
                <div class="card-header" style="background: #10b981; color: white;">
                    <h3 class="card-title">✓ 密钥创建成功</h3>
                </div>

                <div style="padding: 2rem;">
                    <div style="background: #ecfdf5; border-left: 4px solid #10b981; padding: 1rem; margin-bottom: 1.5rem;">
                        <strong style="color: #047857;">创建完成</strong>
                        <p style="color: #047857; margin-top: 0.5rem; margin-bottom: 0;">可以在这里复制密钥，返回列表后也可以继续复制。</p>
                    </div>

                    <div style="margin-bottom: 1.5rem;">
                        <label style="display: block; margin-bottom: 0.5rem; font-weight: 500;">API 密钥</label>
                        <div style="display: flex; gap: 0.5rem;">
                            <input type="text" id="new-api-key" value="${safeResultKey}" readonly
                                   style="flex: 1; padding: 0.75rem; border: 2px solid #10b981; border-radius: 0.5rem; font-family: monospace; font-size: 1rem; background: #f0fdf4;">
                            <button type="button" onclick="copyToClipboard('${copyResultKey}', this)" class="btn btn-primary"
                                    style="padding: 0.75rem 1.5rem; background: #10b981; color: white; border: none; border-radius: 0.5rem; cursor: pointer; white-space: nowrap;">
                                复制
                            </button>
                        </div>
                    </div>

                    <div style="background: #f9fafb; padding: 1rem; border-radius: 0.5rem; margin-bottom: 1.5rem;">
                        <p style="margin: 0; color: #666;"><strong>名称:</strong> ${safeName}</p>
                        ${description ? `<p style="margin: 0.5rem 0 0 0; color: #666;"><strong>描述:</strong> ${safeDescription}</p>` : ''}
                        <p style="margin: 0.5rem 0 0 0; color: #666;"><strong>速率限制:</strong> ${rateLimit} 请求/周期</p>
                    </div>

                    <button onclick="loadAPIKeys()" class="btn btn-primary"
                            style="width: 100%; padding: 0.75rem; background: var(--primary-color); color: white; border: none; border-radius: 0.5rem; cursor: pointer; font-size: 1rem;">
                        返回密钥列表
                    </button>
                </div>
            </div>
        `;

    } catch (error) {
        console.error('创建密钥失败:', error);
        alert(`❌ 创建失败: ${error.message}`);
        submitBtn.disabled = false;
        submitBtn.textContent = '创建密钥';
    }
}

// 复制到剪贴板
function copyToClipboard(text, button = null) {
    const showSuccess = () => {
        if (!button) {
            alert('✓ 已复制到剪贴板');
            return;
        }

        const originalText = button.textContent;
        button.textContent = '已复制';
        button.disabled = true;

        setTimeout(() => {
            button.textContent = originalText;
            button.disabled = false;
        }, 1600);
    };

    const showError = () => {
        alert('复制失败，请手动选择并复制');
    };

    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(showSuccess).catch(() => {
            fallbackCopyText(text) ? showSuccess() : showError();
        });
        return;
    }

    fallbackCopyText(text) ? showSuccess() : showError();
}

function fallbackCopyText(text) {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.setAttribute('readonly', '');
    textarea.style.position = 'fixed';
    textarea.style.left = '-9999px';
    textarea.style.top = '0';
    document.body.appendChild(textarea);
    textarea.select();

    try {
        return document.execCommand('copy');
    } catch (error) {
        console.warn('fallback copy failed:', error);
        return false;
    } finally {
        document.body.removeChild(textarea);
    }
}

// 吊销 API Key
async function deleteKey(keyId) {
    const confirmed = confirm('确定要吊销这个 API 密钥吗？\n\n吊销后使用此密钥的应用将无法访问 API，历史日志会保留。');

    if (!confirmed) return;

    try {
        const response = await fetch(`/admin/api-keys/${keyId}`, {
            method: 'DELETE',
            headers
        });

        if (!response.ok) {
            throw new Error('吊销失败');
        }

        alert('✓ API 密钥已吊销');

        // 重新加载列表
        await loadAPIKeys();

    } catch (error) {
        console.error('吊销密钥失败:', error);
        alert(`❌ 吊销失败: ${error.message}`);
    }
}

// 在线翻译测试
async function loadTranslator() {
    let modelStatus = null;

    try {
        const response = await fetch('/admin/models/status', { headers });
        if (response.ok) {
            modelStatus = await response.json();
        }
    } catch (error) {
        console.warn('读取模型状态失败:', error);
    }

    window.translatorModelStatus = modelStatus;
    const isReady = (model) => isTranslatorModelReady(model, 'en', 'zh');
    const modelOptions = [
        { value: 'argos', label: 'Argos (快速)' },
        { value: 'marian', label: 'MarianMT (准确)' },
        { value: 'm2m100', label: 'M2M100 (多语言)' },
        { value: 'm2m100_1_2b', label: 'M2M100 1.2B (高精度)' },
        { value: 'nllb', label: 'NLLB-200 (多语言)' },
        ...CAUSAL_LM_MODELS.map(model => ({ value: model.value, label: model.label }))
    ].map(model => {
        const ready = isReady(model.value);
        return `<option value="${model.value}" ${ready ? '' : 'disabled'}>${model.label}${ready ? '' : ' - 未就绪'}</option>`;
    }).join('');

    document.getElementById('content-area').innerHTML = `
        <div class="translator-shell">
            <div class="translator-toolbar">
                <div>
                    <h3 class="translator-title">翻译测试工具</h3>
                    <p class="translator-subtitle">使用后台登录态测试本地翻译模型</p>
                </div>
                <div class="translator-model">
                    <label for="model-select">模型</label>
                    <select id="model-select" class="translator-select">
                        ${modelOptions}
                    </select>
                </div>
            </div>

            <div class="translator-langbar">
                <div class="translator-lang-field">
                    <label for="source-lang">源语言</label>
                    <select id="source-lang" class="translator-select" onchange="updateTranslatorMeta()">
                        <option value="en">英语</option>
                        <option value="zh">中文</option>
                        <option value="ja">日语</option>
                        <option value="ko">韩语</option>
                        <option value="fr">法语</option>
                        <option value="de">德语</option>
                        <option value="es">西班牙语</option>
                        <option value="ru">俄语</option>
                    </select>
                </div>

                <button type="button" class="translator-swap" onclick="swapTranslatorLanguages()" title="切换源语言和目标语言">⇄</button>

                <div class="translator-lang-field">
                    <label for="target-lang">目标语言</label>
                    <select id="target-lang" class="translator-select" onchange="updateTranslatorMeta()">
                        <option value="zh">中文</option>
                        <option value="en">英语</option>
                        <option value="ja">日语</option>
                        <option value="ko">韩语</option>
                        <option value="fr">法语</option>
                        <option value="de">德语</option>
                        <option value="es">西班牙语</option>
                        <option value="ru">俄语</option>
                    </select>
                </div>
            </div>

            <div class="translator-grid">
                <section class="translator-panel">
                    <div class="translator-panel-header">
                        <span>输入文本</span>
                        <span id="input-count">0 字符</span>
                    </div>
                    <textarea id="input-text" class="translator-textarea" rows="10" placeholder="输入需要翻译的内容..." oninput="updateTranslatorMeta()"></textarea>
                </section>

                <section class="translator-panel translator-output-panel">
                    <div class="translator-panel-header">
                        <span>翻译结果</span>
                        <span id="translation-meta">en → zh</span>
                    </div>
                    <textarea id="output-text" class="translator-textarea translator-output" rows="10" readonly placeholder="翻译结果会显示在这里"></textarea>
                </section>
            </div>

            <div class="translator-actions">
                <button class="btn translator-primary" onclick="testTranslate()">翻译</button>
                <button class="btn translator-secondary" onclick="clearTranslator()">清空</button>
                <button class="btn translator-secondary" onclick="copyTranslationResult()">复制结果</button>
            </div>

            <div id="translate-result" class="translator-status"></div>
        </div>
    `;
    updateTranslatorMeta();
}

function isTranslatorModelReady(model, sourceLang, targetLang) {
    const status = window.translatorModelStatus;
    if (!status || !status[model]) {
        return true;
    }

    const modelInfo = status[model];
    const pair = `${sourceLang}-${targetLang}`;
    return Boolean(
        modelInfo.loaded &&
        (!Array.isArray(modelInfo.ready_pairs) || modelInfo.ready_pairs.includes(pair))
    );
}

function updateTranslatorModelAvailability() {
    const modelSelect = document.getElementById('model-select');
    const sourceLang = document.getElementById('source-lang')?.value || 'en';
    const targetLang = document.getElementById('target-lang')?.value || 'zh';

    if (!modelSelect) {
        return;
    }

    Array.from(modelSelect.options).forEach(option => {
        const ready = isTranslatorModelReady(option.value, sourceLang, targetLang);
        option.disabled = !ready;
        option.textContent = option.textContent.replace(' - 未就绪', '') + (ready ? '' : ' - 未就绪');
    });

    if (modelSelect.selectedOptions[0]?.disabled) {
        const firstReady = Array.from(modelSelect.options).find(option => !option.disabled);
        if (firstReady) {
            modelSelect.value = firstReady.value;
        }
    }
}

function getLanguageName(langCode) {
    const names = {
        en: '英语',
        zh: '中文',
        ja: '日语',
        ko: '韩语',
        fr: '法语',
        de: '德语',
        es: '西班牙语',
        ru: '俄语'
    };
    return names[langCode] || langCode;
}

function escapeHTML(value) {
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function escapeJSString(value) {
    return String(value ?? '')
        .replace(/\\/g, '\\\\')
        .replace(/'/g, "\\'")
        .replace(/\r/g, '\\r')
        .replace(/\n/g, '\\n');
}

function normalizeApiBaseUrl(value) {
    return String(value || '').trim().replace(/\/+$/, '');
}

function isValidHttpApiBaseUrl(value) {
    try {
        const url = new URL(value);
        return ['http:', 'https:'].includes(url.protocol) && Boolean(url.host);
    } catch (error) {
        return false;
    }
}

function getBrowserApiBaseUrl() {
    return normalizeApiBaseUrl(window.location.origin || 'http://localhost:8000');
}

function resolveApiBaseUrl(settings = {}) {
    const configuredUrl = normalizeApiBaseUrl(settings.api_base_url);
    return configuredUrl && isValidHttpApiBaseUrl(configuredUrl) ? configuredUrl : getBrowserApiBaseUrl();
}

function getApiUrl(path, baseUrl = apiDocsBaseUrl) {
    const base = normalizeApiBaseUrl(baseUrl) || getBrowserApiBaseUrl();
    const rawPath = String(path || '');
    const normalizedPath = rawPath.startsWith('/') ? rawPath : `/${rawPath}`;
    return `${base}${normalizedPath}`;
}

async function fetchApiDocsBaseUrl() {
    try {
        const response = await fetch('/admin/settings', { headers });
        if (response.ok) {
            const settings = await response.json();
            return resolveApiBaseUrl(settings);
        }
    } catch (error) {
        console.warn('读取 API 基础地址失败，使用当前访问地址:', error);
    }

    return getBrowserApiBaseUrl();
}

function updateTranslatorMeta() {
    const input = document.getElementById('input-text');
    const count = document.getElementById('input-count');
    const meta = document.getElementById('translation-meta');
    const sourceLang = document.getElementById('source-lang')?.value || 'en';
    const targetLang = document.getElementById('target-lang')?.value || 'zh';

    if (count && input) {
        count.textContent = `${input.value.length} 字符`;
    }

    if (meta) {
        meta.textContent = `${getLanguageName(sourceLang)} → ${getLanguageName(targetLang)}`;
    }

    updateTranslatorModelAvailability();
}

function swapTranslatorLanguages() {
    const sourceSelect = document.getElementById('source-lang');
    const targetSelect = document.getElementById('target-lang');
    const input = document.getElementById('input-text');
    const output = document.getElementById('output-text');

    const sourceValue = sourceSelect.value;
    sourceSelect.value = targetSelect.value;
    targetSelect.value = sourceValue;

    if (output.value.trim()) {
        input.value = output.value;
        output.value = '';
        document.getElementById('translate-result').innerHTML = '';
    }

    updateTranslatorMeta();
}

function clearTranslator() {
    document.getElementById('input-text').value = '';
    document.getElementById('output-text').value = '';
    document.getElementById('translate-result').innerHTML = '';
    updateTranslatorMeta();
}

function copyTranslationResult() {
    const output = document.getElementById('output-text');

    if (!output.value.trim()) {
        alert('暂无可复制的翻译结果');
        return;
    }

    navigator.clipboard.writeText(output.value).then(() => {
        document.getElementById('translate-result').innerHTML = '<div class="translator-message success">结果已复制到剪贴板</div>';
    }).catch(() => {
        alert('复制失败，请手动复制');
    });
}

function createInlineDownloadProgress(anchor, title, taskId) {
    const container = anchor?.closest('[data-download-card]')
        || anchor?.closest('td')
        || anchor?.parentElement;

    if (!container) {
        return null;
    }

    container.querySelector('.inline-download-progress')?.remove();

    const progress = document.createElement('div');
    progress.className = 'inline-download-progress';
    progress.innerHTML = `
        <div class="inline-download-progress-header">
            <strong>${escapeHTML(title)}</strong>
            <span data-progress-percent>0%</span>
        </div>
        <div class="inline-download-progress-track">
            <div data-progress-bar class="inline-download-progress-bar" style="width: 0%;"></div>
        </div>
        <div class="inline-download-progress-meta">
            <span data-progress-status>等待开始...</span>
        </div>
        <p data-progress-message class="inline-download-progress-message">正在准备任务...</p>
    `;

    container.appendChild(progress);
    return progress;
}

function formatBytes(bytes) {
    if (!bytes || bytes <= 0) return '';
    const units = ['B', 'KB', 'MB', 'GB'];
    let value = bytes;
    let index = 0;

    while (value >= 1024 && index < units.length - 1) {
        value /= 1024;
        index += 1;
    }

    return `${value.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

async function pollDownloadTask(taskId, options = {}) {
    const intervalMs = options.intervalMs || 1000;
    const progressRoot = createInlineDownloadProgress(options.anchor, options.title || '下载进度', taskId);

    while (true) {
        const response = await fetch(`/admin/models/downloads/${taskId}`, { headers });
        const task = await response.json();

        if (!response.ok) {
            throw new Error(task.detail || '获取下载进度失败');
        }

        const percent = Math.max(0, Math.min(100, task.percent || 0));
        const bar = progressRoot?.querySelector('[data-progress-bar]');
        const percentEl = progressRoot?.querySelector('[data-progress-percent]');
        const statusEl = progressRoot?.querySelector('[data-progress-status]');
        const messageEl = progressRoot?.querySelector('[data-progress-message]');

        if (bar) bar.style.width = `${percent}%`;
        if (percentEl) percentEl.textContent = `${percent}%`;
        if (statusEl) statusEl.textContent = task.status || '-';

        const bytesText = task.downloaded_bytes
            ? ` · ${formatBytes(task.downloaded_bytes)}${task.total_bytes_hint ? ` / ${formatBytes(task.total_bytes_hint)}` : ''}`
            : '';
        if (messageEl) {
            messageEl.textContent = `${task.message || ''}${bytesText}`;
        }

        if (task.status === 'completed') {
            if (bar) bar.style.width = '100%';
            if (percentEl) percentEl.textContent = '100%';
            if (messageEl) messageEl.textContent = task.message || '下载完成';
            if (options.onComplete) await options.onComplete(task);
            return task;
        }

        if (task.status === 'failed') {
            if (messageEl) {
                messageEl.textContent = task.error || '下载失败';
                messageEl.classList.add('error');
            }
            throw new Error(task.error || '下载失败');
        }

        await new Promise(resolve => setTimeout(resolve, intervalMs));
    }
}

// 执行翻译测试（管理后台使用 JWT Token）
async function testTranslate() {
    const text = document.getElementById('input-text').value;
    const sourceLang = document.getElementById('source-lang').value;
    const targetLang = document.getElementById('target-lang').value;
    const model = document.getElementById('model-select').value;
    const resultDiv = document.getElementById('translate-result');
    const output = document.getElementById('output-text');

    if (!text.trim()) {
        alert('请输入要翻译的文本');
        return;
    }

    if (sourceLang === targetLang) {
        alert('源语言和目标语言不能相同');
        return;
    }

    output.value = '';
    resultDiv.innerHTML = '<div class="translator-message loading">正在翻译...</div>';

    // 启动状态轮询
    const statusKey = `${model}_${sourceLang}_${targetLang}`;
    const pollInterval = setInterval(async () => {
        try {
            const statusRes = await fetch('/admin/translate-status', { headers });
            const status = await statusRes.json();

            if (status[statusKey]) {
                const msg = status[statusKey].message;
                resultDiv.innerHTML = `<div class="translator-message loading">${escapeHTML(msg)}</div>`;
            }
        } catch (e) {
            // 忽略轮询错误
        }
    }, 1000);

    try {
        // 设置超时控制器
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 300000); // 5分钟超时

        const response = await fetch('/admin/test-translate', {
            method: 'POST',
            headers,
            body: JSON.stringify({
                text,
                source_lang: sourceLang,
                target_lang: targetLang,
                model
            }),
            signal: controller.signal
        });

        clearTimeout(timeoutId);
        clearInterval(pollInterval);

        const result = await response.json();

        if (response.ok) {
            output.value = result.translated_text || '';
            resultDiv.innerHTML = `
                <div class="translator-message success">
                    翻译完成 · ${escapeHTML(result.model_used)} · ${escapeHTML(result.source_lang)} → ${escapeHTML(result.target_lang)}
                </div>
            `;
        } else {
            resultDiv.innerHTML = `
                <div class="translator-message error">
                    翻译失败：${escapeHTML(result.detail || result.error || '未知错误')}
                </div>
            `;
        }
    } catch (error) {
        clearInterval(pollInterval);
        console.error('翻译错误:', error);

        if (error.name === 'AbortError') {
            resultDiv.innerHTML = `
                <div class="translator-message warning">
                    请求超时：可能正在首次加载或下载模型，请稍后重试
                </div>
            `;
        } else {
            resultDiv.innerHTML = `
                <div class="translator-message error">
                    网络错误：${escapeHTML(error.message)}
                </div>
            `;
        }
    }
}

// 模型管理
async function loadModels() {
    const contentArea = document.getElementById('content-area');

    contentArea.innerHTML = '<div style="text-align: center; padding: 3rem;"><p>加载中...</p></div>';

    try {
        // 获取模型状态
        const response = await fetch('/admin/models/status', { headers });
        if (!response.ok) throw new Error('获取模型状态失败');

        const status = await response.json();
        window.modelManagementStatus = status;
        const configResponse = await fetch('/admin/models/config', { headers });
        const modelConfig = configResponse.ok
            ? await configResponse.json()
            : { use_gpu: false, default_model: 'argos', available_models: ['argos', 'marian', 'm2m100'] };
        const defaultModel = modelConfig.default_model || 'argos';
        const ct2StatusLine = (modelInfo) => {
            if (!modelInfo?.has_downloads) {
                return '';
            }
            const count = modelInfo.ctranslate2_models?.length || 0;
            return count > 0
                ? `<br><small class="model-format-ok">✓ CT2 已优化 (${count})</small>`
                : '<br><small class="model-format-warn">原始 Transformers，未 CT2 优化</small>';
        };
        const marianDownloadStatus = status.marian.has_downloads
            ? `<span style="color: #10b981;">✓ ${status.marian.downloaded_models.length} 个模型</span><br><small style="color: #666;">${status.marian.downloaded_models.slice(0, 2).map(m => m.split('/').pop()).join(', ')}${status.marian.downloaded_models.length > 2 ? '...' : ''}</small>${ct2StatusLine(status.marian)}<br><small style="color: #64748b;">后端: ${status.marian.backend || 'auto'}</small>`
            : status.marian.cache_incomplete
                ? '<span style="color: #f59e0b;">⚠ 缓存不完整</span><br><small style="color: #666;">缺少模型权重文件</small>'
                : '<span style="color: #f59e0b;">⚠ 未下载</span>';
        const m2m100DownloadStatus = status.m2m100.has_downloads
            ? `<span style="color: #10b981;">✓ 已下载</span><br><small style="color: #666;">${status.m2m100.downloaded_models[0]?.split('/').pop() || ''}</small>${ct2StatusLine(status.m2m100)}<br><small style="color: #64748b;">后端: ${status.m2m100.backend || 'auto'}</small>`
            : status.m2m100.cache_incomplete
                ? '<span style="color: #f59e0b;">⚠ 缓存不完整</span><br><small style="color: #666;">已有部分文件，但缺少权重</small>'
                : '<span style="color: #f59e0b;">⚠ 未下载</span>';
        const modelDownloadStatus = (modelInfo) => {
            if (!modelInfo) {
                return '<span style="color: #f59e0b;">⚠ 状态未知</span>';
            }
            if (modelInfo.has_downloads) {
                return `<span style="color: #10b981;">✓ 已下载</span><br><small style="color: #666;">${modelInfo.downloaded_models?.[0]?.split('/').pop() || ''}</small>${ct2StatusLine(modelInfo)}<br><small style="color: #64748b;">后端: ${modelInfo.backend || 'auto'}</small>`;
            }
            if (modelInfo.cache_incomplete) {
                return '<span style="color: #f59e0b;">⚠ 缓存不完整</span><br><small style="color: #666;">已有部分文件，但缺少权重</small>';
            }
            return '<span style="color: #f59e0b;">⚠ 未下载</span>';
        };
        const causalLmDownloadStatus = (modelInfo) => {
            if (!modelInfo) {
                return '<span style="color: #f59e0b;">⚠ 状态未知</span>';
            }
            if (modelInfo.has_downloads) {
                return `<span style="color: #10b981;">✓ 已下载</span><br><small style="color: #666;">${escapeHTML(modelInfo.downloaded_models?.[0] || modelInfo.model_name || '')}</small><br><small style="color: #64748b;">后端: ${escapeHTML(modelInfo.backend || 'transformers-causal-lm')}</small>`;
            }
            if (modelInfo.cache_incomplete) {
                return '<span style="color: #f59e0b;">⚠ 缓存不完整</span><br><small style="color: #666;">已有部分文件，但缺少权重</small>';
            }
            return '<span style="color: #f59e0b;">⚠ 未下载</span>';
        };
        const modelActionButton = (modelInfo, infoKey, downloadHandler, convertHandler) => {
            if (!modelInfo?.loaded) {
                return `<button class="btn btn-sm" style="padding: 0.25rem 0.75rem; font-size: 0.875rem; background: #10b981; color: white; border: none; border-radius: 0.375rem; cursor: pointer;" onclick="${downloadHandler}(event)">下载/修复</button>`;
            }
            if ((modelInfo.ctranslate2_models?.length || 0) === 0) {
                return `<button class="btn btn-sm" style="padding: 0.25rem 0.75rem; font-size: 0.875rem; background: #0f766e; color: white; border: none; border-radius: 0.375rem; cursor: pointer;" onclick="${convertHandler}(event)">转换 CT2</button>`;
            }
            return `<div class="action-stack">
                <button class="btn btn-sm" style="padding: 0.25rem 0.75rem; font-size: 0.875rem; background: #64748b; color: white; border: none; border-radius: 0.375rem; cursor: pointer;" onclick="showModelInfo('${infoKey}')">详情</button>
                <button class="btn btn-sm" disabled style="padding: 0.25rem 0.75rem; font-size: 0.875rem; background: #dcfce7; color: #166534; border: none; border-radius: 0.375rem;">CT2 已优化</button>
            </div>`;
        };
        const causalLmActionButton = (modelInfo, modelId) => {
            if (!modelInfo?.loaded) {
                return `<button class="btn btn-sm" style="padding: 0.25rem 0.75rem; font-size: 0.875rem; background: #10b981; color: white; border: none; border-radius: 0.375rem; cursor: pointer;" onclick="downloadCausalLMModel(event, '${modelId}')">下载/修复</button>`;
            }
            return `<div class="action-stack">
                <button class="btn btn-sm" style="padding: 0.25rem 0.75rem; font-size: 0.875rem; background: #64748b; color: white; border: none; border-radius: 0.375rem; cursor: pointer;" onclick="showModelInfo('${modelId}')">详情</button>
                <button class="btn btn-sm" disabled style="padding: 0.25rem 0.75rem; font-size: 0.875rem; background: #dcfce7; color: #166534; border: none; border-radius: 0.375rem;">已下载</button>
            </div>`;
        };
        const causalLmRows = CAUSAL_LM_MODELS.map(model => {
            const modelInfo = status[model.value];
            const modelName = modelInfo?.model_name || model.modelName;
            return `
                        <tr>
                            <td>
                                <strong>${escapeHTML(model.label)}</strong>
                                <br>
                                <small style="color: #666;">${escapeHTML(modelName)}</small>
                            </td>
                            <td>大语言模型翻译</td>
                            <td>${escapeHTML(modelInfo?.size || model.size)}</td>
                            <td>${modelInfo?.loaded ? '<span class="badge badge-success">✓ 可用</span>' : '<span class="badge" style="background: #fef3c7; color: #92400e;">未下载</span>'}</td>
                            <td>
                                ${causalLmDownloadStatus(modelInfo)}
                            </td>
                            <td data-download-card>
                                ${causalLmActionButton(modelInfo, model.value)}
                            </td>
                        </tr>
            `;
        }).join('');
        const causalLmCards = CAUSAL_LM_MODELS.map(model => {
            const modelInfo = status[model.value];
            const modelName = modelInfo?.model_name || model.modelName;
            const downloaded = Boolean(modelInfo?.has_downloads);
            const authNote = modelInfo?.requires_auth ? '<br><small style="color: #92400e;">可能需要先在 HuggingFace 登录/授权</small>' : '';
            return `
                    <div data-download-card style="border: 1px solid var(--border-color); border-radius: 0.5rem; padding: 1.5rem;">
                        <h4 style="margin-bottom: 0.5rem;">${escapeHTML(model.label)}</h4>
                        <p style="color: #666; font-size: 0.9rem; margin-bottom: 1rem;">${escapeHTML(model.note)}</p>
                        <div style="margin-bottom: 1rem;">
                            <span style="background: #ede9fe; color: #5b21b6; padding: 0.25rem 0.5rem; border-radius: 0.25rem; font-size: 0.8rem;">${escapeHTML(model.badge)}</span>
                            <span style="background: #fef3c7; color: #92400e; padding: 0.25rem 0.5rem; border-radius: 0.25rem; font-size: 0.8rem; margin-left: 0.5rem;">${escapeHTML(modelInfo?.size || model.size)}</span>
                        </div>
                        <p style="color: #666; font-size: 0.85rem; margin-bottom: 1rem;"><code>${escapeHTML(modelName)}</code>${authNote}</p>
                        <button class="btn" ${downloaded ? 'disabled' : ''} style="width: 100%; padding: 0.5rem; background: ${downloaded ? '#dcfce7' : '#10b981'}; color: ${downloaded ? '#166534' : 'white'}; border: none; border-radius: 0.375rem; cursor: ${downloaded ? 'not-allowed' : 'pointer'};" onclick="downloadCausalLMModel(event, '${model.value}')">${downloaded ? '已下载' : '下载/修复'}</button>
                    </div>
            `;
        }).join('');
        const m2m100LargeDownloadStatus = modelDownloadStatus(status.m2m100_1_2b);
        const nllbDownloadStatus = modelDownloadStatus(status.nllb);

        contentArea.innerHTML = `
        <div class="card">
            <div class="card-header">
                <h3 class="card-title">已安装模型</h3>
            </div>

            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>模型名称</th>
                            <th>类型</th>
                            <th>大小</th>
                            <th>状态</th>
                            <th>已下载模型</th>
                            <th>操作</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>
                                <strong>Argos Translate</strong>
                                <br>
                                <small style="color: #666;">轻量级翻译</small>
                            </td>
                            <td>离线翻译</td>
                            <td>~50-100MB/包</td>
                            <td>${status.argos.loaded ? '<span class="badge badge-success">✓ 可用</span>' : '<span class="badge badge-danger">✗ 不可用</span>'}</td>
                            <td>
                                ${status.argos.has_downloads
                                    ? `<span style="color: #10b981;">✓ ${status.argos.downloaded_packages.length} 个语言包</span><br><small style="color: #666;">${status.argos.downloaded_packages.slice(0, 3).join(', ')}${status.argos.downloaded_packages.length > 3 ? '...' : ''}</small>`
                                    : '<span style="color: #f59e0b;">⚠ 未下载</span>'}
                            </td>
                            <td>
                                <button class="btn btn-sm" style="padding: 0.25rem 0.75rem; font-size: 0.875rem; background: #3b82f6; color: white; border: none; border-radius: 0.375rem; cursor: pointer;" onclick="manageArgosPackages()">管理语言包</button>
                            </td>
                        </tr>
                        <tr>
                            <td>
                                <strong>MarianMT</strong>
                                <br>
                                <small style="color: #666;">Helsinki-NLP</small>
                            </td>
                            <td>神经机器翻译</td>
                            <td>~200-300MB</td>
                            <td>${status.marian.loaded ? '<span class="badge badge-success">✓ 可用</span>' : '<span class="badge" style="background: #fef3c7; color: #92400e;">未下载</span>'}</td>
                            <td>
                                ${marianDownloadStatus}
                            </td>
                            <td data-download-card>
                                <button class="btn btn-sm" style="padding: 0.25rem 0.75rem; font-size: 0.875rem; background: #0f766e; color: white; border: none; border-radius: 0.375rem; cursor: pointer;" onclick="downloadMarianModel()">下载/转换</button>
                            </td>
                        </tr>
                        <tr>
                            <td>
                                <strong>M2M100</strong>
                                <br>
                                <small style="color: #666;">facebook/m2m100_418M</small>
                            </td>
                            <td>多语言翻译</td>
                            <td>~1.2GB</td>
                            <td>${status.m2m100.loaded ? '<span class="badge badge-success">✓ 可用</span>' : '<span class="badge" style="background: #fef3c7; color: #92400e;">未下载</span>'}</td>
                            <td>
                                ${m2m100DownloadStatus}
                            </td>
                            <td data-download-card>
                                ${modelActionButton(status.m2m100, 'm2m100', 'downloadM2M100Model', 'convertM2M100ModelToCT2')}
                            </td>
                        </tr>
                        <tr>
                            <td>
                                <strong>M2M100 1.2B</strong>
                                <br>
                                <small style="color: #666;">facebook/m2m100_1.2B</small>
                            </td>
                            <td>多语言翻译</td>
                            <td>~4.5GB</td>
                            <td>${status.m2m100_1_2b?.loaded ? '<span class="badge badge-success">✓ 可用</span>' : '<span class="badge" style="background: #fef3c7; color: #92400e;">未下载</span>'}</td>
                            <td>
                                ${m2m100LargeDownloadStatus}
                            </td>
                            <td data-download-card>
                                ${modelActionButton(status.m2m100_1_2b, 'm2m100_1_2b', 'downloadM2M100LargeModel', 'convertM2M100LargeModelToCT2')}
                            </td>
                        </tr>
                        <tr>
                            <td>
                                <strong>NLLB-200</strong>
                                <br>
                                <small style="color: #666;">facebook/nllb-200-distilled-600M</small>
                            </td>
                            <td>多语言翻译</td>
                            <td>~2.5GB+</td>
                            <td>${status.nllb?.loaded ? '<span class="badge badge-success">✓ 可用</span>' : '<span class="badge" style="background: #fef3c7; color: #92400e;">未下载</span>'}</td>
                            <td>
                                ${nllbDownloadStatus}
                            </td>
                            <td data-download-card>
                                ${modelActionButton(status.nllb, 'nllb', 'downloadNLLBModel', 'convertNLLBModelToCT2')}
                            </td>
                        </tr>
                        ${causalLmRows}
                    </tbody>
                </table>
            </div>
        </div>

        <div class="card" style="margin-top: 1.5rem;">
            <div class="card-header">
                <h3 class="card-title">模型获取</h3>
            </div>

            <div style="padding: 1.5rem;">
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1.5rem;">
                    <!-- NLLB-200 -->
                    <div data-download-card style="border: 1px solid var(--border-color); border-radius: 0.5rem; padding: 1.5rem;">
                        <h4 style="margin-bottom: 0.5rem;">NLLB-200</h4>
                        <p style="color: #666; font-size: 0.9rem; margin-bottom: 1rem;">Meta 多语言翻译模型，默认接入 facebook/nllb-200-distilled-600M</p>
                        <div style="margin-bottom: 1rem;">
                            <span style="background: #e0f2fe; color: #0369a1; padding: 0.25rem 0.5rem; border-radius: 0.25rem; font-size: 0.8rem;">多语言</span>
                            <span style="background: #fef3c7; color: #92400e; padding: 0.25rem 0.5rem; border-radius: 0.25rem; font-size: 0.8rem; margin-left: 0.5rem;">~2.5GB+</span>
                        </div>
                        <button class="btn" style="width: 100%; padding: 0.5rem; background: #10b981; color: white; border: none; border-radius: 0.375rem; cursor: pointer;" onclick="downloadNLLBModel(event)">下载/修复 NLLB</button>
                    </div>

                    ${causalLmCards}

                    <!-- Opus-MT 系列 -->
                    <div data-download-card style="border: 1px solid var(--border-color); border-radius: 0.5rem; padding: 1.5rem;">
                        <h4 style="margin-bottom: 0.5rem;">Opus-MT 系列</h4>
                        <p style="color: #666; font-size: 0.9rem; margin-bottom: 1rem;">Helsinki-NLP 多语言对模型</p>
                        <div style="margin-bottom: 1rem;">
                            <span style="background: #e0f2fe; color: #0369a1; padding: 0.25rem 0.5rem; border-radius: 0.25rem; font-size: 0.8rem;">高质量</span>
                            <span style="background: #fef3c7; color: #92400e; padding: 0.25rem 0.5rem; border-radius: 0.25rem; font-size: 0.8rem; margin-left: 0.5rem;">~300MB</span>
                        </div>
                        <input id="opus-model-name" class="form-control" value="Helsinki-NLP/opus-mt-en-zh" placeholder="Helsinki-NLP/opus-mt-en-zh" style="width: 100%; padding: 0.5rem; border: 2px solid var(--border-color); border-radius: 0.5rem; margin-bottom: 0.75rem;">
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem;">
                            <button class="btn" style="padding: 0.5rem; background: #10b981; color: white; border: none; border-radius: 0.375rem; cursor: pointer;" onclick="downloadCustomOpusMTModel(event)">下载模型</button>
                            <button class="btn" style="padding: 0.5rem; background: #3b82f6; color: white; border: none; border-radius: 0.375rem; cursor: pointer;" onclick="downloadMarianModel()">常用列表</button>
                        </div>
                    </div>

                    <!-- M2M100 大模型 -->
                    <div data-download-card style="border: 1px solid var(--border-color); border-radius: 0.5rem; padding: 1.5rem;">
                        <h4 style="margin-bottom: 0.5rem;">M2M100 (1.2B)</h4>
                        <p style="color: #666; font-size: 0.9rem; margin-bottom: 1rem;">更大更准确的 M2M100 版本</p>
                        <div style="margin-bottom: 1rem;">
                            <span style="background: #e0f2fe; color: #0369a1; padding: 0.25rem 0.5rem; border-radius: 0.25rem; font-size: 0.8rem;">高精度</span>
                            <span style="background: #fef3c7; color: #92400e; padding: 0.25rem 0.5rem; border-radius: 0.25rem; font-size: 0.8rem; margin-left: 0.5rem;">4.5GB</span>
                        </div>
                        <button class="btn" style="width: 100%; padding: 0.5rem; background: #10b981; color: white; border: none; border-radius: 0.375rem; cursor: pointer;" onclick="downloadM2M100LargeModel(event)">下载/修复 1.2B</button>
                    </div>
                </div>
            </div>
        </div>

        <div class="card" style="margin-top: 1.5rem;">
            <div class="card-header">
                <h3 class="card-title">模型配置</h3>
            </div>

            <div class="model-config-grid">
                <section class="model-config-panel">
                    <h4>模型存储路径</h4>
                    <div class="model-path-list">
                        <div class="model-path-item">
                            <span class="model-path-label">HuggingFace 缓存</span>
                            <span class="model-path-value">~/.cache/huggingface/</span>
                        </div>
                        <div class="model-path-item">
                            <span class="model-path-label">Argos 语言包</span>
                            <span class="model-path-value">~/.local/share/argos-translate/</span>
                        </div>
                        <div class="model-path-item">
                            <span class="model-path-label">CTranslate2 模型</span>
                            <span class="model-path-value">./models/ctranslate2/</span>
                        </div>
                    </div>
                </section>

                <section class="model-config-panel">
                    <h4>运行配置</h4>
                    <div class="config-field">
                        <label>加速设备</label>
                        <div class="toggle-row">
                            <div class="toggle-text">
                                <strong>启用 GPU 加速</strong>
                                <span>需要服务器 CUDA 环境，保存后重启服务生效</span>
                            </div>
                            <label class="switch" title="启用 GPU 加速">
                                <input type="checkbox" id="use-gpu" ${modelConfig.use_gpu ? 'checked' : ''}>
                                <span class="switch-slider"></span>
                            </label>
                        </div>
                        <div class="field-hint">当前设备: <strong>${modelConfig.device || 'cpu'}</strong></div>
                    </div>

                    <div class="config-field">
                        <label for="default-model">默认模型</label>
                        <select id="default-model" class="form-control">
                            <option value="argos" ${defaultModel === 'argos' ? 'selected' : ''}>Argos (快速)</option>
                            <option value="marian" ${defaultModel === 'marian' ? 'selected' : ''}>MarianMT (准确)</option>
                            <option value="m2m100" ${defaultModel === 'm2m100' ? 'selected' : ''}>M2M100 (多语言)</option>
                            <option value="m2m100_1_2b" ${defaultModel === 'm2m100_1_2b' ? 'selected' : ''}>M2M100 1.2B (高精度)</option>
                            <option value="nllb" ${defaultModel === 'nllb' ? 'selected' : ''}>NLLB-200 (多语言)</option>
                            <option value="qwen3_1_7b" ${defaultModel === 'qwen3_1_7b' ? 'selected' : ''}>Qwen3 1.7B</option>
                            <option value="gemma3_1b" ${defaultModel === 'gemma3_1b' ? 'selected' : ''}>Gemma 3 1B</option>
                            <option value="qwen2_5_0_5b" ${defaultModel === 'qwen2_5_0_5b' ? 'selected' : ''}>Qwen2.5 0.5B</option>
                        </select>
                        <div class="field-hint">未显式指定模型的 API 请求会使用这里的默认模型</div>
                    </div>

                    <button class="btn btn-primary" onclick="saveModelConfig()">
                        保存配置
                    </button>
                </section>
            </div>
        </div>

        <div class="card" style="margin-top: 1.5rem;">
            <div class="card-header">
                <h3 class="card-title">使用说明</h3>
            </div>

            <div style="padding: 1.5rem;">
                <h4>🚀 快速开始</h4>
                <ol style="line-height: 1.8; color: #666;">
                    <li>选择需要的模型或语言包进行安装</li>
                    <li>等待下载完成（首次使用会自动下载）</li>
                    <li>在翻译接口中指定使用的模型</li>
                </ol>

                <h4 style="margin-top: 2rem;">💡 模型选择建议</h4>
                <ul style="line-height: 1.8; color: #666;">
                    <li><strong>Argos:</strong> 适合快速翻译、离线使用</li>
                    <li><strong>MarianMT:</strong> 适合高质量双语翻译</li>
                    <li><strong>M2M100:</strong> 适合多语言互译、小语种</li>
                    <li><strong>Qwen/Gemma:</strong> 适合通用文本翻译和更灵活的表达，但推理更慢、资源占用更高</li>
                </ul>

                <h4 style="margin-top: 2rem;">⚙️ 镜像加速</h4>
                <p style="color: #666; margin-bottom: 0.5rem;">国内下载 HuggingFace 模型较慢，可以使用镜像：</p>
                <pre style="background: #1e293b; color: #e2e8f0; padding: 1rem; border-radius: 0.5rem; overflow-x: auto;">export HF_ENDPOINT=https://hf-mirror.com</pre>
            </div>
        </div>
    `;
    } catch (error) {
        console.error('加载模型管理失败:', error);
        contentArea.innerHTML = `
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">模型管理</h3>
                </div>
                <div style="padding: 2rem; text-align: center;">
                    <p style="color: #ef4444;">模型信息加载失败，请检查登录状态或服务日志</p>
                    <button class="btn btn-primary" onclick="loadModels()" style="margin-top: 1rem; padding: 0.5rem 1.5rem; background: #3b82f6; color: white; border: none; border-radius: 0.375rem; cursor: pointer;">重新加载</button>
                </div>
            </div>
        `;
    }
}

// 管理 Argos 语言包
async function manageArgosPackages() {
    const contentArea = document.getElementById('content-area');

    contentArea.innerHTML = '<div style="text-align: center; padding: 3rem;"><p>加载中...</p></div>';

    try {
        // 获取可用语言包
        const response = await fetch('/admin/models/argos/available', { headers });

        if (!response.ok) {
            throw new Error('获取语言包列表失败');
        }

        const data = await response.json();
        const packages = data.packages || [];

        const languageName = (code, fallback) => fallback || code;
        const jsString = (value) => String(value || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'");
        const grouped = packages.reduce((acc, pkg) => {
            const key = pkg.from_code || 'unknown';
            if (!acc[key]) {
                acc[key] = {
                    code: key,
                    name: languageName(key, pkg.from_name),
                    packages: []
                };
            }
            acc[key].packages.push(pkg);
            return acc;
        }, {});

        const groups = Object.values(grouped).sort((a, b) => a.name.localeCompare(b.name));
        const installedPackages = packages.filter(pkg => pkg.installed);
        const renderPackageCard = (pkg) => {
                const statusBadge = pkg.installed
                    ? '<span class="badge badge-success">✓ 已安装</span>'
                    : '<span class="badge" style="background: #e0e7ff; color: #4338ca;">未安装</span>';

                const buttonHTML = pkg.installed
                    ? '<button class="btn btn-sm" disabled style="padding: 0.5rem 1rem; background: #94a3b8; color: white; border: none; border-radius: 0.375rem; cursor: not-allowed;">已安装</button>'
                    : `<button class="btn btn-sm btn-success" onclick="installArgosPackageReal(event, '${jsString(pkg.from_code)}', '${jsString(pkg.to_code)}')" style="padding: 0.5rem 1rem; background: #10b981; color: white; border: none; border-radius: 0.375rem; cursor: pointer;">立即安装</button>`;

                return `
                    <div data-download-card class="argos-package-card">
                        <div class="argos-package-card-head">
                            <h5>${escapeHTML(pkg.from_name)} → ${escapeHTML(pkg.to_name)}</h5>
                            ${statusBadge}
                        </div>
                        <p>${escapeHTML(pkg.from_code)} → ${escapeHTML(pkg.to_code)}</p>
                        ${buttonHTML}
                    </div>
                `;
        };

        const renderGrid = (items) => items.length
            ? `<div class="argos-package-grid">${items.map(renderPackageCard).join('')}</div>`
            : '<div class="argos-empty">暂无语言包</div>';

        const allPackagesHTML = packages.length
            ? renderGrid(packages)
            : '<div class="argos-empty">暂无可用语言包</div>';

        const installedPackagesHTML = installedPackages.length
            ? renderGrid(installedPackages)
            : '<div class="argos-empty">当前还没有安装 Argos 语言包</div>';

        const tabsHTML = [
            `<button type="button" class="argos-tab active" data-argos-tab="all" aria-selected="true">全部 <span>${packages.length}</span></button>`,
            `<button type="button" class="argos-tab" data-argos-tab="installed" aria-selected="false">已安装 <span>${installedPackages.length}</span></button>`,
            ...groups.map(group => `
                <button type="button" class="argos-tab" data-argos-tab="${escapeHTML(group.code)}" aria-selected="false">
                    ${escapeHTML(group.name)} <span>${group.packages.length}</span>
                </button>
            `)
        ].join('');

        const panelsHTML = [
            `<section class="argos-tab-panel active" data-argos-panel="all">${allPackagesHTML}</section>`,
            `<section class="argos-tab-panel" data-argos-panel="installed">${installedPackagesHTML}</section>`,
            ...groups.map(group => `
                <section class="argos-tab-panel" data-argos-panel="${escapeHTML(group.code)}">
                    <div class="argos-source-summary">
                        <strong>${escapeHTML(group.name)}</strong>
                        <span>${escapeHTML(group.code)} 可安装 ${group.packages.length} 个目标语言包</span>
                    </div>
                    ${renderGrid(group.packages)}
                </section>
            `)
        ].join('');

        contentArea.innerHTML = `
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">Argos 语言包管理</h3>
                    <button class="btn" onclick="loadModels()" style="padding: 0.5rem 1rem; background: #64748b; color: white; border: none; border-radius: 0.375rem; cursor: pointer;">← 返回</button>
                </div>

                <div style="padding: 1.5rem;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; gap: 1rem;">
                        <h4 style="margin: 0;">可用语言包 (${packages.length})</h4>
                        <button class="btn" onclick="manageArgosPackages()" style="padding: 0.5rem 1rem; background: #3b82f6; color: white; border: none; border-radius: 0.375rem; cursor: pointer;">🔄 刷新</button>
                    </div>

                    <div class="argos-package-layout">
                        <div class="argos-tabs" role="tablist">
                            ${tabsHTML}
                        </div>
                        <div class="argos-panels">
                            ${panelsHTML}
                        </div>
                    </div>

                    <div style="margin-top: 2rem; padding: 1rem; background: #f0f9ff; border-left: 4px solid #3b82f6; border-radius: 0.5rem;">
                        <h5 style="margin-top: 0;">💡 说明</h5>
                        <ul style="margin: 0; padding-left: 1.5rem; color: #666; line-height: 1.8;">
                            <li>点击"立即安装"会<strong>真实下载</strong>语言包到服务器</li>
                            <li>安装过程需要几秒到几分钟（取决于网络速度）</li>
                            <li>安装后即可在翻译 API 中使用该语言对</li>
                            <li>已安装的包会在列表中标记</li>
                        </ul>
                    </div>
                </div>
            </div>
        `;
        bindArgosTabs();

    } catch (error) {
        console.error('加载语言包失败:', error);
        contentArea.innerHTML = `
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">Argos 语言包管理</h3>
                    <button class="btn" onclick="loadModels()" style="padding: 0.5rem 1rem; background: #64748b; color: white; border: none; border-radius: 0.375rem; cursor: pointer;">← 返回</button>
                </div>
                <div style="padding: 2rem; text-align: center;">
                    <p style="color: #ef4444;">加载失败，请重试</p>
                    <button class="btn btn-primary" onclick="manageArgosPackages()" style="margin-top: 1rem; padding: 0.5rem 1.5rem; background: #3b82f6; color: white; border: none; border-radius: 0.375rem; cursor: pointer;">重新加载</button>
                </div>
            </div>
        `;
    }
}

function bindArgosTabs() {
    const tabs = Array.from(document.querySelectorAll('.argos-tab'));
    const panels = Array.from(document.querySelectorAll('.argos-tab-panel'));

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const selected = tab.dataset.argosTab;

            tabs.forEach(item => {
                const isActive = item === tab;
                item.classList.toggle('active', isActive);
                item.setAttribute('aria-selected', String(isActive));
            });

            panels.forEach(panel => {
                panel.classList.toggle('active', panel.dataset.argosPanel === selected);
            });
        });
    });
}

// 真实安装 Argos 语言包
async function installArgosPackageReal(event, source, target) {
    const confirmed = confirm(`确定要安装 ${source} → ${target} 语言包吗？\n\n这将会下载并安装真实的语言包（约 50-100MB）`);

    if (!confirmed) return;

    // 显示安装进度
    const button = event.currentTarget;
    button.disabled = true;
    button.textContent = '安装中...';
    button.style.background = '#94a3b8';

    try {
        const response = await fetch('/admin/models/argos/install', {
            method: 'POST',
            headers: {
                ...headers,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                source_lang: source,
                target_lang: target
            })
        });

        const result = await response.json();

        if (response.ok && result.success && result.task_id) {
            await pollDownloadTask(result.task_id, {
                title: `安装 Argos ${source} → ${target}`,
                anchor: button,
                onComplete: async () => {
                    alert(`✓ 安装成功！\n\n现在可以使用 ${source} → ${target} 进行翻译了`);
                    await manageArgosPackages();
                }
            });
        } else {
            alert(`✗ 安装失败\n\n${result.message || result.detail || '未知错误'}`);
            button.disabled = false;
            button.textContent = '立即安装';
            button.style.background = '#10b981';
        }

    } catch (error) {
        console.error('安装失败:', error);
        alert(`安装出错: ${error.message}`);
        button.disabled = false;
        button.textContent = '立即安装';
        button.style.background = '#10b981';
    }
}

// 下载 MarianMT 模型
async function downloadMarianModel() {
    const contentArea = document.getElementById('content-area');

    contentArea.innerHTML = '<div style="text-align: center; padding: 3rem;"><p>加载中...</p></div>';

    try {
        const response = await fetch('/admin/models/marian/available', { headers });

        if (!response.ok) {
            throw new Error('获取模型列表失败');
        }

        const data = await response.json();
        const models = data.models || [];

        let modelsHTML = '';

        if (models.length === 0) {
            modelsHTML = '<div style="padding: 2rem; text-align: center; color: #666;">暂无可用模型</div>';
        } else {
            modelsHTML = models.map(model => {
                const statusBadge = model.downloaded
                    ? '<span class="badge badge-success">✓ 已下载</span>'
                    : '<span class="badge" style="background: #e0e7ff; color: #4338ca;">未下载</span>';

                const buttonHTML = model.downloaded
                    ? model.ctranslate2_converted
                        ? '<button class="btn btn-sm" disabled style="padding: 0.5rem 1rem; background: #0f766e; color: white; border: none; border-radius: 0.375rem; cursor: not-allowed;">CT2 已就绪</button>'
                        : `<button class="btn btn-sm" onclick="convertMarianModelToCT2(event, '${model.model_name}')" style="padding: 0.5rem 1rem; background: #0f766e; color: white; border: none; border-radius: 0.375rem; cursor: pointer;">转换 CT2</button>`
                    : `<button class="btn btn-sm btn-success" onclick="downloadMarianModelReal(event, '${model.model_name}')" style="padding: 0.5rem 1rem; background: #10b981; color: white; border: none; border-radius: 0.375rem; cursor: pointer;">立即下载</button>`;

                return `
                    <div data-download-card style="border: 1px solid var(--border-color); padding: 1.25rem; border-radius: 0.5rem;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
                            <h5 style="margin: 0;">${model.from_name} → ${model.to_name}</h5>
                            ${statusBadge}
                        </div>
                        <p style="color: #666; font-size: 0.875rem; margin-bottom: 0.5rem;">
                            <strong>模型:</strong> ${model.model_name}
                        </p>
                        <p style="color: #666; font-size: 0.875rem; margin-bottom: 0.5rem;">
                            <strong>大小:</strong> ${model.size} | <strong>质量:</strong> ${model.quality}
                        </p>
                        <p style="color: #666; font-size: 0.875rem; margin-bottom: 0.5rem;">
                            <strong>CTranslate2:</strong> ${model.ctranslate2_converted ? '已转换，可用于加速' : (model.downloaded ? '可转换为 int8 本地推理' : '需先下载模型')}
                        </p>
                        <div style="margin-top: 1rem;">
                            ${buttonHTML}
                        </div>
                    </div>
                `;
            }).join('');
        }

        contentArea.innerHTML = `
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">MarianMT 模型下载</h3>
                    <button class="btn" onclick="loadModels()" style="padding: 0.5rem 1rem; background: #64748b; color: white; border: none; border-radius: 0.375rem; cursor: pointer;">← 返回</button>
                </div>

                <div style="padding: 1.5rem;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                        <h4 style="margin: 0;">可用模型 (${models.length})</h4>
                        <button class="btn" onclick="downloadMarianModel()" style="padding: 0.5rem 1rem; background: #3b82f6; color: white; border: none; border-radius: 0.375rem; cursor: pointer;">🔄 刷新</button>
                    </div>

                    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 1rem;">
                        ${modelsHTML}
                    </div>

                    <div style="margin-top: 2rem; padding: 1rem; background: #fef3c7; border-left: 4px solid #f59e0b; border-radius: 0.5rem;">
                        <h5 style="margin-top: 0;">⚠️ 注意</h5>
                        <ul style="margin: 0; padding-left: 1.5rem; color: #92400e; line-height: 1.8;">
                            <li>MarianMT 模型较大（约 300MB），下载需要时间</li>
                            <li>首次下载会从 HuggingFace 下载，国内可能较慢</li>
                            <li>建议使用镜像加速：export HF_ENDPOINT=https://hf-mirror.com</li>
                            <li>下载的模型会缓存到 ~/.cache/huggingface/</li>
                            <li>下载完成后可转换 CTranslate2 int8，本地 CPU 推理通常更快</li>
                        </ul>
                    </div>
                </div>
            </div>
        `;

    } catch (error) {
        console.error('加载模型列表失败:', error);
        contentArea.innerHTML = `
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">MarianMT 模型下载</h3>
                    <button class="btn" onclick="loadModels()" style="padding: 0.5rem 1rem; background: #64748b; color: white; border: none; border-radius: 0.375rem; cursor: pointer;">← 返回</button>
                </div>
                <div style="padding: 2rem; text-align: center;">
                    <p style="color: #ef4444;">加载失败，请重试</p>
                    <button class="btn btn-primary" onclick="downloadMarianModel()" style="margin-top: 1rem; padding: 0.5rem 1.5rem; background: #3b82f6; color: white; border: none; border-radius: 0.375rem; cursor: pointer;">重新加载</button>
                </div>
            </div>
        `;
    }
}

// 真实下载 MarianMT 模型
async function downloadMarianModelReal(event, modelName) {
    const confirmed = confirm(`确定要下载模型吗？\n\n${modelName}\n\n大小: ~300MB\n下载时间: 几分钟（取决于网络）`);

    if (!confirmed) return;

    // 显示下载进度
    const button = event.currentTarget;
    button.disabled = true;
    button.textContent = '下载中...';
    button.style.background = '#94a3b8';

    try {
        const response = await fetch(`/admin/models/marian/download?model_name=${encodeURIComponent(modelName)}`, {
            method: 'POST',
            headers
        });

        const result = await response.json();

        if (response.ok && result.success && result.task_id) {
            await pollDownloadTask(result.task_id, {
                title: `下载 ${modelName}`,
                anchor: button,
                onComplete: async () => {
                    alert('✓ 下载成功！\n\n模型已缓存，现在可以使用了');
                    await downloadMarianModel();
                }
            });
        } else {
            alert(`✗ 下载失败\n\n${result.message || result.detail || '未知错误'}`);
            button.disabled = false;
            button.textContent = '立即下载';
            button.style.background = '#10b981';
        }

    } catch (error) {
        console.error('下载失败:', error);
        alert(`下载出错: ${error.message}`);
        button.disabled = false;
        button.textContent = '立即下载';
        button.style.background = '#10b981';
    }
}

// 转换 MarianMT 为 CTranslate2
async function convertMarianModelToCT2(event, modelName) {
    const confirmed = confirm(`确定要转换为 CTranslate2 吗？\n\n${modelName}\n\n转换会占用 CPU 和磁盘空间，完成后 MarianMT auto 后端会优先使用 CT2 本地模型。`);

    if (!confirmed) return;

    const button = event.currentTarget;
    button.disabled = true;
    button.textContent = '转换中...';
    button.style.background = '#94a3b8';

    try {
        const response = await fetch(`/admin/models/marian/convert-ct2?model_name=${encodeURIComponent(modelName)}`, {
            method: 'POST',
            headers
        });
        const result = await response.json();

        if (!response.ok || !result.success || !result.task_id) {
            throw new Error(result.detail || result.message || '转换失败');
        }

        await pollDownloadTask(result.task_id, {
            title: `转换 CT2 ${modelName}`,
            anchor: button,
            onComplete: async () => {
                await downloadMarianModel();
            }
        });
    } catch (error) {
        alert(`CT2 转换失败: ${error.message}`);
        button.disabled = false;
        button.textContent = '转换 CT2';
        button.style.background = '#0f766e';
    }
}

// 下载自定义 Opus-MT 模型
async function downloadCustomOpusMTModel(event) {
    const input = document.getElementById('opus-model-name');
    const modelName = input?.value.trim();

    if (!modelName) {
        alert('请输入 Opus-MT 模型名称');
        return;
    }

    if (!/^Helsinki-NLP\/opus-mt-[A-Za-z0-9_-]+$/.test(modelName)) {
        alert('模型名称格式不正确，应为 Helsinki-NLP/opus-mt-{源语言}-{目标语言}');
        return;
    }

    const button = event.currentTarget;
    button.disabled = true;
    button.textContent = '下载中...';
    button.style.background = '#94a3b8';

    try {
        const response = await fetch(`/admin/models/marian/download?model_name=${encodeURIComponent(modelName)}`, {
            method: 'POST',
            headers
        });
        const result = await response.json();

        if (!response.ok || !result.success || !result.task_id) {
            throw new Error(result.detail || result.message || '下载失败');
        }

        await pollDownloadTask(result.task_id, {
            title: `下载 ${modelName}`,
            anchor: button,
            onComplete: async () => {
                button.textContent = '已下载';
                await loadModels();
            }
        });
    } catch (error) {
        alert(`Opus-MT 下载失败: ${error.message}`);
        button.disabled = false;
        button.textContent = '下载模型';
        button.style.background = '#10b981';
    }
}

// 下载/修复 M2M100 标准模型
async function downloadM2M100Model(event) {
    const confirmed = confirm(
        '确定要下载/修复 M2M100 标准模型吗？\n\n' +
        '模型: facebook/m2m100_418M\n' +
        '大小: 约 1.2GB\n\n' +
        '下载完成后会写入 HuggingFace 本地缓存，翻译时将只从本地加载。'
    );

    if (!confirmed) return;

    const button = event.currentTarget;
    button.disabled = true;
    button.textContent = '下载中...';
    button.style.background = '#94a3b8';

    try {
        const response = await fetch('/admin/models/m2m100/download', {
            method: 'POST',
            headers
        });
        const result = await response.json();

        if (response.ok && result.success && result.task_id) {
            await pollDownloadTask(result.task_id, {
                title: '下载 M2M100 标准模型',
                anchor: button,
                onComplete: async () => {
                    alert('✓ 下载成功！\n\n现在可以从本地加载 M2M100 了');
                    await loadModels();
                }
            });
        } else {
            throw new Error(result.detail || result.message || '下载失败');
        }
    } catch (error) {
        alert(`M2M100 下载失败: ${error.message}`);
        button.disabled = false;
        button.textContent = '下载/修复';
        button.style.background = '#10b981';
    }
}

// 转换 M2M100 标准模型为 CTranslate2
async function convertM2M100ModelToCT2(event) {
    await convertM2M100ModelToCT2Real(event, '/admin/models/m2m100/convert-ct2', 'M2M100 标准模型');
}

// 转换 M2M100 1.2B 模型为 CTranslate2
async function convertM2M100LargeModelToCT2(event) {
    await convertM2M100ModelToCT2Real(event, '/admin/models/m2m100-large/convert-ct2', 'M2M100 1.2B');
}

async function convertM2M100ModelToCT2Real(event, endpoint, label) {
    const confirmed = confirm(
        `确定要将 ${label} 转换为 CTranslate2 吗？\n\n` +
        `转换会占用较多 CPU、内存和磁盘空间。完成后 M2M100_BACKEND=auto 会优先调用 CT2 本地模型。`
    );

    if (!confirmed) return;

    const button = event.currentTarget;
    button.disabled = true;
    button.textContent = '转换中...';
    button.style.background = '#94a3b8';

    try {
        const response = await fetch(endpoint, {
            method: 'POST',
            headers
        });
        const result = await response.json();

        if (!response.ok || !result.success || !result.task_id) {
            throw new Error(result.detail || result.message || '转换失败');
        }

        await pollDownloadTask(result.task_id, {
            title: `转换 CT2 ${label}`,
            anchor: button,
            onComplete: async () => {
                await loadModels();
            }
        });
    } catch (error) {
        alert(`${label} CT2 转换失败: ${error.message}`);
        button.disabled = false;
        button.textContent = '转换 CT2';
        button.style.background = '#0f766e';
    }
}

// 下载/修复 M2M100 1.2B 模型
async function downloadM2M100LargeModel(event) {
    const confirmed = confirm(
        '确定要下载/修复 M2M100 1.2B 模型吗？\n\n' +
        '模型: facebook/m2m100_1.2B\n' +
        '大小: 约 4.5GB\n\n' +
        '下载完成后会写入 HuggingFace 本地缓存，翻译时将只从本地加载。'
    );

    if (!confirmed) return;

    const button = event.currentTarget;
    button.disabled = true;
    button.textContent = '下载中...';
    button.style.background = '#94a3b8';

    try {
        const response = await fetch('/admin/models/m2m100-large/download', {
            method: 'POST',
            headers
        });
        const result = await response.json();

        if (!response.ok || !result.success || !result.task_id) {
            throw new Error(result.detail || result.message || '下载失败');
        }

        await pollDownloadTask(result.task_id, {
            title: '下载 M2M100 1.2B',
            anchor: button,
            onComplete: async () => {
                await loadModels();
            }
        });
    } catch (error) {
        alert(`M2M100 1.2B 下载失败: ${error.message}`);
        button.disabled = false;
        button.textContent = '下载/修复 1.2B';
        button.style.background = '#10b981';
    }
}

// 下载/修复 NLLB 模型
async function downloadNLLBModel(event) {
    const confirmed = confirm(
        '确定要下载/修复 NLLB-200 模型吗？\n\n' +
        '默认模型: facebook/nllb-200-distilled-600M\n' +
        '大小: 约 2.5GB+\n\n' +
        '下载完成后会写入 HuggingFace 本地缓存，翻译时将只从本地加载。'
    );

    if (!confirmed) return;

    const button = event.currentTarget;
    button.disabled = true;
    button.textContent = '下载中...';
    button.style.background = '#94a3b8';

    try {
        const response = await fetch('/admin/models/nllb/download', {
            method: 'POST',
            headers
        });
        const result = await response.json();

        if (!response.ok || !result.success || !result.task_id) {
            throw new Error(result.detail || result.message || '下载失败');
        }

        await pollDownloadTask(result.task_id, {
            title: '下载 NLLB-200',
            anchor: button,
            onComplete: async () => {
                await loadModels();
            }
        });
    } catch (error) {
        alert(`NLLB 下载失败: ${error.message}`);
        button.disabled = false;
        button.textContent = '下载/修复 NLLB';
        button.style.background = '#10b981';
    }
}

// 下载/修复通用大语言模型
async function downloadCausalLMModel(event, modelId) {
    const modelConfig = CAUSAL_LM_MODELS.find(model => model.value === modelId);
    const modelInfo = window.modelManagementStatus?.[modelId];
    const label = modelConfig?.label || modelId;
    const modelName = modelInfo?.model_name || modelConfig?.modelName || modelId;
    const size = modelInfo?.size || modelConfig?.size || '1GB+';
    const authLine = modelId === 'gemma3_1b'
        ? '\n提示: Gemma 可能需要先在 HuggingFace 接受许可并配置访问令牌。'
        : '';
    const confirmed = confirm(
        `确定要下载/修复 ${label} 吗？\n\n` +
        `模型: ${modelName}\n` +
        `大小: ${size}\n\n` +
        `下载完成后会写入 HuggingFace 本地缓存，翻译时将只从本地加载。${authLine}`
    );

    if (!confirmed) return;

    const button = event.currentTarget;
    button.disabled = true;
    button.textContent = '下载中...';
    button.style.background = '#94a3b8';
    button.style.color = 'white';

    try {
        const response = await fetch(`/admin/models/causal-lm/download?model_id=${encodeURIComponent(modelId)}`, {
            method: 'POST',
            headers
        });
        const result = await response.json();

        if (!response.ok || !result.success || !result.task_id) {
            throw new Error(result.detail || result.message || '下载失败');
        }

        await pollDownloadTask(result.task_id, {
            title: `下载 ${label}`,
            anchor: button,
            onComplete: async () => {
                await loadModels();
            }
        });
    } catch (error) {
        alert(`${label} 下载失败: ${error.message}`);
        button.disabled = false;
        button.textContent = '下载/修复';
        button.style.background = '#10b981';
        button.style.color = 'white';
    }
}

// 转换 NLLB 模型为 CTranslate2
async function convertNLLBModelToCT2(event) {
    const confirmed = confirm(
        '确定要将 NLLB-200 转换为 CTranslate2 吗？\n\n' +
        '转换会占用较多 CPU、内存和磁盘空间。完成后 NLLB_BACKEND=auto 会优先调用 CT2 本地模型。'
    );

    if (!confirmed) return;

    const button = event.currentTarget;
    button.disabled = true;
    button.textContent = '转换中...';
    button.style.background = '#94a3b8';

    try {
        const response = await fetch('/admin/models/nllb/convert-ct2', {
            method: 'POST',
            headers
        });
        const result = await response.json();

        if (!response.ok || !result.success || !result.task_id) {
            throw new Error(result.detail || result.message || '转换失败');
        }

        await pollDownloadTask(result.task_id, {
            title: '转换 CT2 NLLB-200',
            anchor: button,
            onComplete: async () => {
                await loadModels();
            }
        });
    } catch (error) {
        alert(`NLLB CT2 转换失败: ${error.message}`);
        button.disabled = false;
        button.textContent = '转换 CT2';
        button.style.background = '#0f766e';
    }
}

// 显示模型信息
function showModelInfo(modelName) {
    let info = '';

    switch(modelName) {
        case 'm2m100':
            info = `模型: M2M100 (facebook/m2m100_418M)\n\n` +
                   `特点:\n` +
                   `- 支持 100 种语言互译\n` +
                   `- 模型大小: 1.2GB\n` +
                   `- 推理速度: 中等\n` +
                   `- 适用场景: 多语言、小语种\n` +
                   `- 质量: 良好\n\n` +
                   `支持的语言包括:\n` +
                   `en, zh, ja, ko, fr, de, es, ru, ar, hi, th 等`;
            break;
        case 'm2m100_1_2b':
            info = `模型: M2M100 1.2B (facebook/m2m100_1.2B)\n\n` +
                   `特点:\n` +
                   `- 支持多语言互译\n` +
                   `- 模型大小: 约 4.5GB\n` +
                   `- 推理速度: 慢于标准版\n` +
                   `- 适用场景: 更高质量的离线多语言翻译\n\n` +
                   `运行时只从本地 HuggingFace 缓存加载。`;
            break;
        case 'nllb':
            info = `模型: NLLB-200 (facebook/nllb-200-distilled-600M)\n\n` +
                   `特点:\n` +
                   `- Meta 多语言翻译模型\n` +
                   `- 默认接入 distilled 版本，更适合本地部署\n` +
                   `- 可通过 NLLB_MODEL 环境变量切换到更大版本\n\n` +
                   `运行时只从本地 HuggingFace 缓存加载。`;
            break;
        case 'qwen3_1_7b':
            info = `模型: Qwen3 1.7B\n\n` +
                   `默认仓库: Qwen/Qwen3-1.7B\n\n` +
                   `特点:\n` +
                   `- 通用大语言模型翻译\n` +
                   `- 使用 Transformers CausalLM 本地推理\n` +
                   `- 支持通过 QWEN3_MODEL 环境变量替换仓库\n\n` +
                   `运行时只从本地 HuggingFace 缓存加载。`;
            break;
        case 'gemma3_1b':
            info = `模型: Gemma 3 1B\n\n` +
                   `默认仓库: google/gemma-3-1b-it\n\n` +
                   `特点:\n` +
                   `- Google Gemma 3 指令模型\n` +
                   `- 使用 Transformers CausalLM 本地推理\n` +
                   `- 可能需要先在 HuggingFace 接受许可并配置访问令牌\n` +
                   `- 支持通过 GEMMA3_MODEL 环境变量替换仓库\n\n` +
                   `运行时只从本地 HuggingFace 缓存加载。`;
            break;
        case 'qwen2_5_0_5b':
            info = `模型: Qwen2.5 0.5B\n\n` +
                   `默认仓库: Qwen/Qwen2.5-0.5B-Instruct\n\n` +
                   `特点:\n` +
                   `- 轻量指令模型，资源占用较低\n` +
                   `- 使用 Transformers CausalLM 本地推理\n` +
                   `- 支持通过 QWEN2_5_MODEL 环境变量替换仓库\n\n` +
                   `运行时只从本地 HuggingFace 缓存加载。`;
            break;
        default:
            info = `模型信息正在加载...`;
    }

    alert(info);
}

// 保存模型配置
async function saveModelConfig() {
    const useGPU = document.getElementById('use-gpu').checked;
    const defaultModel = document.getElementById('default-model').value;

    try {
        const response = await fetch('/admin/models/config', {
            method: 'POST',
            headers,
            body: JSON.stringify({
                use_gpu: useGPU,
                default_model: defaultModel
            })
        });
        const result = await response.json();

        if (!response.ok || !result.success) {
            throw new Error(result.detail || result.message || '保存失败');
        }

        alert(`配置已保存！\n\nGPU 加速: ${useGPU ? '已启用' : '未启用'}\n默认模型: ${result.default_model}\n\n提示：修改后需要重启服务才能对已初始化模型生效`);
    } catch (error) {
        alert(`配置保存失败: ${error.message}`);
    }
}

// 调用日志
async function loadLogs() {
    const contentArea = document.getElementById('content-area');

    contentArea.innerHTML = '<div style="text-align: center; padding: 3rem;"><p>加载中...</p></div>';

    try {
        const response = await fetch('/admin/logs?limit=100', { headers });
        if (!response.ok) throw new Error('获取调用日志失败');

        const data = await response.json();
        const logs = data.logs || [];
        const rows = logs.map(log => `
            <tr>
                <td>${new Date(log.created_at).toLocaleString()}</td>
                <td>${log.api_key_name || '-'}</td>
                <td>${log.source_lang} → ${log.target_lang}</td>
                <td>
                    ${log.model_used}
                    ${log.model_backend ? `<br><small style="color: #666;">${log.model_backend}</small>` : ''}
                    ${log.actual_model_name ? `<br><small style="color: #666;">${log.actual_model_name}</small>` : ''}
                </td>
                <td>${log.char_count}</td>
                <td>${log.response_time_ms}ms</td>
                <td>
                    <small>
                        加载 ${log.model_load_ms || 0}ms<br>
                        推理 ${log.inference_ms || 0}ms<br>
                        格式 ${log.format_ms || 0}ms<br>
                        ${log.segment_count || 0} 段 / ${log.batch_count || 0} 批
                    </small>
                </td>
                <td>
                    <span class="badge ${log.success ? 'badge-success' : 'badge-danger'}">
                        ${log.success ? '成功' : '失败'}
                    </span>
                </td>
                <td>${log.error_message || '-'}</td>
            </tr>
        `).join('');

        contentArea.innerHTML = `
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">调用日志</h3>
                    <button class="btn" onclick="loadLogs()" style="padding: 0.5rem 1rem; background: #3b82f6; color: white; border: none; border-radius: 0.375rem; cursor: pointer;">刷新</button>
                </div>
                <div style="padding: 1rem; color: #666;">共 ${data.total || 0} 条记录，当前显示 ${logs.length} 条</div>
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>时间</th>
                                <th>API Key</th>
                                <th>语言</th>
                                <th>模型</th>
                                <th>字符数</th>
                                <th>响应时间</th>
                                <th>耗时拆分</th>
                                <th>状态</th>
                                <th>错误</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${rows || '<tr><td colspan="9" style="text-align: center; padding: 2rem; color: #666;">暂无调用记录</td></tr>'}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    } catch (error) {
        console.error('加载调用日志失败:', error);
        contentArea.innerHTML = `
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">调用日志</h3>
                </div>
                <p style="padding: 1rem; color: #ef4444;">加载失败：${error.message}</p>
            </div>
        `;
    }
}

// 系统设置
async function loadSettings() {
    const contentArea = document.getElementById('content-area');

    contentArea.innerHTML = '<div style="text-align: center; padding: 3rem;"><p>加载中...</p></div>';

    try {
        const response = await fetch('/admin/settings', { headers });
        if (!response.ok) throw new Error('获取系统设置失败');

        const settings = await response.json();
        const configuredApiBaseUrl = normalizeApiBaseUrl(settings.api_base_url || '');
        const detectedApiBaseUrl = getBrowserApiBaseUrl();

        contentArea.innerHTML = `
        <div class="card">
            <div class="card-header">
                <h3 class="card-title">系统设置</h3>
            </div>

            <div style="padding: 1.5rem;">
                <h4 style="margin-bottom: 1rem;">基本配置</h4>

                <div class="form-group" style="margin-bottom: 1.5rem;">
                    <label style="display: block; margin-bottom: 0.5rem; font-weight: 500;">默认翻译模型</label>
                    <select id="settings-default-model" class="form-control" style="width: 100%; padding: 0.5rem; border: 2px solid var(--border-color); border-radius: 0.5rem;">
                        <option value="argos" ${settings.default_model === 'argos' ? 'selected' : ''}>Argos (快速)</option>
                        <option value="marian" ${settings.default_model === 'marian' ? 'selected' : ''}>MarianMT (准确)</option>
                        <option value="m2m100" ${settings.default_model === 'm2m100' ? 'selected' : ''}>M2M100 (多语言)</option>
                        <option value="m2m100_1_2b" ${settings.default_model === 'm2m100_1_2b' ? 'selected' : ''}>M2M100 1.2B (高精度)</option>
                        <option value="nllb" ${settings.default_model === 'nllb' ? 'selected' : ''}>NLLB-200 (多语言)</option>
                        <option value="qwen3_1_7b" ${settings.default_model === 'qwen3_1_7b' ? 'selected' : ''}>Qwen3 1.7B</option>
                        <option value="gemma3_1b" ${settings.default_model === 'gemma3_1b' ? 'selected' : ''}>Gemma 3 1B</option>
                        <option value="qwen2_5_0_5b" ${settings.default_model === 'qwen2_5_0_5b' ? 'selected' : ''}>Qwen2.5 0.5B</option>
                    </select>
                </div>

                <div class="form-group" style="margin-bottom: 1.5rem;">
                    <label style="display: block; margin-bottom: 0.5rem; font-weight: 500;">API 速率限制（请求/周期）</label>
                    <input type="number" id="settings-rate-limit" class="form-control" value="${settings.api_rate_limit || 100}" min="1"
                           style="width: 100%; padding: 0.5rem; border: 2px solid var(--border-color); border-radius: 0.5rem;">
                </div>

                <div class="form-group" style="margin-bottom: 1.5rem;">
                    <label style="display: block; margin-bottom: 0.5rem; font-weight: 500;">API 限流周期（秒）</label>
                    <input type="number" id="settings-rate-limit-period" class="form-control" value="${settings.api_rate_limit_period || 3600}" min="1"
                           style="width: 100%; padding: 0.5rem; border: 2px solid var(--border-color); border-radius: 0.5rem;">
                </div>

                <div class="form-group" style="margin-bottom: 1.5rem;">
                    <label style="display: block; margin-bottom: 0.5rem; font-weight: 500;">Token 过期时间（分钟）</label>
                    <input type="number" id="settings-token-expire" class="form-control" value="${settings.token_expire_minutes || 30}" min="1"
                           style="width: 100%; padding: 0.5rem; border: 2px solid var(--border-color); border-radius: 0.5rem;">
                </div>

                <div class="form-group" style="margin-bottom: 1.5rem;">
                    <label style="display: block; margin-bottom: 0.5rem; font-weight: 500;">API 基础地址</label>
                    <input type="url" id="settings-api-base-url" class="form-control"
                           value="${escapeHTML(configuredApiBaseUrl)}"
                           placeholder="${escapeHTML(detectedApiBaseUrl)}"
                           style="width: 100%; padding: 0.5rem; border: 2px solid var(--border-color); border-radius: 0.5rem;">
                    <p style="margin-top: 0.5rem; color: #64748b; font-size: 0.875rem;">
                        留空时 API 文档会自动使用当前访问地址：<code>${escapeHTML(detectedApiBaseUrl)}</code>
                    </p>
                </div>

                <button class="btn btn-primary" onclick="saveSettings()" style="padding: 0.625rem 1.25rem; background: var(--primary-color); color: white; border: none; border-radius: 0.5rem; cursor: pointer;">
                    保存设置
                </button>
            </div>
        </div>

        <div class="card" style="margin-top: 1.5rem;">
            <div class="card-header">
                <h3 class="card-title">安全配置</h3>
            </div>

            <div style="padding: 1.5rem;">
                <div class="form-group" style="margin-bottom: 1.5rem;">
                    <label style="display: block; margin-bottom: 0.5rem; font-weight: 500;">修改管理员密码</label>
                    <input type="password" id="current-password" class="form-control" placeholder="当前密码"
                           style="width: 100%; padding: 0.5rem; border: 2px solid var(--border-color); border-radius: 0.5rem; margin-bottom: 0.5rem;">
                    <input type="password" id="new-password" class="form-control" placeholder="新密码"
                           style="width: 100%; padding: 0.5rem; border: 2px solid var(--border-color); border-radius: 0.5rem; margin-bottom: 0.5rem;">
                    <input type="password" id="confirm-password" class="form-control" placeholder="确认新密码"
                           style="width: 100%; padding: 0.5rem; border: 2px solid var(--border-color); border-radius: 0.5rem;">
                </div>

                <button class="btn btn-primary" onclick="changePassword()" style="padding: 0.625rem 1.25rem; background: var(--primary-color); color: white; border: none; border-radius: 0.5rem; cursor: pointer;">
                    修改密码
                </button>
            </div>
        </div>

        <div class="card" style="margin-top: 1.5rem;">
            <div class="card-header">
                <h3 class="card-title">系统信息</h3>
            </div>

            <div style="padding: 1.5rem;">
                <table style="width: 100%;">
                    <tr style="border-bottom: 1px solid var(--border-color);">
                        <td style="padding: 0.75rem 0; font-weight: 500;">版本</td>
                        <td style="padding: 0.75rem 0;">v${settings.version}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid var(--border-color);">
                        <td style="padding: 0.75rem 0; font-weight: 500;">数据库</td>
                        <td style="padding: 0.75rem 0;">${settings.database}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid var(--border-color);">
                        <td style="padding: 0.75rem 0; font-weight: 500;">可用模型</td>
                        <td style="padding: 0.75rem 0;">${(settings.available_models || []).join(', ')}</td>
                    </tr>
                    <tr>
                        <td style="padding: 0.75rem 0; font-weight: 500;">设备</td>
                        <td style="padding: 0.75rem 0;">${settings.device || 'cpu'}</td>
                    </tr>
                </table>
            </div>
        </div>
    `;
    } catch (error) {
        console.error('加载系统设置失败:', error);
        contentArea.innerHTML = `
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">系统设置</h3>
                </div>
                <p style="padding: 1rem; color: #ef4444;">加载失败：${error.message}</p>
            </div>
        `;
    }
}

// 保存设置
async function saveSettings() {
    const defaultModel = document.getElementById('settings-default-model')?.value || 'argos';
    const rateLimit = parseInt(document.getElementById('settings-rate-limit')?.value, 10) || 100;
    const rateLimitPeriod = parseInt(document.getElementById('settings-rate-limit-period')?.value, 10) || 3600;
    const tokenExpire = parseInt(document.getElementById('settings-token-expire')?.value, 10) || 30;
    const apiBaseUrl = normalizeApiBaseUrl(document.getElementById('settings-api-base-url')?.value || '');

    if (apiBaseUrl && !isValidHttpApiBaseUrl(apiBaseUrl)) {
        alert('❌ API 基础地址必须是有效的 http:// 或 https:// 地址');
        return;
    }

    const confirmMsg = `确定保存以下设置吗？\n\n` +
                       `默认模型: ${defaultModel}\n` +
                       `速率限制: ${rateLimit} 请求/${rateLimitPeriod} 秒\n` +
                       `Token 过期: ${tokenExpire} 分钟\n\n` +
                       `API 基础地址: ${apiBaseUrl || `自动读取（${getBrowserApiBaseUrl()}）`}\n\n` +
                       `这些设置会立即保存到系统配置`;

    if (!confirm(confirmMsg)) return;

    try {
        const response = await fetch('/admin/settings', {
            method: 'POST',
            headers,
            body: JSON.stringify({
                default_model: defaultModel,
                api_rate_limit: rateLimit,
                api_rate_limit_period: rateLimitPeriod,
                token_expire_minutes: tokenExpire,
                api_base_url: apiBaseUrl
            })
        });
        const result = await response.json();

        if (!response.ok || !result.success) {
            throw new Error(result.detail || result.message || '保存失败');
        }

        alert('✓ 设置已保存');
        await loadSettings();
    } catch (error) {
        alert(`❌ 保存失败：${error.message}`);
    }
}

// 修改密码
async function changePassword() {
    const currentPassword = document.getElementById('current-password')?.value;
    const newPassword = document.getElementById('new-password')?.value;
    const confirmPassword = document.getElementById('confirm-password')?.value;

    if (!currentPassword || !newPassword || !confirmPassword) {
        alert('❌ 请输入当前密码和新密码');
        return;
    }

    if (newPassword !== confirmPassword) {
        alert('❌ 两次输入的密码不一致');
        return;
    }

    if (newPassword.length < 6) {
        alert('❌ 密码长度至少6位');
        return;
    }

    const confirmChange = confirm(`确定要修改管理员密码吗？\n\n新密码长度: ${newPassword.length} 位\n\n修改后需要重新登录`);

    if (!confirmChange) return;

    try {
        const response = await fetch('/admin/change-password', {
            method: 'POST',
            headers,
            body: JSON.stringify({
                current_password: currentPassword,
                new_password: newPassword
            })
        });
        const result = await response.json();

        if (!response.ok || !result.success) {
            throw new Error(result.detail || result.message || '修改失败');
        }

        alert('✓ 密码已修改，请重新登录');
        localStorage.removeItem('token');
        window.location.href = '/admin/login';
    } catch (error) {
        alert(`❌ 修改失败：${error.message}`);
        document.getElementById('new-password').value = '';
        document.getElementById('confirm-password').value = '';
    }
}

// API 文档
async function loadDocs() {
    apiDocsBaseUrl = await fetchApiDocsBaseUrl();
    const apiBaseUrl = apiDocsBaseUrl;
    const docsUrl = getApiUrl('/docs', apiBaseUrl);
    const openApiUrl = getApiUrl('/openapi.json', apiBaseUrl);
    const translateUrl = getApiUrl('/translate', apiBaseUrl);

    document.getElementById('content-area').innerHTML = `
        <div class="card">
            <div class="card-header" style="padding: 0; margin-bottom: 1rem;">
                <h3 class="card-title">API 接口文档</h3>
                <button type="button" class="btn btn-primary" onclick="downloadAPIDocs()"
                        style="padding: 0.55rem 1rem; background: var(--primary-color); color: white; border: none; border-radius: 0.5rem; cursor: pointer;">
                    下载 Markdown
                </button>
            </div>
            <p style="color: #475569; margin-top: 0.75rem;">
                客户端只需要调用公开翻译接口；管理员先在后台创建 API Key，再交给客户端使用。完整 Swagger 文档可访问 <code>${escapeHTML(docsUrl)}</code>，OpenAPI JSON 为 <code>${escapeHTML(openApiUrl)}</code>。
            </p>
            <p style="color: #475569; margin-top: 0.75rem;">
                当前示例基础地址：<code>${escapeHTML(apiBaseUrl)}</code>
            </p>

            <h4 style="margin-top: 2rem;">1. 调用流程</h4>
            <ol style="line-height: 1.8;">
                <li>管理员登录 <code>POST /admin/login</code>，获得 JWT Token。</li>
                <li>管理员创建 API Key：<code>POST /admin/api-keys</code>。</li>
                <li>客户端携带 <code>X-API-Key</code> 调用 <code>POST /translate</code>。</li>
                <li>服务按请求中的 <code>model</code> 直接调用对应本地模型；不会自动切换备用模型。</li>
                <li>成功和已认证失败都会写入调用日志，用于统计、限流和耗时分析。</li>
            </ol>

            <h4 style="margin-top: 2rem;">2. 公共翻译接口</h4>
            <p><strong>端点:</strong> <code>POST ${escapeHTML(translateUrl)}</code></p>
            <p><strong>认证:</strong> API Key，请求头 <code>X-API-Key: sk_xxx</code></p>
            <p><strong>Content-Type:</strong> <code>application/json</code></p>

            <h5>请求示例:</h5>
            <pre style="background: var(--bg-color); padding: 1rem; border-radius: 0.5rem; overflow-x: auto;">
curl -X POST "${escapeHTML(translateUrl)}" \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: sk_your_api_key" \\
  -d '{
    "text": "Hello, world!",
    "source_lang": "en",
    "target_lang": "zh",
    "model": "argos"
  }'
            </pre>

            <h5>请求字段:</h5>
            <table style="margin-top: 0.5rem;">
                <thead>
                    <tr>
                        <th>字段</th>
                        <th>必填</th>
                        <th>说明</th>
                    </tr>
                </thead>
                <tbody>
                    <tr><td><code>text</code></td><td>是</td><td>待翻译文本，不能为空；会尽量保留换行、空格、Markdown、HTML、JSON/YAML 等结构。</td></tr>
                    <tr><td><code>source_lang</code></td><td>是</td><td>源语言代码，例如 <code>en</code>、<code>zh</code>。</td></tr>
                    <tr><td><code>target_lang</code></td><td>是</td><td>目标语言代码，不能和源语言相同。</td></tr>
                    <tr><td><code>model</code></td><td>否</td><td>指定模型 ID；不传时使用系统默认模型。</td></tr>
                </tbody>
            </table>

            <h5>响应示例:</h5>
            <pre style="background: var(--bg-color); padding: 1rem; border-radius: 0.5rem; overflow-x: auto;">
{
  "translated_text": "你好，世界！",
  "model_used": "argos",
  "source_lang": "en",
  "target_lang": "zh",
  "success": true,
  "model_backend": "argos",
  "actual_model_name": "en-zh",
  "timing": {
    "backend": "argos",
    "actual_model_name": "en-zh",
    "model_load_ms": 0.12,
    "inference_ms": 8.43,
    "format_ms": 0.31,
    "segment_count": 1,
    "batch_count": 0
  }
}
            </pre>

            <h4 style="margin-top: 2rem;">3. 模型 ID</h4>
            <table style="margin-top: 0.5rem;">
                <thead>
                    <tr>
                        <th>model</th>
                        <th>说明</th>
                        <th>使用条件</th>
                    </tr>
                </thead>
                <tbody>
                    <tr><td><code>argos</code></td><td>轻量级离线翻译</td><td>需安装对应 Argos 语言包。</td></tr>
                    <tr><td><code>marian</code></td><td>Helsinki-NLP Opus-MT</td><td>需下载对应语言对模型；可转换 CTranslate2 int8 后由 <code>MARIAN_BACKEND=auto</code> 优先调用。</td></tr>
                    <tr><td><code>m2m100</code></td><td>facebook/m2m100_418M</td><td>需下载标准 M2M100 模型；可转换 CTranslate2 int8 后由 <code>M2M100_BACKEND=auto</code> 优先调用。</td></tr>
                    <tr><td><code>m2m100_1_2b</code></td><td>facebook/m2m100_1.2B</td><td>需下载 1.2B 模型；可转换 CTranslate2，但转换和本地推理资源占用更高。</td></tr>
                    <tr><td><code>nllb</code></td><td>facebook/nllb-200-distilled-600M</td><td>需下载 NLLB 模型；可转换 CTranslate2 int8 后由 <code>NLLB_BACKEND=auto</code> 优先调用。</td></tr>
                    <tr><td><code>qwen3_1_7b</code></td><td>Qwen/Qwen3-1.7B</td><td>通用大语言模型翻译，需先在“模型管理”下载；使用 Transformers CausalLM 本地推理。</td></tr>
                    <tr><td><code>gemma3_1b</code></td><td>google/gemma-3-1b-it</td><td>Gemma 3 指令模型，可能需要 HuggingFace 授权；使用 Transformers CausalLM 本地推理。</td></tr>
                    <tr><td><code>qwen2_5_0_5b</code></td><td>Qwen/Qwen2.5-0.5B-Instruct</td><td>轻量通用大语言模型翻译，需先在“模型管理”下载。</td></tr>
                </tbody>
            </table>

            <h4 style="margin-top: 2rem;">4. 支持的语言代码</h4>
            <p style="color: #475569;">实际可用语言对取决于对应模型或语言包是否已经下载，可在“模型管理”页面查看状态。</p>
            <ul>
                <li><code>en</code> 英语</li>
                <li><code>zh</code> 简体中文</li>
                <li><code>zt</code> 繁体中文，主要用于 Argos/NLLB 已安装或已支持场景</li>
                <li><code>ja</code> 日语</li>
                <li><code>ko</code> 韩语</li>
                <li><code>fr</code> 法语</li>
                <li><code>de</code> 德语</li>
                <li><code>es</code> 西班牙语</li>
                <li><code>ru</code> 俄语</li>
                <li><code>ar</code>、<code>hi</code>、<code>th</code> 等：NLLB 支持，M2M100 当前页面只开放常用语言。</li>
            </ul>

            <h4 style="margin-top: 2rem;">5. 管理端接口</h4>
            <table style="margin-top: 0.5rem;">
                <thead>
                    <tr>
                        <th>接口</th>
                        <th>认证</th>
                        <th>用途</th>
                    </tr>
                </thead>
                <tbody>
                    <tr><td><code>POST /admin/login</code></td><td>无</td><td>管理员登录，返回 JWT。</td></tr>
                    <tr><td><code>GET /admin/api-keys</code></td><td>Bearer JWT</td><td>查看 API Key 列表。</td></tr>
                    <tr><td><code>POST /admin/api-keys</code></td><td>Bearer JWT</td><td>创建 API Key。</td></tr>
                    <tr><td><code>DELETE /admin/api-keys/{id}</code></td><td>Bearer JWT</td><td>吊销 API Key，历史日志会保留归属。</td></tr>
                    <tr><td><code>GET /admin/models/status</code></td><td>Bearer JWT</td><td>查看模型、语言包、本地缓存完整性。</td></tr>
                    <tr><td><code>GET /admin/models/downloads/{task_id}</code></td><td>Bearer JWT</td><td>查询模型/语言包下载进度。</td></tr>
                    <tr><td><code>POST /admin/models/marian/convert-ct2</code></td><td>Bearer JWT</td><td>将已下载 MarianMT 转换为 CTranslate2 本地模型。</td></tr>
                    <tr><td><code>POST /admin/models/m2m100/convert-ct2</code></td><td>Bearer JWT</td><td>将已下载 M2M100 标准模型转换为 CTranslate2 本地模型。</td></tr>
                    <tr><td><code>POST /admin/models/m2m100-large/convert-ct2</code></td><td>Bearer JWT</td><td>将已下载 M2M100 1.2B 模型转换为 CTranslate2 本地模型。</td></tr>
                    <tr><td><code>POST /admin/models/nllb/convert-ct2</code></td><td>Bearer JWT</td><td>将已下载 NLLB 模型转换为 CTranslate2 本地模型。</td></tr>
                    <tr><td><code>POST /admin/models/causal-lm/download?model_id=...</code></td><td>Bearer JWT</td><td>下载 Qwen/Gemma 通用大语言模型翻译后端。</td></tr>
                </tbody>
            </table>

            <h4 style="margin-top: 2rem;">6. 速率限制</h4>
            <p>每个 API Key 有独立限流，默认 <code>100</code> 请求 / <code>3600</code> 秒周期；请求数和周期都可在系统设置中调整。已认证的成功与失败翻译请求都会计入窗口。</p>

            <h4 style="margin-top: 2rem;">7. 错误返回</h4>
            <p>错误响应使用 FastAPI 标准结构，主体通常为：</p>
            <pre style="background: var(--bg-color); padding: 1rem; border-radius: 0.5rem; overflow-x: auto;">
{
  "detail": "错误说明"
}
            </pre>
            <ul>
                <li><code>400</code>: 不支持的模型、语言对不可用、源语言和目标语言相同。</li>
                <li><code>401</code>: 缺少 API Key、API Key 无效或已过期。</li>
                <li><code>422</code>: JSON 字段缺失、类型错误或 <code>text</code> 为空。</li>
                <li><code>429</code>: 超过 API Key 速率限制。</li>
                <li><code>500</code>: 模型未初始化或服务器内部错误。</li>
            </ul>
        </div>
    `;
}

function getAPIDocsMarkdown(baseUrl = apiDocsBaseUrl) {
    const resolvedBaseUrl = normalizeApiBaseUrl(baseUrl) || getBrowserApiBaseUrl();
    const docsUrl = getApiUrl('/docs', resolvedBaseUrl);
    const openApiUrl = getApiUrl('/openapi.json', resolvedBaseUrl);
    const translateUrl = getApiUrl('/translate', resolvedBaseUrl);

    return `# API 接口文档

客户端只需要调用公开翻译接口；管理员先在后台创建 API Key，再交给客户端使用。

完整 Swagger 文档：\`${docsUrl}\`

OpenAPI JSON：\`${openApiUrl}\`

API 基础地址：\`${resolvedBaseUrl}\`

## 1. 调用流程

1. 管理员登录 \`POST /admin/login\`，获得 JWT Token。
2. 管理员创建 API Key：\`POST /admin/api-keys\`。
3. 客户端携带 \`X-API-Key\` 调用 \`POST /translate\`。
4. 服务按请求中的 \`model\` 直接调用对应本地模型；不会自动切换备用模型。
5. 成功和已认证失败都会写入调用日志，用于统计、限流和耗时分析。

## 2. 公共翻译接口

**端点：** \`POST ${translateUrl}\`

**认证：** API Key，请求头 \`X-API-Key: sk_xxx\`

**Content-Type：** \`application/json\`

### 请求示例

\`\`\`bash
curl -X POST "${translateUrl}" \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: sk_your_api_key" \\
  -d '{
    "text": "Hello, world!",
    "source_lang": "en",
    "target_lang": "zh",
    "model": "argos"
  }'
\`\`\`

### 请求字段

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| \`text\` | 是 | 待翻译文本，不能为空；会尽量保留换行、空格、Markdown、HTML、JSON/YAML 等结构。 |
| \`source_lang\` | 是 | 源语言代码，例如 \`en\`、\`zh\`。 |
| \`target_lang\` | 是 | 目标语言代码，不能和源语言相同。 |
| \`model\` | 否 | 指定模型 ID；不传时使用系统默认模型。 |

### 响应示例

\`\`\`json
{
  "translated_text": "你好，世界！",
  "model_used": "argos",
  "source_lang": "en",
  "target_lang": "zh",
  "success": true,
  "model_backend": "argos",
  "actual_model_name": "en-zh",
  "timing": {
    "backend": "argos",
    "actual_model_name": "en-zh",
    "model_load_ms": 0.12,
    "inference_ms": 8.43,
    "format_ms": 0.31,
    "segment_count": 1,
    "batch_count": 0
  }
}
\`\`\`

## 3. 模型 ID

| model | 说明 | 使用条件 |
| --- | --- | --- |
| \`argos\` | 轻量级离线翻译 | 需安装对应 Argos 语言包。 |
| \`marian\` | Helsinki-NLP Opus-MT | 需下载对应语言对模型；可转换 CTranslate2 int8 后由 \`MARIAN_BACKEND=auto\` 优先调用。 |
| \`m2m100\` | facebook/m2m100_418M | 需下载标准 M2M100 模型；可转换 CTranslate2 int8 后由 \`M2M100_BACKEND=auto\` 优先调用。 |
| \`m2m100_1_2b\` | facebook/m2m100_1.2B | 需下载 1.2B 模型；可转换 CTranslate2，但转换和本地推理资源占用更高。 |
| \`nllb\` | facebook/nllb-200-distilled-600M | 需下载 NLLB 模型；可转换 CTranslate2 int8 后由 \`NLLB_BACKEND=auto\` 优先调用。 |
| \`qwen3_1_7b\` | Qwen/Qwen3-1.7B | 通用大语言模型翻译，需先在“模型管理”下载；使用 Transformers CausalLM 本地推理。 |
| \`gemma3_1b\` | google/gemma-3-1b-it | Gemma 3 指令模型，可能需要 HuggingFace 授权；使用 Transformers CausalLM 本地推理。 |
| \`qwen2_5_0_5b\` | Qwen/Qwen2.5-0.5B-Instruct | 轻量通用大语言模型翻译，需先在“模型管理”下载。 |

## 4. 支持的语言代码

实际可用语言对取决于对应模型或语言包是否已经下载，可在“模型管理”页面查看状态。

| 代码 | 语言 |
| --- | --- |
| \`en\` | 英语 |
| \`zh\` | 简体中文 |
| \`zt\` | 繁体中文，主要用于 Argos/NLLB 已安装或已支持场景 |
| \`ja\` | 日语 |
| \`ko\` | 韩语 |
| \`fr\` | 法语 |
| \`de\` | 德语 |
| \`es\` | 西班牙语 |
| \`ru\` | 俄语 |
| \`ar\`、\`hi\`、\`th\` 等 | NLLB 支持，M2M100 当前页面只开放常用语言。 |

## 5. 管理端接口

| 接口 | 认证 | 用途 |
| --- | --- | --- |
| \`POST /admin/login\` | 无 | 管理员登录，返回 JWT。 |
| \`GET /admin/api-keys\` | Bearer JWT | 查看 API Key 列表。 |
| \`POST /admin/api-keys\` | Bearer JWT | 创建 API Key。 |
| \`DELETE /admin/api-keys/{id}\` | Bearer JWT | 吊销 API Key，历史日志会保留归属。 |
| \`GET /admin/models/status\` | Bearer JWT | 查看模型、语言包、本地缓存完整性。 |
| \`GET /admin/models/downloads/{task_id}\` | Bearer JWT | 查询模型/语言包下载进度。 |
| \`POST /admin/models/marian/convert-ct2\` | Bearer JWT | 将已下载 MarianMT 转换为 CTranslate2 本地模型。 |
| \`POST /admin/models/m2m100/convert-ct2\` | Bearer JWT | 将已下载 M2M100 标准模型转换为 CTranslate2 本地模型。 |
| \`POST /admin/models/m2m100-large/convert-ct2\` | Bearer JWT | 将已下载 M2M100 1.2B 模型转换为 CTranslate2 本地模型。 |
| \`POST /admin/models/nllb/convert-ct2\` | Bearer JWT | 将已下载 NLLB 模型转换为 CTranslate2 本地模型。 |
| \`POST /admin/models/causal-lm/download?model_id=...\` | Bearer JWT | 下载 Qwen/Gemma 通用大语言模型翻译后端。 |

## 6. 速率限制

每个 API Key 有独立限流，默认 \`100\` 请求 / \`3600\` 秒周期；请求数和周期都可在系统设置中调整。已认证的成功与失败翻译请求都会计入窗口。

## 7. 错误返回

错误响应使用 FastAPI 标准结构，主体通常为：

\`\`\`json
{
  "detail": "错误说明"
}
\`\`\`

| 状态码 | 说明 |
| --- | --- |
| \`400\` | 不支持的模型、语言对不可用、源语言和目标语言相同。 |
| \`401\` | 缺少 API Key、API Key 无效或已过期。 |
| \`422\` | JSON 字段缺失、类型错误或 \`text\` 为空。 |
| \`429\` | 超过 API Key 速率限制。 |
| \`500\` | 模型未初始化或服务器内部错误。 |
`;
}

async function downloadAPIDocs(format = 'md') {
    const normalizedFormat = String(format || 'md').toLowerCase();

    if (normalizedFormat !== 'md') {
        alert('当前仅支持 Markdown 格式下载');
        return;
    }

    apiDocsBaseUrl = await fetchApiDocsBaseUrl();
    const content = getAPIDocsMarkdown(apiDocsBaseUrl);
    const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    const date = new Date().toISOString().slice(0, 10);

    link.href = url;
    link.download = `translation-api-docs-${date}.md`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}

// DOMContentLoaded 中已经处理了初始加载，这里移除重复调用
