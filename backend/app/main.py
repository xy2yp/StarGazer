"""
FastAPI 应用主入口。
负责创建和配置 FastAPI 实例，定义应用生命周期事件 (启动/关闭)，挂载所有 API 路由，并提供静态文件服务。
"""
import asyncio
import uuid
import logging
import json
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.version import __version__ as APP_VERSION
from posthog import Posthog

from app.api import auth, users, stars, settings as api_settings, tags as api_tags, version as api_version
from app.db import create_db_and_tables
from app.core.scheduler import periodic_sync_scheduler

# 用于持有后台定时同步任务的句柄
background_task = None
logger = logging.getLogger(__name__)

def _handle_telemetry():
    """
    处理匿名遥测数据发送。

    安全地发送一次性的、匿名的“版本已部署”事件。
    其核心逻辑如下：
    1. 检查是否通过环境变量禁用了遥测。
    2. 在 `/data/.instance` 文件中持久化一个匿名的实例 ID 和已发送遥测的版本号。
    3. 确保每个版本只发送一次事件，避免重复。
    4. 所有操作都在异常捕获中进行，确保遥测失败不会影响主应用启动。
    """
    # 检查用户是否已选择禁用遥测
    if settings.DISABLE_TELEMETRY:
        logger.info("Telemetry is disabled by user.")
        return

    current_version = APP_VERSION
    instance_file_path = Path("/data/.instance")
    instance_data = {}

    # 尝试读取已有的实例状态文件
    if instance_file_path.exists():
        try:
            with open(instance_file_path, "r") as f:
                instance_data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Could not read or parse instance file at {instance_file_path}. Will create a new one. Error: {e}")
            instance_data = {}
    
    # 检查当前版本的遥测事件是否已发送过
    if instance_data.get("telemetry_sent", {}).get(current_version):
        logger.info(f"Telemetry event for version '{current_version}' has already been sent. Skipping.")
        return

    # 初始化 PostHog 客户端以发送事件
    POSTHOG_API_KEY = "phc_BjL2UNXEEeitRX5xMEBruwSVZe7sfgEPuqgNtCzxTmr" 
    posthog_client = Posthog(project_api_key=POSTHOG_API_KEY, host="https://us.i.posthog.com")

    try:
        # 获取或生成一个唯一的、匿名的实例 ID
        instance_id = instance_data.get("instance_id")
        if not instance_id:
            instance_id = str(uuid.uuid4())
            instance_data["instance_id"] = instance_id
            logger.info(f"Generated new anonymous instance ID: {instance_id}")

        # 发送匿名的“版本已部署”事件
        posthog_client.capture(
            distinct_id=instance_id,
            event="instance_deployed",
            properties={
                "version": current_version
            }
        )
        logger.info(f"Anonymous telemetry event 'instance_deployed' captured for instance ID: {instance_id}, version: {current_version}")

        # 更新状态，标记当前版本已发送
        if "telemetry_sent" not in instance_data:
            instance_data["telemetry_sent"] = {}
        instance_data["telemetry_sent"][current_version] = True

        # 将更新后的状态持久化到文件
        try:
            with open(instance_file_path, "w") as f:
                json.dump(instance_data, f, indent=2)
            logger.info(f"Instance state saved to {instance_file_path}")
        except IOError as e:
            logger.error(f"Failed to write instance state to file: {e}")

    except Exception as e:
        # 捕获所有潜在异常，防止遥测功能中断应用启动
        logger.error(f"Failed to handle telemetry event: {e}", exc_info=False)
    finally:
        # 确保在函数退出前，所有排队的事件都被发出
        if 'posthog_client' in locals() and posthog_client:
            posthog_client.shutdown()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理器。
    在 FastAPI 应用启动和关闭时执行指定的异步操作。
    """
    # --- 应用启动时执行 ---
    print("StarGazer is starting up...")
    
    # 初始化数据库和表结构
    create_db_and_tables()

    # 处理匿名遥测
    _handle_telemetry()
    
    # 创建并启动后台同步任务，但让它延迟5秒再执行第一次
    print("Starting background sync scheduler with initial delay...")
    # 我们给一个短暂的延迟（例如5秒），以确保FastAPI完全启动完毕
    INITIAL_SCHEDULER_DELAY = 5 
    background_task = asyncio.create_task(
        periodic_sync_scheduler(initial_delay=INITIAL_SCHEDULER_DELAY)
    )
    
    yield # 在此期间，应用会处理请求
    
    # --- 应用关闭时执行 ---
    print("StarGazer is shutting down...")
    
    # 取消并等待后台任务结束
    if background_task:
        print("Cancelling background sync scheduler...")
        background_task.cancel()
        try:
            # 等待任务实际完成取消操作
            await background_task
        except asyncio.CancelledError:
            print("Background sync scheduler cancelled successfully.")

# 创建并配置 FastAPI 应用实例
app = FastAPI(
    title="StarGazer API - 星眸 API",
    description="API for StarGazer, a personal GitHub star manager.",
    version=APP_VERSION,
    lifespan=lifespan # 注册生命周期管理器
)

# --- 路由挂载 ---
app.include_router(auth.router)  # 挂载认证相关的路由
app.include_router(users.router)  # 挂载用户相关的路由
app.include_router(stars.router)  # 挂载 star 仓库相关的路由
app.include_router(api_settings.router) # 挂载 settings 相关的路由
app.include_router(api_tags.router) # 挂载自定义标签的相关路由
app.include_router(api_version.router) # 挂载版本检查相关的路由

# --- 静态文件 ---
# 挂载前端静态文件，实现单页应用 (SPA) 托管
static_files_dir = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=static_files_dir, html=True), name="static")
