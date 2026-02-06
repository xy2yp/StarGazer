/**
 * StarGazer Main Application Module
 *
 * 职责: 应用的入口、状态管理和业务逻辑总指挥。
 * 提供完整的前端应用生命周期管理，包括用户认证、数据同步、界面交互等核心功能。
 */
const app = (() => {

    // --- 核心状态管理 ---
    const state = {
        isLoggedIn: false,
        isLoading: true,
        user: null,
        settings: {},
        allRepos: [],
        metadata: {
            tags: [],
            languages: []
        },
        filteredRepos: [],
        activeFilter: { type: 'system', value: 'all' },
        activeSort: 'starred_at',
        searchQuery: '',
        currentView: 'list',
        selectedRepoId: null,
        isDetailsPanelOpen: false,
    };

    // --- 实例与DOM缓存 ---
    let virtualScroller = null;
    let tagsSortable = null;
    let languagesSortable = null;

    const elements = {
        sidebar: document.getElementById('sidebar'),
        sortBySelect: document.getElementById('sort-by'),
        searchBox: document.getElementById('search-box'),
        viewSwitcher: document.getElementById('view-switcher'),
        repoListContainer: document.getElementById('repo-list-container'),
        userMenu: document.querySelector('.dropdown-container'),
        repoDetailsPanel: document.getElementById('repo-details'),
        menuToggleButton: document.getElementById('menu-toggle-button'),
        overlay: document.getElementById('overlay'),
    };

    // --- 辅助工具函数 ---

    const _debounce = (func, delay = 300) => {
        let timeoutId;
        return (...args) => {
            clearTimeout(timeoutId);
            timeoutId = setTimeout(() => func.apply(this, args), delay);
        };
    };

    /**
     * 初始化排序功能，为指定列表提供拖拽排序能力
     * @param {string} listElementId - 目标列表元素的ID
     * @param {string} dataAttribute - 数据属性名
     * @param {Function} apiCallback - 排序更新后的API回调函数
     */

    const initSortable = (listElementId, dataAttribute, apiCallback) => {
        // 在重新初始化之前，先销毁旧的 Sortable 实例
        if (listElementId === 'tags-list' && tagsSortable) {
            tagsSortable.destroy();
        }
        if (listElementId === 'languages-list' && languagesSortable) {
            languagesSortable.destroy();
        }

        const listElement = document.getElementById(listElementId);
        if (!listElement) return;

        // 创建新的 Sortable 实例并保存引用
        const newSortableInstance = new Sortable(listElement, {
            animation: 150,
            ghostClass: 'sortable-ghost',
            dataIdAttr: dataAttribute,
            delay: 150, // 设置适中的延迟，平衡响应性和精准性
            delayOnTouchStart: true, // 仅在触摸设备上应用延迟
            touchStartThreshold: 8, // 减少拖拽抗动容忍度，提升操作精确性
            forceFallback: false, // 在支持的浏览器上优先使用原生拖拽
            fallbackTolerance: 5, // 拖拽开始前的容忍像素
            onStart: (evt) => {},

            onEnd: async (evt) => {
                const newOrder = newSortableInstance.toArray(); // 从当前实例获取最新排序
                if (dataAttribute === 'data-tag') {
                    state.metadata.tags = newOrder;
                } else if (dataAttribute === 'data-language') {
                    state.metadata.languages = newOrder;
                }
                try {
                    await apiCallback(newOrder);
                    ui.showToast(i18n.t('toasts.saveOrderSuccess'), 'success');
                } catch (error) {
                    console.error('Failed to save order:', error);
                    ui.showToast(
                        i18n.t('toasts.saveOrderError'),
                        'error'
                    );
                    app.refresh();
                }
            }
        });

        if (listElementId === 'tags-list') {
            tagsSortable = newSortableInstance;
        }
        if (listElementId === 'languages-list') {
            languagesSortable = newSortableInstance;
        }
    };

    /**
     * 计算筛选器的计数信息，为侧边栏的显示提供数据基础
     * @returns {Object} 包含各类型筛选器及其对应计数的对象
     */
    const _calculateCounts = () => {
        const counts = { all: state.allRepos.length, constellation: 0, untagged: 0, tags: {}, languages: {} };
        // 遍历所有仓库，精确计算各类筛选器（“特别关注”、“未分类”、各标签和语言）的计数。
        // '_favorite' 是一个特殊的内部标签，用于标记“特别关注”的仓库 (constellation)。
        // “未分类” (untagged) 指的是除了 '_favorite' 外没有其他任何标签的仓库。
        for (const repo of state.allRepos) {
            const isFavorite = repo.tags.includes('_favorite');
            const hasOtherTags = repo.tags.some(t => t !== '_favorite');
            if (isFavorite) counts.constellation++;
            if (!hasOtherTags) counts.untagged++;
            repo.tags.forEach(tag => {
                if (tag !== '_favorite') {
                    counts.tags[tag] = (counts.tags[tag] || 0) + 1;
                }
            });
            if (repo.language) counts.languages[repo.language] = (counts.languages[repo.language] || 0) + 1;
        }
        return counts;
    };

    /**
     * 按照筛选条件和排序规则处理仓库数据，并更新对应的显示视图
     * 支持系统筛选、标签筛选、语言筛选、全文搜索以及多维度排序
     */
    const _filterAndSortRepos = () => {
        let result = [...state.allRepos];
        const filterType = state.activeFilter.type;
        const filterValue = state.activeFilter.value;
        if (filterType === 'system') {
            if (filterValue === 'constellation') {
                result = result.filter(r => r.tags.includes('_favorite'));
            } else if (filterValue === 'untagged') {
                result = result.filter(r => !r.tags.some(t => t !== '_favorite'));
            }
        } else if (filterType === 'tag') {
            result = result.filter(r => r.tags.includes(filterValue));
        } else if (filterType === 'language') {
            result = result.filter(r => r.language === filterValue);
        }

        // 当存在搜索查询时，使用 Fuse.js 进行模糊搜索，并禁用默认排序，
        // 因为 Fuse.js 的结果已按相关性排序。
        const query = state.searchQuery.toLowerCase().trim();
        if (query) {
            const fuseOptions = {
                keys: [
                    { name: 'name', weight: 0.4 },
                    { name: 'alias', weight: 0.4 },
                    { name: 'full_name', weight: 0.3 },
                    { name: 'ai_summary', weight: 0.25 },  // 新增：AI 总结
                    { name: 'description', weight: 0.2 },
                    { name: 'notes', weight: 0.2 },
                    { name: 'language', weight: 0.1 },
                    { name: 'tags', weight: 0.1 }
                ],
                threshold: 0.4,
                ignoreLocation: true,
            };
            const fuse = new Fuse(result, fuseOptions);
            result = fuse.search(query).map(res => res.item);
        }

        if (!query) {
            const sortBy = state.activeSort;
            if (sortBy === 'name') {
                result.sort((a, b) => a.name.localeCompare(b.name));
            } else if (sortBy === 'stargazers_count') {
                result.sort((a, b) => b.stargazers_count - a.stargazers_count);
            } else {
                result.sort((a, b) => new Date(b[sortBy]) - new Date(a[sortBy]));
            }
        }

        state.filteredRepos = result;
    
        if (state.currentView === 'card') {
            ui.renderAllCards(state.filteredRepos);
        } else {
            if (virtualScroller) virtualScroller.setData(state.filteredRepos);
        }
    };

    const _rerender = (options = {}) => {
        const { onlyUpdateDetails = false } = options;

        if (!onlyUpdateDetails) {
            const counts = _calculateCounts();
            ui.renderSidebar(counts, state.metadata.tags, state.metadata.languages, state.activeFilter);
            
            // 在侧边栏 DOM 更新后，重新初始化 SortableJS
            initSortable('tags-list', 'data-tag', api.updateTagsOrder);
            initSortable('languages-list', 'data-language', api.updateLanguagesOrder);

            _filterAndSortRepos();
        }

        if (state.isDetailsPanelOpen && state.selectedRepoId) {
            const repo = state.allRepos.find(r => r.id === state.selectedRepoId);
            if (repo) {
                const allKnownTags = state.metadata.tags.filter(t => t !== '_favorite');
                ui.toggleRepoDetails(repo, {
                    onSave: handleUpdateRepo,
                    onTagsChange: handleTagsChange,
                    allKnownTags
                });
            } else {
                ui.toggleRepoDetails(null);
                Object.assign(state, { isDetailsPanelOpen: false, selectedRepoId: null });
            }
        } else {
            ui.toggleRepoDetails(null);
        }
    };

    const setState = (partialState) => {
        /**
         * 统一的状态更新函数，封装了状态变更和UI重绘。
         * 内置优化：当仅变更与详情面板相关的状态时，会跳过大部分UI的重绘，
         * 只更新详情面板本身，以提高性能。
         * @param {Object} partialState - 需要合并到主状态的部分状态对象。
         */
        const oldDetailsState = {
            isDetailsPanelOpen: state.isDetailsPanelOpen,
            selectedRepoId: state.selectedRepoId
        };
        const keys = Object.keys(partialState);
        const onlyDetailsChanged = keys.every(key => key === 'isDetailsPanelOpen' || key === 'selectedRepoId') && keys.length > 0;

        Object.assign(state, partialState);
        
        if (onlyDetailsChanged) {
            _rerender({ onlyUpdateDetails: true });
        } else {
            _rerender();
        }
    };

    // --- 业务逻辑处理器 ---

    const handleUpdateRepo = async (repoId, field, value) => {
        const repoIndex = state.allRepos.findIndex(r => r.id === repoId);
        if (repoIndex === -1) return;
        const originalRepo = JSON.parse(JSON.stringify(state.allRepos[repoIndex]));
        let originalTags;
        if (field === 'tags') originalTags = [...state.metadata.tags];
        state.allRepos[repoIndex][field] = value;
        
        const onlyUpdateDetails = (field !== 'tags');
        _rerender({ onlyUpdateDetails });

        // 采用乐观更新策略：先修改本地状态并立即重绘UI，然后发送API请求。
        // 如果API请求失败，则回滚状态到原始值并再次重绘，确保UI与后端数据最终一致。
        try {
            const updatedRepo = await api.updateRepo(repoId, { [field]: value });
            state.allRepos[repoIndex] = updatedRepo;
            if (field === 'tags') {
                const newTags = new Set(state.metadata.tags);
                updatedRepo.tags.forEach(tag => newTags.add(tag));
                if (state.metadata.tags.length !== newTags.size) {
                    state.metadata.tags = Array.from(newTags);
                    _rerender();
                }
            }
            ui.showToast(i18n.t('toasts.updateSuccess'), 'success');
        } catch (error) {
            console.error('Failed to update repo:', error);
            state.allRepos[repoIndex] = originalRepo;
            if (field === 'tags' && originalTags) state.metadata.tags = originalTags;
            _rerender();
            ui.showToast(
                i18n.t('toasts.updateError', { error: error.data?.message_zh || i18n.t('toasts.errors.network') }),
                'error'
            );
        }
    };

    /**
     * 切换仓库的收藏状态
     * @param {number} repoId - 仓库ID
     */
    const handleToggleFavorite = (repoId) => {
        const repo = state.allRepos.find(r => r.id === repoId);
        if (!repo) return;

        const isFavorite = repo.tags.includes('_favorite');
        const newTags = isFavorite
            ? repo.tags.filter(t => t !== '_favorite')
            : [...repo.tags, '_favorite'];
        handleUpdateRepo(repoId, 'tags', newTags);
    };

    /**
     * 处理仓库的标签变更，同时保持收藏状态不变
     * @param {number} repoId - 仓库ID
     * @param {string[]} newTags - 新的标签数组
     */
    const handleTagsChange = (repoId, newTags) => {
        const repo = state.allRepos.find(r => r.id === repoId);
        if (!repo) return;

        const isFavorite = repo.tags.includes('_favorite');
        const newFullTags = isFavorite
            ? [...new Set(['_favorite', ...newTags])]
            : newTags;
        handleUpdateRepo(repoId, 'tags', newFullTags);
    };

    const handleOpenSettings = async () => {
        try {
            ui.setGlobalLoading(true);
            const settings = await api.getSettings();
            state.settings = settings;
            ui.showSettingsView(settings, handleSaveSettings);
        } catch (error) {
            console.error("Failed to get settings:", error);
            ui.showToast(
                i18n.t('toasts.settingsGetError', { error: error.data?.message_zh || i18n.t('toasts.errors.networkShort') }),
                'error'
            );
        } finally {
            ui.setGlobalLoading(false);
        }
    };

    const handleSaveSettings = async (settingsData) => {
        const oldLang = state.settings.ui_language;
        const newLang = settingsData.ui_language;
        const languageChanged = oldLang !== newLang && oldLang !== undefined;

        try {
            ui.setGlobalLoading(true);
            const result = await api.updateSettings(settingsData);
            state.settings = result;

            if (languageChanged) {
                localStorage.setItem('stargazer-lang', newLang);
                location.reload();
                return; 
            }

            ui.hideSettingsView();
            ui.showToast(i18n.t('toasts.settingsSaveSuccess'), 'success');

            if (result.test_push_status) {
                if (result.test_push_status === 'success') {
                    ui.showToast(i18n.t('toasts.pushTestSuccess'), 'success', 5000);
                } else {
                    ui.showToast(
                        i18n.t('toasts.pushTestError', { error: result.test_push_error }),
                        'error',
                        10000
                    );
                }
            }

        } catch (error) {
            console.error("Failed to save settings:", error);
            ui.showToast(
                i18n.t('toasts.settingsSaveError', { error: error.data?.message_zh || i18n.t('toasts.errors.network') }),
                'error'
            );
        } finally {
            ui.setGlobalLoading(false);
        }
    };

    const handleDeleteTag = async (tagName) => {
        const counts = _calculateCounts();
        if ((counts.tags[tagName] || 0) > 0) {
            ui.showToast(
                i18n.t('toasts.deleteTagInUse', { tagName }),
                'error',
                5000
            );
            return;
        }
        ui.showConfirmationModal({
            title: i18n.t('modals.deleteTag.title', { tagName }),
            content: i18n.t('modals.deleteTag.content'),
            onConfirm: async () => {
                try {
                    ui.setGlobalLoading(true);
                    await api.deleteTag(tagName);
                    ui.showToast(i18n.t('toasts.deleteTagSuccess', { tagName }), 'success');
                    await app.refresh();
                } catch (error) {
                    console.error("Failed to delete tag:", error);
                    ui.showToast(
                        i18n.t('toasts.deleteTagError'),
                        'error'
                    );
                } finally {
                    ui.setGlobalLoading(false);
                }
            },
            confirmText: i18n.t('modals.deleteTag.confirm'),
            cancelText: i18n.t('modals.deleteTag.cancel')
        });
    };

    const handleAddNewTag = async (tagName) => {
        tagName = tagName.trim();
        if (!tagName) {
            ui.showToast(i18n.t('toasts.addTagEmpty'), 'info');
            return;
        }
        if (state.metadata.tags.some(t => t.toLowerCase() === tagName.toLowerCase())) {
            ui.showToast(i18n.t('toasts.addTagExists', { tagName }), 'error');
            return;
        }

        const newTagsOrder = [...state.metadata.tags, tagName];
        try {
            ui.setGlobalLoading(true);
            await api.updateTagsOrder(newTagsOrder);
            state.metadata.tags = newTagsOrder;
            _rerender();
            ui.showToast(i18n.t('toasts.addTagSuccess', { tagName }), 'success');
        } catch (error) {
            console.error("Failed to add new tag:", error);
            ui.showToast(
                i18n.t('toasts.addTagError'),
                'error'
            );
        } finally {
            ui.setGlobalLoading(false);
        }
    };

    const _smartSync = (isAutoSync = false) => {
        const initialMessage = isAutoSync ? i18n.t('toasts.sync.auto') : i18n.t('toasts.sync.manual');
        const workingToast = ui.showToast(initialMessage, 'info', 5000);

        const removeWorkingToast = () => {
            if (!workingToast) return;
            workingToast.classList.remove('show');
            workingToast.addEventListener('transitionend', () => workingToast.remove());
        };

        api.sync().then(stats => {
            removeWorkingToast();
            const successMessage = i18n.t('toasts.sync.success', { added: stats.added, updated: stats.updated, removed: stats.removed });
            ui.showToast(successMessage, 'success', 5000);
            if (stats.added > 0 || stats.removed > 0 || stats.updated > 0) {
                app.refresh();
            }
        }).catch(error => {
            removeWorkingToast();
            const errorMessage = i18n.t('toasts.sync.error', { error: error.data?.message_zh || i18n.t('toasts.errors.networkShort') });
            ui.showToast(errorMessage, 'error', 10000);
        });
    };

    /**
     * 手动触发同步
     */
    const handleManualSync = () => {
        _smartSync(false);
    };
    const handleLogout = () => {
        ui.showConfirmationModal({
            title: i18n.t('modals.logout.title'),
            content: i18n.t('modals.logout.content'),
            onConfirm: () => {
                window.location.href = '/auth/logout';
            }
        });
    };

    const _bindEventListeners = () => {
        /**
         * 绑定应用所需的所有DOM事件监听器。
         * 该函数只执行一次，通过 internal flag `_isBound` 防止重复绑定。
         * 涵盖了侧边栏、顶部工具栏、仓库列表和全局事件。
         */
        if (elements.sidebar._isBound) return;

        const toggleSidebar = () => {
            elements.sidebar.classList.toggle('is-open');
            elements.overlay.classList.toggle('is-active');
        };

        if (elements.menuToggleButton) {
            elements.menuToggleButton.addEventListener('click', (e) => {
                e.stopPropagation();
                toggleSidebar();
            });
        }
        if (elements.overlay) {
            elements.overlay.addEventListener('click', () => {
                if (elements.sidebar.classList.contains('is-open')) {
                    toggleSidebar();
                }
            });
        }

        let activeDeleteTimer = null;
        
        let touchStartTime = 0;
        let touchStartX = 0;
        let touchStartY = 0;
        const INTERACTION_THRESHOLDS = {
            CLICK_MAX_DURATION: 200,
            DRAG_MIN_DISTANCE: 10,
        };

        elements.sidebar.addEventListener('touchstart', (e) => {
            const touch = e.touches[0];
            touchStartTime = Date.now();
            touchStartX = touch.clientX;
            touchStartY = touch.clientY;
        }, { passive: true });

        elements.sidebar.addEventListener('touchend', (e) => {
            const touchEndTime = Date.now();
            const touchDuration = touchEndTime - touchStartTime;
            
            if (touchDuration < INTERACTION_THRESHOLDS.CLICK_MAX_DURATION) {
                return;
            }
        }, { passive: true });

        elements.sidebar.addEventListener('click', (e) => {
            const link = e.target.closest('a.group-item');
            const addBtn = e.target.closest('#add-tag-button');
            const deleteBtn = e.target.closest('.delete-tag-btn');

            if (window.innerWidth <= 768 && link && elements.sidebar.classList.contains('is-open')) {
                if (link.dataset.language || link.dataset.filter) {
                    setTimeout(() => {
                        if (elements.sidebar.classList.contains('is-open')) {
                            toggleSidebar();
                        }
                    }, 300);
                }
            }

            if (deleteBtn) {
                e.preventDefault();
                e.stopPropagation();
                handleDeleteTag(deleteBtn.dataset.tagName);
                return;
            }
            if (addBtn) {
                e.preventDefault();
                let cleanup;
                const onSave = (v) => {
                    if (cleanup) cleanup();
                    handleAddNewTag(v);
                };
                const onCancel = () => {
                    if (cleanup) cleanup();
                };
                cleanup = ui.showTagInput(onSave, onCancel);
                return;
            }
            if (link) {
                e.preventDefault();

                const isMobileTagClick = window.innerWidth <= 768 && link.dataset.tag;

                const { filter, tag, language } = link.dataset;
                let newFilter;
                if (filter) {
                    newFilter = { type: 'system', value: filter };
                } else if (tag) {
                    newFilter = { type: 'tag', value: tag };
                } else if (language) {
                    newFilter = { type: 'language', value: language };
                }
                
                if (newFilter) {
                    // 关键交互：为了在移动端实现“长按（或非快速点击）标签后显示删除按钮”的效果，
                    // 这里采用了一个修复竞态条件的设计：
                    // 1. 立即调用 setState 更新过滤器，这会触发UI重绘。
                    // 2. 在UI重绘完成后 (通过将后续代码放在 setState 调用之后)，
                    //    在新的DOM结构中查找当前激活的标签项。
                    // 3. 对新找到的元素添加 'show-delete' class，并启动一个定时器来移除它。
                    // 这种方法确保了我们的DOM操作始终作用在最新的、正确的元素上。
                    setState({ activeFilter: newFilter });

                    if (isMobileTagClick) {
                        if (activeDeleteTimer) {
                            clearTimeout(activeDeleteTimer.timerId);
                            activeDeleteTimer = null; 
                        }

                        const newActiveLink = document.querySelector(`a.group-item.is-active[data-tag="${newFilter.value}"]`);
                        if (newActiveLink) {
                            const rightContent = newActiveLink.querySelector('.filter-right-content');
                            if (rightContent) {
                                rightContent.classList.add('show-delete');
                                const timerId = setTimeout(() => {
                                    rightContent.classList.remove('show-delete');
                                    activeDeleteTimer = null;
                                }, 1500);
                                activeDeleteTimer = { element: rightContent, timerId };
                            }
                        }
                    }
                }
            }
        });


        elements.searchBox.addEventListener('input', _debounce((e) => {
            setState({ searchQuery: e.target.value });
        }, 300));

        elements.viewSwitcher.addEventListener('click', (e) => {
            const button = e.target.closest('button');
            if (!button || button.classList.contains('active')) return;

            const scrollContainer = document.getElementById('virtual-scroll-container');
            if (scrollContainer) {
                scrollContainer.scrollTop = 0;
            }

            elements.viewSwitcher.querySelector('.active').classList.remove('active');
            button.classList.add('active');
            ui.updateViewSwitcher();

            const newView = button.dataset.view;
            state.currentView = newView;
            ui.switchRepoView(newView);
            
            if (virtualScroller) {
                virtualScroller.destroy();
                virtualScroller = null;
            }

            if (newView === 'list') {
                virtualScroller = ui.initVirtualScroller();
                virtualScroller.updateItemHeight();
            }

            _filterAndSortRepos();
        });

        if (elements.sortBySelect) {
            const sortByDisplay = document.getElementById('sort-selector-display');

            elements.sortBySelect.addEventListener('change', (e) => {
                const selectElement = e.target;
                const selectedOption = selectElement.options[selectElement.selectedIndex];
                const translationKey = selectedOption.dataset.i18n;
                const newActiveValue = e.target.value;

                if (sortByDisplay && translationKey) {
                    sortByDisplay.textContent = i18n.t(translationKey);
                }
                setState({ activeSort: newActiveValue });
                ui.updateMobileSortActiveState(newActiveValue);
            });

            const initialSelectedOption = elements.sortBySelect.querySelector(`option[value="${state.activeSort}"]`);
            if (sortByDisplay && initialSelectedOption && initialSelectedOption.dataset.i18n) {
                sortByDisplay.textContent = i18n.t(initialSelectedOption.dataset.i18n);
            }
        }

        const mobileSortContainer = document.getElementById('mobile-sort-container');
        if (mobileSortContainer) {
            const mobileSortButton = document.getElementById('mobile-sort-button');
            const mobileSortOptions = document.getElementById('mobile-sort-options');

            mobileSortButton.addEventListener('click', (e) => {
                e.stopPropagation(); // 阻止事件冒泡，防止触发全局点击事件而立即关闭
                mobileSortOptions.classList.toggle('is-open');
            });

            mobileSortOptions.addEventListener('click', (e) => {
                const link = e.target.closest('a');
                if (!link) return;
                e.preventDefault();

                const newValue = link.dataset.value;
                const translationKey = link.dataset.i18n;

                setState({ activeSort: newValue });
                elements.sortBySelect.value = newValue;
                const sortByDisplay = document.getElementById('sort-selector-display');
                if (sortByDisplay && translationKey) {
                    sortByDisplay.textContent = i18n.t(translationKey);
                }
                ui.updateMobileSortActiveState(newValue);
                
                mobileSortOptions.classList.remove('is-open');
            });
        }


        elements.repoListContainer.addEventListener('click', (e) => {
            const repoItem = e.target.closest('.repo-item');
            if (!repoItem) return;

            const repoId = parseInt(repoItem.dataset.repoId, 10);
            if (state.selectedRepoId === repoId && state.isDetailsPanelOpen) {
                ui.toggleRepoDetails(null);
                setState({ isDetailsPanelOpen: false, selectedRepoId: null });
            } else {
                const repo = state.allRepos.find(r => r.id === repoId);
                if (repo) {
                    const allKnownTags = state.metadata.tags.filter(t => t !== '_favorite');
                    ui.toggleRepoDetails(repo, {
                        onSave: handleUpdateRepo,
                        onTagsChange: handleTagsChange,
                        allKnownTags
                    });
                    setState({ selectedRepoId: repoId, isDetailsPanelOpen: true });
                }
            }
        });

        elements.repoDetailsPanel.addEventListener('click', (e) => {
            const favoriteBtn = e.target.closest('#details-favorite-btn');
            const aliasContainer = e.target.closest('.editable-container[data-field="alias"]');

            if (favoriteBtn) {
                const icon = favoriteBtn.querySelector('i');
                if (icon) {
                    icon.classList.add('heart-animate');
                    icon.addEventListener('animationend', () => icon.classList.remove('heart-animate'), { once: true });
                }
                handleToggleFavorite(state.selectedRepoId);
            }
        });

        elements.userMenu.addEventListener('click', (e) => {
            const targetElement = e.target.closest('a');
            if (!targetElement) return;

            const targetId = targetElement.id;
            if (targetId === 'settings-button' || targetId === 'manual-sync-button' || targetId === 'logout-button') {
                e.preventDefault();
                switch (targetId) {
                    case 'settings-button':
                        handleOpenSettings();
                        break;
                    case 'manual-sync-button':
                        handleManualSync();
                        break;
                    case 'logout-button':
                        handleLogout();
                        break;
                }
            }
        });


        document.addEventListener('click', (e) => {
            const userMenuDetails = elements.userMenu;
            if (userMenuDetails?.hasAttribute('open') && !userMenuDetails.contains(e.target) && !e.target.closest('summary')) {
                userMenuDetails.removeAttribute('open');
            }

            const mobileSortContainer = document.getElementById('mobile-sort-container');
            const isClickInsideSortMenu = mobileSortContainer?.contains(e.target);
            const mobileSortOptions = document.getElementById('mobile-sort-options');

            if (mobileSortOptions?.classList.contains('is-open') && !isClickInsideSortMenu) {
                mobileSortOptions.classList.remove('is-open');
            }
            
            const isClickInsideVditorPopup = e.target.closest('.vditor-panel, .vditor-menu, .vditor-dropdown');

            if (state.isDetailsPanelOpen && !e.target.closest('#repo-details') && !e.target.closest('.repo-item') && !isClickInsideVditorPopup) {
                ui.toggleRepoDetails(null);
                setState({ isDetailsPanelOpen: false, selectedRepoId: null });
            }
        });

        window.addEventListener('resize', _debounce(() => {
            if (virtualScroller && state.currentView === 'list') {
                virtualScroller.updateItemHeight();
            }
        }, 200));

        document.addEventListener('detailsPanelClosed', (e) => {
            if (e.detail && e.detail.source === 'swipe') {
                setState({ isDetailsPanelOpen: false, selectedRepoId: null });
            }
        });

        elements.sidebar._isBound = true;
    };

    /**
     * 初始化应用，包括用户认证、数据获取、事件绑定等
     */
    return {
        checkForUpdates: async () => {
            try {
                const data = await api.checkForUpdates();
                if (data && data.has_update) {
                    const message = i18n.t('toasts.updateNotification', { latestVersion: data.latest_version });
                    ui.showToast(message, 'success', 5000);
                }
            } catch (error) {
                console.error('Version check failed:', error);
            }
        },

        async init() {
            console.log('StarGazer App is initializing...');
            const transitionOverlay = document.getElementById('transition-overlay');
            const body = document.body;

            try {
                const user = await api.getMe();
                setState({ isLoggedIn: true, user: user });

                if (transitionOverlay) {
                    const transitionText = transitionOverlay.querySelector('.transition-text');

                    transitionText.addEventListener('animationend', () => {
                        transitionOverlay.classList.remove('is-active');
                        transitionOverlay.style.display = 'none';
                        
                        ui.showView('app-view'); 

                        requestAnimationFrame(() => {
                            ui.updateViewSwitcher();
                        });

                    }, { once: true });

                    transitionOverlay.style.display = 'flex';
                    transitionOverlay.classList.add('is-active');

                    setTimeout(() => {
                        body.classList.remove('app-loading');
                    }, 100);

                } else {
                    ui.showView('app-view');
                    requestAnimationFrame(() => {
                        ui.updateViewSwitcher();
                    });
                }

                const savedLang = localStorage.getItem('stargazer-lang') || document.documentElement.lang.split('-')[0] || 'zh';
                await i18n.init(savedLang);

                const [starsResponse, settings] = await Promise.all([
                    api.getStars(),
                    api.getSettings()
                ]);

                ui.renderUserProfile(user);
                setState({
                    allRepos: starsResponse.stars,
                    metadata: starsResponse.metadata,
                    settings: settings
                });

                virtualScroller = ui.initVirtualScroller();
                if (virtualScroller) {
                    virtualScroller.updateItemHeight();
                }
                
                _bindEventListeners();
                ui.initMobileSorter(state.activeSort);
                _rerender();

                app.checkForUpdates();

                // 应用启动时执行一次智能同步检查。
                // 业务规则：如果自上次成功同步以来已超过2小时，则在后台自动触发一次同步，
                // 以确保用户在长时间未访问后仍能看到相对较新的数据。
                // 如果从未同步过（例如首次启动或后端服务重启），也会触发一次。
                try {
                    const lastSyncTimestamp = await api.getLastSuccessfulSync();
                    if (lastSyncTimestamp) {
                        const now = new Date();
                        const lastSyncDate = new Date(lastSyncTimestamp);
                        const hoursSinceLastSync = (now - lastSyncDate) / (1000 * 60 * 60);

                        if (hoursSinceLastSync > 2) {
                            console.log('超过2小时未同步，触发自动同步。');
                            _smartSync(true); 
                        }
                    } else {
                        console.log('未找到上次同步时间，首次触发自动同步。');
                        _smartSync(true);
                    }
                } catch (error) {
                    console.error('检查自动同步条件时出错:', error);
                }

            } catch (error) {
                console.log("User not logged in or initialization failed:", error);
                if (error?.status === 401) {
                    setState({ isLoggedIn: false });
                    ui.showView('login-view');
                } else {
                    ui.showToast(
                        i18n.t('toasts.initError', { error: error.data?.message_zh || i18n.t('toasts.errors.unknownNetwork') }),
                        'error',
                        0
                    );
                }
            } finally {
                setState({ isLoading: false });
                ui.setGlobalLoading(false);
                if (body.classList.contains('app-loading') && !state.isLoggedIn) {
                    body.classList.remove('app-loading');
                }
            }
        },

        async refresh() {
            ui.setGlobalLoading(true);
            try {
                const starsResponse = await api.getStars();
                setState({
                    allRepos: starsResponse.stars,
                    metadata: starsResponse.metadata
                });
            } catch (error) {
                console.error("Failed to refresh data:", error);
                ui.showToast(i18n.t('toasts.refreshError'), 'error');
            } finally {
                ui.setGlobalLoading(false);
            }
        },

        // AI 分析相关函数
        async handleSummarizeAll() {
            ui.showConfirmationModal({
                title: i18n.t('modals.summary.title'),
                content: i18n.t('modals.summary.content'),
                onConfirm: async () => {
                    try {
                        const result = await api.startSummary('all');
                        if (result.total === 0) {
                            ui.showToast(i18n.t('toasts.summary.noRepos'), 'info');
                        } else {
                            ui.showToast(i18n.t('toasts.summary.started', { total: result.total }), 'success');
                        }
                    } catch (error) {
                        console.error('启动分析失败:', error);
                        ui.showToast(
                            i18n.t('toasts.summary.error', { error: error.data?.message_zh || i18n.t('toasts.errors.network') }),
                            'error'
                        );
                    }
                },
                confirmText: i18n.t('modals.summary.confirm'),
                cancelText: i18n.t('modals.summary.cancel')
            });
        },

        async handleSummarizeUnanalyzed() {
            try {
                const result = await api.startSummary('unanalyzed');
                if (result.total === 0) {
                    ui.showToast(i18n.t('toasts.summary.noRepos'), 'info');
                } else {
                    ui.showToast(i18n.t('toasts.summary.started', { total: result.total }), 'success');
                }
            } catch (error) {
                console.error('启动总结失败:', error);
                ui.showToast(
                    i18n.t('toasts.summary.error', { error: error.data?.message_zh || i18n.t('toasts.errors.network') }),
                    'error'
                );
            }
        }
    }; 
})();

document.addEventListener('DOMContentLoaded', () => {
    app.init();
});
