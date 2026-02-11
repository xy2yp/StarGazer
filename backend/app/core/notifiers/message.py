"""
推送消息生成器。
负责根据用户的语言偏好，从本地化的模板文件生成通知消息。
在应用启动时缓存所有语言模板，以避免频繁的文件 I/O 操作。
"""
import json
import logging
from pathlib import Path
from typing import Tuple, Dict, Any, Optional
from datetime import datetime

from app.models import Repo
from app.core.github import GitHubApiClient

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


def _get_notification_templates(lang: str) -> Dict[str, Any]:
    """获取指定语言的 notification 模板，回退到中文。"""
    lang_templates = _TEMPLATES_CACHE.get(lang, _TEMPLATES_CACHE.get("zh", {}))
    return lang_templates.get("notification", {})


def _format_pushed_at(pushed_at_str: Optional[str]) -> str:
    """将 pushed_at UTC 时间转换为本地时间并格式化。"""
    try:
        if pushed_at_str and pushed_at_str.endswith('Z'):
            pushed_at_utc = datetime.fromisoformat(pushed_at_str[:-1] + '+00:00')
        else:
            pushed_at_utc = datetime.fromisoformat(pushed_at_str)
        pushed_at_local = pushed_at_utc.astimezone()
        return pushed_at_local.strftime('%Y-%m-%d %H:%M')
    except (ValueError, TypeError, AttributeError):
        return pushed_at_str or "N/A"


async def create_notification_message(
    repo: Repo, lang: str = "en",
    github_token: Optional[str] = None,
    old_pushed_at: Optional[str] = None
) -> Tuple[str, str]:
    """
    根据指定语言，为更新的仓库生成本地化的通知消息。
    如果提供了 old_pushed_at 和 github_token，会尝试获取 commit 列表；
    获取失败时回退到仓库 description。

    参数:
        repo: 发生了实质性更新的 Repo 对象。
        lang: 目标语言代码 (例如 'zh', 'en')。
        github_token: GitHub access token，用于获取 commit 列表。
        old_pushed_at: 旧的 pushed_at 值，用于确定 commit 查询起点。
    返回:
        一个元组 (title, content)，包含了最终的通知标题和内容。
    """
    notification_templates = _get_notification_templates(lang)
    repo_update = notification_templates.get("repo_update", {})

    # 构建 commits_section
    commits_section = ""
    if old_pushed_at and github_token:
        github_client = GitHubApiClient(token=github_token)
        try:
            commits = await github_client.get_recent_commits(repo.full_name, since=old_pushed_at)
        finally:
            await github_client.client.aclose()

        if commits:
            header = repo_update.get("commits_header", "📝 Recent Updates")
            commit_lines = "\n".join(f"• {msg}" for msg in commits)
            commits_section = f"{header}\n\n{commit_lines}"

    # 获取失败或无 old_pushed_at 时回退到 description
    if not commits_section:
        header = repo_update.get("fallback_header", "📝 About")
        description = repo.description or "N/A"
        commits_section = f"{header}\n\n{description}"

    formatted_pushed_at = _format_pushed_at(repo.pushed_at)
    repo_link_text = repo_update.get("repo_link", "Repository")

    # 填充标题模板
    title_template = repo_update.get("title", "🌌 StarGazer {repo_name} Updated")
    title = title_template.format(repo_name=repo.name)

    # 填充内容模板
    content_template = repo_update.get(
        "content",
        "{commits_section}\n\n✨ {stargazers_count}  ⏱️ {pushed_at}\n🔗 [{repo_link}]({repo_html_url})"
    )
    content = content_template.format(
        commits_section=commits_section,
        stargazers_count=repo.stargazers_count,
        pushed_at=formatted_pushed_at,
        repo_link=repo_link_text,
        repo_html_url=repo.html_url,
    )

    return title, content


def create_ai_error_message(error_type: str, lang: str = "en") -> Tuple[str, str]:
    """
    根据错误类型和语言生成 AI 分析异常通知消息。

    参数:
        error_type: 错误类型枚举值，支持:
            config_missing / github_token_missing / api_key_invalid / github_token_invalid
        lang: 目标语言代码 (例如 'zh', 'en')。
    返回:
        一个元组 (title, content)，包含通知标题和内容。
    """
    notification_templates = _get_notification_templates(lang)
    ai_error = notification_templates.get("ai_error", {})

    title = ai_error.get("title", "🌌 StarGazer AI Analysis Error")

    reason = ai_error.get(f"{error_type}_reason", error_type)
    suggestion = ai_error.get(f"{error_type}_suggestion", "")

    content_template = ai_error.get("content", "⚠️ {reason}\n\n{suggestion}")
    content = content_template.format(reason=reason, suggestion=suggestion)

    return title, content
