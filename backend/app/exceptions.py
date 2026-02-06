"""
自定义异常类。
定义项目中所有业务逻辑相关的自定义异常，继承自 FastAPI 的 HTTPException。
以及 AI/README 服务层的非 HTTP 业务异常。
"""
from fastapi import HTTPException, status
from .schemas import ErrorResponse
from .config import settings

class ApiException(HTTPException):
    """
    项目通用的 API 异常基类。
    自动将错误信息包装成统一的 ErrorResponse 格式，并支持多语言。
    在 DEBUG 模式下，可以附带详细的调试信息。
    """
    def __init__(
        self,
        status_code: int,
        code: str,
        message_zh: str,
        message_en: str,
        details: str = None
    ):
        """
        初始化一个 API 异常。
            status_code: HTTP 状态码。
            code: 内部定义的错误码。
            message_zh: 中文错误信息。
            message_en: 英文错误信息。
            details: 详细的调试信息 (仅 DEBUG 模式下)。
        """
        # 在 DEBUG 模式下，将 details 字段加入响应体，方便调试
        response_details = details if settings.DEBUG else None

        # 将结构化的 ErrorResponse 模型作为 HTTPException 的 detail 负载。
        # FastAPI 会自动将其序列化为 JSON。
        # exclude_none=True 确保当 details 为 None 时，该字段不会出现在最终的 JSON 响应中。
        super().__init__(
            status_code=status_code,
            detail=ErrorResponse(
                code=code,
                message_zh=message_zh,
                message_en=message_en,
                details=response_details
            ).model_dump(exclude_none=True)
        )


# --- AI/README 服务层业务异常 ---

class AIServiceError(Exception):
    """AI 服务异常基类"""
    pass


class InvalidApiKeyError(AIServiceError):
    """API 密钥无效（致命错误，应停止整个批量任务）"""
    pass


class RateLimitError(AIServiceError):
    """API 限流（可重试）"""
    pass


class ApiEndpointError(AIServiceError):
    """API 端点返回 5xx 错误（可重试）"""
    pass


class NetworkTimeoutError(AIServiceError):
    """网络超时（可重试）"""
    pass


class EmptyContentError(AIServiceError):
    """AI 返回内容为空或过短（不可修复，不再重试）"""
    pass


class GitHubApiError(Exception):
    """GitHub API 调用失败（可重试）"""
    pass


class InvalidGitHubTokenError(GitHubApiError):
    """GitHub Access Token 无效或过期（致命错误，应停止整个批量任务）"""
    pass
