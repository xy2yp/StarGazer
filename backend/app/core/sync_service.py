"""
核心同步服务逻辑。
负责执行从 GitHub 到本地数据库的数据同步流程。
包括获取远程数据、与本地数据进行比对、准备数据库操作（增、删、改）。
"""
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from sqlmodel import Session, select, delete

from app.models import Repo
from app.core.github import GitHubApiClient
from app.exceptions import ApiException
from fastapi import status

logger = logging.getLogger(__name__)

# 在内存中存储上次成功同步的时间戳
LAST_SUCCESSFUL_SYNC_AT: Optional[datetime] = None

def _diff_and_prepare_operations(
    github_repos_data: List[Dict],
    db_repos: List[Repo]
) -> Tuple[List[Dict], List[Repo], List[int], List[Repo]]:
    """
    比对 GitHub 数据和本地数据，生成数据库操作指令。
    参数:
        github_repos_data: 从 GitHub API 获取的仓库数据列表。
        db_repos: 从本地数据库查询出的仓库对象列表。
    返回:
        一个元组，包含:
        - to_add (List[Dict]): 需要新增的仓库的数据字典列表。
        - to_update (List[Repo]): 需要更新的所有仓库对象列表。
        - to_remove_ids (List[int]): 需要删除的仓库 ID 列表。
        - substantive_updated_repos (List[Repo]): 发生了实质性更新的仓库对象列表，用于发送通知。
    """
    logger.info("Starting diff calculation...")

    # 将列表转换为以 repo.id 为键的字典，以提高查找效率
    github_repos_map = {repo['id']: repo for repo in github_repos_data}
    db_repos_map = {repo.id: repo for repo in db_repos}

    # 提取两边的 ID 集合，用于快速计算差集
    github_ids = set(github_repos_map.keys())
    db_ids = set(db_repos_map.keys())

    add_ids = github_ids - db_ids
    remove_ids = db_ids - github_ids
    common_ids = github_ids.intersection(db_ids)

    # 准备新增和删除列表
    to_add = [github_repos_map[id] for id in add_ids]
    to_remove_ids = list(remove_ids)
    
    to_update: List[Repo] = []
    substantive_updated_repos: List[Repo] = []

    # 定义“实质性更新”字段，这些字段的变化会触发通知
    substantive_fields = ['name', 'full_name', 'description', 'language', 'html_url', 'pushed_at']

    # 遍历共同的仓库，检查更新
    for repo_id in common_ids:
        github_repo = github_repos_map[repo_id]
        db_repo = db_repos_map[repo_id]
        
        has_substantive_update = False
        # 检查实质性字段是否有变化
        for field in substantive_fields:
            if getattr(db_repo, field) != github_repo.get(field):
                setattr(db_repo, field, github_repo.get(field))
                has_substantive_update = True
        
        # Star 数只更新，不计入实质性更新
        if db_repo.stargazers_count != github_repo.get('stargazers_count'):
            db_repo.stargazers_count = github_repo.get('stargazers_count')

        # starred_at 时间只更新，不计入实质性更新
        if db_repo.starred_at != github_repo.get('starred_at'):
            db_repo.starred_at = github_repo.get('starred_at')
        
        if has_substantive_update:
            # 如果有实质性更新，加入到专门用于通知的列表
            substantive_updated_repos.append(db_repo)
        
        # 无论是否有实质性更新，都将其加入 to_update 列表，以确保 star 数等非实质性字段也被更新
        to_update.append(db_repo)

    logger.info(
        f"Diff complete. To add: {len(to_add)}, "
        f"To substantively update: {len(substantive_updated_repos)}, "
        f"To remove: {len(to_remove_ids)}."
    )
    
    return to_add, to_update, to_remove_ids, substantive_updated_repos

async def run_full_sync(session: Session, access_token: str) -> Tuple[Dict[str, int], List[Repo]]:
    """
    执行一次完整的从 GitHub 到本地数据库的数据同步。
    参数:
        session: 数据库会话对象。
        access_token: 用于认证的 GitHub access token。
    返回:
        一个元组，包含:
        - stats (Dict): 同步操作的统计结果（新增、更新、删除的数量等）。
        - updated_repos (List[Repo]): 发生了实质性更新的仓库对象列表，用于后续发送通知。    
    异常:
        ApiException: 如果在同步过程中发生任何不可恢复的错误。
    """
    logger.info("Core sync service: Starting full sync process.")

    try:
        # 1. 从 GitHub 并发获取所有星标数据
        github_client = GitHubApiClient(token=access_token)
        github_repos_data = await github_client.get_all_starred_repos()

        # 2. 从本地数据库获取所有现有数据
        db_repos = session.exec(select(Repo)).all()

        # 3. 执行核心比对算法，获取操作指令和待通知列表
        to_add, to_update, to_remove_ids, updated_repos_for_notification = _diff_and_prepare_operations(
            github_repos_data=github_repos_data,
            db_repos=db_repos
        )
        
        # 4. 准备数据库操作（暂存更改，不提交）
        if to_remove_ids:
            delete_statement = delete(Repo).where(Repo.id.in_(to_remove_ids))
            session.exec(delete_statement)
        
        for repo_data in to_add:
            session.add(Repo.model_validate(repo_data))
            
        for repo in to_update:
            session.add(repo)
        
        # 5. 构建统计结果
        stats = {
            "added": len(to_add),
            "updated": len(updated_repos_for_notification),
            "removed": len(to_remove_ids),
            "total_from_github": len(github_repos_data)
        }
        
        # 6. 更新内存中的成功同步时间戳
        global LAST_SUCCESSFUL_SYNC_AT
        LAST_SUCCESSFUL_SYNC_AT = datetime.now()

        # 7. 返回统计结果和待通知列表
        return stats, updated_repos_for_notification

    except ApiException:
        # 如果是已知、已包装的 API 异常，直接重新抛出
        raise
    except Exception as e:
        # 捕获任何其他未知异常，并包装成标准的 ApiException
        logger.error(f"An unexpected error occurred in core sync service: {e}", exc_info=True)
        raise ApiException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="CORE_SYNC_UNEXPECTED_ERROR",
            message_zh="执行同步时发生未知内部错误",
            message_en="An unexpected internal error occurred during sync execution.",
        )
