"""Collect AI news candidates for human review before they enter the inspiration pool."""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urljoin
from xml.etree import ElementTree as ET

import pandas as pd
import requests
from bs4 import BeautifulSoup

import config
from utils import file_saver


NEWS_COLUMNS = ["title", "content", "url", "source", "type", "tags", "published_at", "created_at", "relevance_score", "status"]


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _parse_date(value: str) -> datetime | None:
    value = _safe_text(value)
    if not value:
        return None
    try:
        if value.isdigit():
            return datetime.fromtimestamp(int(value), tz=timezone.utc)
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        pass
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


def _format_date(value: str) -> str:
    parsed = _parse_date(value)
    if parsed is None:
        return _safe_text(value)
    return parsed.date().isoformat()


def _is_recent_enough(value: str) -> bool:
    minimum = _parse_date(config.AI_NEWS_MIN_PUBLISHED_DATE)
    if minimum is None:
        return True
    parsed = _parse_date(value)
    if parsed is None:
        return True
    return parsed >= minimum


def _score_relevance(title: str, content: str, source: str = "") -> tuple[float, str]:
    text = f"{title} {content}".lower()
    hits = []
    for keyword in config.AI_NEWS_RELEVANCE_KEYWORDS:
        if keyword.lower() in text:
            hits.append(keyword)

    high_value_signals = [
        "case study", "customer story", "implementation", "production", "deployment",
        "lessons learned", "postmortem", "案例", "落地", "实践", "复盘", "踩坑", "生产环境",
        "benchmark", "leaderboard", "evaluation", "eval", "lmarena", "chatbot arena", "swe-bench",
    ]
    promo_signals = ["announce", "announcing", "introducing", "launch", "release", "new model", "what's new", "this month", "generally available"]
    practice_sources = ["Chip Huyen Blog", "The Gradient", "Latent Space"]
    discussion_sources = ["Reddit LocalLLaMA Latest", "Reddit MachineLearning Latest", "Hacker News AI Latest", "Hacker News AI Benchmarks", "Hacker News AI Business"]
    vendor_sources = ["Google Cloud AI Blog", "AWS Machine Learning Blog", "Microsoft AI Customer Stories", "Hugging Face Blog"]

    generic_hits = {hit for hit in hits if hit.lower() in {"ai", "agent", "agents", "llm", "model", "rag"}}
    specific_hits = set(hits) - generic_hits

    score = 1.0 + len(specific_hits) * 0.9 + len(generic_hits) * 0.25
    score += sum(2.2 for signal in high_value_signals if signal in text)
    score -= sum(1.2 for signal in promo_signals if signal in text)
    if source in practice_sources:
        score += 1.2
    if source in discussion_sources:
        score += 2.0
    if source in vendor_sources:
        score -= 1.0
    score = min(10.0, max(0.0, score))
    return round(score, 2), ";".join(dict.fromkeys(hits))


def _normalize_item(title: str, content: str, url: str, source: str, published_at: str = "") -> dict[str, Any]:
    score, tags = _score_relevance(title, content, source)
    return {
        "title": _safe_text(title),
        "content": _safe_text(content),
        "url": _safe_text(url),
        "source": source,
        "type": "ai_news_candidate",
        "tags": tags,
        "published_at": _format_date(published_at),
        "created_at": datetime.now().strftime("%Y-%m-%d"),
        "relevance_score": score,
        "status": "candidate",
    }


def _collect_rss_source(source: dict[str, str]) -> list[dict[str, Any]]:
    response = requests.get(source["url"], headers=config.SCRAPER_HEADERS, timeout=20)
    response.raise_for_status()
    root = ET.fromstring(response.content)

    items = []
    channel_items = root.findall(".//item")
    atom_items = root.findall("{http://www.w3.org/2005/Atom}entry")

    for item in channel_items[: config.AI_NEWS_MAX_ITEMS_PER_SOURCE]:
        title = item.findtext("title") or ""
        link = item.findtext("link") or ""
        description = item.findtext("description") or item.findtext("summary") or ""
        published_at = item.findtext("pubDate") or item.findtext("published") or item.findtext("updated") or ""
        content = BeautifulSoup(description, "lxml").get_text(" ", strip=True)
        if _is_recent_enough(published_at):
            items.append(_normalize_item(title, content, link, source["name"], published_at))

    for item in atom_items[: config.AI_NEWS_MAX_ITEMS_PER_SOURCE]:
        title = item.findtext("{http://www.w3.org/2005/Atom}title") or ""
        link_element = item.find("{http://www.w3.org/2005/Atom}link")
        link = link_element.attrib.get("href", "") if link_element is not None else ""
        summary = item.findtext("{http://www.w3.org/2005/Atom}summary") or ""
        published_at = item.findtext("{http://www.w3.org/2005/Atom}published") or item.findtext("{http://www.w3.org/2005/Atom}updated") or ""
        content = BeautifulSoup(summary, "lxml").get_text(" ", strip=True)
        if _is_recent_enough(published_at):
            items.append(_normalize_item(title, content, link, source["name"], published_at))

    return items


def _collect_reddit_source(source: dict[str, str]) -> list[dict[str, Any]]:
    response = requests.get(source["url"], headers={**config.SCRAPER_HEADERS, "User-Agent": "ai-marketing-workbench/1.0"}, timeout=20)
    response.raise_for_status()
    data = response.json()
    items = []
    for child in data.get("data", {}).get("children", [])[: config.AI_NEWS_MAX_ITEMS_PER_SOURCE]:
        item = child.get("data", {})
        title = item.get("title", "")
        content = item.get("selftext", "")
        permalink = item.get("permalink", "")
        url = item.get("url") or urljoin("https://www.reddit.com", permalink)
        created = str(int(item.get("created_utc", 0))) if item.get("created_utc") else ""
        if _is_recent_enough(created):
            items.append(_normalize_item(title, content, url, source["name"], created))
    return items


def _collect_hn_algolia_source(source: dict[str, str]) -> list[dict[str, Any]]:
    response = requests.get(source["url"], headers=config.SCRAPER_HEADERS, timeout=20)
    response.raise_for_status()
    data = response.json()
    items = []
    for hit in data.get("hits", [])[: config.AI_NEWS_MAX_ITEMS_PER_SOURCE]:
        title = hit.get("title") or hit.get("story_title") or ""
        url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
        content = hit.get("_highlightResult", {}).get("title", {}).get("value", "")
        content = BeautifulSoup(content, "lxml").get_text(" ", strip=True)
        published_at = hit.get("created_at", "")
        if _is_recent_enough(published_at):
            items.append(_normalize_item(title, content, url, source["name"], published_at))
    return items


def _collect_html_source(source: dict[str, str]) -> list[dict[str, Any]]:
    response = requests.get(source["url"], headers=config.SCRAPER_HEADERS, timeout=20)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")

    items = []
    for link in soup.select("a"):
        title = link.get_text(" ", strip=True)
        href = link.get("href", "")
        if not title or len(title) < 8:
            continue
        if not href:
            continue
        url = urljoin(source["url"], href)
        items.append(_normalize_item(title, "", url, source["name"]))
        if len(items) >= config.AI_NEWS_MAX_ITEMS_PER_SOURCE:
            break
    return items


def collect_ai_news_candidates(sources: list[dict[str, str]] | None = None) -> pd.DataFrame:
    sources = sources or config.AI_NEWS_SOURCES
    all_items = []

    print("\n[AI消息采集] 开始采集候选消息...")
    for source in sources:
        try:
            print(f"  -> {source['name']} ({source['type']})")
            if source["type"] == "rss":
                items = _collect_rss_source(source)
            elif source["type"] == "html":
                items = _collect_html_source(source)
            elif source["type"] == "reddit":
                items = _collect_reddit_source(source)
            elif source["type"] == "hn_algolia":
                items = _collect_hn_algolia_source(source)
            else:
                print(f"     跳过未知类型: {source['type']}")
                continue
            all_items.extend(items)
            print(f"     获取 {len(items)} 条")
        except Exception as exc:
            print(f"     采集失败: {exc}")

    if not all_items:
        return pd.DataFrame(columns=NEWS_COLUMNS)

    candidates = pd.DataFrame(all_items)
    candidates = candidates[NEWS_COLUMNS]
    candidates["_dedupe_title"] = candidates["title"].fillna("").astype(str).str.lower().str.strip()
    candidates.drop_duplicates(subset=["_dedupe_title"], inplace=True, keep="first")
    candidates.drop(columns=["_dedupe_title"], inplace=True)
    candidates["_sort_time"] = pd.to_datetime(candidates["published_at"], errors="coerce", utc=True)
    candidates.sort_values(by="_sort_time", ascending=False, inplace=True, na_position="last")
    candidates.drop(columns=["_sort_time"], inplace=True)
    candidates.reset_index(drop=True, inplace=True)
    file_saver.save_dataframe(candidates, config.AI_NEWS_CANDIDATES_PATH)
    return candidates
