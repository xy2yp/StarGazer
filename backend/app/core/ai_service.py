"""
AI 服务模块：负责调用 AI API 进行仓库总结

支持连接池复用（通过 async with 上下文管理器）和多语言提示词。
提示词模板从 locales/ 目录的 JSON 文件加载，遵循项目统一的 i18n 机制。
"""
import json
import httpx
import asyncio
import logging
from pathlib import Path
from typing import Optional

from app.exceptions import (
    InvalidApiKeyError, RateLimitError, ApiEndpointError,
    NetworkTimeoutError, EmptyContentError,
)

logger = logging.getLogger(__name__)

# 加载 locale 文件中的 AI 提示词模板
_LOCALES_PATH = Path(__file__).parent.parent / "locales"
_PROMPT_CACHE: dict[str, str] = {}


def _load_prompts():
    """从 locales 目录加载 AI 提示词模板到内存缓存"""
    if not _LOCALES_PATH.is_dir():
        logger.warning(f"Locales directory not found at: {_LOCALES_PATH}")
        return

    for lang_file in _LOCALES_PATH.glob("*.json"):
        lang_code = lang_file.stem
        try:
            with open(lang_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                prompt = data.get("ai_summary_prompt")
                if prompt:
                    _PROMPT_CACHE[lang_code] = prompt
                    logger.info(f"Loaded AI prompt template for '{lang_code}'.")
        except (IOError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load AI prompt from {lang_file}: {e}")


_load_prompts()


def get_prompt_template(language: str) -> str:
    """根据语言获取提示词模板，不支持的语言回退到中文"""
    return _PROMPT_CACHE.get(language, _PROMPT_CACHE.get("zh", ""))


class AIService:
    """AI 服务类：封装 AI API 调用逻辑，支持连接池复用"""

    def __init__(self, base_url: str, api_key: str, model: str, language: str = "zh"):
        """
        初始化 AI 服务

        Args:
            base_url: AI API 基础 URL
            api_key: API 密钥
            model: 模型名称
            language: 提示词语言（"zh" 或 "en"），默认中文
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.model = model
        self.language = language
        self.temperature = 0.3
        self.max_tokens = 4096
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """创建连接池"""
        self._client = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """关闭连接池"""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端，未通过上下文管理器使用时自动创建临时客户端"""
        if self._client:
            return self._client
        # 兼容不使用 async with 的场景（如单次调用）
        self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def summarize_repository(
        self,
        full_name: str,
        readme_content: str
    ) -> str:
        """
        总结单个仓库

        Args:
            full_name: 仓库全名（owner/name）
            readme_content: README 内容（已截取前 2000 字符）

        Returns:
            AI 生成的总结文本

        Raises:
            AIServiceError: AI API 调用失败的各类子异常
        """
        # 根据语言选择提示词模板
        template = get_prompt_template(self.language)
        prompt = template.format(
            full_name=full_name,
            readme_content=readme_content[:2000]
        )

        try:
            summary = await self._call_ai_api(prompt)

            # 验证返回内容
            if not summary or len(summary.strip()) < 10:
                raise EmptyContentError("AI 返回内容过短或为空")

            # 截取前 400 字符（数据库限制）
            if len(summary) > 400:
                logger.warning(f"AI 返回内容过长（{len(summary)} 字符），截取前 400 字符")
                summary = summary[:400]

            return summary.strip()

        except Exception as e:
            logger.error(f"AI 总结失败：{full_name}，错误：{e}")
            raise

    async def _call_ai_api(self, prompt: str) -> str:
        """
        调用 AI API

        Args:
            prompt: 提示词

        Returns:
            AI 返回的文本

        Raises:
            AIServiceError: API 调用失败的各类子异常
        """
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }

        client = self._get_client()
        try:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()

            data = response.json()
            logger.info(f"AI API 原始响应：{data}")
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            if not content:
                raise EmptyContentError("AI API 返回内容为空")

            return content

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise InvalidApiKeyError(f"HTTP 401: {e.response.text[:200]}")
            elif e.response.status_code == 429:
                raise RateLimitError(f"HTTP 429: {e.response.text[:200]}")
            elif e.response.status_code in [500, 502, 503, 504]:
                raise ApiEndpointError(f"HTTP {e.response.status_code}")
            else:
                raise ApiEndpointError(f"HTTP {e.response.status_code}")

        except httpx.TimeoutException:
            raise NetworkTimeoutError("AI API 请求超时")

        except httpx.ConnectError as e:
            raise NetworkTimeoutError(f"AI API 连接失败：{e}")

        except (EmptyContentError, InvalidApiKeyError, RateLimitError,
                ApiEndpointError, NetworkTimeoutError):
            # 已分类的异常直接向上抛出，不重新包装
            raise

        except Exception as e:
            raise ApiEndpointError(f"未知错误：{str(e)}")

    async def handle_rate_limit_with_retry(
        self,
        full_name: str,
        readme_content: str
    ) -> Optional[str]:
        """
        处理限流并重试

        Args:
            full_name: 仓库全名
            readme_content: README 内容

        Returns:
            AI 生成的总结文本，失败返回 None
        """
        retry_delays = [30, 60, 120]

        for attempt, delay in enumerate(retry_delays, start=1):
            try:
                return await self.summarize_repository(full_name, readme_content)

            except RateLimitError:
                if attempt < len(retry_delays):
                    logger.warning(
                        f"API 限流，等待 {delay} 秒后重试（第 {attempt} 次）：{full_name}"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"重试 {len(retry_delays)} 次后仍限流：{full_name}")
                    return None

        return None
