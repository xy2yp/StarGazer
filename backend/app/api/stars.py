"""
处理与 Stars 数据相关的 API 端点。
提供获取星标仓库、同步 GitHub 数据、更新仓库信息等功能。
包括从本地数据库查询数据并生成筛选元数据，以及管理数据同步的完整流程。
"""
import logging
from typing import List, Set, Dict, Any, Optional
from fastapi import APIRouter, Depends, status
from sqlmodel import Session, select, SQLModel

from app.db import get_session
from app.models import Repo, AppSettings
from app.core import settings_service
from app.schemas import StarsResponse, RepoResponse, SyncResponse, RepoUpdateRequest
from app.exceptions import ApiException
from app.api.dependencies import get_token_from_cookie
from app.api.users import get_current_github_user 
from datetime import datetime
import app.core.sync_service as sync_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/stars",
    tags=["Stars"],
)


@router.get("/last-successful-sync", response_model=Optional[datetime], summary="Get the timestamp of the last successful sync")
def get_last_successful_sync_timestamp():
    """
    获取在服务器内存中记录的上次成功同步的时间戳。
    如果服务器重启或从未成功同步过，将返回 null。
    """
    return sync_service.LAST_SUCCESSFUL_SYNC_AT

def _apply_custom_order(all_items: Set[str], order_list: List[str]) -> List[str]:
    """
    根据用户自定义的排序列表对所有项进行排序。    
    优先按照 order_list 中的顺序排列，剩余项目按字母顺序排列在最后。
    """
    # 按自定义顺序排列的项目
    ordered_items = [item for item in order_list if item in all_items]
    # 剩余项目按字母顺序排序
    remaining_items_set = all_items - set(ordered_items)
    remaining_items_sorted = sorted(list(remaining_items_set))
    return ordered_items + remaining_items_sorted

@router.get("", response_model=StarsResponse, summary="Get all starred repositories from local DB")
async def get_all_stars(
    session: Session = Depends(get_session),
    _github_user: dict = Depends(get_current_github_user) 
):
    """
    从本地数据库获取当前用户的所有星标仓库信息。    
    同时生成用于前端筛选的元数据（语言列表、标签列表），这些元数据会根据用户的自定义排序设置进行排序。
    """
    try:
        # 从数据库查询所有仓库记录
        statement = select(Repo)
        db_repos = session.exec(statement).all()

        # 聚合实际使用的编程语言
        actual_used_languages_set = set()
        for repo in db_repos:
            if repo.language:
                actual_used_languages_set.add(repo.language)

        # 聚合实际使用的标签（排除内部标签 '_favorite'）
        actual_used_tags_set = set()
        for repo in db_repos:
            if repo.tags:
                user_visible_tags = {tag for tag in repo.tags if tag != '_favorite'}
                actual_used_tags_set.update(user_visible_tags)

        # 获取用户的自定义排序设置
        app_settings = settings_service.get_app_settings(session)
        user_defined_tags_order = app_settings.tags_order
        user_defined_languages_order = app_settings.languages_order

        # 合并用户定义的排序和实际使用的项目
        all_relevant_tags_set = set(user_defined_tags_order)
        all_relevant_tags_set.update(actual_used_tags_set)
        
        all_relevant_languages_set = set(user_defined_languages_order)
        all_relevant_languages_set.update(actual_used_languages_set)

        # 应用自定义排序
        sorted_tags = _apply_custom_order(all_relevant_tags_set, user_defined_tags_order)
        sorted_languages = _apply_custom_order(all_relevant_languages_set, user_defined_languages_order)

        metadata = {
            "languages": sorted_languages,
            "tags": sorted_tags,
        }

        # 构建并返回响应
        stars_as_dicts = [repo.model_dump() for repo in db_repos]
        return StarsResponse(
            stars=[RepoResponse.model_validate(repo_dict) for repo_dict in stars_as_dicts],
            metadata=metadata
        )

    except Exception as e:
        logger.error(f"Failed to query stars from database: {e}", exc_info=True)
        raise ApiException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="DB_QUERY_FAILED",
            message_zh="查询数据库时发生未知错误",
            message_en="An unknown error occurred while querying the database",
        )

@router.post("/sync", response_model=SyncResponse, summary="Sync stars from GitHub to local DB")
async def sync_stars(
    session: Session = Depends(get_session),
    github_user: dict = Depends(get_current_github_user),
):
    """
    触发从 GitHub 同步星标仓库到本地数据库。
        调用核心同步服务执行完整的数据同步流程，包括获取最新的仓库信息、对比本地数据库、处理新增/更新/删除的仓库。
    """
    # 从数据库中获取 GitHub access token
    access_token = settings_service.get_access_token(session)
    
    if not access_token:
        raise ApiException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="AUTH_NO_SERVER_SESSION",
            message_zh="无法开始同步，因为服务器会话不存在",
            message_en="Cannot start sync because server session not found."
        )

    user_login = github_user.get("login")
    logger.info(f"API sync request received for user: {user_login}")

    try:
        # 调用核心同步服务执行数据同步，返回统计信息
        stats, _ = await sync_service.run_full_sync(session=session, access_token=access_token)
        
        # 同步成功后提交数据库事务
        session.commit()
        logger.info(f"API sync finished successfully for user: {user_login}. Stats: {stats}")
        
        return SyncResponse(**stats)

    except Exception as e:
        logger.error(f"API sync failed for user: {user_login}. Error: {e}", exc_info=True)
        
        # 发生错误时回滚数据库事务
        session.rollback()
        
        # 包装未知异常为标准的 ApiException
        if not isinstance(e, ApiException):
            raise ApiException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                code="API_SYNC_UNEXPECTED_ERROR",
                message_zh="处理同步请求时发生未知错误",
                message_en="An unexpected error occurred while processing the sync request.",
            )
        # 重新抛出已知的 ApiException
        raise e

@router.patch(
    "/{repo_id}",
    response_model=RepoResponse,
    summary="Update a starred repository's custom data"
)
async def update_repo_details(
    repo_id: int,
    repo_update: RepoUpdateRequest,
    session: Session = Depends(get_session),
    _token: str = Depends(get_token_from_cookie),
):
    """
    更新指定仓库的用户自定义信息。
    
    支持更新别名、备注、标签等用户可编辑的字段。
    使用 PATCH 语义，只更新请求中明确提供的字段。
    """
    # 从数据库获取要更新的仓库对象
    db_repo = session.get(Repo, repo_id)
    if not db_repo:
        raise ApiException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="REPO_NOT_FOUND",
            message_zh=f"ID 为 {repo_id} 的仓库不存在",
            message_en=f"Repository with id {repo_id} not found"
        )

    # 获取请求中明确设置的字段（exclude_unset=True 确保只获取有值的字段）
    update_data = repo_update.model_dump(exclude_unset=True)

    if not update_data:
        # 如果请求体为空，直接返回当前对象
        return db_repo

    # 更新指定的字段
    for key, value in update_data.items():
        setattr(db_repo, key, value)
    
    # 提交更改到数据库
    try:
        session.add(db_repo)
        session.commit()
        session.refresh(db_repo) # 刷新以获取最新状态
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to update repo {repo_id}: {e}", exc_info=True)
        raise ApiException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="REPO_UPDATE_FAILED",
            message_zh="更新仓库信息时发生数据库错误",
            message_en="Database error occurred while updating repository"
        )

    logger.info(f"Updated repo {repo_id} with data: {update_data.keys()}")
    
    return db_repo
