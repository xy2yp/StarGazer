"""
应用程序的配置管理。
通过 Pydantic 从环境变量或 .env 文件中加载配置，并提供类型安全的全局配置实例。
"""
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # GitHub OAuth App 配置
    GITHUB_CLIENT_ID: str
    GITHUB_CLIENT_SECRET: str

    # 用于加密/签名 Cookie 的密钥，必须是一个安全的随机字符串
    SECRET_KEY: str

    # 数据库文件的路径
    DATABASE_URL: str = "sqlite:////data/stargazer.db"

    # 调试模式开关，在生产环境中应设为 False
    DEBUG: bool = False

    # Cookie 有效期（天）
    COOKIE_MAX_AGE_DAYS: int = 30

    # 反向代理域名 (可选)
    DOMAIN: Optional[str] = None

    # 匿名遥测开关
    DISABLE_TELEMETRY: bool = False

    # 网络代理配置 (可选)
    HTTP_PROXY: Optional[str] = None
    HTTPS_PROXY: Optional[str] = None

    # Pydantic 模型配置
    # - case_sensitive=False: 环境变量名不区分大小写。
    # - env_file='.env': 从 .env 文件中读取环境变量。
    # - env_file_encoding='utf-8': 指定 .env 文件的编码。
    model_config = SettingsConfigDict(
        case_sensitive=False, 
        env_file='.env', 
        env_file_encoding='utf-8'
    )

# 创建一个全局可用的配置实例，供应用其他部分导入和使用
settings = Settings()
