"""Build an inspiration pool from AI news and personal practice notes."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

import config
from utils import file_saver


INSPIRATION_COLUMNS = ["title", "content", "url", "source", "type", "tags", "created_at"]


def load_manual_inspirations(path: str | None = None) -> pd.DataFrame:
    source_path = Path(path or config.INSPIRATION_INPUT_PATH)
    if not source_path.exists():
        return pd.DataFrame(columns=INSPIRATION_COLUMNS)

    df = pd.read_csv(source_path, encoding="utf-8-sig")
    for column in INSPIRATION_COLUMNS:
        if column not in df.columns:
            df[column] = ""
    return df[INSPIRATION_COLUMNS]


def normalize_scraped_items(items: list[dict[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    if isinstance(items, pd.DataFrame):
        df = items.copy()
    else:
        df = pd.DataFrame(items)

    if df.empty:
        return pd.DataFrame(columns=INSPIRATION_COLUMNS)

    for column in ["title", "content", "url", "source"]:
        if column not in df.columns:
            df[column] = ""

    normalized = pd.DataFrame()
    normalized["title"] = df["title"].fillna("").astype(str)
    normalized["content"] = df["content"].fillna("").astype(str)
    normalized["url"] = df["url"].fillna("").astype(str)
    normalized["source"] = df["source"].fillna("scraped_ai_news").astype(str)
    normalized["type"] = "ai_news"
    normalized["tags"] = ""
    normalized["created_at"] = datetime.now().strftime("%Y-%m-%d")
    return normalized[INSPIRATION_COLUMNS]


def build_inspiration_pool(
    scraped_items: list[dict[str, Any]] | pd.DataFrame | None = None,
    include_manual: bool = True,
) -> pd.DataFrame:
    frames = []
    if include_manual:
        frames.append(load_manual_inspirations())
    if scraped_items is not None:
        frames.append(normalize_scraped_items(scraped_items))

    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return pd.DataFrame(columns=INSPIRATION_COLUMNS)

    inspiration_pool = pd.concat(frames, ignore_index=True)
    inspiration_pool["title"] = inspiration_pool["title"].fillna("").astype(str).str.strip()
    inspiration_pool["content"] = inspiration_pool["content"].fillna("").astype(str).str.strip()
    inspiration_pool = inspiration_pool[(inspiration_pool["title"] != "") | (inspiration_pool["content"] != "")]
    inspiration_pool.drop_duplicates(subset=["title", "content"], inplace=True, keep="first")
    inspiration_pool.reset_index(drop=True, inplace=True)

    file_saver.save_dataframe(inspiration_pool, config.INSPIRATION_POOL_PATH)
    return inspiration_pool


def append_selected_news_to_inspirations(
    candidates_path: str | None = None,
    inspiration_path: str | None = None,
) -> pd.DataFrame:
    candidate_file = Path(candidates_path or config.AI_NEWS_CANDIDATES_PATH)
    inspiration_file = Path(inspiration_path or config.INSPIRATION_INPUT_PATH)
    if not candidate_file.exists():
        return load_manual_inspirations(inspiration_path)

    candidates = pd.read_csv(candidate_file, encoding="utf-8-sig")
    if "status" not in candidates.columns:
        return load_manual_inspirations(inspiration_path)

    selected = candidates[candidates["status"].fillna("").astype(str).str.lower() == "selected"].copy()
    if selected.empty:
        return load_manual_inspirations(inspiration_path)

    selected["type"] = "ai_news"
    selected = selected[INSPIRATION_COLUMNS]

    manual = load_manual_inspirations(inspiration_path)
    merged = pd.concat([manual, selected], ignore_index=True)
    merged.drop_duplicates(subset=["title", "url"], inplace=True, keep="first")
    merged.reset_index(drop=True, inplace=True)
    file_saver.save_dataframe(merged, str(inspiration_file))
    return merged
