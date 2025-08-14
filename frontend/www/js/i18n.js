/**
 * StarGazer I18n Module
 *
 * 职责: 初始化 i18next 库并提供翻译功能。
 * 这是一个简化的配置器，它依赖于 i18next.min.js 先被加载。
 */
const i18n = (() => {
    let isInitialized = false;

    /**
     * 初始化 i18next 实例
     * @param {string} lng - 初始语言 (e.g., 'zh' or 'en')
     */
    async function init(lng = 'zh') {
        if (isInitialized) {
            console.log('i18next is already initialized.');
            return;
        }
        if (!window.i18next) {
            console.error('i18next library is not loaded. Please check the script tag in index.html.');
            return;
        }

        try {
            // 手动获取语言包
            const [zh, en] = await Promise.all([
                fetch('locales/zh.json').then(res => res.json()),
                fetch('locales/en.json').then(res => res.json())
            ]);

            await window.i18next.init({
                lng: lng, // 默认语言
                fallbackLng: 'zh', // 如果找不到翻译，回退到中文
                debug: false, // 设为 true 可以在控制台看到调试信息
                resources: {
                    zh: { translation: zh },
                    en: { translation: en }
                },
                interpolation: {
                    escapeValue: false // not needed for react as it escapes by default
                }
            });
            isInitialized = true;
            console.log(`i18next initialized with language: ${lng}`);
        } catch (error) {
            console.error('Failed to initialize i18next:', error);
        }
    }

    /**
     * 翻译函数，是 i18next.t 的一个简单封装
     * @param {string} key - 翻译键
     * @param {object} options - 选项，如变量插值
     * @returns {string}
     */
    function t(key, options) {
        if (!isInitialized) {
            // 在初始化完成前，返回键本身，避免报错
            return key;
        }
        return window.i18next.t(key, options);
    }
    
    /**
     * 切换语言，并触发页面重载。
     * @param {string} lng - 新语言
     */
    async function changeLanguage(lng) {
        if (!isInitialized) {
            console.error("i18n not initialized, can't change language.");
            return;
        }
        await window.i18next.changeLanguage(lng);
        console.log(`Language changed to ${lng}.`);
        // 在 main.js 中调用此函数后，执行 location.reload() 来完全应用语言变化。
    }

    return {
        init,
        t,
        changeLanguage
    };
})();
