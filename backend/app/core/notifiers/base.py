"""
定义所有通知器 (Notifier) 必须遵守的抽象基类 (ABC) 接口。
提供了Notifier类，它是一个抽象基类，确保所有具体的通知器实现都包含 `channel_name` 属性和 `send` 方法。
"""
import abc
from typing import Dict, Any


class Notifier(abc.ABC):
    """
    通知器的抽象基类。
    """

    def __init__(self, config: Dict[str, Any], use_proxy: bool):
        """
        初始化通知器实例。
        参数:
            config: 特定于该通知渠道的配置字典 (例如: {'url': '...', 'token': '...'})。
            use_proxy: 指示在发送请求时是否应使用全局代理的布尔值。
        """
        self.config = config
        self.use_proxy = use_proxy

    @property
    @abc.abstractmethod
    def channel_name(self) -> str:
        """
        返回通知渠道的名称，用于日志记录。
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def send(self, title: str, content: str) -> bool:
        """
        发送通知的抽象方法。
        参数:
            title: 通知的标题。
            content: 通知的内容 (支持 Markdown)。
        返回:
            一个布尔值，表示发送是否成功。
        """
        raise NotImplementedError
