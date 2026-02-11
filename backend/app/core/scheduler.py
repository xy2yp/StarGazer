"""
后台定时任务调度器。
基于 asyncio 实现，用于周期性地执行数据同步和推送通知。
包含智能休眠逻辑，支持免打扰(DND)时段。
"""
import asyncio
import logging
import random
from datetime import datetime, time, timedelta
from sqlmodel import Session
from app.db import engine

from app.core.settings_service import get_app_settings, increment_failed_push_count, get_access_token
from app.core.sync_service import run_full_sync
from app.core.notifiers.factory import create_notifier
from app.core.notifiers.message import create_notification_message
from app.core.summary_service import get_repos_to_summarize, summarize_repos_batch
from app.models import AppSettings

logger = logging.getLogger(__name__)

def _is_in_dnd_hours(dnd_enabled: bool, start_hour: int, end_hour: int) -> bool:
    """
    检查当前时间是否在用户的免打扰（Do Not Disturb）时段内。支持跨天设置（如 23:00 - 07:00）。
    """
    if not dnd_enabled or start_hour == end_hour:
        return False
    
    now_time = datetime.now().time()
    start_time = time(start_hour, 0)
    end_time = time(end_hour, 0)

    # 处理跨天和当天两种情况
    if start_time < end_time:
        # DND 时段在当天（如 09:00 - 18:00）
        return start_time <= now_time < end_time
    else: 
        # DND 时段跨天（如 23:00 - 07:00）
        return now_time >= start_time or now_time < end_time

async def _perform_sync_and_notify_actions(session: Session) -> AppSettings:
    """
    执行单次后台同步周期的核心业务逻辑。
    该函数在一个给定的数据库会话中完成所有操作，并返回最新的应用设置。
    这是被定时调度器和测试脚本共同调用的核心。
    """
    app_settings = get_app_settings(session)
    access_token = get_access_token(session)

    # --- 条件检查：判断本周期是否应该跳过核心任务 ---
    should_skip_sync = False
    if not app_settings.is_background_sync_enabled:
        logger.info("Background sync is disabled by user. Skipping task for this cycle.")
        should_skip_sync = True
    elif not access_token:
        logger.warning("No access token found in settings. Skipping task for this cycle.")
        should_skip_sync = True
    elif _is_in_dnd_hours(app_settings.is_dnd_enabled, app_settings.dnd_start_hour, app_settings.dnd_end_hour):
        logger.info("In DND hours. Skipping task for this cycle.")
        should_skip_sync = True

    # --- 核心任务执行 ---
    if not should_skip_sync:
        logger.info("Executing scheduled background sync...")
        # 1. 执行核心同步逻辑（只准备数据库更改，不提交）
        stats, updated_repos = await run_full_sync(session=session, access_token=access_token)
        logger.info(f"Scheduled sync finished. Staged changes: {stats}")

        # 刷新设置，确保获取最新的推送配置
        try:
            session.refresh(app_settings)
            logger.info("Refreshed app_settings from DB before checking push notifications.")
        except Exception:
            # 如果刷新失败，重新获取一次作为备用方案
            app_settings = get_app_settings(session)

        # 2. 检查是否需要发送通知
        if app_settings.is_push_enabled and updated_repos:
            # V24.05.20 根据用户需求，仅推送被标记为"特别关注"的仓库
            favorite_repos_to_notify = [
                repo for repo in updated_repos if repo.tags and "_favorite" in repo.tags
            ]

            if favorite_repos_to_notify:
                logger.info(f"Found {len(favorite_repos_to_notify)} updated 'Favorite' repos to notify.")
                notifier = create_notifier(session, app_settings)

                if notifier:
                    old_pushed_at_map = stats.get("old_pushed_at_map", {})
                    # 先异步生成所有消息，再并发发送
                    notification_tasks = []
                    for repo in favorite_repos_to_notify:
                        old_pushed_at = old_pushed_at_map.get(repo.id)
                        title, content = await create_notification_message(
                            repo,
                            lang=app_settings.ui_language,
                            github_token=access_token,
                            old_pushed_at=old_pushed_at,
                        )
                        notification_tasks.append(notifier.send(title, content))
                    results = await asyncio.gather(*notification_tasks, return_exceptions=True)
                    
                    # 处理发送结果，为失败的通知增加失败计数
                    failed_sends = sum(1 for res in results if isinstance(res, Exception) or res is False)
                    if failed_sends > 0:
                        for _ in range(failed_sends):
                            increment_failed_push_count(session)
                        logger.error(f"{failed_sends} notification(s) failed to send. Details in previous logs.")
                else:
                    logger.warning("Push is enabled, but no valid notifier could be created from settings.")

        # 3. 在一次事务中提交所有数据库更改（包括同步数据和失败计数）
        session.commit()
        logger.info("All database changes for this cycle have been committed.")

        # 4. 检查是否需要触发 AI 自动总结
        if app_settings.is_ai_enabled and app_settings.is_auto_analysis_enabled:
            updated_repo_ids = stats.get("updated_repo_ids", [])
            try:
                # 获取需要总结的仓库
                repos_to_summarize, readme_cache = await get_repos_to_summarize(
                    mode="auto",
                    updated_repo_ids=updated_repo_ids
                )

                if repos_to_summarize:
                    logger.info(f"开始自动 AI 总结，共 {len(repos_to_summarize)} 个仓库")
                    await summarize_repos_batch(repos_to_summarize, app_settings, readme_cache)
                else:
                    logger.info("没有需要自动总结的仓库")

            except Exception as e:
                logger.error(f"自动 AI 总结失败：{e}", exc_info=True)
                # AI 总结失败不影响主流程，继续执行

    return app_settings


async def periodic_sync_scheduler(initial_delay: int = 0):
    """
    后台数据同步和通知推送的主调度循环。
    一个常驻的异步任务，负责管理会话、循环和休眠，并在每个周期调用核心业务逻辑。
    """
    logger.info("Background sync scheduler started.")

    if initial_delay > 0:
        logger.info(f"Initial delay of {initial_delay} seconds before first run.")
        await asyncio.sleep(initial_delay)

    while True:
        app_settings: AppSettings | None = None
        session: Session | None = None
        
        try:
            with Session(engine) as session:
                # 调用被重构的、可测试的核心函数
                app_settings = await _perform_sync_and_notify_actions(session)

        except asyncio.CancelledError:
            # 捕获取消信号，正常退出循环
            logger.info("Background sync scheduler has been cancelled.")
            break
        except Exception as e:
            logger.error(f"An unexpected error occurred in the scheduler's main loop: {e}", exc_info=True)
            if session:
                # 回滚所有暂存的更改，保证数据一致性
                session.rollback()
                logger.info("Transaction has been rolled back due to an error.")
        
        finally:
            # --- 智能休眠：无论任务成功、跳过或失败，都必须执行 ---
            sleep_seconds = 2 * 3600  # 默认休眠 2 小时

            if app_settings:
                # 如果成功获取了设置，则根据设置计算休眠时间
                is_sync_enabled = app_settings.is_background_sync_enabled
                is_dnd_enabled = app_settings.is_dnd_enabled
                dnd_start = app_settings.dnd_start_hour
                dnd_end = app_settings.dnd_end_hour
                
                # 只有在同步开启且处于免打扰时段，才计算特殊的DND休眠时间
                if is_sync_enabled and _is_in_dnd_hours(is_dnd_enabled, dnd_start, dnd_end):
                    now = datetime.now()
                    end_of_dnd = now.replace(hour=dnd_end, minute=0, second=0, microsecond=0)
                    
                    # 处理跨天情况
                    if now.time() >= time(dnd_start, 0):
                        end_of_dnd += timedelta(days=1)

                    # 加入随机抖动，避免多个实例在同一时刻唤醒
                    jitter = random.randint(1, 10)
                    sleep_seconds = max(0, (end_of_dnd - now).total_seconds()) + jitter
                    logger.info(f"Next run is in DND period. Scheduler will sleep for {sleep_seconds/3600:.2f} hours until {end_of_dnd.strftime('%Y-%m-%d %H:%M')}.")
                else:
                    # 对于其他所有情况（同步禁用、不在免打扰时段），都使用常规的同步间隔
                    sleep_seconds = app_settings.sync_interval_hours * 3600
            else:
                logger.warning("Could not read app settings to determine sleep interval. Defaulting to 2 hours.")
            
            logger.info(f"Background sync scheduler will sleep for {sleep_seconds/3600:.2f} hours.")
            await asyncio.sleep(sleep_seconds)
