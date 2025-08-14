"""
通知器工厂，根据用户配置动态创建并返回相应的通知器实例。
提供了一个create_notifier 函数，根据 AppSettings 中的配置来决定创建哪个具体的通知器 (Webhook, Gotify, etc.)。
"""
import logging
from typing import Optional
from sqlmodel import Session

from app.models import AppSettings
from app.core import settings_service
from .base import Notifier
from .webhook import WebhookNotifier
from .gotify import GotifyNotifier 
from .bark import BarkNotifier
from .serverchan import ServerChanNotifier

logger = logging.getLogger(__name__)

# 将渠道名称与对应的通知器类关联起来的映射
# 增加新渠道时，在这里添加映射
NOTIFIER_MAP = {
    "webhook": WebhookNotifier,
    "gotify": GotifyNotifier,
    "bark": BarkNotifier,
    "serverchan": ServerChanNotifier,
}


def create_notifier(session: Session, settings: AppSettings) -> Optional[Notifier]:
    """
    根据应用设置，创建并返回一个具体的通知器实例。
    参数:
        settings: 从数据库中获取的应用设置对象。
    返回:
        一个具体的 Notifier 实例，如果用户未开启推送或配置无效，则返回 None。
    """
    # 1. 检查推送功能是否被用户开启
    if not settings.is_push_enabled:
        return None

    # 2. 获取用户选择的渠道和该渠道的配置
    channel_name = settings.push_channel
    channel_config = settings_service.get_decrypted_push_config(session)

    if not channel_name:
        logger.warning("Push notification is enabled, but no channel is selected.")
        return None

    # 3. 从映射中查找对应的通知器类
    NotifierClass = NOTIFIER_MAP.get(channel_name)

    if not NotifierClass:
        logger.error(f"No notifier implementation found for channel: '{channel_name}'")
        return None
        
    if not channel_config:
        logger.warning(f"Push channel '{channel_name}' is selected, but its config is empty.")
        return None

    # 4. 创建并返回通知器实例，同时传入代理使用决策
    try:
        logger.info(f"Creating notifier for channel: '{channel_name}'")
        return NotifierClass(
            config=channel_config,
            use_proxy=settings.is_push_proxy_enabled # 将“是否使用代理”的决策传递下去
        )
    except Exception as e:
        logger.error(f"Failed to create notifier for channel '{channel_name}'. Error: {e}", exc_info=True)
        return None
