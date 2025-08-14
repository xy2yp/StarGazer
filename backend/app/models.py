"""
定义所有与数据库表结构对应的 SQLModel 模型。
- Repo: 对应数据库中的 'repo' 表，存储每个 GitHub 星标仓库的详细信息。
- AppSettings: 对应数据库中的 'appsettings' 表，用于存储应用的各项配置。
"""
from typing import Optional, List, Dict, Any
from sqlmodel import Field, SQLModel, JSON, Column, String

class Repo(SQLModel, table=True):
    """代表一个 GitHub 星标仓库的数据库模型。"""
    # 主键
    id: int = Field(default=None, primary_key=True, description="GitHub 仓库的唯一数字 ID")

    # --- 从 GitHub API 同步的基础字段 ---
    name: str = Field(index=True, description="仓库名称")
    full_name: str = Field(index=True, description="仓库全名，格式为 owner/name")
    owner_login: str = Field(description="拥有者用户名")
    owner_avatar_url: str = Field(description="拥有者头像 URL")
    html_url: str = Field(description="仓库的 GitHub 页面 URL")
    description: Optional[str] = Field(default=None, description="仓库描述")
    language: Optional[str] = Field(default=None, index=True, description="主要编程语言")
    stargazers_count: int = Field(description="Star 数量")
    pushed_at: str = Field(description="最后一次 push 的时间 (ISO 8601 字符串)")
    starred_at: str = Field(index=True, description="用户收藏此仓库的时间 (ISO 8601 字符串)")

    # --- 用户在应用内自定义的字段 ---
    alias: Optional[str] = Field(
        default=None, 
        index=True, 
        max_length=50,  # 最大长度限制，在 SQLModel 层面提供校验
        description="用户为仓库设置的别名"
    )
    notes: Optional[str] = Field(
        default=None, 
        max_length=65535, # 在 SQLModel 层面提供校验
        sa_column=Column(String(65535)), # 明确告知 SQLAlchemy 使用 TEXT 类型的列以支持长文本
        description="用户的详细备注 (支持 Markdown)"
    )
    tags: List[str] = Field(
        default_factory=list, 
        sa_column=Column(JSON), 
        description="用户为此仓库打的标签列表"
    )

class AppSettings(SQLModel, table=True):
    """代表应用全局配置的数据库模型，设计为单行表。"""
    # 使用固定的主键 1，确保这张表只有一行记录
    id: Optional[int] = Field(default=1, primary_key=True)
    
    # --- 后台任务相关 --- 
    github_access_token: Optional[str] = Field(default=None, description="用于后台定时同步的 GitHub Access Token")
    is_background_sync_enabled: bool = Field(default=True, description="是否开启后台自动同步")
    sync_interval_hours: int = Field(default=2, description="后台同步的间隔时间（小时）")

    # --- 推送通知相关 ---
    is_push_enabled: bool = Field(default=False, description="是否开启推送通知")
    push_channel: Optional[str] = Field(default=None, description="用户选择的推送渠道类型 (如 'webhook', 'bark')")
    push_config: Dict[str, Any] = Field(
        default_factory=dict, 
        sa_column=Column(JSON), 
        description="所选推送渠道的具体配置 (如 {'url': '...'})"
    )
    is_dnd_enabled: bool = Field(default=False, description="是否开启推送免打扰模式")
    dnd_start_hour: int = Field(default=23, description="免打扰时段的开始时间（小时, 0-23）")
    dnd_end_hour: int = Field(default=7, description="免打扰时段的结束时间（小时, 0-23）")
    is_push_proxy_enabled: bool = Field(default=False, description="是否为推送通知启用网络代理")
    failed_push_count: int = Field(default=0, description="累计发送失败的通知计数器")

    # --- 界面排序与展示相关 ---
    tags_order: List[str] = Field(default_factory=list, sa_column=Column(JSON), description="用户自定义的标签/分组排序")
    languages_order: List[str] = Field(default_factory=list, sa_column=Column(JSON), description="用户自定义的语言排序")
    ui_language: str = Field(
        default="zh", 
        max_length=10, 
        description="用户选择的界面语言"
    )
