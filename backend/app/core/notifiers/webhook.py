"""
通用 Webhook 推送通知服务的实现。
定义了 WebhookNotifier 类，提供一个高度可定制的通知器，
允许用户通过任意的 Webhook URL 发送 POST 或 GET 请求，并支持自定义 JSON 模板。
"""
import httpx
import logging
import json 
from typing import Dict, Any

from .base import Notifier
from app.config import settings

logger = logging.getLogger(__name__)


class WebhookNotifier(Notifier):
    """
    通用 Webhook 推送器。
    支持的配置项:
    - url: (必需) Webhook 的完整 URL。
    - method: (可选) HTTP 请求方法，支持 'POST' (默认) 或 'GET'。
    - json: (可选) 一个 JSON 字符串，作为请求体模板。其中 `{title}` 和 `{content}` 会被替换。
            默认为: '{"text": "{title}\{content}"}'
    """
    @property
    def channel_name(self) -> str:
        return "webhook"

    # __init__ 方法由基类 Notifier 继承，无需重写。

    async def send(self, title: str, content: str) -> bool:
        """
        使用用户配置的 Webhook 发送通知。
        """
        # 从配置中获取 Webhook 的具体参数
        url = self.config.get("url")
        method = self.config.get("method", "POST").upper()
        json_template_str = self.config.get("json", '{"text": "{title}\n{content}"}')
        
        if not url:
            logger.error(f"[{self.channel_name}] Webhook URL is not configured.")
            return False

        # 动态构建代理配置
        proxies = {}
        if self.use_proxy:
            # 当用户为推送开启了代理时，读取环境变量中的代理设置
            if settings.HTTP_PROXY:
                proxies["http://"] = settings.HTTP_PROXY
            if settings.HTTPS_PROXY:
                proxies["https://"] = settings.HTTPS_PROXY
            if proxies:
                logger.info(f"[{self.channel_name}] Sending notification via proxy.")

        try:
            # 步骤 1: 解析用户定义的 JSON 模板字符串
            try:
                template_obj = json.loads(json_template_str)
            except json.JSONDecodeError as e:
                logger.error(f"[{self.channel_name}] User-defined JSON template is invalid: {e}. Template was: '{json_template_str}'")
                return False

            # 步骤 2: 递归地填充模板中的 {title} 和 {content} 占位符
            def fill_template(obj):
                if isinstance(obj, dict):
                    return {k: fill_template(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [fill_template(elem) for elem in obj]
                elif isinstance(obj, str):
                    if obj == "{title}":
                        return title
                    if obj == "{content}":
                        return content
                    return obj.replace("{title}", title).replace("{content}", content)
                else:
                    return obj

            payload = fill_template(template_obj)

            # 步骤 3: 使用 httpx 发送请求
            async with httpx.AsyncClient(proxies=proxies if proxies else None, timeout=15.0) as client:
                if method == 'POST':
                    # httpx 的 json 参数会自动处理序列化和 Content-Type header
                    response = await client.post(url, json=payload)
                elif method == 'GET':
                    # GET 请求通常使用 params 来传递查询参数
                    response = await client.get(url, params=payload)
                else:
                    logger.error(f"[{self.channel_name}] Unsupported HTTP method: {method}")
                    return False

                # 检查响应状态码，如果不是 2xx，则会抛出异常
                response.raise_for_status()

            logger.info(f"[{self.channel_name}] Notification sent successfully to {url}")
            return True

        except Exception as e:
            logger.error(f"[{self.channel_name}] Failed to send notification to {url}. Error: {e}", exc_info=True)
            return False
