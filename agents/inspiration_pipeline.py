"""Build an inspiration pool from AI news and personal practice notes."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

import config
from utils import file_saver
from utils.db_manager import DBManager

INSPIRATION_COLUMNS = ["title", "content", "url", "source", "type", "tags", "created_at"]

def load_manual_inspirations(path: str | None = None) -> pd.DataFrame:
    db = DBManager()
    results = db.fetch_all("SELECT title, content, url, source, type, tags, created_at FROM inspirations")
    return pd.DataFrame(results)



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
    db = DBManager()
    
    # Note: scraped_items are now handled by the collector/web_app and stored in ai_news_candidates.
    # This function now only focuses on returning the curated inspiration pool.

    # Always return the current state of the DB
    inspiration_pool = pd.DataFrame(db.fetch_all("SELECT * FROM inspirations"))
    
    if inspiration_pool.empty:
        return pd.DataFrame(columns=INSPIRATION_COLUMNS)
        
    # Clean up and deduplicate in memory before returning
    inspiration_pool["title"] = inspiration_pool["title"].fillna("").astype(str).str.strip()
    inspiration_pool["content"] = inspiration_pool["content"].fillna("").astype(str).str.strip()
    inspiration_pool = inspiration_pool[(inspiration_pool["title"] != "") | (inspiration_pool["content"] != "")]
    inspiration_pool.drop_duplicates(subset=["title", "content"], inplace=True, keep="first")
    inspiration_pool.reset_index(drop=True, inplace=True)
    
    return inspiration_pool[INSPIRATION_COLUMNS]




def append_selected_news_to_inspirations(
    candidates_path: str | None = None,
    inspiration_path: str | None = None,
) -> pd.DataFrame:
    db = DBManager()
    candidates = pd.DataFrame(db.fetch_all("SELECT * FROM ai_news_candidates"))
    if candidates.empty and candidates_path:
        candidate_file = Path(candidates_path)
        if candidate_file.exists():
            candidates = pd.read_csv(candidate_file, encoding="utf-8-sig")
    if candidates.empty or "status" not in candidates.columns:
        return load_manual_inspirations(inspiration_path)

    selected = candidates[candidates["status"].fillna("").astype(str).str.lower() == "selected"].copy()
    if selected.empty:
        return load_manual_inspirations(inspiration_path)

    selected["type"] = "ai_news"
    # Ensure columns match DB
    cols = ["title", "content", "url", "source", "type", "tags", "created_at"]
    for col in cols:
        if col not in selected.columns:
            selected[col] = ""
    
    # Save selected news to DB
    db.save_dataframe(selected[cols], 'inspirations', if_exists='append')
    
    return load_manual_inspirations(inspiration_path)

