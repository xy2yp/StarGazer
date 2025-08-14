"""
处理 GitHub OAuth2 的认证流程。
负责处理用户的登录、登出，以及与 GitHub 的 OAuth2 授权流程，包括：
1. 引导用户到 GitHub 进行授权。
2. 处理来自 GitHub 的回调，交换 access_token。
3. 将 access_token 保存到数据库并设置 Cookie。
4. 处理用户退出登录的逻辑。
"""
import httpx
import logging
from typing import Optional
from fastapi import APIRouter, Depends, Response, status
from sqlmodel import Session

from app.config import settings
from app.db import get_session
from app.exceptions import ApiException
from fastapi.responses import RedirectResponse
from app.core.settings_service import save_access_token
from app.core import settings_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建认证相关路由的 APIRouter 实例
router = APIRouter(
    prefix="/auth",  
    tags=["Authentication"], 
)

# GitHub OAuth2 的常量 URL
GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"

@router.get("/login", summary="Redirect to GitHub for OAuth2 login")
async def login():
    """构建 GitHub 授权 URL 并将用户重定向到 GitHub 进行 OAuth2 授权。"""
    # 定义 GitHub 权限范围：
    # - 'read:user': 读取用户基本信息。
    # - 'repo': 访问用户的仓库信息，包括 private repo 和 star 记录。
    scope = "read:user repo"
    
    auth_url = (
        f"{GITHUB_AUTH_URL}"
        f"?client_id={settings.GITHUB_CLIENT_ID}"
        f"&scope={scope}"
    )
    
    return RedirectResponse(url=auth_url)

@router.get("/callback", summary="Handle callback from GitHub after authorization")
async def callback(
    session: Session = Depends(get_session),
    code: Optional[str] = None, 
    error: Optional[str] = None
):
    """
    处理来自 GitHub 的 OAuth2 回调。    
    交换授权码获取 access_token，并将其持久化到数据库和 Cookie 中。
    """
    # 检查用户是否拒绝了授权
    if error:
        logger.warning(f"User denied GitHub authorization: {error}")
        raise ApiException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="AUTH_DENIED_BY_USER",
            message_zh="您已取消 GitHub 授权",
            message_en="Authorization denied by user",
            details=error
        )

    # 检查是否缺少授权码
    if not code:
        logger.error("Callback received without a 'code' or 'error' parameter.")
        raise ApiException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="AUTH_INVALID_CALLBACK",
            message_zh="无效的回调请求，缺少授权码",
            message_en="Invalid callback from GitHub: missing authorization code"
        )

    # 准备向 GitHub 发送请求以交换 access_token
    params = {
        "client_id": settings.GITHUB_CLIENT_ID,
        "client_secret": settings.GITHUB_CLIENT_SECRET,
        "code": code,
    }

    # 配置代理设置 (如果有配置的话)
    proxies = {}
    if settings.HTTP_PROXY:
        proxies["http://"] = settings.HTTP_PROXY
    if settings.HTTPS_PROXY:
        proxies["https://"] = settings.HTTPS_PROXY

    try:
        async with httpx.AsyncClient(proxies=proxies if proxies else None) as client:
            headers = {"Accept": "application/json"} 
            token_response = await client.post(
                url=GITHUB_TOKEN_URL,
                params=params,
                headers=headers,
            )
            token_response.raise_for_status()

    except httpx.RequestError as e:
        # 网络层面的错误 (DNS 解析失败、连接超时等)
        logger.error(f"Network error while requesting access token: {e}")
        raise ApiException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="AUTH_GITHUB_CONNECTION_FAILED",
            message_zh="无法连接到 GitHub 服务器",
            message_en="Failed to connect to GitHub to get access token",
            details=str(e)
        )
    except httpx.HTTPStatusError as e:
        # HTTP 状态码错误 (4xx, 5xx)
        logger.error(f"GitHub returned an error status {e.response.status_code}: {e.response.text}")
        raise ApiException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="AUTH_GITHUB_API_ERROR",
            message_zh="GitHub API 返回错误",
            message_en="GitHub API returned a non-200 response",
            details=e.response.text
        )

    token_data = token_response.json()
    
    # 检查 GitHub 返回的 JSON 内容中是否包含错误信息
    if "error" in token_data:
        error_details = token_data.get("error_description", "No description provided.")
        logger.error(f"GitHub returned an error in JSON payload: {token_data['error']} - {error_details}")
        raise ApiException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="AUTH_GITHUB_VALIDATION_FAILED",
            message_zh="GitHub 验证失败，可能是授权码已过期或无效",
            message_en="GitHub validation failed, maybe the code is expired or invalid",
            details=error_details
        )

    access_token = token_data.get("access_token")
    if not access_token:
        logger.error(f"Access token not found in GitHub response payload: {token_data}")
        raise ApiException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="AUTH_TOKEN_NOT_FOUND",
            message_zh="未能从 GitHub 的响应中找到访问令牌",
            message_en="Could not find access token in GitHub's response",
            details=str(token_data)
        )
    
    # 将 access_token 保存到数据库
    try:
        save_access_token(session=session, token=access_token)
        session.commit()
        logger.info("Access token has been committed to the database.")
        
    except Exception as e:
        session.rollback()
        logger.error(f"Critical: Failed to save access token to DB, transaction rolled back: {e}", exc_info=True)
        raise ApiException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="DB_SAVE_TOKEN_FAILED",
            message_zh="无法保存用户凭证到数据库，请检查服务器配置后重试",
            message_en="Could not save user token to the database. Please check server configuration and try again."
        )

    # 将 access_token 存入 HttpOnly Cookie 并重定向到前端主页
    redirect_response = RedirectResponse(url="/")
    
    max_age_seconds = settings.COOKIE_MAX_AGE_DAYS * 24 * 60 * 60
    redirect_response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,          # 防止 JavaScript 访问此 Cookie
        samesite="lax",         # 提供 CSRF 保护
        secure=not settings.DEBUG, # 生产环境中只允许 HTTPS 传输
        max_age=max_age_seconds,
    )
    
    logger.info("Successfully authenticated user, persisted token, and set access_token cookie.")
    
    return redirect_response

@router.get("/logout", summary="Log out the user")
async def logout(
    response: Response,
    session: Session = Depends(get_session)
):
    """处理用户退出登录，清除数据库中的 token 和浏览器中的 Cookie。"""
    logger.info("User requested logout. Clearing token from DB and cookie.")
    
    try:
        # 从数据库中清除 access_token
        settings_service.save_access_token(session=session, token=None)
        session.commit()
        logger.info("Access token successfully cleared from the database.")
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to clear token from DB during logout: {e}", exc_info=True)
    
    # 删除浏览器中的 Cookie
    cookie_domain = settings.DOMAIN if settings.DOMAIN else None
    response.delete_cookie("access_token", domain=cookie_domain)
    
    return RedirectResponse(url="/")
