"""
总结任务服务：负责批量总结仓库的核心逻辑
"""
import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from sqlmodel import Session, select

from app.models import Repo, AppSettings
from app.core.ai_service import AIService
from app.core.readme_service import get_readme_content
from app.core.notifiers.factory import create_notifier
from app.core.notifiers.message import create_ai_error_message
from app.core.security import decrypt_data
from app.exceptions import (
    InvalidApiKeyError, ApiEndpointError, NetworkTimeoutError,
    EmptyContentError, GitHubApiError, InvalidGitHubTokenError,
)
from app.db import engine

logger = logging.getLogger(__name__)


async def get_repos_to_summarize(
    mode: str,
    updated_repo_ids: Optional[List[int]] = None
) -> Tuple[List[Repo], Dict[int, Tuple[Optional[str], Optional[str]]]]:
    """
    筛选需要总结的仓库

    Args:
        mode: 总结模式
            - "auto": 自动模式（后台同步时触发）
            - "all": 总结所有仓库
            - "unanalyzed": 总结未总结的仓库（含失败可重试）
        updated_repo_ids: 有更新的仓库 ID 列表（仅 auto 模式使用）

    Returns:
        (repos, readme_cache): 需要总结的仓库列表，以及 auto 模式下预取的 README 缓存
            readme_cache 的 key 是 repo.id，value 是 (content, sha)
    """
    readme_cache: Dict[int, Tuple[Optional[str], Optional[str]]] = {}

    with Session(engine) as session:
        if mode == "all":
            repos = session.exec(select(Repo)).all()
            logger.info(f"模式：总结所有仓库，共 {len(repos)} 个")
            return list(repos), readme_cache

        elif mode == "unanalyzed":
            repos = session.exec(
                select(Repo).where(Repo.analyzed_at == None)
            ).all()
            logger.info(f"模式：总结未总结的仓库，共 {len(repos)} 个")
            return list(repos), readme_cache

        elif mode == "auto":
            repos_to_summarize = []

            # 1. 从未总结过的仓库
            never_analyzed = session.exec(
                select(Repo).where(Repo.analyzed_at == None)
            ).all()
            repos_to_summarize.extend(never_analyzed)
            logger.info(f"从未总结过的仓库：{len(never_analyzed)} 个")

            # 2. 有更新的仓库（检查 README 是否变化）
            if updated_repo_ids:
                settings = session.get(AppSettings, 1)
                if not settings or not settings.github_access_token:
                    logger.warning("GitHub Access Token 未配置，跳过 README 变化检测")
                else:
                    access_token = decrypt_data(settings.github_access_token)
                    updated_repos = session.exec(
                        select(Repo).where(Repo.id.in_(updated_repo_ids))
                    ).all()

                    for repo in updated_repos:
                        # 只检查已总结过的仓库
                        if repo.analyzed_at is not None:
                            try:
                                content, current_sha = await get_readme_content(
                                    repo.full_name,
                                    access_token
                                )
                                # 判断 README 是否变化
                                old_sha = repo.readme_sha
                                changed = False
                                if old_sha is None and current_sha is not None:
                                    logger.info(f"README 从无到有：{repo.full_name}")
                                    changed = True
                                elif old_sha is not None and current_sha is not None and old_sha != current_sha:
                                    logger.info(f"README 已变化：{repo.full_name}，旧 SHA：{old_sha}，新 SHA：{current_sha}")
                                    changed = True

                                if changed:
                                    repos_to_summarize.append(repo)
                                    # 缓存已获取的 README，避免总结时重复请求
                                    readme_cache[repo.id] = (content, current_sha)
                            except Exception as e:
                                logger.warning(f"检查 README 变化失败，跳过：{repo.full_name}，错误：{e}")

            logger.info(f"模式：自动模式，共筛选出 {len(repos_to_summarize)} 个仓库需要总结")
            return repos_to_summarize, readme_cache

        else:
            raise ValueError(f"未知的总结模式：{mode}")


async def summarize_repos_batch(
    repos: List[Repo],
    settings: AppSettings,
    readme_cache: Optional[Dict[int, Tuple[Optional[str], Optional[str]]]] = None
) -> dict:
    """
    批量总结仓库

    Args:
        repos: 需要总结的仓库列表
        settings: 应用设置
        readme_cache: 预取的 README 缓存（auto 模式下由 get_repos_to_summarize 提供）

    Returns:
        总结结果统计
    """
    if not repos:
        logger.info("没有需要总结的仓库")
        return {"total": 0, "success": 0, "failed": 0}

    # 检查配置
    if not settings.ai_base_url or not settings.ai_model:
        logger.error("AI 配置缺失：base_url 或 model 为空")
        # 发送通知（如果启用）
        with Session(engine) as session:
            notifier = create_notifier(session, settings)
            if notifier:
                title, content = create_ai_error_message("config_missing", lang=settings.ui_language)
                await notifier.send(title, content)
        raise Exception("AI 配置缺失")

    if not settings.github_access_token:
        logger.error("GitHub Access Token 未配置")
        # 发送通知（如果启用）
        with Session(engine) as session:
            notifier = create_notifier(session, settings)
            if notifier:
                title, content = create_ai_error_message("github_token_missing", lang=settings.ui_language)
                await notifier.send(title, content)
        raise Exception("GitHub Access Token 未配置")

    # 解密敏感字段（数据库中以加密形式存储）
    github_token = decrypt_data(settings.github_access_token)
    ai_api_key = decrypt_data(settings.ai_api_key) if settings.ai_api_key else None

    # 初始化统计
    total = len(repos)
    success_count = 0
    failed_count = 0

    # 获取并发数
    concurrency = settings.ai_concurrency

    # 分批处理
    batch_size = 50
    logger.info(f"开始批量总结，共 {total} 个仓库，并发数：{concurrency}")

    # 创建共享的 AIService 实例，复用连接池
    async with AIService(
        base_url=settings.ai_base_url,
        api_key=ai_api_key,
        model=settings.ai_model,
        language=settings.ui_language
    ) as ai_service:
        for batch_idx in range(0, total, batch_size):
            batch_repos = repos[batch_idx:batch_idx + batch_size]
            batch_num = batch_idx // batch_size + 1
            logger.info(f"处理批次 {batch_num}，共 {len(batch_repos)} 个仓库")

            # 并发处理当前批次
            for i in range(0, len(batch_repos), concurrency):
                concurrent_repos = batch_repos[i:i + concurrency]
                tasks = [
                    summarize_single_repo(repo, github_token, settings, ai_service, readme_cache)
                    for repo in concurrent_repos
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # 统计结果
                for result in results:
                    if isinstance(result, Exception):
                        failed_count += 1
                        # 致命错误：API 密钥无效或 GitHub Token 无效，停止整个批量任务
                        if isinstance(result, (InvalidApiKeyError, InvalidGitHubTokenError)):
                            logger.error(f"致命错误，停止总结：{result}")
                            raise result
                    elif result:
                        success_count += 1
                    else:
                        failed_count += 1

                # 并发组间延迟
                if i + concurrency < len(batch_repos):
                    logger.info("并发组完成，等待 20 秒...")
                    await asyncio.sleep(20)

            # 批次间延迟
            if batch_idx + batch_size < total:
                logger.info(f"批次 {batch_num} 完成，等待 60 秒...")
                await asyncio.sleep(60)

    logger.info(f"批量总结完成：总数 {total}，成功 {success_count}，失败 {failed_count}")
    return {"total": total, "success": success_count, "failed": failed_count}


async def summarize_single_repo(
    repo: Repo,
    github_token: str,
    settings: AppSettings,
    ai_service: AIService,
    readme_cache: Optional[Dict[int, Tuple[Optional[str], Optional[str]]]] = None
) -> bool:
    """
    总结单个仓库的完整流程

    Args:
        repo: 仓库对象
        github_token: 解密后的 GitHub Access Token
        settings: 应用设置（用于发送通知）
        ai_service: 共享的 AI 服务实例
        readme_cache: 预取的 README 缓存

    Returns:
        True: 总结成功
        False: 总结失败
    """
    logger.info(f"开始总结仓库：{repo.full_name}")

    try:
        # 步骤 1：优先使用预取的 README 缓存，否则请求 GitHub API
        if readme_cache and repo.id in readme_cache:
            readme_content, readme_sha = readme_cache[repo.id]
            logger.info(f"使用预取的 README：{repo.full_name}")
        else:
            readme_content, readme_sha = await get_readme_content(
                repo.full_name,
                github_token
            )

        # 步骤 2：如果没有 README，标记为成功
        if readme_content is None:
            with Session(engine) as session:
                db_repo = session.get(Repo, repo.id)
                if db_repo:
                    db_repo.ai_summary = None
                    db_repo.analyzed_at = datetime.now()
                    db_repo.analysis_failed = False
                    db_repo.readme_sha = None
                    session.add(db_repo)
                    session.commit()
            logger.info(f"仓库无 README，标记为成功：{repo.full_name}")
            return True

        # 步骤 3：截取 README 前 2000 字符
        readme_content = readme_content[:2000]

        # 步骤 4：调用 AI API 总结
        summary = await ai_service.handle_rate_limit_with_retry(
            repo.full_name,
            readme_content
        )

        # 步骤 5：写入数据库
        with Session(engine) as session:
            db_repo = session.get(Repo, repo.id)
            if db_repo:
                if summary is None:
                    # 限流重试失败
                    db_repo.analysis_failed = True
                    db_repo.analyzed_at = None
                    session.add(db_repo)
                    session.commit()
                    logger.error(f"限流重试失败，标记为失败：{repo.full_name}")
                    return False

                db_repo.ai_summary = summary
                db_repo.analyzed_at = datetime.now()
                db_repo.analysis_failed = False
                db_repo.readme_sha = readme_sha
                session.add(db_repo)
                session.commit()

        logger.info(f"总结成功：{repo.full_name}")
        return True

    except InvalidApiKeyError:
        # 致命错误：向上抛出，停止整个批量任务
        logger.error(f"API 密钥无效：{repo.full_name}")
        with Session(engine) as session:
            notifier = create_notifier(session, settings)
            if notifier:
                title, content = create_ai_error_message("api_key_invalid", lang=settings.ui_language)
                await notifier.send(title, content)
        raise

    except (ApiEndpointError, NetworkTimeoutError) as e:
        # 可重试错误：标记失败但不写时间戳，下次可重试
        with Session(engine) as session:
            db_repo = session.get(Repo, repo.id)
            if db_repo:
                db_repo.analysis_failed = True
                db_repo.analyzed_at = None
                session.add(db_repo)
                session.commit()
        logger.warning(f"可重试错误，标记为失败：{repo.full_name}，错误：{e}")
        return False

    except EmptyContentError:
        # 不可修复错误：写入时间戳，不再重试
        with Session(engine) as session:
            db_repo = session.get(Repo, repo.id)
            if db_repo:
                db_repo.analysis_failed = True
                db_repo.analyzed_at = datetime.now()
                session.add(db_repo)
                session.commit()
        logger.error(f"AI 返回内容异常，标记为失败且不再重试：{repo.full_name}")
        return False

    except InvalidGitHubTokenError:
        # 致命错误：GitHub Token 无效，向上抛出停止整个批量任务
        logger.error(f"GitHub Token 无效：{repo.full_name}")
        with Session(engine) as session:
            notifier = create_notifier(session, settings)
            if notifier:
                title, content = create_ai_error_message("github_token_invalid", lang=settings.ui_language)
                await notifier.send(title, content)
        raise

    except GitHubApiError as e:
        # GitHub API 失败：标记失败但不写时间戳，下次可重试
        with Session(engine) as session:
            db_repo = session.get(Repo, repo.id)
            if db_repo:
                db_repo.analysis_failed = True
                db_repo.analyzed_at = None
                session.add(db_repo)
                session.commit()
        logger.warning(f"GitHub API 失败，标记为失败：{repo.full_name}，错误：{e}")
        return False

    except Exception as e:
        # 未知错误：标记失败但不写时间戳
        with Session(engine) as session:
            db_repo = session.get(Repo, repo.id)
            if db_repo:
                db_repo.analysis_failed = True
                db_repo.analyzed_at = None
                session.add(db_repo)
                session.commit()
        logger.error(f"未知错误：{repo.full_name}，错误：{e}")
        return False
