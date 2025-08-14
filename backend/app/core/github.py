"""
GitHub API 客户端封装。
封装所有与 GitHub API 的直接交互，提供智能重试机制、网络代理支持和并发数据获取功能。
支持获取用户的所有星标仓库，包含分页处理和错误恢复能力。
"""
import httpx
import asyncio
import re
import logging
from typing import List, Dict, Any
import backoff

from app.config import settings
from app.exceptions import ApiException
from fastapi import status

logger = logging.getLogger(__name__)

GITHUB_API_BASE_URL = "https://api.github.com"
STARS_PER_PAGE = 100
MAX_RETRIES = 3

def _is_recoverable_error(e: Exception) -> bool:
    """
    判断异常是否可恢复（适合重试）。    
    网络错误和服务器端错误（5xx）被认为是可恢复的，而客户端错误（4xx）通常不适合重试。
    """
    if isinstance(e, (httpx.RequestError, httpx.ReadTimeout)):
        return True
    if isinstance(e, httpx.HTTPStatusError):
        return e.response.status_code >= 500
    return False

# 配置 backoff 装饰器，用于自动重试
retry_on_server_error = backoff.on_exception(
    backoff.expo,
    Exception,
    max_tries=MAX_RETRIES,
    on_backoff=lambda details: logger.warning(
        f"Retrying ({details['tries']}/{MAX_RETRIES}) "
        f"in {details['wait']:.1f}s due to: {details['exception']}"
    ),
    giveup=lambda e: not _is_recoverable_error(e)
)

class GitHubApiClient:
    """
    GitHub API 客户端，内置并发、分页、智能重试和代理支持。
    提供获取用户星标仓库的功能，自动处理 GitHub API 的分页机制，并在网络错误或服务器错误时自动重试。
    """
    def __init__(self, token: str):
        """
        初始化 GitHub API 客户端。
        """
        self._token = token
        
        # 配置网络代理（如果有设置的话）
        proxies = {}
        if settings.HTTP_PROXY:
            proxies["http://"] = settings.HTTP_PROXY
        if settings.HTTPS_PROXY:
            proxies["https://"] = settings.HTTPS_PROXY

        self.client = httpx.AsyncClient(
            base_url=GITHUB_API_BASE_URL,
            headers={
                "Authorization": f"token {self._token}",
                "Accept": "application/vnd.github.star+json",
            },
            timeout=30.0,
            proxies=proxies if proxies else None
        )
        if proxies:
            logger.info(f"GitHubApiClient is configured to use proxies: {proxies}")

    @retry_on_server_error
    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """
        统一的 HTTP 请求方法，带有自动重试机制。
        对于 4xx 客户端错误不会重试，对于 5xx 服务器错误会自动重试。
        """
        response = await self.client.request(method, url, **kwargs)

        if 400 <= response.status_code < 500:
            if response.status_code == 401:
                raise ApiException(
                    status_code=status.HTTP_401_UNAUTHORIZED, 
                    code="AUTH_INVALID_TOKEN", 
                    message_zh="GitHub Token 无效或已过期", 
                    message_en="Invalid or expired GitHub token"
                )
            # 对于其他 4xx 错误直接抛出，不重试
            response.raise_for_status()

        # 对于 5xx 错误会抛出异常，触发 backoff 重试机制
        response.raise_for_status()
        return response

    async def _get_total_pages(self) -> int:
        """
        通过 HEAD 请求探测星标仓库的总页数。        
        利用 GitHub API 的 Link header 来确定分页信息。
        """
        try:
            response = await self._request("HEAD", "/user/starred", params={"per_page": STARS_PER_PAGE})
        except ApiException:
            raise
        except Exception as e:
            logger.error(f"Failed to probe total pages from GitHub after all retries: {e}", exc_info=True)
            raise ApiException(
                status_code=status.HTTP_502_BAD_GATEWAY, 
                code="GITHUB_API_PROBE_FAILED", 
                message_zh="探测 GitHub API 失败", 
                message_en="Failed to probe GitHub API"
            )

        link_header = response.headers.get("link")
        if not link_header:
            return 1
        
        # 从 Link header 中提取最后一页的页码
        last_page_match = re.search(r'page=(\d+)>; rel="last"', link_header)
        return int(last_page_match.group(1)) if last_page_match else 1

    async def _get_stars_by_page(self, page: int) -> List[Dict[str, Any]]:
        """获取指定页码的星标仓库列表。"""
        response = await self._request("GET", "/user/starred", params={"per_page": STARS_PER_PAGE, "page": page})
        return response.json()

    async def get_all_starred_repos(self) -> List[Dict[str, Any]]:
        """
        并发获取用户所有星标的仓库。        
        自动处理分页，使用 asyncio.gather 并发请求所有页面以提高效率。
        返回清理后的仓库数据列表。
        """
        try:
            total_pages = await self._get_total_pages()
            logger.info(f"Total pages to fetch from GitHub: {total_pages}")
            
            if total_pages == 0:
                return []

            # 并发请求所有页面
            tasks = [self._get_stars_by_page(page) for page in range(1, total_pages + 1)]
            pages_results = await asyncio.gather(*tasks)
            
            # 合并所有页面的结果
            all_stars = [item for page in pages_results for item in page]
            
            logger.info(f"Successfully fetched a total of {len(all_stars)} starred repos from GitHub.")
            
            cleaned_stars = []

            if not all_stars:
                logger.warning("get_all_starred_repos: all_stars list is empty after fetching from GitHub.")
            elif 'repo' not in all_stars[0]:
                logger.error(f"get_all_starred_repos: 'repo' key not found in first item. Item keys: {all_stars[0].keys()}")

            # 清理和标准化数据格式
            for item in all_stars:
                repo_data = item.get("repo", {})
                if not repo_data or not repo_data.get('id'):
                    logger.warning(f"Skipping an item because it has no repo_data or repo_data['id']. Item: {item}")
                    continue
                owner = repo_data.get("owner", {})
                cleaned_stars.append({
                    "id": repo_data.get("id"),
                    "name": repo_data.get("name"),
                    "full_name": repo_data.get("full_name"),
                    "owner_login": owner.get("login"),
                    "owner_avatar_url": owner.get("avatar_url"),
                    "html_url": repo_data.get("html_url"),
                    "description": repo_data.get("description"),
                    "language": repo_data.get("language"),
                    "stargazers_count": repo_data.get("stargazers_count"),
                    "pushed_at": repo_data.get("pushed_at"),
                    "starred_at": item.get("starred_at"), 
                })

            return cleaned_stars

        except Exception as e:
            logger.error(f"Failed to get all starred repos due to an unrecoverable error: {e}", exc_info=True)
            if isinstance(e, ApiException):
                raise e
            raise ApiException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                code="GITHUB_SYNC_FAILED", 
                message_zh="同步 GitHub 数据时发生未知错误", 
                message_en="An unknown error occurred during GitHub sync"
            )
