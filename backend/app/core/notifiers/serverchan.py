"""
Server酱 (ServerChan) 推送通知服务的实现。
定义了 ServerChanNotifier 类，用于通过 Server酱 Turbo 版的 API 发送推送通知。
"""
import httpx
import logging
from .base import Notifier
from app.config import settings

logger = logging.getLogger(__name__)


class ServerChanNotifier(Notifier):
    """
    Server酱 Turbo 版推送器。
    支持的配置项:
    - sendkey: (必需) Server酱 SendKey。
    """
    @property
    def channel_name(self) -> str:
        return "serverchan"

    async def send(self, title: str, content: str) -> bool:
        sendkey = self.config.get("sendkey")
        if not sendkey:
            logger.error(f"[{self.channel_name}] ServerChan SendKey is not configured.")
            return False

        # Server酱 Turbo 版的 API endpoint
        url = f"https://sctapi.ftqq.com/{sendkey}.send"
        
        # API 要求使用 x-www-form-urlencoded 格式的 body
        payload = {
            "title": title,
            "desp": content, 
        }
        
        proxies = {}
        if self.use_proxy:
            if settings.HTTP_PROXY: proxies["http://"] = settings.HTTP_PROXY
            if settings.HTTPS_PROXY: proxies["https://"] = settings.HTTPS_PROXY

        try:
            async with httpx.AsyncClient(proxies=proxies if proxies else None, timeout=15.0) as client:
                response = await client.post(url, data=payload)
                response.raise_for_status() # 处理 HTTP 层面非 2xx 的错误

                res_json = response.json()
                
                # 成功的响应 code 为 0，失败时为其他错误码 (如 40001: bad sendkey)
                if res_json.get("code") == 0:
                    pushid = res_json.get("data", {}).get("pushid", "N/A")
                    logger.info(f"[{self.channel_name}] Notification sent successfully. PushID: {pushid}")
                    return True
                else:
                    error_message = res_json.get("message", "Unknown ServerChan API error")
                    error_code = res_json.get("code", "N/A")
                    logger.error(
                        f"[{self.channel_name}] Failed to send notification. "
                        f"ServerChan API error: {error_message} (Code: {error_code})"
                    )
                    return False

        except Exception as e:
            logger.error(f"[{self.channel_name}] An unexpected error occurred while sending notification. Error: {e}", exc_info=True)
            return False
