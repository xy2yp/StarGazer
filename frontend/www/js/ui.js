/**
 * StarGazer UI Module
 *
 * 职责: 封装所有与 DOM 相关的操作。
 * 规范:
 * 1. 模块内所有函数只负责渲染，不包含业务逻辑。
 * 2. 通过 ID 高效地选择元素，并将常用元素缓存起来。
 * 3. 使用 <template> 进行高效的节点克隆，避免拼接 HTML 字符串。
 */
const ui = (() => {
    // 元素缓存
    const elements = {
        loginView: document.getElementById('login-view'),
        starfieldContainer: document.getElementById('starfield-container'),
        appView: document.getElementById('app-view'),
        avatarContainer: document.getElementById('avatar-container'),
        userLogin: document.getElementById('user-login'),
        body: document.body,
        sidebar: {
            itself: document.getElementById('sidebar'),
            tagsList: document.getElementById('tags-list'),
            addTagContainer: document.getElementById('add-tag-container'),
            languagesList: document.getElementById('languages-list'),
            allReposFilter: document.querySelector('[data-filter="all"]'),
            constellationFilter: document.querySelector('[data-filter="constellation"]'),
            untaggedFilter: document.querySelector('[data-filter="untagged"]'),
        },
        repoListContainer: document.getElementById('repo-list-container'),
        viewSwitcher: document.getElementById('view-switcher'),
        virtualScrollContainer: document.getElementById('virtual-scroll-container'),
        repoDetails: document.getElementById('repo-details'),
        toastContainer: document.getElementById('toast-container'),
        confirmationModal: document.getElementById('confirmation-modal'),
        confirmationModalTitle: document.getElementById('confirmation-modal-title'),
        confirmationModalContent: document.getElementById('confirmation-modal-content'),
        settingsViewModal: document.getElementById('settings-view-modal'),
        imagePreviewModal: document.getElementById('image-preview-modal'),
        repoListItemTemplate: document.getElementById('repo-list-item-template'),
        repoCardItemTemplate: document.getElementById('repo-card-item-template'),
    };

    let currentSwipeGesture = null;

    // 虚拟滚动器类
    /**
     * VirtualScroller Class
     * 一个极简的、用于固定高度列表项的虚拟滚动器。
     * 通过只渲染视口内及缓冲区内的 DOM 元素，来高性能地处理长列表。
     */
    class VirtualScroller {
        constructor(container, options) {
            this.container = container;
            this.itemHeight = options.itemHeight;
            this.renderItem = options.renderItem;
            this.buffer = options.buffer || 10;

            this.items = [];
            this.visibleItems = new Map();

            this.sizer = document.createElement('div');
            this.sizer.className = 'virtual-scroll-sizer';
            this.viewport = document.createElement('div');
            this.viewport.className = 'virtual-scroll-viewport';

            this.container.innerHTML = '';
            this.container.appendChild(this.sizer);
            this.container.appendChild(this.viewport);

            this.scrollHandler = this._onScroll.bind(this);
            this.container.addEventListener('scroll', this.scrollHandler);

            this._onScroll();
        }

        _onScroll() {
            if (this.items.length === 0) {
                if (!this.viewport.querySelector('.empty-state')) {
                    this.viewport.innerHTML = `<article class="empty-state"><p>${i18n.t('emptyState.title')}</p><p>${i18n.t('emptyState.prompt')}</p></article>`;
                }
                return;
            }
            if (this.viewport.querySelector('.empty-state')) {
                this.viewport.innerHTML = '';
            }

            const scrollTop = this.container.scrollTop;
            const containerHeight = this.container.clientHeight;

            const startIndex = Math.floor(scrollTop / this.itemHeight);
            const endIndex = Math.min(this.items.length - 1, Math.floor((scrollTop + containerHeight) / this.itemHeight));
            const renderStartIndex = Math.max(0, startIndex - this.buffer);
            const renderEndIndex = Math.min(this.items.length - 1, endIndex + this.buffer);

            // DOM Diffing：只渲染新增项，移除消失项，保持不变项
            // 使用 Map 存储已渲染的DOM节点，实现高效查找和更新
            const newVisibleIndexes = new Set();
            for (let i = renderStartIndex; i <= renderEndIndex; i++) {
                newVisibleIndexes.add(i);
                if (!this.visibleItems.has(i)) {
                    const itemData = this.items[i];
                    const element = this.renderItem(itemData);
                    element.style.position = 'absolute';
                    element.style.top = `${i * this.itemHeight}px`;
                    element.style.height = `${this.itemHeight}px`;
                    element.style.width = '100%';
                    this.viewport.appendChild(element);
                    this.visibleItems.set(i, element);
                }
            }
            for (const [index, element] of this.visibleItems.entries()) {
                if (!newVisibleIndexes.has(index)) {
                    element.remove();
                    this.visibleItems.delete(index);
                }
            }
        }

        setData(items) {
            this.items = items;
            this.sizer.style.height = `${this.items.length * this.itemHeight}px`;
            this.visibleItems.forEach(el => el.remove());
            this.visibleItems.clear();
            this.container.scrollTop = 0;
            this._onScroll();
        }

        updateConfig({ itemHeight, renderItem }) {
            this.itemHeight = itemHeight || this.itemHeight;
            this.renderItem = renderItem || this.renderItem;
            this.setData(this.items);
        }

        /**
         * 销毁滚动器，清理事件监听和DOM节点
         */
        destroy() {
            this.container.removeEventListener('scroll', this.scrollHandler);

            const sizer = this.container.querySelector('.virtual-scroll-sizer');
            if (sizer) sizer.remove();

            const viewport = this.container.querySelector('.virtual-scroll-viewport');
            if (viewport) viewport.innerHTML = '';

            this.container.style.overflowY = '';
        }
    

        /**
         * 动态测量并应用新的列表项高度，以响应CSS变化（如窗口缩放）。
         */
        updateItemHeight() {
            if (this.items.length === 0) return;

            // 测量策略：离屏渲染获取CSS驱动的响应式高度
            // 创建真实DOM节点但放置在屏幕外(top: -9999px)，测量后立即移除
            const sampleItem = this.renderItem(this.items[0]);
            sampleItem.style.position = 'absolute';
            sampleItem.style.top = '-9999px';
            sampleItem.style.left = '0';
            this.container.appendChild(sampleItem);
        
            const newHeight = sampleItem.offsetHeight;

            this.container.removeChild(sampleItem);

            if (newHeight > 0 && this.itemHeight !== newHeight) {
                this.itemHeight = newHeight;
                this.sizer.style.height = `${this.items.length * this.itemHeight}px`;
            
                this.visibleItems.forEach(el => el.remove());
                this.visibleItems.clear();
                this._onScroll();
            }
        }
    } 

    // --- 3. 私有辅助渲染函数 ---

    /**
     * 初始化滚动条悬停延迟行为。
     * 为指定元素配置鼠标悬停时立即显示滚动条，离开后延迟隐藏的交互模式。
     * 使用 Map 管理多个定时器，确保悬停状态切换的准确性。
     */
    const _initScrollbarHoverDelay = () => {
        const hoverDelaySelectors = [
            '#virtual-scroll-container'
        ];
        
        const hideTimers = new Map();
        
        hoverDelaySelectors.forEach(selector => {
            const element = document.querySelector(selector);
            if (!element) return;
            
            element.addEventListener('mouseenter', () => {
                if (hideTimers.has(selector)) {
                    clearTimeout(hideTimers.get(selector));
                    hideTimers.delete(selector);
                }
                element.classList.add('scrollbar-hover-active');
            });
            
            element.addEventListener('mouseleave', () => {
                if (hideTimers.has(selector)) {
                    clearTimeout(hideTimers.get(selector));
                }
                const timerId = setTimeout(() => {
                    element.classList.remove('scrollbar-hover-active');
                    hideTimers.delete(selector);
                }, 1500);
                hideTimers.set(selector, timerId);
            });
        });
        
        const sidebar = document.querySelector('#sidebar');
        if (sidebar) {
            sidebar.addEventListener('mouseenter', () => {
                sidebar.classList.add('scrollbar-hover-active');
            });
            
            sidebar.addEventListener('mouseleave', () => {
                sidebar.classList.remove('scrollbar-hover-active');
            });
        }
    };

    /**
     * 滚动条自动隐藏：滚动时显示，停止后淡出
     * @param {HTMLElement} element - 目标元素
     * @returns {Function} 清理函数
     */
    const _applyAutoHideScrollbarBehavior = (element) => {
        if (!element) return;

        let hideTimer = null;
        element.classList.add('scroll-behavior--auto-hide');

        const handleScroll = () => {
            element.classList.add('scrolling');

            if (hideTimer) {
                clearTimeout(hideTimer);
            }

            hideTimer = setTimeout(() => {
                element.classList.remove('scrolling');
                hideTimer = null;
            }, 1500);
        };

        element.addEventListener('scroll', handleScroll);

        return () => {
            element.removeEventListener('scroll', handleScroll);
        };
    };

    /**
     * 初始化移动端滚动条自动隐藏
     */
    const _initScrollbarAutoHide = () => {
        ['#sidebar', '#virtual-scroll-container'].forEach(selector => {
            const element = document.querySelector(selector);
            _applyAutoHideScrollbarBehavior(element);
        });
    };

    /**
     * 备注预览区滚动条悬停交互
     * 使用自定义属性防止重复绑定
     */
    const _addNotesPreviewHoverDelay = (notesPreview) => {
        if (!notesPreview || notesPreview.hasScrollbarHoverDelay) return;
        
        notesPreview.addEventListener('mouseenter', () => {
            notesPreview.classList.add('scrollbar-hover-active');
        });
        
        notesPreview.addEventListener('mouseleave', () => {
            notesPreview.classList.remove('scrollbar-hover-active');
        });
        
        notesPreview.hasScrollbarHoverDelay = true;
    };

    /**
     * 创建 GitHub 图标 SVG
     * @param {number} size - 图标尺寸
     * @param {string} extraStyles - 额外样式
     * @returns {string} SVG字符串
     */
    const _createGithubIconSVG = (size, extraStyles = '') => {
        const style = extraStyles ? `style="${extraStyles}"` : '';
        return `<svg height="${size}" aria-hidden="true" viewBox="0 0 16 16" version="1.1" width="${size}" fill="currentColor" ${style}><path d="M8 0.198c-4.4 0-8 3.6-8 8 0 3.5 2.3 6.5 5.5 7.6.4.1.5-.2.5-.4v-1.4c-2.2.5-2.7-1.1-2.7-1.1-.4-1-.9-1.2-.9-1.2-.7-.5.1-.5.1-.5.8.1 1.2.8 1.2.8.7 1.2 1.9 .9 2.3.7.1-.5.3-.9.5-1.1-1.8-.2-3.6-.9-3.6-4 0-.9.3-1.6.8-2.2-.1-.2-.4-1 .1-2.1 0 0 .7-.2 2.2.8.6-.2 1.3-.3 2-.3s1.4.1 2 .3c1.5-1 2.2-.8 2.2-.8.4 1.1.2 1.9.1 2.1.5.6.8 1.3.8 2.2 0 3.1-1.9 3.8-3.6 4 .3.3.6.8.6 1.5v2.2c0 .2.1.5.5.4C13.7 14.698 16 11.698 16 8.198c0-4.4-3.6-8-8-8z"></path></svg>`;
    };
    
    /**
     * 为头像图片添加加载失败的备用处理。
     * 当头像无法加载时，自动替换为 GitHub 默认图标。
     */
    const _addAvatarFallback = (imgElement, containerElement) => {
        imgElement.onerror = () => {
            containerElement.innerHTML = _createGithubIconSVG(22);
            imgElement.onerror = null; 
        };
    };

    /**
     * 将 ISO 时间字符串格式化为相对时间的友好文本。
     * 支持多级时间单位：秒、分钟、小时、天、月、年，并配合国际化显示。
     */
    const _formatTimeAgo = (isoString) => {
        if (!isoString) return i18n.t('timeAgo.unknown');
        const date = new Date(isoString);
        const now = new Date();
        const seconds = Math.floor((now - date) / 1000);

        if (seconds < 60) return i18n.t('timeAgo.now');
        
        const minutes = Math.floor(seconds / 60);
        if (minutes < 60) return i18n.t('timeAgo.minute', { count: minutes });

        const hours = Math.floor(minutes / 60);
        if (hours < 24) return i18n.t('timeAgo.hour', { count: hours });

        const days = Math.floor(hours / 24);
        if (days < 30) return i18n.t('timeAgo.day', { count: days });
        
        const months = Math.floor(days / 30);
        if (months < 12) return i18n.t('timeAgo.month', { count: months });

        const years = Math.floor(months / 12);
        return i18n.t('timeAgo.year', { count: years });
    };

    /**
     * 将 ISO 时间字符串格式化为本地时区的详细日期时间。
     * 作为相对时间的补充，用于需要精确时间信息的场景。
     */
    const _formatDateTime = (isoString) => {
        if (!isoString) return '未知';
        try {
            return new Date(isoString).toLocaleString();
        } catch (e) {
            return isoString;
        }
    };

    /**
     * 按需异步加载 JavaScript 和/或 CSS 文件。
     * 内置缓存机制，确保同一资源在单次会话中只被加载一次。
     * @param {string} [jsUrl] - 要加载的 JS 文件 URL。
     * @param {string} [cssUrl] - 要加载的 CSS 文件 URL。
     * @returns {Promise<void[]>} 一个在所有请求的资源都加载完毕后 resolve 的 Promise。
     */
    const _loadResource = ((cache = {}) => (jsUrl, cssUrl) => {
        const key = `${jsUrl || ''}|${cssUrl || ''}`;
        if (cache[key]) return cache[key];
        const promises = [];
        if (cssUrl && !document.querySelector(`link[href="${cssUrl}"]`)) {
            promises.push(new Promise((resolve, reject) => {
                const link = document.createElement('link');
                link.rel = 'stylesheet';
                link.href = cssUrl;
                link.onload = resolve;
                link.onerror = () => reject(new Error(`Failed to load CSS: ${cssUrl}`));
                document.head.appendChild(link);
            }));
        }
        if (jsUrl && !document.querySelector(`script[src="${jsUrl}"]`)) {
            promises.push(new Promise((resolve, reject) => {
                const script = document.createElement('script');
                script.src = jsUrl;
                script.onload = resolve;
                script.onerror = () => reject(new Error(`Failed to load script: ${jsUrl}`));
                document.head.appendChild(script);
            }));
        }
        cache[key] = Promise.all(promises);
        return cache[key];
    })();

    // GitHub 图标 SVG 常量，用于外部链接和备用头像
    const GITHUB_ICON_SVG = `<svg height="16" aria-hidden="true" viewBox="0 0 16 16" version="1.1" width="16" fill="currentColor" style="vertical-align: text-bottom; margin-right: 0.5em;"><path d="M8 0.198c-4.4 0-8 3.6-8 8 0 3.5 2.3 6.5 5.5 7.6.4.1.5-.2.5-.4v-1.4c-2.2.5-2.7-1.1-2.7-1.1-.4-1-.9-1.2-.9-1.2-.7-.5.1-.5.1-.5.8.1 1.2.8 1.2.8.7 1.2 1.9 .9 2.3.7.1-.5.3-.9.5-1.1-1.8-.2-3.6-.9-3.6-4 0-.9.3-1.6.8-2.2-.1-.2-.4-1 .1-2.1 0 0 .7-.2 2.2.8.6-.2 1.3-.3 2-.3s1.4.1 2 .3c1.5-1 2.2-.8 2.2-.8.4 1.1.2 1.9.1 2.1.5.6.8 1.3.8 2.2 0 3.1-1.9 3.8-3.6 4 .3.3.6.8.6 1.5v2.2c0 .2.1.5.5.4C13.7 14.698 16 11.698 16 8.198c0-4.4-3.6-8-8-8z"></path></svg>`;

    /**
     * 创建侧边栏筛选器项目的 DOM 元素。
     * 根据筛选器类型和当前激活状态，动态生成带计数和激活样式的列表项。
     */
    const _createFilterItem = ({ text, count, dataType, dataValue, isDraggable = false }, activeFilter) => {
        const li = document.createElement('li');
        const a = document.createElement('a');
        a.href = '#';
        a.className = 'group-item';
        a.dataset[dataType] = dataValue;
        a.draggable = false;

        const isActive = activeFilter && activeFilter.type === dataType && activeFilter.value === dataValue;
        if (isActive) {
            a.classList.add('is-active');
        }

        if (isDraggable) {
            li.classList.add('group-item-draggable');
            li.dataset[dataType] = dataValue;
        }
        const nameSpan = document.createElement('span');
        nameSpan.className = 'filter-name';
        nameSpan.textContent = text;

        const rightContent = document.createElement('span');
        rightContent.className = 'filter-right-content';

        const countSpan = document.createElement('span');
        countSpan.className = 'filter-count';
        countSpan.textContent = count;

        rightContent.appendChild(countSpan);
        a.appendChild(nameSpan);
        a.appendChild(rightContent);

        li.appendChild(a);
        return li;
    };

    /**
     * 创建一个 Toast 通知元素并显示。
     * Toast 会在指定延迟后自动淡出并从 DOM 中移除。
     * @param {string} message - Toast 中显示的消息文本。
     * @param {string} type - Toast 的类型 (e.g., 'info', 'success', 'error')，用于 CSS 样式。
     * @param {number} duration - Toast 的显示时长（毫秒），-1 表示永久显示。
     * @returns {HTMLElement} 创建的 Toast 元素。
     */
    const _createToast = (message, type, duration) => {
        const toast = document.createElement('article');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        elements.toastContainer.appendChild(toast);
        setTimeout(() => toast.classList.add('show'), 10);
        if (duration > 0) {
            setTimeout(() => {
                toast.classList.remove('show');
                toast.addEventListener('transitionend', () => toast.remove());
            }, duration);
        }
        return toast;
    };

    /**
     * 为登录页创建动态的、高性能的星空背景。
     * @param {HTMLElement} container - 用于容纳星星的DOM元素。
     * @param {number} starCount - 要生成的星星数量。
     */
    const _createStarfield = (container, starCount = 200) => {
        if (!container || container.children.length > 0) return; // 防止重复创建

        const fragment = document.createDocumentFragment();
        for (let i = 0; i < starCount; i++) {
            const star = document.createElement('div');
            star.classList.add('star');

            const size = Math.random() * 2 + 1;
            star.style.width = `${size}px`;
            star.style.height = `${size}px`;

            star.style.top = `${Math.random() * 100}%`;
            star.style.left = `${Math.random() * 100}%`;

            const duration = Math.random() * 30 + 20; // 20-50s
            const delay = Math.random() * -50;       // -50s to 0s (让动画一开始就处于不同阶段)
            star.style.animationDuration = `${duration}s`;
            star.style.animationDelay = `${delay}s`;
            star.style.opacity = Math.random() * 0.5 + 0.5;

            fragment.appendChild(star);
        }
        container.appendChild(fragment);
    };

    /**
     * 创建一个简单的分组（Tag）显示元素。
     * @param {string} tag - 要显示的分组名称。
     * @returns {HTMLElement} 创建的 span 元素。
     */
    const _createTagElement = (tag) => {
        const el = document.createElement('span');
        el.className = 'tag';
        el.textContent = tag;
        return el;
    };

    /**
     * 根据仓库数据创建“列表视图”中的单个列表项 DOM 元素。
     * 使用 <template> 提高性能，并填充所有必要的数据字段。
     * @param {object} repo - 仓库数据对象。
     * @returns {HTMLElement} 创建的列表项元素。
     */
    const _createRepoListItem = (repo) => {
        const fragment = elements.repoListItemTemplate.content.cloneNode(true);
        const item = fragment.firstElementChild;
        item.dataset.repoId = repo.id;

        const displayName = repo.alias || repo.full_name;
        item.querySelector('.repo-display-name').textContent = displayName;

        const descElement = item.querySelector('.repo-description');
        if (repo.description) {
            descElement.textContent = repo.description;
            descElement.style.fontStyle = 'normal';
        } else {
            descElement.textContent = i18n.t('detailsPane.noDescription');
            descElement.style.fontStyle = 'italic';
        }
        item.querySelector('.repo-stars span').textContent = repo.stargazers_count.toLocaleString();
        item.querySelector('.repo-updated-at span').textContent = _formatTimeAgo(repo.pushed_at);
        item.querySelector('.repo-language-text').textContent = repo.language || 'N/A';
        const favoriteIcon = item.querySelector('.repo-favorite-icon i');
        if (repo.tags.includes('_favorite')) {
            favoriteIcon.classList.replace('fa-regular', 'fa-solid');
        }
        const tagsContainer = item.querySelector('.repo-tags-container');
        repo.tags.filter(t => t !== '_favorite').forEach(tag => {
            tagsContainer.appendChild(_createTagElement(tag));
        });
        return item;
    };

    /**
     * 根据仓库数据创建“卡片视图”中的单个卡片项 DOM 元素。
     * @param {object} repo - 仓库数据对象。
     * @returns {HTMLElement} 创建的卡片项元素。
     */
    const _createRepoCardItem = (repo) => {
        const fragment = elements.repoCardItemTemplate.content.cloneNode(true);
        const item = fragment.firstElementChild;
        item.dataset.repoId = repo.id;

        const displayName = repo.alias || repo.full_name;
        item.querySelector('.repo-display-name').textContent = displayName;
        const favoriteIcon = item.querySelector('.repo-favorite-icon i');
        if (repo.tags.includes('_favorite')) {
            favoriteIcon.classList.replace('fa-regular', 'fa-solid');
        }

        const tagsContainer = item.querySelector('.repo-card-tags');
        tagsContainer.innerHTML = '';

        const nonFavoriteTags = repo.tags.filter(t => t !== '_favorite');
        if (nonFavoriteTags.length > 0) {
            nonFavoriteTags.slice(0, 2).forEach(tag => {
                tagsContainer.appendChild(_createTagElement(tag));
            });
            tagsContainer.style.display = 'flex';
        } else {
            tagsContainer.style.display = 'none';
        }

        const descElement = item.querySelector('.repo-card-description');
        if (repo.description) {
            descElement.textContent = repo.description;
            descElement.style.fontStyle = 'normal';
        } else {
            descElement.textContent = i18n.t('detailsPane.noDescription');
            descElement.style.fontStyle = 'italic';
        }

        item.querySelector('.repo-stars span').textContent = repo.stargazers_count.toLocaleString();
        item.querySelector('.repo-updated-at span').textContent = _formatTimeAgo(repo.pushed_at);
        item.querySelector('.repo-language-text').textContent = repo.language || 'N/A';
        return item;
    };

    /**
     * 为指定的 DOM 元素启用“行内编辑”功能。
     * @param {object} config - 配置对象。
     * @param {HTMLElement} config.displayElement - 要应用行内编辑的父容器元素。
     * @param {string} config.field - 要编辑的字段名 (e.g., 'alias')。
     * @param {string|number} config.repoId - 仓库 ID。
     * @param {function} config.onSave - 保存时调用的回调函数。
     */
    const _enableInlineEditing = ({ displayElement, field, repoId, onSave }) => {
        // 核心逻辑：动态创建/销毁input元素，管理事件监听器
        // 在文本元素上模拟"点击即可编辑"效果，防止事件累积
        const enterEditMode = (e) => {
            if (displayElement.classList.contains('is-editing')) return;
            
            if (e) e.stopPropagation();

            displayElement.classList.add('is-editing');
            
            const originalValue = displayElement.dataset.originalValue || '';
            
            const textNode = displayElement.querySelector('.repo-display-name');
            if(textNode) textNode.style.display = 'none';

            const wrapper = document.createElement('div');
            wrapper.className = 'inline-editor-wrapper';
            
            const editor = document.createElement('input');
            editor.type = 'text';
            editor.maxLength = 50;
            editor.className = 'inline-editor';
            editor.value = originalValue;
            
            const clearButton = document.createElement('span');
            clearButton.className = 'inline-editor-clear';
            clearButton.innerHTML = '<i class="fa-solid fa-xmark"></i>';
            clearButton.title = i18n.t('inlineEditor.clear');
            
            clearButton.onmousedown = (ev) => {
                ev.preventDefault();
                ev.stopPropagation();
                editor.value = '';
                editor.focus();
            };
            
            wrapper.appendChild(editor);
            wrapper.appendChild(clearButton);
            displayElement.appendChild(wrapper);
            
            editor.focus();
            editor.select();

            const exitAndSaveChanges = () => {
                const newValue = editor.value.trim();
                
                if (newValue !== originalValue) {
                    onSave(repoId, field, newValue);
                }

                wrapper.remove();
                if(textNode) textNode.style.display = '';
                displayElement.classList.remove('is-editing');
                
                displayElement.removeEventListener('click', enterEditMode);
                displayElement.addEventListener('click', enterEditMode);
            };

            const handleKeyDown = (ev) => {
                if (ev.key === 'Enter') {
                    editor.blur();
                } else if (ev.key === 'Escape') {
                    wrapper.remove();
                    if(textNode) textNode.style.display = '';
                    displayElement.classList.remove('is-editing');
                    displayElement.removeEventListener('click', enterEditMode);
                    displayElement.addEventListener('click', enterEditMode);
                }
            };

            editor.addEventListener('blur', exitAndSaveChanges, { once: true });
            editor.addEventListener('keydown', handleKeyDown);
        };

        displayElement.removeEventListener('click', enterEditMode);
        displayElement.addEventListener('click', enterEditMode);
    };

    // 为备注区初始化 Vditor 编辑器，并管理其生命周期
    const _initVditorNotesEditor = (repo, onSave) => {
        const editorWrapper = document.getElementById('notes-editor-wrapper');
        const vditorDiv = document.getElementById('vditor-editor');
        if (!editorWrapper || !vditorDiv) return;

        let vditorInstance = null;
        let globalClickHandler = null;

        const renderPreview = (content) => {
            const trimmedContent = content ? content.trim() : '';
            const previewHTML = trimmedContent
                ? DOMPurify.sanitize(marked.parse(trimmedContent))
                : `<p class="placeholder-text">${i18n.t('detailsPane.notesEditor.placeholder')}</p>`;
            vditorDiv.innerHTML = `<div class="prose" id="notes-preview">${previewHTML}</div>`;
            
            const notesPreview = document.getElementById('notes-preview');
            if (notesPreview) {
                requestAnimationFrame(() => {
                    const isMobile = window.matchMedia("(max-width: 768px)").matches;
                    const hasOverflow = notesPreview.scrollHeight > notesPreview.clientHeight;

                    if (hasOverflow) {
                        if (isMobile) {
                            _applyAutoHideScrollbarBehavior(notesPreview);
                        } else {
                            notesPreview.classList.add('scroll-behavior--hover');
                            _addNotesPreviewHoverDelay(notesPreview);
                        }
                    } else {
                         notesPreview.classList.remove('scroll-behavior--hover');
                    }
                });
            }
        };

        const exitEditMode = () => {
            if (globalClickHandler) {
                document.removeEventListener('mousedown', globalClickHandler);
                globalClickHandler = null;
            }

            if (vditorInstance) {
                const newValue = vditorInstance.getValue();
                const originalValue = repo.notes || '';

                if (elements.repoDetails.classList.contains('is-vditor-fullscreen')) {
                    elements.repoDetails.classList.remove('is-vditor-fullscreen');
                }

                vditorInstance.destroy();
                vditorInstance = null;

                if (newValue !== originalValue) {
                    onSave(repo.id, 'notes', newValue);
                }
            }

            editorWrapper.classList.remove('is-editing');
            renderPreview(repo.notes);
            editorWrapper.addEventListener('click', enterEditMode);
        };

        const enterEditMode = async (e) => {
            if (e) e.stopPropagation();
            if (e && e.target.closest('a[href]')) return;
            if (editorWrapper.classList.contains('is-editing')) return;

            editorWrapper.removeEventListener('click', enterEditMode);
            editorWrapper.classList.add('is-editing');
            vditorDiv.innerHTML = '';

            const isDarkMode = document.documentElement.getAttribute('data-theme') === 'dark';
            const originalValue = repo.notes || '';

            requestAnimationFrame(() => {
                try {
                    vditorInstance = new Vditor('vditor-editor', {
                        popup: document.body,
                        height: 300,
                        mode: 'ir',
                        value: originalValue,
                        placeholder: i18n.t('detailsPane.notesEditor.placeholder'),
                        theme: isDarkMode ? 'dark' : 'light',
                        preview: {
                            hljs: {
                                enable: false, // 禁用代码高亮
                            }
                        },
                        cache: { enable: false },
                        cdn: 'assets/libs/vditor',
                        toolbar: [], // 设置为空数组以禁用工具栏
                        fullscreen: {
                            index: 1000,
                            handler: (isFullscreen) => {
                                elements.repoDetails.classList.toggle('is-vditor-fullscreen', isFullscreen);
                            }
                        },
                        after: () => {
                            editorWrapper.querySelector('.vditor')?.classList.add('vditor--editing');
                            vditorInstance.focus();

                            const vditorIr = editorWrapper.querySelector('.vditor-ir');
                            if (vditorIr) {
                                const irElement = vditorIr.querySelector('pre[contenteditable="true"]') || vditorIr;

                                const checkScrollbarNeed = () => {
                                    // 使用真正的滚动容器 irElement 来判断内容是否溢出
                                    const hasScroll = irElement.scrollHeight > irElement.clientHeight;
                                    
                                    // 在滚动的元素 irElement 上应用样式类，而不是父容器
                                    if (hasScroll) {
                                        irElement.classList.add('scroll-behavior--always-visible');
                                    } else {
                                        irElement.classList.remove('scroll-behavior--always-visible');
                                    }
                                };
                                
                                setTimeout(checkScrollbarNeed, 500);
                                
                                ['input', 'keyup', 'paste'].forEach(eventType => {
                                    irElement.addEventListener(eventType, () => {
                                        setTimeout(checkScrollbarNeed, 100); // 延迟检测以等待DOM更新
                                    });
                                });
                                
                                if (window.ResizeObserver) {
                                    const resizeObserver = new ResizeObserver(() => {
                                        setTimeout(checkScrollbarNeed, 100);
                                    });
                                    // 监听内部滚动元素 irElement 的大小变化
                                    resizeObserver.observe(irElement);
                                }
                            } else {
                                console.error('未找到 .vditor-ir 元素');
                            }

                            if (!globalClickHandler) {
                                globalClickHandler = (event) => {
                                    if (editorWrapper.contains(event.target) || event.target.closest('.vditor-panel, .vditor-menu, .vditor-dropdown')) {
                                        return;
                                    }
                                    exitEditMode();
                                };
                                document.addEventListener('mousedown', globalClickHandler);
                            }
                        },
                    });
                } catch (error) {
                    console.error("Failed to init Vditor:", error);
                    ui.showToast(i18n.t('detailsPane.notesEditor.failedToLoad'), 'error');
                    exitEditMode();
                }
            });
        };

        renderPreview(repo.notes);
        editorWrapper.addEventListener('click', enterEditMode);
    };


    // 创建一个交互式的分组编辑器组件
    const _createTagsEditor = (repo, allKnownTags, onTagsChange) => {
        const editorContainer = document.createElement('div');
        editorContainer.className = 'tags-editor';

        const currentTags = repo.tags.filter(t => t !== '_favorite');

        // 渲染已有的分组为药丸
        currentTags.forEach(tag => {
            const pill = document.createElement('span');
            pill.className = 'tag-pill';
            const text = document.createElement('span');
            text.textContent = tag;
            pill.appendChild(text);
            const removeBtn = document.createElement('span');
            removeBtn.className = 'remove-tag';
            removeBtn.innerHTML = '<i class="fa-solid fa-xmark"></i>';
            removeBtn.title = `移除分组 '${tag}'`;
            removeBtn.onclick = (e) => {
                e.stopPropagation();
                
                // 添加CSS类触发移除动画
                pill.classList.add('is-removing');
                
                // 监听动画结束事件
                pill.addEventListener('animationend', () => {
                    // 动画结束后执行真正的删除操作
                    const newTags = currentTags.filter(t => t !== tag);
                    onTagsChange(repo.id, newTags);
                }, { once: true }); // 确保事件只触发一次后自动移除
            };
            pill.appendChild(removeBtn);
            editorContainer.appendChild(pill);
        });

        // “添加分组”按钮的交互逻辑
        const addButton = document.createElement('button');
        addButton.className = 'add-tag-button';
        addButton.innerHTML = `<i class="fa-solid fa-plus"></i> <span>${i18n.t('detailsPane.tagsEditor.addTag')}</span>`;
        
        const enterAddMode = () => {
            addButton.style.display = 'none';

            const inputWrapper = document.createElement('div');
            inputWrapper.className = 'tag-input-wrapper';

            const input = document.createElement('input');
            input.type = 'text';
            input.className = 'tag-add-input'; // 应用专属class
            input.placeholder = i18n.t('detailsPane.tagsEditor.placeholder');
            
            const suggestionsContainer = document.createElement('div');
            suggestionsContainer.className = 'tag-suggestions scroll-on-overflow-visible'; // 应用通用滚动条样式
            
            inputWrapper.appendChild(input);
            inputWrapper.appendChild(suggestionsContainer);
            editorContainer.appendChild(inputWrapper);
            input.focus();

            const addTag = (tag) => {
                tag = tag.trim();
                if (tag && !currentTags.includes(tag)) {
                    const newTags = [...currentTags, tag];
                    onTagsChange(repo.id, newTags);
                }
                exitAddMode();
            };

            const exitAddMode = () => {
                document.removeEventListener('click', handleGlobalClick);
                inputWrapper.remove();
                addButton.style.display = 'inline-flex';
            };

            const handleGlobalClick = (e) => {
                if (!inputWrapper.contains(e.target)) {
                    exitAddMode();
                }
            };
            
            const showSuggestions = (query = '') => {
                const lowerQuery = query.toLowerCase();
                const availableTags = allKnownTags.filter(tag => 
                    !currentTags.includes(tag) && tag.toLowerCase().includes(lowerQuery)
                );
                
                suggestionsContainer.innerHTML = '';
                if (availableTags.length > 0) {
                    availableTags.forEach(suggestion => {
                        const div = document.createElement('div');
                        div.textContent = suggestion;
                        div.onclick = () => addTag(suggestion);
                        suggestionsContainer.appendChild(div);
                    });
                    suggestionsContainer.style.display = 'block';
                } else {
                    suggestionsContainer.style.display = 'none';
                }
            };

            setTimeout(() => document.addEventListener('click', handleGlobalClick), 0);

            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    addTag(input.value);
                } else if (e.key === 'Escape') {
                    exitAddMode();
                }
            });

            input.addEventListener('input', () => showSuggestions(input.value));
            
            // 点击后立即使显示所有可用分组
            showSuggestions();
        };

        addButton.onclick = enterAddMode;
        editorContainer.appendChild(addButton);

        return editorContainer;
    };

    // --- 3. 私有辅助渲染函数 ---

    /**
     * 初始化移动端详情面板的右滑关闭手势。
     * @param {HTMLElement} detailsPanel - 详情面板的 DOM 元素。
     * @param {function} onCloseCallback - 手势成功触发关闭时调用的回调函数。
     * @returns {{destroy: function}|null} 返回一个包含 `destroy` 方法的对象用于清理，或在非移动端环境下返回 `null`。
     */
    const _initMobileSwipeGesture = (detailsPanel, onCloseCallback) => {
        // 只在移动端启用手势功能
        if (window.innerWidth > 768) return null;
        
        // 手势配置参数
        const SWIPE_CONFIG = {
            edgeSensitiveWidth: 120,       // 左边缘敏感区域宽度(px)
            normalThreshold: 0.25,         // 普通滑动阈值
            fastThreshold: 0.15,           // 快速滑动阈值
            fastVelocity: 0.3,             // 快速滑动速度阈值
            closeAnimation: 200,           // 快速关闭动画时长(ms)
            bounceAnimation: 250,          // 回弹动画时长(ms)
            normalAnimation: 300,          // 正常关闭动画时长(ms)
            disableInEdit: true,           // Vditor编辑时禁用
            disableInDropdown: true,       // 下拉展开时禁用
        };

        // 检查是否应该禁用手势的函数
        const shouldDisableGesture = () => {
            // 检查Vditor是否处于编辑模式
            if (SWIPE_CONFIG.disableInEdit) {
                const vditorWrapper = detailsPanel.querySelector('.notes-editor-container.is-editing');
                if (vditorWrapper) return true;
            }
            
            // 检查是否有下拉列表展开
            if (SWIPE_CONFIG.disableInDropdown) {
                const activeDropdown = detailsPanel.querySelector('.tag-suggestions[style*="display: block"]');
                if (activeDropdown) return true;
            }
            
            return false;
        };

        // 检查是否在边缘敏感区域开始的手势
        const isEdgeGesture = (startX) => {
            const panelRect = detailsPanel.getBoundingClientRect();
            const relativeX = startX - panelRect.left;
            return relativeX <= SWIPE_CONFIG.edgeSensitiveWidth;
        };

        // 初始化Hammer.js手势识别
        const hammer = new Hammer(detailsPanel);
        
        // 更宽松的手势配置，降低触发门槛
        hammer.get('swipe').set({ 
            direction: Hammer.DIRECTION_RIGHT,
            threshold: 5,   // 最小滑动距离
            velocity: 0.05  // 最小速度要求
        });

        // 配置pan手势用于跟随效果
        hammer.get('pan').set({ 
            direction: Hammer.DIRECTION_HORIZONTAL,
            threshold: 1    // pan手势的触发门槛
        });

        let isPanningRight = false;
        let startX = 0;
        let isEdgeStarted = false; // 标记是否从边缘开始

        // Pan开始事件 - 实现面板跟随手指移动
        hammer.on('panstart', (e) => {
            if (shouldDisableGesture()) return;
            
            startX = e.center.x;
            isEdgeStarted = isEdgeGesture(startX); // 检查是否从边缘开始
            isPanningRight = false;
            
            // 阻止浏览器默认的滑动行为
            e.preventDefault();
            e.srcEvent.preventDefault();
            
            // 设置面板过渡动画为无，让跟随更流畅
            detailsPanel.style.transition = 'none';
        });

        // Pan移动事件 - 面板跟随手指移动
        hammer.on('panmove', (e) => {
            if (shouldDisableGesture()) return;
            
            // 阻止浏览器默认行为
            e.preventDefault();
            e.srcEvent.preventDefault();
            
            const deltaX = e.center.x - startX;
            
            // 只处理向右的滑动，优先处理边缘手势
            if (deltaX > 0) {
                // 边缘手势更敏感，非边缘手势需要更大的移动距离
                const shouldActivate = isEdgeStarted || deltaX > 30;
                
                if (shouldActivate) {
                    isPanningRight = true;
                    // 计算移动比例，添加阻尼效果
                    const moveRatio = Math.min(deltaX / window.innerWidth, 0.8);
                    const translateX = moveRatio * 100;
                    
                    // 应用变换，让面板跟随手指移动
                    detailsPanel.style.transform = `translateX(${translateX}%)`;
                    
                    // 调整背景遮罩透明度（如果有的话）
                    const overlay = document.getElementById('overlay');
                    if (overlay && overlay.classList.contains('is-active')) {
                        const opacity = Math.max(0.4 * (1 - moveRatio * 2), 0);
                        overlay.style.opacity = opacity;
                    }
                }
            }
        });

        // Pan结束事件 - 判断是否关闭面板
        hammer.on('panend', (e) => {
            if (shouldDisableGesture() || !isPanningRight) {
                // 恢复面板样式
                detailsPanel.style.transition = '';
                detailsPanel.style.transform = '';
                const overlay = document.getElementById('overlay');
                if (overlay) overlay.style.opacity = '';
                return;
            }
            
            // 阻止浏览器默认行为
            e.preventDefault();
            e.srcEvent.preventDefault();
            
            const deltaX = e.center.x - startX;
            const velocity = Math.abs(e.velocityX);
            const screenWidth = window.innerWidth;
            
            // 判断是否应该关闭面板
            let shouldClose = false;
            
            // 边缘手势的阈值更低
            const thresholdMultiplier = isEdgeStarted ? 0.8 : 1.0;
            
            // 根据速度和距离判断
            if (velocity >= SWIPE_CONFIG.fastVelocity) {
                // 快速滑动：距离要求较低
                shouldClose = deltaX >= screenWidth * SWIPE_CONFIG.fastThreshold * thresholdMultiplier;
            } else {
                // 普通滑动：距离要求较高
                shouldClose = deltaX >= screenWidth * SWIPE_CONFIG.normalThreshold * thresholdMultiplier;
            }
            
            if (shouldClose) {
                // 关闭面板
                const animationDuration = velocity >= SWIPE_CONFIG.fastVelocity ? 
                    SWIPE_CONFIG.closeAnimation : SWIPE_CONFIG.normalAnimation;
                
                detailsPanel.style.transition = `transform ${animationDuration}ms ease-out`;
                detailsPanel.style.transform = 'translateX(100%)';
                
                // 恢复背景遮罩
                const overlay = document.getElementById('overlay');
                if (overlay) {
                    overlay.style.transition = `opacity ${animationDuration}ms ease-out`;
                    overlay.style.opacity = '0';
                }
                
                // 动画结束后执行关闭回调
                setTimeout(() => {
                    detailsPanel.style.transition = '';
                    detailsPanel.style.transform = '';
                    if (overlay) {
                        overlay.style.transition = '';
                        overlay.style.opacity = '';
                    }
                    onCloseCallback();
                }, animationDuration);
            } else {
                // 回弹到原位
                detailsPanel.style.transition = `transform ${SWIPE_CONFIG.bounceAnimation}ms ease-out`;
                detailsPanel.style.transform = '';
                
                // 恢复背景遮罩
                const overlay = document.getElementById('overlay');
                if (overlay) {
                    overlay.style.transition = `opacity ${SWIPE_CONFIG.bounceAnimation}ms ease-out`;
                    overlay.style.opacity = '';
                }
                
                // 动画结束后清理样式
                setTimeout(() => {
                    detailsPanel.style.transition = '';
                    if (overlay) overlay.style.transition = '';
                }, SWIPE_CONFIG.bounceAnimation);
            }
            
            isPanningRight = false;
            isEdgeStarted = false; // 重置边缘标记
        });

        // 直接右滑手势事件 - 快速右滑关闭
        hammer.on('swiperight', (e) => {
            if (shouldDisableGesture()) return;
            
            // 阻止浏览器默认行为
            e.preventDefault();
            e.srcEvent.preventDefault();
            
            // 只有边缘手势或足够快的滑动才触发快速关闭
            const swipeStartX = e.center.x - (e.distance * Math.cos(e.angle * Math.PI / 180));
            const isFromEdge = isEdgeGesture(swipeStartX);
            const isFastEnough = e.velocity > SWIPE_CONFIG.fastVelocity;
            
            if (isFromEdge || isFastEnough) {
                // 快速右滑直接关闭
                detailsPanel.style.transition = `transform ${SWIPE_CONFIG.closeAnimation}ms ease-out`;
                detailsPanel.style.transform = 'translateX(100%)';
                
                const overlay = document.getElementById('overlay');
                if (overlay) {
                    overlay.style.transition = `opacity ${SWIPE_CONFIG.closeAnimation}ms ease-out`;
                    overlay.style.opacity = '0';
                }
                
                setTimeout(() => {
                    detailsPanel.style.transition = '';
                    detailsPanel.style.transform = '';
                    if (overlay) {
                        overlay.style.transition = '';
                        overlay.style.opacity = '';
                    }
                    onCloseCallback();
                }, SWIPE_CONFIG.closeAnimation);
            }
        });

        // 添加touchstart事件监听，阻止浏览器默认行为
        const preventDefaultTouch = (e) => {
            const touch = e.touches[0];
            if (!touch) return;
            
            // 检查触摸目标是否为可交互元素
            const target = e.target;
            const isInteractiveElement = target.closest('button, a, input, .tag-pill, .tag-suggestions, [role="button"]');
            
            // 如果触摸的是可交互元素，不阻止默认行为，让其正常处理点击
            if (isInteractiveElement) {
                return;
            }
            
            // 只有在非交互元素的边缘区域，且很可能是滑动手势时才阻止默认行为
            const isFromEdge = isEdgeGesture(touch.clientX);
            if (isFromEdge) {
                // 存储初始触摸位置，用于后续判断是否为滑动
                preventDefaultTouch._initialTouch = {
                    x: touch.clientX,
                    y: touch.clientY,
                    time: Date.now()
                };
                // 暂时不阻止，等待touchmove来确认是否为滑动手势
            }
        };

        // touchmove事件处理，精确判断滑动意图
        const preventDefaultTouchMove = (e) => {
            const touch = e.touches[0];
            if (!touch || !preventDefaultTouch._initialTouch) return;
            
            const deltaX = touch.clientX - preventDefaultTouch._initialTouch.x;
            const deltaY = touch.clientY - preventDefaultTouch._initialTouch.y;
            const deltaTime = Date.now() - preventDefaultTouch._initialTouch.time;
            
            // 只有当确实是水平滑动手势时才阻止默认行为
            const isHorizontalSwipe = Math.abs(deltaX) > Math.abs(deltaY) && Math.abs(deltaX) > 10;
            const isFromEdge = isEdgeGesture(preventDefaultTouch._initialTouch.x);
            
            // 同时满足：1）从边缘开始 2）水平滑动 3）移动距离足够 时才阻止默认行为
            if (isFromEdge && isHorizontalSwipe && deltaX > 0) {
                e.preventDefault();
            }
        };

        // touchend事件清理
        const cleanupTouch = () => {
            preventDefaultTouch._initialTouch = null;
        };

        detailsPanel.addEventListener('touchstart', preventDefaultTouch, { passive: false });
        detailsPanel.addEventListener('touchmove', preventDefaultTouchMove, { passive: false });
        detailsPanel.addEventListener('touchend', cleanupTouch, { passive: true });
        detailsPanel.addEventListener('touchcancel', cleanupTouch, { passive: true });

        // 返回Hammer实例和清理函数
        return {
            destroy: () => {
                hammer.destroy();
                detailsPanel.removeEventListener('touchstart', preventDefaultTouch);
                detailsPanel.removeEventListener('touchmove', preventDefaultTouchMove);
                detailsPanel.removeEventListener('touchend', cleanupTouch);
                detailsPanel.removeEventListener('touchcancel', cleanupTouch);
            }
        };
    };

    // 根据 repo 对象，创建详情面板的内部 DOM 结构
    const _createRepoDetailsContent = (repo, allKnownTags, onTagsChange) => {
        const ownerAvatarUrl = (repo.owner && repo.owner.avatar_url) || repo.owner_avatar_url || '';
        const ownerLogin = (repo.owner && repo.owner.login) || repo.owner_login || 'N/A';
        
        const rawDisplayName = repo.alias || repo.full_name;
        const displayName = rawDisplayName.replace(/\//g, '/\u200B');

        const rawSubName = repo.alias ? repo.full_name : '';
        const subName = rawSubName.replace(/\//g, '/\u200B');

        const isFavorite = repo.tags.includes('_favorite');
        const heartIconClass = isFavorite ? 'fa-solid fa-heart is-favorite' : 'fa-regular fa-heart';
        const favoriteButtonText = isFavorite ? i18n.t('detailsPane.favoriteButton.unfavorite') : i18n.t('detailsPane.favoriteButton.favorite');
        
        const container = document.createElement('div');
        container.className = 'details-grid';
        
        // 动态创建 Header DOM 以便绑定 onerror 事件
        const header = document.createElement('header');
        header.className = 'details-hero-section';

        const avatarContainer = document.createElement('div');
        avatarContainer.className = 'avatar';
        const avatarImg = document.createElement('img');
        avatarImg.src = ownerAvatarUrl;
        avatarImg.alt = `${ownerLogin} avatar`;
        _addAvatarFallback(avatarImg, avatarContainer); // 为仓库作者头像添加备用逻辑
        avatarContainer.appendChild(avatarImg);

        const titleGroup = document.createElement('div');
        titleGroup.className = 'title-group';
        const editableContainer = document.createElement('div');
        editableContainer.className = 'editable-container';
        editableContainer.dataset.field = 'alias';
        editableContainer.dataset.originalValue = repo.alias || '';

        const h3 = document.createElement('h3');
        h3.className = 'repo-display-name'; // 统一class
        h3.textContent = displayName;
        editableContainer.appendChild(h3);

        titleGroup.appendChild(editableContainer);

        if (subName) {
            const p = document.createElement('p');
            p.textContent = subName;
            titleGroup.appendChild(p);
        }

        header.appendChild(avatarContainer);
        header.appendChild(titleGroup);
        container.appendChild(header);
        
        const descriptionHTML = repo.description && repo.description.trim()
            ? DOMPurify.sanitize(marked.parse(repo.description.trim()))
            : `<span class="placeholder-text">${i18n.t('detailsPane.noDescription')}</span>`;

        const restOfContent = document.createElement('div');
        restOfContent.innerHTML = `
            <section class="details-actions-section">
                <button id="details-favorite-btn"><i class="${heartIconClass}"></i><span>${favoriteButtonText}</span></button>
                <a href="${repo.html_url}" target="_blank" rel="noopener noreferrer" role="button"><i class="fa-brands fa-github"></i><span>${i18n.t('detailsPane.viewOnGithub')}</span></a>
            </section>
            <section class="details-tags-section">
                <h3 class="section-title">${i18n.t('detailsPane.sections.tags')}</h3>
                <div id="details-tags-container"></div>
            </section>
            <section class="details-info-section">
                <h3 class="section-title">${i18n.t('detailsPane.sections.details')}</h3>
                <div class="details-stats-grid">
                    <div class="stat-item"><span class="stat-value">${repo.stargazers_count.toLocaleString()}</span><span class="stat-label">${i18n.t('detailsPane.stats.stars')}</span></div>
                    <div class="stat-item"><span class="stat-value">${repo.language || '-'}</span><span class="stat-label">${i18n.t('detailsPane.stats.language')}</span></div>
                    <div class="stat-item"><span class="stat-value">${_formatTimeAgo(repo.pushed_at)}</span><span class="stat-label">${i18n.t('detailsPane.stats.updated')}</span></div>
                </div>
                <div class="description-content-wrapper">
                     <div class="description-content">${descriptionHTML}</div>
                </div>
            </section>
            <section class="details-notes-section">
                <h3 class="section-title">${i18n.t('detailsPane.sections.notes')}</h3>
                <div id="notes-editor-wrapper" class="notes-editor-container">
                    <div id="vditor-editor"></div>
                </div>
            </section>
        `;
        while (restOfContent.firstChild) {
            container.appendChild(restOfContent.firstChild);
        }

        const tagsEditor = _createTagsEditor(repo, allKnownTags, onTagsChange);
        container.querySelector('#details-tags-container').appendChild(tagsEditor);

        // 实现描述区域的非对称交互展开/收起
        const descriptionWrapper = container.querySelector('.description-content-wrapper');
        const descriptionContent = descriptionWrapper.querySelector('.description-content');

        // 仅当项目有有效描述时，才执行展开/收起逻辑
        if (repo.description && repo.description.trim()) {
            requestAnimationFrame(() => {
                const isOverflowing = descriptionContent.scrollHeight > (descriptionContent.clientHeight + 1);
                
                if (isOverflowing) {
                    descriptionWrapper.classList.add('is-expandable');
                    
                    const expandLink = document.createElement('a');
                    expandLink.className = 'expand-link';
                    expandLink.textContent = i18n.t('detailsPane.expand');
                    descriptionWrapper.appendChild(expandLink);
                    
                    expandLink.addEventListener('click', (e) => {
                        e.preventDefault();
                        e.stopPropagation();

                        const isExpanded = descriptionWrapper.classList.contains('is-expanded');

                        if (isExpanded) {
                            // 收起
                            descriptionContent.style.maxHeight = null; // 移除内联样式，让 CSS 接管
                            descriptionWrapper.classList.remove('is-expanded');
                            expandLink.textContent = i18n.t('detailsPane.expand');
                        } else {
                            // 展开
                            const fullHeight = descriptionContent.scrollHeight;
                            descriptionContent.style.maxHeight = `${fullHeight}px`; // 设置为完整高度以触发动画
                            descriptionWrapper.classList.add('is-expanded');
                            expandLink.textContent = i18n.t('detailsPane.collapse');
                        }
                    });
                }
            });
        }
        
        // 为详情面板应用“滚动时可见”的滚动条行为
        _applyAutoHideScrollbarBehavior(container);

        return container;
    };

    // 获取推送渠道特定的配置字段
    const _getChannelConfigFields = (channel) => {
        const allFields = {
            bark: [{ name: 'key', label: i18n.t('settingsModal.pushChannels.bark.key'), type: 'text', required: true }, { name: 'server_url', label: i18n.t('settingsModal.pushChannels.bark.server'), type: 'text', placeholder: 'https://api.day.app' }],
            gotify: [{ name: 'url', label: i18n.t('settingsModal.pushChannels.gotify.url'), type: 'text', required: true }, { name: 'token', label: i18n.t('settingsModal.pushChannels.gotify.token'), type: 'text', required: true }, { name: 'priority', label: i18n.t('settingsModal.pushChannels.gotify.priority'), type: 'select', options: [0, 1, 2, 3, 4, 5, 6, 7, 8], default: 8 }],
            serverchan: [{ name: 'sendkey', label: i18n.t('settingsModal.pushChannels.serverchan.key'), type: 'text', required: true }],
            webhook: [{ name: 'url', label: i18n.t('settingsModal.pushChannels.webhook.url'), type: 'text', required: true }, { name: 'method', label: i18n.t('settingsModal.pushChannels.webhook.method'), type: 'select', options: ['POST', 'GET'], default: 'POST' }, { name: 'json', label: i18n.t('settingsModal.pushChannels.webhook.json'), type: 'textarea', rows: 3 }],
        };
        return allFields[channel] || [];
    };

    // 根据设置数据，创建完整的设置表单 DOM 元素
    const _createSettingsForm = (settings, structure) => {
        const form = document.createElement('form');
        form.id = 'settings-form';
        form.setAttribute('onsubmit', 'return false;');
        
        let formHtml = '';
        structure.forEach((section, index) => {
            formHtml += `<fieldset class="settings-item" data-section="${section.id}">`;
            
            formHtml += `<legend class="settings-item-title">${section.legend}</legend>`;
            
            formHtml += `<p class="settings-item-description">${section.tooltip}</p>`;
            
            // 处理每个设置字段
            section.fields.forEach(field => {
                formHtml += `<div class="settings-control-row" data-field-id="${field.id}">`;
                
                if (field.type === 'switch') {
                    formHtml += `<span class="settings-control-label">${field.label}</span>`;
                    formHtml += `<label class="toggle-switch" for="${field.id}">
                        <input type="checkbox" id="${field.id}" name="${field.id}" ${field.value ? 'checked' : ''}>
                        <span class="slider"></span>
                    </label>`;
                } else if (field.type === 'button-group') {
                    formHtml += `<label class="settings-control-label">${field.label}</label>`;
                    formHtml += `<div class="button-group">`;
                    field.buttons.forEach(btn => {
                        formHtml += `<button type="button" id="${btn.id}" class="secondary">${btn.text}</button>`;
                    });
                    formHtml += `</div>`;
                } else {
                    formHtml += `<label class="settings-control-label" for="${field.id}">${field.label}</label>`;

                    switch (field.type) {
                        case 'select':
                            formHtml += `<select id="${field.id}" name="${field.id}">`;
                            const currentValue = field.value === null || field.value === undefined ? '' : field.value;
                            if (field.placeholder) {
                                formHtml += `<option value="" ${currentValue === '' ? 'selected' : ''}>${field.placeholder}</option>`;
                            }
                            field.options.forEach(opt => {
                                if (typeof opt === 'object') {
                                    formHtml += `<option value="${opt.value}" ${opt.value === currentValue ? 'selected' : ''}>${opt.text}</option>`;
                                } else {
                                    if (opt === '' && field.placeholder) return;
                                    formHtml += `<option value="${opt}" ${opt === currentValue ? 'selected' : ''}>${opt}${field.unit || ''}</option>`;
                                }
                            });
                            formHtml += `</select>`;
                            break;
                        case 'text':
                        case 'number':
                        case 'url':
                        case 'email':
                            formHtml += `<input type="${field.type}" id="${field.id}" name="${field.id}" value="${field.value || ''}" ${field.required ? 'required' : ''} placeholder="${field.placeholder || ''}">`;
                            break;
                        case 'password':
                            formHtml += `<input type="${field.type}" id="${field.id}" name="${field.id}" value="${field.value || ''}" ${field.required ? 'required' : ''} placeholder="${field.placeholder || ''}" autocomplete="new-password" data-lpignore="true" data-form-type="other">`;
                            break;
                        case 'textarea':
                            formHtml += `<textarea id="${field.id}" name="${field.id}" rows="${field.rows || 3}" placeholder="${field.placeholder || ''}">${field.value || ''}</textarea>`;
                            break;
                        case 'button':
                            formHtml += `<button type="button" id="${field.id}" class="secondary">${field.buttonText || field.label}</button>`;
                            break;
                    }
                }
                
                formHtml += `</div>`;
            });
            
            // 推送通知的配置容器
            if (section.id === 'notifications') {
                formHtml += '<div id="channel-config-container" class="settings-config-container"></div>';
            }
            
            formHtml += `</fieldset>`;
        });
        
        form.innerHTML = formHtml;
        return form;
    };

    // 创建捐赠部分的DOM，使用<fieldset>以统一布局，并用JS实现折叠
    const _createDonationSection = () => {
        const fieldset = document.createElement('fieldset');
        fieldset.className = 'settings-item is-collapsible is-collapsed';

        const legend = document.createElement('legend');
        legend.className = 'settings-item-title';
        legend.innerHTML = `
            ${i18n.t('settingsModal.donation.legend')}
            <i class="fa-solid fa-chevron-down collapse-indicator"></i>
        `;

        const contentWrapper = document.createElement('div');
        contentWrapper.className = 'collapsible-content';
        contentWrapper.innerHTML = `
            <div>
                <p class="settings-item-description">${i18n.t('settingsModal.donation.tooltip')}</p>
                <div class="donation-content">
                    <figure class="donation-qr-code">
                        <img src="assets/images/donate-alipay.png" alt="Alipay QR Code" data-action="zoom-in">
                        <figcaption>${i18n.t('settingsModal.donation.alipay')}</figcaption>
                    </figure>
                    <figure class="donation-qr-code">
                        <img src="assets/images/donate-wechat.png" alt="WeChat Pay QR Code" data-action="zoom-in">
                        <figcaption>${i18n.t('settingsModal.donation.wechat')}</figcaption>
                    </figure>
                </div>
            </div>
        `;

        legend.addEventListener('click', () => {
            fieldset.classList.toggle('is-collapsed');
        });
        
        fieldset.appendChild(legend);
        fieldset.appendChild(contentWrapper);

        return fieldset;
    };

    // 初始化图片预览模态框的逻辑
    const _initImagePreview = (container) => {
        const modal = elements.imagePreviewModal;
        if (!modal) return;

        const images = container.querySelectorAll('img[data-action="zoom-in"]');
        
        const showModal = (src) => {
            modal.innerHTML = `
                <article>
                    <img src="${src}" alt="Enlarged QR Code">
                </article>
            `;
            modal.showModal();
        };

        const closeModal = () => {
            modal.close();
        };

        images.forEach(img => {
            img.addEventListener('click', (e) => {
                e.stopPropagation();
                showModal(img.src);
            });
        });

        // 点击对话框背景（非图片区域）关闭
        modal.addEventListener('click', (e) => {
            if (e.target.tagName !== 'IMG') {
                closeModal();
            }
        });
    };

    // --- 4. 公开 API ---
    // 这个 return 语句包裹了所有可以从外部（即 main.js）调用的函数
    return {
        /**
         * 切换主视图 (登录 vs 应用)
         * @param {string} viewId - 'login-view' 或 'app-view'
         */
        showView(viewId) {
            if (viewId === 'app-view') {
                elements.loginView.style.display = 'none';
                elements.appView.style.display = 'grid';
                
                // 初始化滚动条延迟隐藏控制（仅在显示app-view时执行一次）
                if (!elements.appView.hasScrollbarDelayInit) {
                    _initScrollbarHoverDelay();
                    if (window.matchMedia("(max-width: 768px)").matches) {
                        _initScrollbarAutoHide();
                    }
                    elements.appView.hasScrollbarDelayInit = true;
                }
            } else {
                elements.loginView.style.display = 'flex';
                elements.appView.style.display = 'none';
                _createStarfield(elements.starfieldContainer);
            }
        },

        /**
         * 直接渲染所有卡片到视口，用于非虚拟滚动的网格布局
         * @param {Array} repos - 要渲染的仓库数据数组
         */
        renderAllCards(repos) {
            const viewport = elements.virtualScrollContainer.querySelector('.virtual-scroll-viewport');
            if (!viewport) return; // 如果视口不存在，直接返回

            viewport.innerHTML = ''; // 清空视口
            if (repos.length === 0) {
                viewport.innerHTML = `<article class="empty-state"><p>${i18n.t('emptyState.title')}</p><p>${i18n.t('emptyState.prompt')}</p></article>`;
                return;
            }
            const fragment = document.createDocumentFragment();
            repos.forEach(repo => {
                const cardElement = _createRepoCardItem(repo);
                fragment.appendChild(cardElement);
            });
            viewport.appendChild(fragment);
        },

        updateViewSwitcher() {
            // 使用已缓存的元素，避免重复查询DOM，提升效率
            const switcher = elements.viewSwitcher;
            if (!switcher) return; // 防御性编程：如果切换器不存在，则直接返回

            const activeItem = switcher.querySelector('button.active');
            if (!activeItem) return; // 如果找不到激活的按钮，也直接返回

            const glider = switcher.querySelector('.glider');
            if (glider) {
                // 计算滑块应有的宽度和相对于父元素的左侧偏移量
                const gliderWidth = activeItem.offsetWidth;
                const gliderOffset = activeItem.offsetLeft;

                // 应用样式来移动并调整滑块大小
                glider.style.width = `${gliderWidth}px`;
                glider.style.transform = `translateX(${gliderOffset}px)`;
            }
        },

        /**
         * 渲染页眉的用户信息
         * @param {object} user - 从 API 获取的用户对象
         */
        renderUserProfile(user) {
            const avatarContainer = elements.avatarContainer;
            if (!avatarContainer) return;
            avatarContainer.innerHTML = '';
            const img = document.createElement('img');
            img.id = 'user-avatar';
            img.src = user.avatar_url;
            img.alt = user.login;
            // 为用户头像添加备用逻辑
            _addAvatarFallback(img, avatarContainer);
            avatarContainer.appendChild(img);
            elements.userLogin.textContent = user.login;

            // I18n: 在渲染完基础信息后，立即翻译所有静态文本
            const i18nItems = document.querySelectorAll('[data-i18n]');
            i18nItems.forEach(item => {
                const i18nAttr = item.dataset.i18n;
                if (!i18nAttr) return;

                // 确保 i18n 模块已加载并可用
                if (i18n && typeof i18n.t === 'function') {
                    if (i18nAttr.startsWith('[placeholder]')) {
                        const key = i18nAttr.replace('[placeholder]', '');
                        item.placeholder = i18n.t(key);
                    } else {
                        const key = i18nAttr;
                        // 对于 <option> 元素，我们只更新文本内容，保留 value
                        if (item.tagName === 'OPTION') {
                            item.textContent = i18n.t(key);
                        } else {
                            // 对于其他元素，直接替换内容
                            item.innerHTML = i18n.t(key);
                        }
                    }
                }
            });
        },

        /**
         * 渲染左侧栏的分组和语言列表
         * @param {object} counts - 包含各类计数的对象
         * @param {string[]} sortedTags - 排序后的用户分组名数组
         * @param {string[]} sortedLanguages - 排序后的语言名数组
         */
        renderSidebar(counts, sortedTags, sortedLanguages, activeFilter) {
            
        const sidebarElements = elements.sidebar;

            // 静态节点（一级标签）根据状态更新激活样式
            const systemFilters = [sidebarElements.allReposFilter, sidebarElements.constellationFilter, sidebarElements.untaggedFilter];
            systemFilters.forEach(el => {
                if (el) {
                    const isActive = activeFilter && activeFilter.type === 'system' && activeFilter.value === el.dataset.filter;
                    el.classList.toggle('is-active', isActive);
                }
            });

            const updateCount = (element, count) => {
                if (!element) return;
                let countSpan = element.querySelector('.filter-count');
                if (!countSpan) {
                    countSpan = document.createElement('span');
                    countSpan.className = 'filter-count';
                    element.appendChild(document.createTextNode(' '));
                    element.appendChild(countSpan);
                }
                countSpan.textContent = count;
            };

            updateCount(sidebarElements.allReposFilter, counts.all);
            updateCount(sidebarElements.constellationFilter, counts.constellation);
            updateCount(sidebarElements.untaggedFilter, counts.untagged);
            const tagsFragment = document.createDocumentFragment();
            sortedTags.filter(tag => tag !== '_favorite').forEach(tag => {
                const tagCount = counts.tags[tag] || 0;
                const item = _createFilterItem({ text: tag, count: tagCount, dataType: 'tag', dataValue: tag, isDraggable: true }, activeFilter);
                const deleteBtn = document.createElement('button');
                deleteBtn.className = 'delete-tag-btn button-icon';
                deleteBtn.innerHTML = '<i class="fa-solid fa-trash-can"></i>';
                deleteBtn.dataset.tagName = tag;
                deleteBtn.title = `删除分组 '${tag}'`;
                item.querySelector('.filter-right-content').appendChild(deleteBtn);
                tagsFragment.appendChild(item);
            });
            sidebarElements.tagsList.innerHTML = '';
            sidebarElements.tagsList.appendChild(tagsFragment);
            const langsFragment = document.createDocumentFragment();
            sortedLanguages.forEach(lang => {
                const langCount = counts.languages[lang] || 0;
                if (langCount > 0) {
                    langsFragment.appendChild(_createFilterItem({ text: lang, count: langCount, dataType: 'language', dataValue: lang, isDraggable: true }, activeFilter));
                }
            });
            sidebarElements.languagesList.innerHTML = '';
            sidebarElements.languagesList.appendChild(langsFragment);
        },


        /**
         * 初始化并返回一个 VirtualScroller 实例 (仅用于列表视图)
         */
        initVirtualScroller() {
            const currentItemHeight = window.innerWidth <= 768 ? 124 : 84;
            return new VirtualScroller(elements.virtualScrollContainer, {
                itemHeight: currentItemHeight, // 使用动态计算出的高度
                renderItem: _createRepoListItem            });
        },

        /**
         * 切换仓库列表的视图模式，并确保 viewport 容器存在
         * @param {string} viewMode - 'list' 或 'card'
         */
        switchRepoView(viewMode) {
            // 确保视口元素存在，这是修复卡片视图空白的关键
            let viewport = elements.virtualScrollContainer.querySelector('.virtual-scroll-viewport');
            if (!viewport) {
                viewport = document.createElement('div');
                viewport.className = 'virtual-scroll-viewport';
                elements.virtualScrollContainer.innerHTML = ''; // 先清空，以防有旧的 sizer
                elements.virtualScrollContainer.appendChild(viewport);
            }

            if (viewMode === 'card') {
                elements.repoListContainer.classList.remove('view-list');
                elements.repoListContainer.classList.add('view-card');
                return { itemHeight: 220, renderItem: _createRepoCardItem };
            }
            // 默认是列表视图
            elements.repoListContainer.classList.remove('view-card');
            elements.repoListContainer.classList.add('view-list');
            return { itemHeight: 64, renderItem: _createRepoListItem };
        },

        /**
         * 渲染或更新右侧详情面板
         * @param {object} repo - 仓库数据对象
         * @param {object} options - 包含回调函数的配置对象
         */
        toggleRepoDetails(repo, options = {}) {
            if (repo) {
                const { onSave, onTagsChange, allKnownTags } = options;
                elements.repoDetails.innerHTML = ''; // 清空旧内容
                
                // 1. 创建详情面板的静态 DOM 结构
                const content = _createRepoDetailsContent(repo, allKnownTags, onTagsChange);
                elements.repoDetails.appendChild(content);
                
                // 2. 为“别名”启用行内编辑
                const aliasContainer = elements.repoDetails.querySelector('[data-field="alias"]');
                if (aliasContainer) {
                    _enableInlineEditing({ 
                        displayElement: aliasContainer, 
                        field: 'alias', 
                        repoId: repo.id, 
                        onSave 
                    });
                }
                
                // 3. 初始化 Vditor 备注编辑器
                _initVditorNotesEditor(repo, onSave);

                // 4. 显示面板
                elements.repoDetails.classList.add('is-active');

                // 使用 mousedown + click 防火墙，阻止内部交互关闭面板
                elements.repoDetails.addEventListener('mousedown', (e) => {
                    // 如果鼠标按下的目标是链接、按钮或输入框（或其内部元素），则阻止事件冒泡
                    if (e.target.closest('a, button, input')) {
                        e.stopPropagation();
                    }
                });
                
                // click事件防火墙，确保按钮点击不会意外关闭右侧栏
                elements.repoDetails.addEventListener('click', (e) => {
                    if (e.target.closest('a, button, input, .tag-input-wrapper, .tag-suggestions')) {
                        e.stopPropagation();
                    }
                });

                // 初始化移动端右滑收起手势
                // 先清理之前的手势实例（如果存在）
                if (currentSwipeGesture) {
                    currentSwipeGesture.destroy();
                    currentSwipeGesture = null;
                }
                
                // 初始化新的手势处理
                currentSwipeGesture = _initMobileSwipeGesture(elements.repoDetails, () => {
                    // 手势触发的关闭回调 - 需要调用主应用的关闭逻辑
                    ui.toggleRepoDetails(null);
                    const closeEvent = new CustomEvent('detailsPanelClosed', {
                        detail: { source: 'swipe' }
                    });
                    document.dispatchEvent(closeEvent);
                });

            } else {
                // 清理移动端手势实例
                if (currentSwipeGesture) {
                    currentSwipeGesture.destroy();
                    currentSwipeGesture = null;
                }
                
                elements.repoDetails.classList.remove('is-active');
                // 在过渡动画结束后再清空内容，避免闪烁
                elements.repoDetails.addEventListener('transitionend', () => {
                    if (!elements.repoDetails.classList.contains('is-active')) {
                        elements.repoDetails.innerHTML = '';
                    }
                }, { once: true });
            }
        },

        /**
         * 显示一个 Toast 通知
         */
        showToast(message, type = 'info', duration = 3000) {
            return _createToast(message, type, duration);
        },

        /**
         * 显示一个确认对话框
         */
        showConfirmationModal({ title, content, onConfirm, confirmText = '', cancelText = '' }) {
            const modal = elements.confirmationModal;
            if (!modal) return;

                        const contentWrapper = modal.querySelector('#confirmation-modal-content');
            if (contentWrapper) {
                contentWrapper.innerHTML = `
                    <div class="confirmation-title">${title}</div>
                    <div class="confirmation-body">${content}</div>
                `;
            }

            const confirmBtn = modal.querySelector('.modal-confirm-btn');
            const cancelBtn = modal.querySelector('.modal-close-btn');
            
            if(confirmBtn && confirmText) confirmBtn.textContent = confirmText;
            if(cancelBtn && cancelText) cancelBtn.textContent = cancelText;

            let confirmHandler, cancelHandler, closeHandler;

                        const animatedClose = () => {
                // 添加关闭动画标记
                modal.setAttribute('closing', '');
                
                // 等待动画完成后再真正关闭弹窗
                setTimeout(() => {
                    modal.removeAttribute('closing');
                    modal.close();
                }, 200); // 对应 modal-scale-out 动画时长
            };

            const cleanup = () => {
                if(confirmBtn) confirmBtn.removeEventListener('click', confirmHandler);
                if(cancelBtn) cancelBtn.removeEventListener('click', cancelHandler);
                modal.removeEventListener('close', closeHandler);
            };

            confirmHandler = () => {
                onConfirm();
                animatedClose(); // 使用带动画的关闭
            };

            cancelHandler = () => {
                animatedClose(); // 使用带动画的关闭
            };

            closeHandler = () => {
                cleanup();
            };

            if(confirmBtn) confirmBtn.addEventListener('click', confirmHandler, { once: true });
            if(cancelBtn) cancelBtn.addEventListener('click', cancelHandler, { once: true });
            modal.addEventListener('close', closeHandler, { once: true });

            const handleKeyDown = (e) => {
                if (e.key === 'Escape') {
                    e.preventDefault(); // 阻止默认的立即关闭行为
                    animatedClose();
                    modal.removeEventListener('keydown', handleKeyDown);
                }
            };
            modal.addEventListener('keydown', handleKeyDown);

            modal.showModal();

            // 将默认焦点设置在更安全的“取消”按钮上
            if(cancelBtn) {
                cancelBtn.focus();
            }
        },

        /**
         * 在侧边栏显示用于添加新分组的输入框
         */
        showTagInput(onSave, onCancel) {
            const addTagContainer = elements.sidebar.addTagContainer;
            if (!addTagContainer) return;
            const originalContent = addTagContainer.innerHTML;
            addTagContainer.innerHTML = `<div class="tag-input-container"><input type="text" id="new-tag-input" placeholder="${i18n.t('tagInput.placeholder')}" maxlength="30"></div>`;
            const input = addTagContainer.querySelector('#new-tag-input');
            input.focus();
            const handleKeyDown = (e) => {
                if (e.key === 'Enter') onSave(input.value);
                else if (e.key === 'Escape') onCancel();
            };
            const handleBlur = () => { onCancel(); };
            input.addEventListener('keydown', handleKeyDown);
            input.addEventListener('blur', handleBlur);
            return () => {
                input.removeEventListener('keydown', handleKeyDown);
                input.removeEventListener('blur', handleBlur);
                addTagContainer.innerHTML = originalContent;
            };
        },
        
        /**
         * 设置全局加载状态（显示在鼠标指针上）
         * @param {boolean} isLoading - 是否正在加载
         */
        setGlobalLoading(isLoading) {
            document.body.classList.toggle('is-loading', isLoading);
        },

        /**
         * 显示一个全屏的加载遮罩层 
         * @param {string} text - 显示在加载动画下方的文本
         */
        showGlobalBlocker(text) {
            let blocker = document.getElementById('global-blocker');
            if (!blocker) {
                blocker = document.createElement('div');
                blocker.id = 'global-blocker';
                document.body.appendChild(blocker);
            }
            blocker.innerHTML = `<article><progress></progress><p>${text}</p></article>`;
            document.body.classList.add('is-blocked');
        },
        
        /**
         * 隐藏并移除全屏加载遮罩层
         */
        hideGlobalBlocker() {
            const blocker = document.getElementById('global-blocker');
            if (blocker) blocker.remove();
            document.body.classList.remove('is-blocked');
        },

        /**
         * 显示系统设置视图，并填充表单
         * @param {object} currentSettings - 当前的设置数据
         * @param {function} onSaveCallback - 保存按钮点击时的回调
         */
        showSettingsView(currentSettings, onSaveCallback) {
            const settingsView = elements.settingsViewModal;
            if (!settingsView) {
                console.error("CRITICAL: Dialog with id #settings-view-modal not found in HTML!");
                return;
            }

            settingsView.innerHTML = `
                <article>
                    <div id="settings-form-container"></div>
                    <footer class="settings-footer">
                        <button type="button" class="secondary close-settings">${i18n.t('settingsModal.buttons.cancel')}</button>
                        <button type="submit" form="settings-form" class="primary">${i18n.t('settingsModal.buttons.save')}</button>
                    </footer>
                </article>
            `;

            const formContainer = settingsView.querySelector('#settings-form-container');
            if (!formContainer) {
                console.error("CRITICAL: #settings-form-container not found after creating dialog content!");
                return;
            }

            const structure = [
                { id: 'language', legend: i18n.t('settingsModal.language.legend'), tooltip: i18n.t('settingsModal.language.tooltip'), fields: [{ id: 'ui_language', label: i18n.t('settingsModal.language.label'), type: 'select', value: currentSettings.ui_language, options: [{ value: 'zh', text: i18n.t('settingsModal.language.options.zh') }, { value: 'en', text: i18n.t('settingsModal.language.options.en') }] }] },
                { id: 'sync', legend: i18n.t('settingsModal.sync.legend'), tooltip: i18n.t('settingsModal.sync.tooltip'), fields: [{ id: 'is_background_sync_enabled', label: i18n.t('settingsModal.sync.enableLabel'), type: 'switch', value: currentSettings.is_background_sync_enabled }, { id: 'sync_interval_hours', label: i18n.t('settingsModal.sync.intervalLabel'), type: 'select', value: currentSettings.sync_interval_hours, options: [1, 2, 6, 12, 24, 36, 48], unit: i18n.t('settingsModal.sync.intervalUnit') }] },
                { id: 'ai_summary', legend: i18n.t('settingsModal.ai.legend'), tooltip: i18n.t('settingsModal.ai.tooltip'), fields: [{ id: 'is_ai_enabled', label: i18n.t('settingsModal.ai.enableLabel'), type: 'switch', value: currentSettings.is_ai_enabled || false }, { id: 'is_auto_analysis_enabled', label: i18n.t('settingsModal.ai.autoLabel'), type: 'switch', value: currentSettings.is_auto_analysis_enabled || false }, { id: 'ai_base_url', label: i18n.t('settingsModal.ai.baseUrlLabel'), type: 'text', value: currentSettings.ai_base_url || '', placeholder: i18n.t('settingsModal.ai.baseUrlPlaceholder') }, { id: 'ai_api_key', label: i18n.t('settingsModal.ai.apiKeyLabel'), type: 'password', value: currentSettings.ai_api_key || '', placeholder: i18n.t('settingsModal.ai.apiKeyPlaceholder') }, { id: 'ai_model', label: i18n.t('settingsModal.ai.modelLabel'), type: 'text', value: currentSettings.ai_model || '', placeholder: i18n.t('settingsModal.ai.modelPlaceholder') }, { id: 'ai_concurrency', label: i18n.t('settingsModal.ai.concurrencyLabel'), type: 'select', value: currentSettings.ai_concurrency || 1, options: [1, 2, 3, 4, 5], unit: i18n.t('settingsModal.ai.concurrencyUnit') }, { id: 'ai_summary_buttons', label: i18n.t('settingsModal.ai.manualLabel'), type: 'button-group', buttons: [{ id: 'summarize_all_button', text: i18n.t('settingsModal.ai.summarizeAll') }, { id: 'summarize_unanalyzed_button', text: i18n.t('settingsModal.ai.summarizeUnanalyzed') }] }] },
                { id: 'notifications', legend: i18n.t('settingsModal.notifications.legend'), tooltip: i18n.t('settingsModal.notifications.tooltip'), fields: [{ id: 'is_push_enabled', label: i18n.t('settingsModal.notifications.enableLabel'), type: 'switch', value: currentSettings.is_push_enabled }, { id: 'push_channel', label: i18n.t('settingsModal.notifications.channelLabel'), type: 'select', value: currentSettings.push_channel, options: [{value: 'bark', text: 'Bark'}, {value: 'gotify', text: 'Gotify'}, {value: 'serverchan', text: 'ServerChan'}, {value: 'webhook', text: 'WebHook'}], placeholder: i18n.t('settingsModal.notifications.channelPlaceholder') }, { id: 'is_push_proxy_enabled', label: i18n.t('settingsModal.notifications.proxyLabel'), type: 'switch', value: currentSettings.is_push_proxy_enabled }] },
                { id: 'dnd', legend: i18n.t('settingsModal.dnd.legend'), tooltip: i18n.t('settingsModal.dnd.tooltip'), fields: [{ id: 'is_dnd_enabled', label: i18n.t('settingsModal.dnd.enableLabel'), type: 'switch', value: currentSettings.is_dnd_enabled }, { id: 'dnd_start_hour', label: i18n.t('settingsModal.dnd.startLabel'), type: 'select', value: currentSettings.dnd_start_hour, options: Array.from({ length: 24 }, (_, i) => i), unit: i18n.t('settingsModal.dnd.timeUnit') }, { id: 'dnd_end_hour', label: i18n.t('settingsModal.dnd.endLabel'), type: 'select', value: currentSettings.dnd_end_hour, options: Array.from({ length: 24 }, (_, i) => i), unit: i18n.t('settingsModal.dnd.timeUnit') }] }
            ];

            const formElement = _createSettingsForm(currentSettings, structure);
            formContainer.appendChild(formElement);

            // 将捐赠区添加到表单末尾
            const donationSection = _createDonationSection();
            formElement.appendChild(donationSection);

            // 初始化捐赠区的图片预览功能
            _initImagePreview(donationSection);

            // 缓存所有需要控制的DOM元素
            const syncSwitch = formElement.querySelector('#is_background_sync_enabled');
            const pushSwitch = formElement.querySelector('#is_push_enabled');
            const dndSwitch = formElement.querySelector('#is_dnd_enabled');
            const aiSwitch = formElement.querySelector('#is_ai_enabled');

            const syncIntervalSelect = formElement.querySelector('#sync_interval_hours');
            const pushChannelSelect = formElement.querySelector('#push_channel');
            const pushProxySwitch = formElement.querySelector('#is_push_proxy_enabled');
            const channelConfigContainer = formElement.querySelector('#channel-config-container');
            const dndStartSelect = formElement.querySelector('#dnd_start_hour');
            const dndEndSelect = formElement.querySelector('#dnd_end_hour');

            const autoAnalysisSwitch = formElement.querySelector('#is_auto_analysis_enabled');
            const aiBaseUrlInput = formElement.querySelector('#ai_base_url');
            const aiApiKeyInput = formElement.querySelector('#ai_api_key');
            const aiModelInput = formElement.querySelector('#ai_model');
            const aiConcurrencySelect = formElement.querySelector('#ai_concurrency');
            const summarizeAllButton = formElement.querySelector('#summarize_all_button');
            const summarizeUnanalyzedButton = formElement.querySelector('#summarize_unanalyzed_button');

            const updateFormState = () => {
                const isSyncEnabled = syncSwitch.checked;
                const isAiEnabled = aiSwitch.checked;

                // 规则 1 & 2: 级联关闭开关
                // 如果同步被关闭，则强制关闭其所有子开关
                if (!isSyncEnabled) {
                    pushSwitch.checked = false;
                    dndSwitch.checked = false;
                }
                // 在同步开关状态处理之后，再检查推送开关。如果它被关闭，则强制关闭其子开关
                const isPushEnabled = pushSwitch.checked; // 重新获取推送开关的（可能已被改变的）状态
                if (!isPushEnabled) {
                    dndSwitch.checked = false;
                }
                const isDndEnabled = dndSwitch.checked; // 重新获取DND开关的最终状态

                // AI 设置的级联逻辑
                if (!isAiEnabled) {
                    autoAnalysisSwitch.checked = false;
                }

                // 规则 3: 根据最终的开关状态，设置所有控件的可用性
                // a. 同步设置的子项
                syncIntervalSelect.disabled = !isSyncEnabled;

                // b. 推送设置的总开关和子项
                pushSwitch.disabled = !isSyncEnabled;
                const pushSubItemsDisabled = !isSyncEnabled || !isPushEnabled;
                pushChannelSelect.disabled = pushSubItemsDisabled;
                pushProxySwitch.disabled = pushSubItemsDisabled;
                channelConfigContainer.querySelectorAll('input, select, textarea').forEach(el => {
                    el.disabled = pushSubItemsDisabled;
                });

                // c. DND设置的总开关和子项
                dndSwitch.disabled = !isSyncEnabled || !isPushEnabled;
                dndStartSelect.disabled = !isSyncEnabled || !isPushEnabled || !isDndEnabled;
                dndEndSelect.disabled = !isSyncEnabled || !isPushEnabled || !isDndEnabled;

                // d. AI 设置的子项
                if (autoAnalysisSwitch) autoAnalysisSwitch.disabled = !isAiEnabled;
                if (aiBaseUrlInput) aiBaseUrlInput.disabled = !isAiEnabled;
                if (aiApiKeyInput) aiApiKeyInput.disabled = !isAiEnabled;
                if (aiModelInput) aiModelInput.disabled = !isAiEnabled;
                if (aiConcurrencySelect) aiConcurrencySelect.disabled = !isAiEnabled;
                if (summarizeAllButton) summarizeAllButton.disabled = !isAiEnabled;
                if (summarizeUnanalyzedButton) summarizeUnanalyzedButton.disabled = !isAiEnabled;
            };

            // 绑定事件监听器
            syncSwitch.addEventListener('change', updateFormState);
            pushSwitch.addEventListener('change', updateFormState);
            dndSwitch.addEventListener('change', updateFormState);
            aiSwitch.addEventListener('change', updateFormState);

            // 绑定 AI 总结按钮事件
            if (summarizeAllButton) {
                summarizeAllButton.addEventListener('click', () => {
                    if (typeof app !== 'undefined' && app.handleSummarizeAll) {
                        app.handleSummarizeAll();
                    }
                });
            }
            if (summarizeUnanalyzedButton) {
                summarizeUnanalyzedButton.addEventListener('click', () => {
                    if (typeof app !== 'undefined' && app.handleSummarizeUnanalyzed) {
                        app.handleSummarizeUnanalyzed();
                    }
                });
            }

            const settingsViewClickHandler = (e) => {
                if (e.target.matches('.close-settings') || e.target.closest('.close-settings')) {
                    ui.hideSettingsView();
                    return;
                }
                if (e.target.matches('button[type="submit"]')) {
                    e.preventDefault();
                    const formData = new FormData(formElement);
                    const dataToSave = {};
                    formElement.querySelectorAll('input, select, textarea').forEach(el => {
                        if (!el.name) return;

                        if (el.type === 'checkbox') {
                            dataToSave[el.name] = el.checked;
                        } else {
                            const value = el.value;
                            const processedValue = isFinite(value) && value.trim() !== '' ? parseFloat(value) : value;
                            
                            if (el.name.startsWith('push_config.')) {
                                if (!dataToSave.push_config) dataToSave.push_config = {};
                                const configKey = el.name.substring('push_config.'.length);
                                dataToSave.push_config[configKey] = processedValue;
                            } else {
                                dataToSave[el.name] = processedValue;
                            }
                        }
                    });
                    // 这段代码确保所有未选中的开关都能以 false 的形式被保存，这是良好的编程习惯。
                    structure.forEach(section => section.fields.forEach(field => {
                        if (field.type === 'switch' && !dataToSave.hasOwnProperty(field.id)) {
                            dataToSave[field.id] = false;
                        }
                    }));

                    // 根据层级依赖关系，在保存前强制校准数据，确保数据模型的一致性。
                    
                    // 规则3：如果“后台同步”被关闭，则其所有子功能（推送、勿扰）也必须被强制关闭。
                    if (dataToSave.is_background_sync_enabled === false) {
                        dataToSave.is_push_enabled = false;
                        dataToSave.is_dnd_enabled = false;
                    }

                    // 规则4：如果“通知推送”被关闭，则其子功能（勿扰）也必须被强制关闭。
                    // 这个检查必须在“后台同步”检查之后，因为它可能已经被前者设为 false。
                    if (dataToSave.is_push_enabled === false) {
                        dataToSave.is_dnd_enabled = false;
                    }
                    
                    // 调用回调函数，将经过校准的、干净的数据发送到后端。
                    onSaveCallback(dataToSave);
                }
            };

            // 在添加新监听器前，先移除可能存在的旧监听器，防止事件累积导致重复请求
            if (settingsView._currentHandler) {
                settingsView.removeEventListener('click', settingsView._currentHandler);
            }
            settingsView.addEventListener('click', settingsViewClickHandler);
            settingsView._currentHandler = settingsViewClickHandler;

            const renderChannelConfig = (channel) => {
                channelConfigContainer.innerHTML = '';
                const fields = _getChannelConfigFields(channel);
                if (fields.length > 0) {
                    let configHtml = '';
                    fields.forEach(f => {
                        configHtml += `<div class="settings-control-row" data-field-id="${f.name}">`;
                        configHtml += `<label class="settings-control-label" for="push_config.${f.name}">${f.label}${f.required ? ' <span class="required" style="color:red">*</span>' : ''}</label>`;
                        switch (f.type) {
                            case 'select':
                                configHtml += `<select id="push_config.${f.name}" name="push_config.${f.name}">`;
                                (f.options || []).forEach(opt => {
                                    configHtml += `<option value="${opt}" ${opt === (currentSettings.push_config?.[f.name] || f.default) ? 'selected' : ''}>${opt}</option>`;
                                });
                                configHtml += `</select>`;
                                break;
                            case 'textarea':
                                configHtml += `<textarea id="push_config.${f.name}" name="push_config.${f.name}" rows="${f.rows || 3}" placeholder="${f.placeholder || ''}">${currentSettings.push_config?.[f.name] || f.default || ''}</textarea>`;
                                break;
                            default:
                                const value = currentSettings.push_config?.[f.name] !== undefined ? currentSettings.push_config[f.name] : (f.default !== undefined ? f.default : '');
                                configHtml += `<input type="${f.type}" id="push_config.${f.name}" name="push_config.${f.name}" value="${value}" ${f.required ? 'required' : ''} placeholder="${f.placeholder || ''}">`;
                                break;
                        }
                        configHtml += `</div>`;
                    });
                    channelConfigContainer.innerHTML = configHtml;
                    channelConfigContainer.style.display = 'block';

                    // 为JSON Template输入框添加自动增长功能
                    const jsonTextarea = channelConfigContainer.querySelector('textarea[name="push_config.json"]');
                    if (jsonTextarea) {
                        jsonTextarea.rows = 1; // 设置初始高度为1行

                        const autoGrow = (element) => {
                            element.style.height = 'auto';
                            element.style.height = (element.scrollHeight) + 'px';
                        };

                        jsonTextarea.addEventListener('input', () => autoGrow(jsonTextarea));

                        // 初始化时检查一次，确保有默认值时也能正确显示高度
                        setTimeout(() => autoGrow(jsonTextarea), 100);
                    }
                } else {
                    channelConfigContainer.style.display = 'none';
                }
                const pushProxyRow = formElement.querySelector('[data-field-id="is_push_proxy_enabled"]');
                if (pushProxyRow) {
                    pushProxyRow.style.display = channel ? 'grid' : 'none';
                }
            };

            if (pushChannelSelect) {
                pushChannelSelect.addEventListener('change', (e) => renderChannelConfig(e.target.value));
                renderChannelConfig(pushChannelSelect.value);
            }

            // 在所有内容都渲染和绑定完成后，最后执行一次状态更新，确保初始UI状态完全正确
            updateFormState();

            settingsView.showModal();
        },

        /**
         * 隐藏并移除系统设置视图
         */
        hideSettingsView() {
            const settingsView = elements.settingsViewModal;
            if (settingsView && settingsView.close) {
                settingsView.close();
            }
        },

        /**
         * 初始化移动端排序菜单
         * 从桌面的 <select> 中读取选项，并动态创建移动端菜单项。
         * @param {string} currentSortValue - 当前激活的排序值。
         */
        initMobileSorter(currentSortValue) {
            const desktopSelect = document.getElementById('sort-by');
            const mobileOptionsList = document.getElementById('mobile-sort-options');
            if (!desktopSelect || !mobileOptionsList) return;

            mobileOptionsList.innerHTML = ''; 
            const fragment = document.createDocumentFragment();

            Array.from(desktopSelect.options).forEach(option => {
                const li = document.createElement('li');
                const a = document.createElement('a');
                a.href = '#';
                a.dataset.value = option.value;
                a.dataset.i18n = option.dataset.i18n;
                a.textContent = option.textContent;

                if (option.value === currentSortValue) {
                    const checkIcon = document.createElement('i');
                    checkIcon.className = 'fa-solid fa-check';
                    a.appendChild(checkIcon);
                }
                
                li.appendChild(a);
                fragment.appendChild(li);
            });
            mobileOptionsList.appendChild(fragment);
        },

        /**
         * 更新移动端排序菜单的激活状态
         * @param {string} newActiveValue - 新的被激活的排序值。
         */
        updateMobileSortActiveState(newActiveValue) {
            const mobileOptions = document.querySelectorAll('#mobile-sort-options a');
            mobileOptions.forEach(a => {
                const existingCheck = a.querySelector('.fa-check');
                if (existingCheck) existingCheck.remove();

                if (a.dataset.value === newActiveValue) {
                    const checkIcon = document.createElement('i');
                    checkIcon.className = 'fa-solid fa-check';
                    a.appendChild(checkIcon);
                }
            });
        },

        
    };
})();
