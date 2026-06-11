"""Application service layer for the local content workspace."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

import config
from agents.inspiration_pipeline import INSPIRATION_COLUMNS, build_inspiration_pool, load_manual_inspirations
from agents.ip_content_pipeline import (
    ConsistencyGatekeeper,
    IPContentPipeline,
    PlatformDraft,
    ScenarioEngineer,
    TopicFact,
    TopicOutline,
    TrendScout,
    BusinessInsightTranslator,
    save_pipeline_outputs,
)
from collectors.ai_news_collector import NEWS_COLUMNS, collect_ai_news_candidates
from utils import file_saver


def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []
    return df.fillna("").to_dict(orient="records")


def _read_csv(path: str, columns: list[str]) -> pd.DataFrame:
    file_path = Path(path)
    if not file_path.exists():
        return pd.DataFrame(columns=columns)
    df = pd.read_csv(file_path, encoding="utf-8-sig")
    for column in columns:
        if column not in df.columns:
            df[column] = ""
    return df[columns]


def get_dashboard_data() -> dict[str, Any]:
    candidates = _read_csv(config.AI_NEWS_CANDIDATES_PATH, NEWS_COLUMNS)
    inspirations = load_manual_inspirations()
    approved_dir = Path(config.IP_APPROVED_OUTPUT_DIR)
    approved_files = sorted(approved_dir.glob("*.md"), key=lambda path: path.stat().st_mtime, reverse=True) if approved_dir.exists() else []

    return {
        "candidates": _records(candidates),
        "inspirations": _records(inspirations),
        "approved_files": [],
        "llm_enabled": config.IP_PIPELINE_USE_LLM,
        "counts": {
            "candidates": len(candidates),
            "selected_candidates": len(candidates[candidates.get("status", "") == "selected"]) if not candidates.empty else 0,
            "inspirations": len(inspirations),
            "approved_files": len(approved_files),
        },
    }


def collect_news() -> dict[str, Any]:
    candidates = collect_ai_news_candidates()
    return {
        "message": f"采集完成，共 {len(candidates)} 条候选消息。",
        "candidates": _records(candidates),
    }


def update_candidate_status(row_index: int, status: str) -> dict[str, Any]:
    candidates = _read_csv(config.AI_NEWS_CANDIDATES_PATH, NEWS_COLUMNS)
    if row_index < 0 or row_index >= len(candidates):
        raise ValueError("候选消息不存在")
    candidates.at[row_index, "status"] = status
    file_saver.save_dataframe(candidates, config.AI_NEWS_CANDIDATES_PATH)
    return {"message": "状态已更新", "candidate": candidates.iloc[row_index].fillna("").to_dict()}


def add_inspiration(payload: dict[str, Any]) -> dict[str, Any]:
    inspirations = load_manual_inspirations()
    new_item = {
        "title": str(payload.get("title", "")).strip(),
        "content": str(payload.get("content", "")).strip(),
        "url": str(payload.get("url", "")).strip(),
        "source": str(payload.get("source", "个人输入")).strip() or "个人输入",
        "type": str(payload.get("type", "practice_insight")).strip() or "practice_insight",
        "tags": str(payload.get("tags", "")).strip(),
        "created_at": str(payload.get("created_at", "")).strip() or datetime.now().strftime("%Y-%m-%d"),
    }
    if not new_item["title"] and not new_item["content"]:
        raise ValueError("标题和内容不能同时为空")

    updated = pd.concat([inspirations, pd.DataFrame([new_item])], ignore_index=True)
    updated.drop_duplicates(subset=["title", "content"], inplace=True, keep="first")
    updated.reset_index(drop=True, inplace=True)
    file_saver.save_dataframe(updated, config.INSPIRATION_INPUT_PATH)
    return {"message": "灵感已保存", "inspirations": _records(updated)}


def delete_inspiration(index: int) -> dict[str, Any]:
    inspirations = load_manual_inspirations()
    if index < 0 or index >= len(inspirations):
        raise ValueError("灵感不存在")
    
    updated = inspirations.drop(index)
    updated.reset_index(drop=True, inplace=True)
    file_saver.save_dataframe(updated, config.INSPIRATION_INPUT_PATH)
    return {"message": "灵感已删除", "inspirations": _records(updated)}


def promote_selected_candidates() -> dict[str, Any]:
    candidates = _read_csv(config.AI_NEWS_CANDIDATES_PATH, NEWS_COLUMNS)
    if candidates.empty:
        return {"message": "没有候选消息可加入灵感池", "inspirations": _records(load_manual_inspirations())}

    selected = candidates[candidates["status"].fillna("").astype(str).str.lower() == "selected"].copy()
    if selected.empty:
        return {"message": "还没有标记 selected 的候选消息", "inspirations": _records(load_manual_inspirations())}

    selected["type"] = "ai_news"
    selected = selected[INSPIRATION_COLUMNS]
    inspirations = load_manual_inspirations()
    updated = pd.concat([inspirations, selected], ignore_index=True)
    updated.drop_duplicates(subset=["title", "url"], inplace=True, keep="first")
    updated.reset_index(drop=True, inplace=True)
    file_saver.save_dataframe(updated, config.INSPIRATION_INPUT_PATH)
    return {"message": f"已加入 {len(selected)} 条候选消息到灵感池", "inspirations": _records(updated)}


def generate_content(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    inspiration_pool = build_inspiration_pool(None, include_manual=True)
    if inspiration_pool.empty:
        raise ValueError("灵感池为空，请先添加消息或实践感悟")

    if payload and "selected_indices" in payload:
        indices = payload["selected_indices"]
        if not indices:
            raise ValueError("未勾选任何灵感内容")
        inspiration_pool = inspiration_pool.iloc[indices].copy()
        inspiration_pool.reset_index(drop=True, inplace=True)

    result = IPContentPipeline().run(inspiration_pool)
    approved_files = [
        path for key, path in result.output_files.items()
        if key.startswith("approved_")
    ]
    return {
        "message": "内容生成完成",
        "llm_enabled": config.IP_PIPELINE_USE_LLM,
        "counts": {
            "facts": len(result.facts),
            "outlines": len(result.outlines),
            "drafts": len(result.drafts),
            "approved": len(result.approved),
        },
        "approved_files": approved_files,
        "output_files": result.output_files,
    }


def generate_facts(payload: dict[str, Any]) -> dict[str, Any]:
    inspirations = load_manual_inspirations()
    indices = payload.get("selected_indices", [])
    if not indices:
        raise ValueError("请先勾选灵感")
    selected = inspirations.iloc[indices].copy()
    selected.reset_index(drop=True, inplace=True)
    facts = TrendScout().run(selected)
    return {"message": f"已生成 {len(facts)} 条事实", "facts": [fact.__dict__ for fact in facts]}


def generate_outlines(payload: dict[str, Any]) -> dict[str, Any]:
    raw_facts = payload.get("facts", [])
    if not raw_facts:
        raise ValueError("请先勾选事实")
    facts = [
        TopicFact(
            topic_id=str(item.get("topic_id", f"T{idx + 1:03d}")),
            fact=str(item.get("fact", "")),
            source_titles=list(item.get("source_titles", [])),
            source_urls=list(item.get("source_urls", [])),
            evidence_count=int(item.get("evidence_count", 1) or 1),
            discussion_score=float(item.get("discussion_score", 0) or 0),
            reason=str(item.get("reason", "人工编辑")),
        )
        for idx, item in enumerate(raw_facts)
        if str(item.get("fact", "")).strip()
    ]
    outlines = BusinessInsightTranslator().run(facts)
    return {"message": f"已生成 {len(outlines)} 个大纲", "outlines": [outline.__dict__ for outline in outlines]}


def generate_drafts(payload: dict[str, Any]) -> dict[str, Any]:
    raw_outlines = payload.get("outlines", [])
    if not raw_outlines:
        raise ValueError("请先勾选大纲")
    outlines = [
        TopicOutline(
            topic_id=str(item.get("topic_id", f"T{idx + 1:03d}")),
            title_hook=str(item.get("title_hook", "")),
            anxiety_background=str(item.get("anxiety_background", "")),
            technical_breakdown=str(item.get("technical_breakdown", "")),
            practical_solution=str(item.get("practical_solution", "")),
            private_domain_hook=str(item.get("private_domain_hook", "")),
            content_angle=str(item.get("content_angle", "")),
        )
        for idx, item in enumerate(raw_outlines)
        if str(item.get("title_hook", "")).strip()
    ]
    drafts = ScenarioEngineer().run(outlines)
    return {"message": f"已生成 {len(drafts)} 条初稿", "drafts": [draft.__dict__ for draft in drafts]}


def review_drafts(payload: dict[str, Any]) -> dict[str, Any]:
    raw_drafts = payload.get("drafts", [])
    if not raw_drafts:
        raise ValueError("请先勾选初稿")
    drafts = [
        PlatformDraft(
            topic_id=str(item.get("topic_id", f"T{idx + 1:03d}")),
            platform=str(item.get("platform", "wechat_article")),
            title=str(item.get("title", "")),
            body=str(item.get("body", "")),
            word_count=len(str(item.get("body", ""))),
        )
        for idx, item in enumerate(raw_drafts)
        if str(item.get("body", "")).strip()
    ]
    reviews = ConsistencyGatekeeper().run(drafts)
    approved_keys = {(review.topic_id, review.platform) for review in reviews if review.passed}
    approved = [draft for draft in drafts if (draft.topic_id, draft.platform) in approved_keys]
    output_files = save_pipeline_outputs([], [], drafts, reviews, approved)
    approved_files = [path for key, path in output_files.items() if key.startswith("approved_")]
    return {
        "message": f"质检完成，通过 {len(approved)} 条，需修改 {len(drafts) - len(approved)} 条",
        "reviews": [review.__dict__ for review in reviews],
        "approved_files": approved_files,
    }


def read_file_content(path: str) -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        raise ValueError("文件不存在")
    
    # 安全检查：只允许读取 output 目录下的文件
    try:
        file_path.resolve().relative_to(Path(config.OUTPUT_DIR).resolve())
    except ValueError:
        raise ValueError("无权访问该文件")
        
    return {"content": file_path.read_text(encoding="utf-8")}
