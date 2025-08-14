/**
 * StarGazer API Module
 * 
 * 职责: 封装所有与后端 API 的 fetch 调用。
 * 规范:
 * 1. 模块内所有函数都返回 Promise。
 * 2. 成功时，Promise resolve 解析后的 JSON 数据。
 * 3. 失败时，Promise reject 一个包含 { status, data } 的标准错误对象。
 * 4. 此模块不进行任何 DOM 操作。
 */
const api = (() => {
    // 使用 IIFE (立即调用函数表达式) 创建一个模块，以封装私有实现（如 _request），
    // 并仅向外暴露一个包含公共 API 方法的对象。这有助于避免污染全局命名空间。

    /**
     * 私有的请求处理器，所有 API 调用都通过它。
     * @param {string} url - 请求的 URL
     * @param {object} options - fetch 的配置对象 (method, headers, body, etc.)
     * @returns {Promise<any>} - 返回解析后的数据或在失败时 reject
     */
    const _request = async (url, options = {}) => {
        try {
            // 关键设置：确保浏览器在跨域请求中自动携带 cookie，
            // 这是维持后端会话（session）和用户认证状态所必需的。
            options.credentials = 'include';
            const response = await fetch(url, options);

            if (response.ok) {
                // 根据 HTTP 规范，204 No Content 表示请求已成功处理，但没有内容返回。
                // 在此进行特殊处理，直接返回 null，以避免对空响应体调用 .json() 而引发错误。
                if (response.status === 204) {
                    return null;
                }
                return response.json();
            } else {
                // 健壮性设计：尝试解析错误响应体。如果解析失败（例如500错误且无JSON体），
                // 则回退到一个空对象，以确保 downstream 的错误处理器总能安全地访问 .data 属性。
                const errorData = await response.json().catch(() => ({})); 
                return Promise.reject({
                    status: response.status,
                    data: errorData
                });
            }
        } catch (e) {
            // 为网络层面的失败（如服务器无法访问）创建一个标准化的错误对象。
            // 使用 'network_error' 作为特有的 status，以便上层逻辑可以轻松区分
            // 是 HTTP 级别的错误（如 401, 500）还是完全无法通信的错误。
            return Promise.reject({
                status: 'network_error',
                data: { 
                    message_zh: '网络连接失败，请检查您的网络或服务器状态。',
                    message_en: 'Network connection failed. Please check your network or server status.'
                }
            });
        }
    };

    return {
        /**
         * 检查应用是否有新版本
         * GET /api/version/check
         */
        checkForUpdates: () => _request('/api/version/check'),

        /**
         * 获取当前用户信息
         * GET /api/me
         */
        getMe: () => _request('/api/me'),

        /**
         * 获取所有 Star 数据和元数据 (回滚后的版本)
         * GET /api/stars
         */
        getStars: () => _request('/api/stars'),

        /**
         * 手动触发后端同步
         * POST /api/sync
         */
        sync: () => _request('/api/stars/sync', { method: 'POST' }),

        /**
         * 获取上次成功同步的时间戳
         * GET /api/stars/last-successful-sync
         */
        getLastSuccessfulSync: () => _request('/api/stars/last-successful-sync'),

        /**
         * 获取应用设置
         * GET /api/settings
         */
        getSettings: () => _request('/api/settings'),

        /**
         * 更新应用设置
         * PUT /api/settings
         * @param {object} settingsData - 包含要更新的设置的对象
         */
        updateSettings: (settingsData) => _request('/api/settings', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settingsData)
        }),

        /**
         * 重置推送失败计数
         * POST /api/settings/reset-failed-push-count
         */
        resetFailedPushCount: () => _request('/api/settings/reset-failed-push-count', { method: 'POST' }),
        
        /**
         * 更新单个仓库的用户自定义数据
         * PATCH /api/stars/{repo_id}
         * @param {number} repoId - 仓库 ID
         * @param {object} repoData - 包含要更新的字段的对象 (e.g., { alias, notes, tags })
         */
        // 使用 PATCH 方法进行部分更新。这意味着API调用者只需提供需要变更的字段
        // (例如 { notes: "新的笔记" })，而无需发送整个仓库对象。
        updateRepo: (repoId, repoData) => _request(`/api/stars/${repoId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(repoData)
        }),

        /**
         * 更新“我的分组”的自定义排序
         * PUT /api/settings/tags-order
         * @param {string[]} tagsArray - 排序后的标签名数组
         */
        // 使用 PUT 方法，因为此操作的意图是用客户端提供的全新数组
        // [完全替换] 服务器上现有的标签排序。
        updateTagsOrder: (tagsArray) => _request('/api/settings/tags-order', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(tagsArray)
        }),

        /**
         * 更新“开发语言”的自定义排序
         * PUT /api/settings/languages-order
         * @param {string[]} languagesArray - 排序后的语言名数组
         */
        updateLanguagesOrder: (languagesArray) => _request('/api/settings/languages-order', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(languagesArray)
        }),

        /**
         * 全局删除一个分组
         * DELETE /api/tags/{tag_name}
         * @param {string} tagName - 要删除的分组名称
         */
        deleteTag: (tagName) => {
            // 安全与正确性：对标签名进行 URL 编码，以防止标签中包含的特殊字符破坏 API 路由的结构。
            const encodedTagName = encodeURIComponent(tagName);
            return _request(`/api/tags/${encodedTagName}`, { method: 'DELETE' });
        }
    };
})();
