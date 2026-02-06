"""
README 获取服务：负责从 GitHub API 获取仓库的 README 内容和 SHA

通过单次 JSON 格式请求同时获取 SHA 和 content（base64 解码），
避免双重请求浪费 GitHub API 配额。
"""
import base64
import httpx
import logging
from typing import Optional, Tuple

from app.exceptions import GitHubApiError, InvalidGitHubTokenError

logger = logging.getLogger(__name__)


async def get_readme_content(
    full_name: str,
    github_token: str
) -> Tuple[Optional[str], Optional[str]]:
    """
    使用 GitHub 官方 API 获取 README 内容和 SHA（单次请求）

    通过 JSON 格式响应同时获取 sha 和 base64 编码的 content，
    解码后返回原始 Markdown 文本。

    Args:
        full_name: 仓库全名（owner/name）
        github_token: GitHub Access Token

    Returns:
        (content, sha): README 内容和 SHA 值
        (None, None): 没有 README

    Raises:
        GitHubApiError: GitHub API 调用失败
    """
    url = f"https://api.github.com/repos/{full_name}/readme"
    headers = {
        "Authorization": f"token {github_token}"
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url, headers=headers)

            if response.status_code == 404:
                logger.info(f"仓库无 README：{full_name}")
                return None, None

            if response.status_code == 200:
                data = response.json()
                sha = data.get("sha")

                # base64 解码获取原始 Markdown 内容
                encoded_content = data.get("content", "")
                encoding = data.get("encoding", "base64")

                if encoding == "base64" and encoded_content:
                    content = base64.b64decode(encoded_content).decode("utf-8")
                else:
                    content = encoded_content

                logger.info(f"获取 README 成功：{full_name}，SHA：{sha}")
                return content, sha

            if response.status_code == 401:
                logger.error(f"GitHub Token 无效：{full_name}，状态码：401")
                raise InvalidGitHubTokenError("GitHub Access Token 无效或过期")

            # 其他错误（500, 503 等）
            logger.error(f"GitHub API 失败：{full_name}，状态码：{response.status_code}")
            raise GitHubApiError(f"GitHub API 返回 {response.status_code}")

        except httpx.TimeoutException:
            logger.error(f"获取 README 超时：{full_name}")
            raise GitHubApiError(f"获取 README 超时：{full_name}")

        except GitHubApiError:
            raise

        except Exception as e:
            logger.error(f"获取 README 异常：{full_name}，错误：{e}")
            raise GitHubApiError(f"获取 README 异常：{str(e)}")
