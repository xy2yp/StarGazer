"""
处理与 AI 总结相关的 API 端点
"""
import logging
import asyncio
from fastapi import APIRouter, Depends, BackgroundTasks, status
from sqlmodel import Session
from pydantic import BaseModel
from typing import Optional

from app.db import get_session
from app.exceptions import ApiException
from app.api.dependencies import get_token_from_cookie
from app.api.users import get_current_github_user
from app.core.summary_service import get_repos_to_summarize, summarize_repos_batch
from app.core import settings_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/summary",
    tags=["Summary"],
)


class SummaryStartRequest(BaseModel):
    """启动总结任务的请求体"""
    mode: str  # "all" | "unanalyzed"


class SummaryStartResponse(BaseModel):
    """启动总结任务的响应体"""
    message: str
    total: int


class SummaryStatusResponse(BaseModel):
    """总结状态的响应体（可选，用于调试）"""
    is_running: bool
    progress: Optional[dict] = None


# 全局状态（简单实现，生产环境建议使用 Redis）
_summary_status = {
    "is_running": False,
    "total": 0,
    "completed": 0,
    "failed": 0
}


@router.post("/start", response_model=SummaryStartResponse, summary="Start AI summary task")
async def start_summary(
    request: SummaryStartRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    _token: str = Depends(get_current_github_user),
):
    """
    手动触发 AI 总结任务

    Args:
        request: 请求体，包含总结模式
        background_tasks: FastAPI 后台任务
        session: 数据库会话
        _token: 用户认证 token

    Returns:
        总结任务启动响应
    """
    try:
        # 检查模式
        if request.mode not in ["all", "unanalyzed"]:
            raise ApiException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="INVALID_MODE",
                message_zh="无效的总结模式",
                message_en="Invalid summary mode"
            )

        # 检查是否已有任务在运行
        if _summary_status["is_running"]:
            raise ApiException(
                status_code=status.HTTP_409_CONFLICT,
                code="TASK_ALREADY_RUNNING",
                message_zh="已有总结任务正在运行",
                message_en="A summary task is already running"
            )

        # 获取需要总结的仓库
        repos, readme_cache = await get_repos_to_summarize(mode=request.mode)

        if not repos:
            return SummaryStartResponse(
                message="没有需要总结的仓库",
                total=0
            )

        # 获取应用设置
        app_settings = settings_service.get_app_settings(session)

        # 在后台启动总结任务
        background_tasks.add_task(
            _run_summary_task,
            repos,
            app_settings,
            readme_cache
        )

        # 更新状态
        _summary_status["is_running"] = True
        _summary_status["total"] = len(repos)
        _summary_status["completed"] = 0
        _summary_status["failed"] = 0

        logger.info(f"总结任务已启动，模式：{request.mode}，共 {len(repos)} 个仓库")

        return SummaryStartResponse(
            message="总结任务已启动",
            total=len(repos)
        )

    except ApiException:
        raise
    except Exception as e:
        logger.error(f"启动总结任务失败：{e}", exc_info=True)
        raise ApiException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="SUMMARY_START_FAILED",
            message_zh="启动总结任务失败",
            message_en="Failed to start summary task"
        )


@router.get("/status", response_model=SummaryStatusResponse, summary="Get summary task status")
async def get_summary_status(
    _token: str = Depends(get_current_github_user),
):
    """
    查询总结任务状态（可选，用于调试）

    Returns:
        总结任务状态
    """
    return SummaryStatusResponse(
        is_running=_summary_status["is_running"],
        progress={
            "total": _summary_status["total"],
            "completed": _summary_status["completed"],
            "failed": _summary_status["failed"]
        } if _summary_status["is_running"] else None
    )


async def _run_summary_task(repos, app_settings, readme_cache=None):
    """
    后台运行总结任务

    Args:
        repos: 需要总结的仓库列表
        app_settings: 应用设置
        readme_cache: 预取的 README 缓存
    """
    try:
        result = await summarize_repos_batch(repos, app_settings, readme_cache)

        # 更新状态
        _summary_status["completed"] = result["success"]
        _summary_status["failed"] = result["failed"]

        logger.info(f"总结任务完成：成功 {result['success']}，失败 {result['failed']}")

    except Exception as e:
        logger.error(f"总结任务执行失败：{e}", exc_info=True)

    finally:
        # 重置运行状态
        _summary_status["is_running"] = False
