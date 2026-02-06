"""
定义应用中用于数据传输（API 输入和输出）的 Pydantic 模型。
这些模型不直接与数据库交互，而是作为 API 路由的请求体（输入）和响应体（输出）的结构定义和数据验证层。
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime

class ErrorResponse(BaseModel):
    """标准化的 API 错误响应结构。"""
    code: str         # 错误码
    message_zh: str   # 中文提示
    message_en: str   # 英文提示
    details: Optional[str] = None # 调试信息(仅 DEBUG 模式)

class UserResponse(BaseModel):
    """`/api/me` 接口返回的用户信息结构。"""
    login: str          # GitHub 用户名
    avatar_url: str     # GitHub 头像 URL
    html_url: str       # GitHub 主页 URL
    name: Optional[str] = None # GitHub 显示名称

class RepoResponse(BaseModel):
    """API 响应中单个仓库的数据结构。"""
    id: int                     # GitHub 仓库的唯一 ID
    name: str                   # 仓库名称
    full_name: str              # 仓库全名 (owner/name)
    owner_login: str            # 拥有者用户名
    owner_avatar_url: str       # 拥有者头像 URL
    html_url: str               # 仓库的 GitHub 页面 URL
    description: Optional[str] = None # 仓库描述
    language: Optional[str] = None    # 主要编程语言
    stargazers_count: int       # Star 数量
    pushed_at: str              # 最后一次 push 的时间 (ISO 8601 格式)
    starred_at: str             # 用户收藏仓库的时间 (ISO 8601 格式)
    alias: Optional[str] = None     # 用户设置的别名
    notes: Optional[str] = None     # 用户的详细备注 (支持 Markdown)
    tags: List[str] = []            # 用户打的标签列表
    ai_summary: Optional[str] = None  # AI 生成的仓库总结
    analyzed_at: Optional[datetime] = None  # AI 分析时间戳
    analysis_failed: Optional[bool] = None  # AI 分析是否失败

class StarsResponse(BaseModel):
    """`/api/stars` 接口的完整响应体结构。"""
    stars: List[RepoResponse]       # 仓库列表
    metadata: Dict[str, Any]       # 用于前端筛选的预聚合元数据

class SyncResponse(BaseModel):
    """`/api/sync` 接口的响应体结构。"""
    status: str = "ok"          # 操作状态
    added: int                  # 新增的仓库数量
    updated: int                # 更新的仓库数量
    removed: int                # 移除的仓库数量
    total_from_github: int      # 从 GitHub API 获取的仓库总数

class RepoUpdateRequest(BaseModel):
    """更新仓库信息 (`PATCH /api/stars/{repo_id}`) 的请求体结构。"""
    alias: Optional[str] = Field(None, description="用户设置的别名", max_length=50)
    notes: Optional[str] = Field(None, description="用户的详细备注", max_length=65535)
    tags: Optional[List[str]] = Field(None, description="用户设置的标签列表")

    @field_validator('tags')
    @classmethod
    def validate_tag_length(cls, tags_list: Optional[List[str]]) -> Optional[List[str]]:
        """
        校验 `tags` 字段中每个标签的长度。
        """
        if tags_list is None:
            return None

        TAG_MAX_LENGTH = 30 # 单个标签的最大长度限制
        for tag in tags_list:
            if len(tag) > TAG_MAX_LENGTH:
                # Pydantic 会捕获此 ValueError 并返回一个标准的 422 校验错误响应
                raise ValueError(f"标签 '{tag[:10]}...' 的长度不能超过 {TAG_MAX_LENGTH} 个字符。")
        
        return tags_list

class AppSettingsUpdateRequest(BaseModel):
    """更新应用设置的请求体结构。"""
    # 后台任务相关
    github_access_token: Optional[str] = None
    is_background_sync_enabled: Optional[bool] = None
    sync_interval_hours: Optional[int] = None

    # 推送通知相关
    is_push_enabled: Optional[bool] = None
    push_channel: Optional[str] = None
    push_config: Optional[Dict[str, Any]] = None
    is_dnd_enabled: Optional[bool] = None
    dnd_start_hour: Optional[int] = None
    dnd_end_hour: Optional[int] = None
    is_push_proxy_enabled: Optional[bool] = None

    # 界面相关
    tags_order: Optional[List[str]] = None
    languages_order: Optional[List[str]] = None
    ui_language: Optional[str] = None

    # AI 总结相关
    is_ai_enabled: Optional[bool] = None
    is_auto_analysis_enabled: Optional[bool] = None
    ai_base_url: Optional[str] = None
    ai_api_key: Optional[str] = None
    ai_model: Optional[str] = None
    ai_concurrency: Optional[int] = Field(None, ge=1, le=5)

class AppSettingsResponse(BaseModel):
    """应用设置的响应体结构。"""
    # 后台任务相关
    github_access_token: Optional[str] = None
    is_background_sync_enabled: bool
    sync_interval_hours: int

    # 推送通知相关
    is_push_enabled: bool
    push_channel: Optional[str] = None
    push_config: Dict[str, Any]
    is_dnd_enabled: bool
    dnd_start_hour: int
    dnd_end_hour: int
    is_push_proxy_enabled: bool
    failed_push_count: int

    # 界面相关
    tags_order: List[str]
    languages_order: List[str]
    ui_language: str

    # AI 总结相关
    is_ai_enabled: bool
    is_auto_analysis_enabled: bool
    ai_base_url: Optional[str] = None
    ai_api_key: Optional[str] = None
    ai_model: Optional[str] = None
    ai_concurrency: int
