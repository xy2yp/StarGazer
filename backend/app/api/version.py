"""
专门用于处理版本检查和更新通知的 API 端点。
包含每日缓存机制以避免频繁请求。支持版本比较和更新提醒功能。
"""
import httpx
import re
import logging
from fastapi import APIRouter
from datetime import datetime, date, timedelta

from app.version import __version__ as CURRENT_VERSION

router = APIRouter(prefix="/api/version", tags=["Version"])
logger = logging.getLogger(__name__)

# GitHub 版本文件的 URL 地址
GITHUB_VERSION_URL = "https://raw.githubusercontent.com/xy2yp/StarGazer/refs/heads/main/backend/app/version.py"

class VersionChecker:
    """
    带有每日缓存功能的版本检查器。    
    实现"每日历日一次"的检查策略，避免频繁请求 GitHub。
    使用正则表达式解析版本信息。
    """
    def __init__(self):
        self._cache = None
        # 初始化上次检查日期为昨天，确保服务启动后第一次请求能触发检查
        self._last_check_date = date.today() - timedelta(days=1)

    async def get_version_info(self):
        """
        获取版本信息，包含缓存逻辑。        
        如果是新的一天，则从 GitHub 获取最新版本信息；
        否则返回缓存的结果。检查失败时返回安全的默认值。
        """
        # 检查是否需要进行新的版本检查（今天是否是新的一天）
        if date.today() != self._last_check_date:
            logger.info(f"New day ({date.today()}). Performing version check from {GITHUB_VERSION_URL}")
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(GITHUB_VERSION_URL, timeout=10.0)
                    response.raise_for_status()

                content = response.text
                # 使用正则表达式从版本文件中提取版本号
                match = re.search(r"__version__\s*=\s*['\"]([^'\"]+)['\"]", content)
                
                if not match:
                    raise ValueError("Could not parse version from remote file using regex.")

                latest_version = match.group(1)

                # 检查成功，更新缓存和检查日期
                has_update = latest_version != CURRENT_VERSION
                self._cache = {
                    "current_version": CURRENT_VERSION,
                    "latest_version": latest_version,
                    "has_update": has_update
                }
                self._last_check_date = date.today()
                logger.info(f"Version check successful. Current: {CURRENT_VERSION}, Latest: {latest_version}, Update available: {has_update}")

            except Exception as e:
                logger.error(f"Version check failed: {e}. Will use cached or safe data.")
                # 检查失败，不更新检查日期，以便下次 API 请求能立即重试
                # 如果是首次启动且检查失败，创建安全的默认缓存
                if not self._cache:
                    self._cache = {
                        "current_version": CURRENT_VERSION,
                        "latest_version": CURRENT_VERSION,
                        "has_update": False,
                        "error": "check_failed"
                    }
        
        # 返回当前缓存的版本信息
        return self._cache

# 创建全局的版本检查器实例
version_checker = VersionChecker()

@router.get("/check", summary="检查应用是否有新版本")
async def check_for_updates():
    """
    检查 GitHub 仓库中的最新版本，并与当前运行的版本进行比较。    
    特性：
    - 包含每日缓存，每天只向 GitHub 发送一次请求。
    - 网络检查失败时静默处理，返回缓存数据或安全的默认值。
    - 失败后允许下次请求立即重试，而不需要等到第二天。
    """
    return await version_checker.get_version_info()
