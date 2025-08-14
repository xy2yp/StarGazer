"""
处理与用户相关的 API 端点。
提供获取当前用户信息的功能，并包含用于身份验证的依赖项函数。
通过 GitHub API 验证用户身份并返回用户信息。
"""
import httpx
import logging
from fastapi import APIRouter, Depends, Response, status

from sqlmodel import Session
from app.db import get_session
from app.config import settings
from app.exceptions import ApiException
from app.schemas import UserResponse
from app.api.dependencies import get_token_from_cookie 
from app.core import settings_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["Users"],
)

GITHUB_USER_API_URL = "https://api.github.com/user"

async def get_current_github_user(
    response: Response,
    _cookie_exists: None = Depends(get_token_from_cookie), 
    session: Session = Depends(get_session)
) -> dict:
    """
    验证用户身份并返回 GitHub 用户信息。    
    1. 从数据库中获取存储的 access_token。
    2. 使用 token 调用 GitHub API 获取用户信息。
    3. 处理 token 过期或无效的情况，自动清理相关数据。
    返回:
        dict: GitHub API 返回的用户信息字典。
    异常:
        ApiException: 当认证失败或网络错误时抛出相应异常。
    """
    # 从数据库中获取并解密 access_token
    access_token = settings_service.get_access_token(session)

    if not access_token:
        # 数据库中没有 token，判定为未授权
        logger.warning("No access token found in database. Forcing logout.")
        response.delete_cookie("access_token") 
        raise ApiException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="AUTH_NO_SERVER_SESSION",
            message_zh="服务器会话不存在或已过期，请重新登录",
            message_en="Server session not found or expired, please log in again"
        )
    
    headers = {
        "Authorization": f"token {access_token}",
        "Accept": "application/vnd.github.v3+json",
    }
    
    # 配置代理设置（如果有配置的话）
    proxies = {}
    if settings.HTTP_PROXY:
        proxies["http://"] = settings.HTTP_PROXY
    if settings.HTTPS_PROXY:
        proxies["https://"] = settings.HTTPS_PROXY
    
    try:
        async with httpx.AsyncClient(proxies=proxies if proxies else None) as client:
            api_response = await client.get(GITHUB_USER_API_URL, headers=headers)
            
            if api_response.status_code == 401:
                # token 无效或过期，清理 Cookie 和数据库中的 token
                logger.warning(f"Invalid or expired GitHub token (from DB). Clearing cookie and DB token.")
                response.delete_cookie("access_token")
                settings_service.save_access_token(session, token=None)
                session.commit()
                raise ApiException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    code="AUTH_INVALID_TOKEN",
                    message_zh="用户凭证无效或已过期，请重新登录",
                    message_en="Invalid or expired token, please log in again"
                )
            
            api_response.raise_for_status()
            return api_response.json()

    except httpx.RequestError as e:
        # 网络层面的错误
        logger.error(f"Network error while fetching user info from GitHub: {e}")
        raise ApiException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="GET_USER_GITHUB_API_ERROR",
            message_zh="从 GitHub 获取用户信息时出错，请稍后重试",
            message_en="Error fetching user info from GitHub, please try again later",
            details=str(e)
        )
    except httpx.HTTPStatusError as e:
        # HTTP 状态码错误
        logger.error(f"GitHub API returned an error status for /user: {e.response.text}")
        raise ApiException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="GET_USER_GITHUB_API_ERROR",
            message_zh="从 GitHub 获取用户信息时出错，请稍后重试",
            message_en="Error fetching user info from GitHub, please try again later",
            details=e.response.text
        )

@router.get("/me", response_model=UserResponse, summary="Get current user info")
async def get_current_user_api(
    github_user: dict = Depends(get_current_github_user)
):
    """
    获取当前已认证用户的基本信息。    
    通过依赖注入 get_current_github_user 来验证用户身份， 并返回格式化的用户信息响应。
    """
    user_login = github_user.get('login')
    logger.info(f"Successfully provided user info for: {user_login}")
    return UserResponse(**github_user)
