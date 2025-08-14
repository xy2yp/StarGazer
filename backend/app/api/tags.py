"""
自定义标签管理的 API 端点。
提供全局删除标签的功能，包括从用户的自定义排序中移除标签，以及从所有已标记该标签的仓库中移除该标签。
"""
import logging
from fastapi import APIRouter, Depends, status, Path
from sqlmodel import Session
from urllib.parse import unquote

from app.db import get_session
from app.exceptions import ApiException
from app.api.dependencies import get_token_from_cookie
from app.api.users import get_current_github_user
from app.core import tags_service
from app.core import settings_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/tags",
    tags=["Tags"],
    dependencies=[Depends(get_current_github_user)] # 保护此路由下的所有端点
)

@router.delete(
    "/{tag_name}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a tag globally"
)
def delete_tag(
    session: Session = Depends(get_session),
    tag_name: str = Path(..., description="要删除的标签名称 (需要 URL 编码)")
):
    """
    全局删除指定的自定义标签。    
    1. 从用户的自定义标签排序配置中移除该标签。
    2. 从所有已标记此标签的仓库中移除该标签。
        tag_name: 要删除的标签名称，URL 路径参数会被自动 URL 解码。
    """
    # URL 路径参数可能包含特殊字符（如空格编码为 %20），需要解码
    decoded_tag_name = unquote(tag_name)
    logger.info(f"API request received to delete tag: '{decoded_tag_name}'")
    
    try:
        # 调用服务层执行标签删除的业务逻辑
        tags_service.delete_tag_globally(session, decoded_tag_name)
        # 由 API 层控制事务提交时机
        session.commit()
        logger.info(f"Successfully deleted tag '{decoded_tag_name}' and committed changes.")
    except Exception as e:
        # 发生错误时回滚整个事务
        session.rollback()
        logger.error(f"Failed to delete tag '{decoded_tag_name}', transaction rolled back.", exc_info=True)
        raise ApiException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="TAG_DELETE_FAILED",
            message_zh="删除分组时发生服务器内部错误",
            message_en="An internal server error occurred while deleting the tag."
        )
    
    # 成功时返回 204 No Content，不需要响应体
    return
