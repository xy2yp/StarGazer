"""
FastAPI 依赖项函数。
定义在多个路由中共用的依赖项函数，主要用于身份验证和数据提取。
"""
from fastapi import Cookie, status
from typing import Optional
from app.exceptions import ApiException

async def get_token_from_cookie(access_token: Optional[str] = Cookie(default=None)) -> str:
    """
    从请求的 Cookie 中提取并验证 access_token。
    用作 FastAPI 依赖项，确保用户已通过身份验证。
    如果 Cookie 中没有 access_token，会抛出 401 未授权异常。
    返回:
        str: 提取到的 access_token。 
    异常:
        ApiException: 当 access_token 不存在时抛出 401 错误。
    """
    if not access_token:
        raise ApiException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="AUTH_MISSING_TOKEN",
            message_zh="用户未登录或会话已过期，请重新登录",
            message_en="User not logged in or session has expired, please log in again"
        )
    
    return access_token
