"""
Gotify 推送通知服务的实现。
定义了 GotifyNotifier 类，用于通过自建的 Gotify 服务器发送推送通知。
支持 Markdown 格式的消息内容。
"""
import httpx
import logging
from .base import Notifier
from app.config import settings

logger = logging.getLogger(__name__)


class GotifyNotifier(Notifier):
    """
    Gotify 推送通知器。
    支持的配置项:
    - url: (必需) Gotify 服务器地址。
    - token: (必需) Gotify App Token。
    - priority: (可选) 消息优先级，默认为 8。
    """
    @property
    def channel_name(self) -> str:
        return "gotify"

    async def send(self, title: str, content: str) -> bool:
        base_url = self.config.get("url", "").rstrip('/')
        token = self.config.get("token")
        priority = self.config.get("priority", 8)

        if not base_url or not token:
            logger.error(f"[{self.channel_name}] Gotify URL or Token is not configured.")
            return False
            
        url = f"{base_url}/message?token={token}"
        payload = {
            "title": title,
            "message": content,
            "priority": priority,
            "extras": {
                "client::display": {
                    "contentType": "text/markdown" # 告诉客户端使用 Markdown 渲染
                }
            }
        }

        proxies = {}
        if self.use_proxy:
            if settings.HTTP_PROXY: proxies["http://"] = settings.HTTP_PROXY
            if settings.HTTPS_PROXY: proxies["https://"] = settings.HTTPS_PROXY

        try:
            async with httpx.AsyncClient(proxies=proxies if proxies else None, timeout=15.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()

                logger.info(f"[{self.channel_name}] Notification sent successfully to {base_url}")
                return True

        except Exception as e:
            logger.error(f"[{self.channel_name}] Failed to send notification. Error: {e}", exc_info=True)
            return False
