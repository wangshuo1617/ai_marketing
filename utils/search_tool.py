import os
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


class SearchToolError(RuntimeError):
    """Raised when external research cannot be completed."""


class SearchTool:
    """Tavily AI search tool for retrieving high-quality, AI-ready content."""
    
    def __init__(self):
        self.api_key = os.getenv("TAVILY_API_KEY")
        self.base_url = "https://api.tavily.com/search"

    def search(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        """Perform a search and return a list of Tavily results with content."""
        if not self.api_key:
            raise SearchToolError("TAVILY_API_KEY 未配置，无法检索外部素材")
        if not query.strip():
            raise SearchToolError("搜索词为空，无法检索外部素材")

        payload = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": "advanced",
            "max_results": max_results,
            "include_answer": False,
            "include_images": False,
            "include_raw_content": False,
        }

        try:
            response = requests.post(self.base_url, json=payload, timeout=30)
            response.raise_for_status()
        except requests.HTTPError as exc:
            detail = response.text[:300] if response is not None else str(exc)
            raise SearchToolError(f"Tavily 请求失败: HTTP {response.status_code}: {detail}") from exc
        except requests.RequestException as exc:
            raise SearchToolError(f"Tavily 请求失败: {exc}") from exc

        data = response.json()
        results = data.get("results", [])
        if not isinstance(results, list):
            raise SearchToolError("Tavily 返回格式异常：results 不是列表")
        return results

    def get_context(self, query: str, max_results: int = 3) -> dict[str, Any]:
        """Return formatted LLM context plus structured diagnostics."""
        results = self.search(query, max_results)
        if not results:
            raise SearchToolError(f"Tavily 未返回相关素材，搜索词: {query}")
        
        context_parts = []
        sources = []
        for i, res in enumerate(results, 1):
            title = str(res.get("title") or "").strip()
            url = str(res.get("url") or "").strip()
            content = str(res.get("content") or "").strip()
            if not content:
                continue
            sources.append({"title": title, "url": url})
            context_parts.append(f"Source {i}: {title}\nURL: {url}\nContent: {content}")

        if not context_parts:
            raise SearchToolError(f"Tavily 返回了 {len(results)} 条结果，但没有可用正文素材")
        
        return {
            "query": query,
            "result_count": len(results),
            "usable_count": len(context_parts),
            "sources": sources,
            "context": "\n\n".join(context_parts),
        }
