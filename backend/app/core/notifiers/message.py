"""
推送消息生成器。
负责根据用户的语言偏好，从本地化的模板文件生成通知消息。
在应用启动时缓存所有语言模板，以避免频繁的文件 I/O 操作。
"""
import json
import logging
from pathlib import Path
from typing import Tuple, Dict, Any
from datetime import datetime

from app.models import Repo

logger = logging.getLogger(__name__)

# 全局模板缓存
# 定义模板文件所在的目录路径
_LOCALES_PATH = Path(__file__).parent.parent.parent / "locales"
# 定义一个字典，在应用启动时缓存所有加载的语言模板，避免频繁的磁盘 I/O
_TEMPLATES_CACHE: Dict[str, Dict[str, Any]] = {}


def _load_templates():
    """
    模块首次加载时扫描 locales 目录，将所有 .json 模板文件加载到内存缓存中。
    """
    if not _LOCALES_PATH.is_dir():
        logger.warning(f"Locales directory not found at: {_LOCALES_PATH}")
        return
        
    logger.info(f"Loading notification templates from: {_LOCALES_PATH}")
    for lang_file in _LOCALES_PATH.glob("*.json"):
        lang_code = lang_file.stem  
        try:
            with open(lang_file, "r", encoding="utf-8") as f:
                _TEMPLATES_CACHE[lang_code] = json.load(f)
                logger.info(f"Successfully loaded '{lang_code}' templates.")
        except (IOError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load or parse locale file {lang_file}: {e}")

# 在 Python 模块被导入时，立即执行一次模板加载函数
_load_templates()


def create_notification_message(repo: Repo, lang: str = "en") -> Tuple[str, str]:
    """
    根据指定语言，为更新的仓库生成本地化的通知消息。
    参数:
        repo: 发生了实质性更新的 Repo 对象。
        lang: 目标语言代码 (例如 'zh', 'en')。
    返回:
        一个元组 (title, content)，包含了最终的通知标题和内容。
    """
    
    # 将仓库的 pushed_at UTC 时间转换为本地时间并格式化
    try:
        pushed_at_str = repo.pushed_at
        # 兼容 ISO 8601 格式，包括带 'Z' 和不带 'Z' 的情况
        if pushed_at_str and pushed_at_str.endswith('Z'):
            pushed_at_utc = datetime.fromisoformat(pushed_at_str[:-1] + '+00:00')
        else:
            pushed_at_utc = datetime.fromisoformat(pushed_at_str)

        pushed_at_local = pushed_at_utc.astimezone() # 转换为当前系统的本地时区
        formatted_pushed_at = pushed_at_local.strftime('%Y-%m-%d %H:%M:%S %Z')
    except (ValueError, TypeError, AttributeError):
        # 如果解析失败，则使用原始字符串或 "N/A" 作为备用
        formatted_pushed_at = repo.pushed_at or "N/A"

    # 准备用于模板替换的变量字典
    replacements = {
        "repo_name": repo.name,
        "repo_full_name": repo.full_name,
        "repo_description": repo.description or "N/A", # 提供备用值
        "stargazers_count": repo.stargazers_count,
        "pushed_at": formatted_pushed_at,
        "repo_html_url": repo.html_url,
    }
    
    # --- 模板选择与填充 ---
    # 1. 从缓存中获取对应语言的模板。如果指定语言不存在，则回退到中文 ('zh')
    # 2. 如果连 'zh' 都不存在，则回退到一个空字典，以防止程序崩溃
    lang_templates = _TEMPLATES_CACHE.get(lang, _TEMPLATES_CACHE.get("zh", {}))
    
    # 3. 从语言模板中获取 'notification' 部分
    notification_templates = lang_templates.get("notification", {})

    # 4. 获取标题和内容模板，并提供硬编码的备用值，以确保函数总能返回有效的字符串
    title_template = notification_templates.get("title", "Update for {repo_name}")
    content_template = notification_templates.get("content", "A repository you starred has been updated.")

    # 5. 使用 format 方法填充模板
    title = title_template.format(**replacements)
    content = content_template.format(**replacements)

    return title, content
