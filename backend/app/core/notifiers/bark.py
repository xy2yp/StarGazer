"""
Bark 推送通知服务的实现。
定义了 BarkNotifier 类，用于通过 Bark 服务发送推送通知。
支持官方服务器和自建服务器，并能从消息内容中自动提取跳转链接。
"""
import re
import httpx
import logging
from .base import Notifier
from app.config import settings

logger = logging.getLogger(__name__)


class BarkNotifier(Notifier):
    """
    Bark 推送通知器。
    支持的配置项:
    - key: (必需) 你的 Bark 设备 Key。
    - server_url: (可选) 自建 Bark 服务器地址。如果未提供，则使用官方服务器 "https://api.day.app"。
    """
    @property
    def channel_name(self) -> str:
        return "bark"

    async def send(self, title: str, content: str) -> bool:
        key = self.config.get("key")
        server_url = self.config.get("server_url", "https://api.day.app").rstrip('/')
        
        if not key:
            logger.error(f"[{self.channel_name}] Bark key is not configured.")
            return False

        # 提取跳转 URL
        url_match = re.search(r'\[(?:.*?(?:跃迁|jump).*?)\]\((.*?)\)', content, re.IGNORECASE)
        jump_url = url_match.group(1) if url_match else None

        # Bark API v2 使用 POST JSON 格式
        url = f"{server_url}/push"
        payload = {
            "title": title,
            "body": content,
            "device_key": key,
            "group": "StarGazer", 
            "level": "active", 
        }

        # 只有在成功提取到 URL 时，才将其添加到 payload 中
        if jump_url:
            payload["url"] = jump_url
            logger.info(f"[{self.channel_name}] Extracted jump URL for Bark: {jump_url}")

        # 动态构建代理配置
        proxies = {}
        if self.use_proxy:
            if settings.HTTP_PROXY: proxies["http://"] = settings.HTTP_PROXY
            if settings.HTTPS_PROXY: proxies["https://"] = settings.HTTPS_PROXY

        try:
            async with httpx.AsyncClient(proxies=proxies if proxies else None, timeout=15.0) as client:
                response = await client.post(url, json=payload)

                # 检查 HTTP 状态码，处理网络或服务器层面的错误
                if response.status_code != 200:
                    logger.error(
                        f"[{self.channel_name}] Request to Bark server failed with HTTP status {response.status_code}. "
                        f"Response: {response.text}"
                    )
                    return False
                
                # 解析 JSON，处理 Bark API 的业务逻辑错误
                res_json = response.json()
                if res_json.get("code") == 200:
                    logger.info(f"[{self.channel_name}] Notification sent successfully via Bark.")
                    return True
                else:
                    error_message = res_json.get("message", "Unknown Bark API error")
                    error_code = res_json.get("code", "N/A")
                    logger.error(
                        f"[{self.channel_name}] Failed to send notification. "
                        f"Bark API returned a business error: {error_message} (Code: {error_code})"
                    )
                    return False

        except Exception as e:
            logger.error(f"[{self.channel_name}] An unexpected error occurred while sending notification. Error: {e}", exc_info=True)
            return False
