"""
数据库初始化和会话管理。
负责创建数据库引擎、建立表结构，并提供 FastAPI 依赖注入所需的数据库会话。
"""
from sqlmodel import create_engine, Session, SQLModel
from app.config import settings
from app.models import Repo, AppSettings

# 根据配置创建数据库引擎。
# - echo=settings.DEBUG: 在调试模式下打印 SQL 语句。
# - connect_args={"check_same_thread": False}: 允许在多线程环境中使用 SQLite。
engine = create_engine(
    settings.DATABASE_URL, 
    echo=settings.DEBUG,
    connect_args={"check_same_thread": False}
)

def create_db_and_tables():
    """创建数据库文件和所有定义的表结构。"""
    SQLModel.metadata.create_all(engine)

def get_session():
    """为 FastAPI 依赖注入系统提供数据库会话的生成器。"""
    with Session(engine) as session:
        yield session
