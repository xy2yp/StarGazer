"""
处理与用户自定义标签（Tags）相关的业务逻辑。
提供全局删除标签的服务。
所有函数都只准备数据库更改，而不提交事务，将事务控制权交给上层的 API 路由。
"""
import logging
from sqlmodel import Session, select

from app.models import Repo, AppSettings
from app.core.settings_service import get_app_settings

logger = logging.getLogger(__name__)

def delete_tag_globally(session: Session, tag_name: str):
    """
    全局删除一个自定义标签。
    1. 从 AppSettings.tags_order (用户自定义的排序列表) 中移除该标签。
    2. 从所有已标记此标签的 Repo 记录中移除该标签。
    参数:
        session: 数据库会话对象。
        tag_name: 需要被全局删除的标签名称。
    """
    logger.info(f"Starting global deletion for tag: '{tag_name}'")

    # 步骤 1: 更新 AppSettings.tags_order
    settings = get_app_settings(session)
    if tag_name in settings.tags_order:
        logger.info(f"Removing '{tag_name}' from AppSettings.tags_order.")
        # 创建一个新的列表，其中不包含要删除的 tag_name
        new_order = [tag for tag in settings.tags_order if tag != tag_name]
        settings.tags_order = new_order
        session.add(settings)
    else:
        logger.warning(f"Tag '{tag_name}' not found in AppSettings.tags_order, skipping update to settings.")

    # 步骤 2: 更新所有包含该标签的 Repo.tags
    statement = select(Repo).where(Repo.tags.contains(tag_name))
    repos_to_update = session.exec(statement).all()

    if not repos_to_update:
        logger.info(f"No repos found containing the tag '{tag_name}'. No repositories need updating.")
        return # 如果没有仓库需要更新，可以提前结束
    logger.info(f"Found {len(repos_to_update)} repos to update. Removing tag '{tag_name}' from each.")

    # 遍历这些仓库，并从它们的 tags 列表中移除指定的 tag_name
    for repo in repos_to_update:
        if tag_name in repo.tags:
            # 创建一个新的列表以确保变更被 ORM 追踪
            updated_tags = [t for t in repo.tags if t != tag_name]
            repo.tags = updated_tags
            session.add(repo)
    
    logger.info(f"Global deletion for tag '{tag_name}' has been staged in the session. Awaiting commit.")
