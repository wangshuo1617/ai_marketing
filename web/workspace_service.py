"""Application service layer for the local content workspace."""

from __future__ import annotations

import json
import re
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
)
from collectors.ai_news_collector import NEWS_COLUMNS, collect_ai_news_candidates
from utils import file_saver
from utils.db_manager import DBManager
from utils.image_generator import generate_image_file
from utils.llm_reply import llm_reply
from utils.prompt_loader import load_prompt



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
    db = DBManager()
    candidates = pd.DataFrame(db.fetch_all("SELECT * FROM ai_news_candidates"))
    inspirations = load_manual_inspirations()
    facts = db.fetch_all("SELECT id, fact, discussion_score, reason, created_at FROM topic_facts ORDER BY id DESC LIMIT 20")
    outlines = db.fetch_all(
        """
        SELECT id, fact_id, title_hook, anxiety_background, technical_breakdown,
               practical_solution, private_domain_hook, content_angle, created_at
        FROM topic_outlines
        ORDER BY id DESC
        LIMIT 20
        """
    )
    drafts = db.fetch_all(
        """
        SELECT id, outline_id, platform, title, body, word_count, score, passed, issues, created_at
        FROM platform_drafts
        ORDER BY id DESC
        LIMIT 30
        """
    )
    approved_drafts = db.fetch_all("SELECT * FROM platform_drafts WHERE passed = 1")

    return {
        "candidates": _records(candidates),
        "inspirations": _records(inspirations),
        "facts": [
            {
                "topic_id": str(item.get("id", "")),
                "fact": item.get("fact", ""),
                "source_titles": [],
                "source_urls": [],
                "evidence_count": 1,
                "discussion_score": item.get("discussion_score", 0) or 0,
                "reason": item.get("reason", ""),
            }
            for item in reversed(facts)
        ],
        "outlines": [
            {
                "topic_id": str(item.get("id", "")),
                "title_hook": item.get("title_hook", ""),
                "anxiety_background": item.get("anxiety_background", ""),
                "technical_breakdown": item.get("technical_breakdown", ""),
                "practical_solution": item.get("practical_solution", ""),
                "private_domain_hook": item.get("private_domain_hook", ""),
                "content_angle": item.get("content_angle", ""),
            }
            for item in reversed(outlines)
        ],
        "drafts": [
            {
                "topic_id": str(item.get("id", "")),
                "platform": item.get("platform", ""),
                "title": item.get("title", ""),
                "body": item.get("body", ""),
                "word_count": item.get("word_count", 0) or len(str(item.get("body", ""))),
            }
            for item in reversed(drafts)
        ],
        "approved_files": [],
        "llm_enabled": config.IP_PIPELINE_USE_LLM,
        "counts": {
            "candidates": len(candidates),
            "selected_candidates": len(candidates[candidates.get("status", "") == "selected"]) if not candidates.empty else 0,
            "inspirations": len(inspirations),
            "facts": len(facts),
            "outlines": len(outlines),
            "drafts": len(drafts),
            "approved_files": len(approved_drafts),
        },
    }


def _insert_cover_into_markdown(markdown: str, cover: dict[str, Any]) -> str:
    cover_line = f"![{cover['alt_text']}]({cover['public_url']})"
    lines = markdown.splitlines()
    if not lines:
        return cover_line
    if lines[0].startswith("# "):
        return "\n".join([lines[0], "", cover_line, "", *lines[1:]]).strip()
    return "\n".join([cover_line, "", *lines]).strip()


def get_draft(draft_id: int, include_complete: bool = True) -> dict[str, Any]:
    db = DBManager()
    rows = db.fetch_all("SELECT * FROM platform_drafts WHERE id = ?", (draft_id,))
    if not rows:
        raise ValueError("初稿不存在")
    draft = rows[0]
    if not include_complete:
        return draft
    complete_rows = db.fetch_all(
        """
        SELECT id, title, markdown, version, updated_at
        FROM complete_drafts
        WHERE draft_id = ?
        ORDER BY version DESC, id DESC
        LIMIT 1
        """,
        (draft_id,),
    )
    if complete_rows:
        draft["complete_draft"] = complete_rows[0]
    return draft


def _strip_title_from_markdown(markdown: str) -> tuple[str, str]:
    lines = markdown.splitlines()
    if lines and lines[0].startswith("# "):
        title = lines[0][2:].strip()
        body = "\n".join(lines[1:]).strip()
        return title, body
    return "", markdown.strip()


def _extract_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    match = re.search(r"```json\s*(.*?)\s*```", cleaned, re.S | re.I)
    if match:
        cleaned = match.group(1).strip()
    else:
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if match:
            cleaned = match.group(0)
    return json.loads(cleaned)


def _markdown_blocks(markdown: str) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    block_index = 0
    in_code_block = False
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block or not stripped:
            continue
        if stripped.startswith("#"):
            block_index += 1
            level = len(stripped) - len(stripped.lstrip("#"))
            blocks.append({"block_index": block_index, "type": f"h{min(level, 6)}", "text": stripped.lstrip("#").strip()[:360]})
            continue
        if stripped.startswith(("!", "|", ">")):
            continue
        block_type = "list_item" if stripped.startswith(("- ", "* ", "+ ")) or re.match(r"^\d+[.)、]\s+", stripped) else "paragraph"
        if block_type == "paragraph" and len(stripped) < 8:
            continue
        block_index += 1
        blocks.append({"block_index": block_index, "type": block_type, "text": stripped[:360]})
    return blocks


def _build_visual_plan(title: str, markdown: str, max_images: int) -> dict[str, Any]:
    blocks = _markdown_blocks(markdown)
    if not blocks:
        return {"cover": {}, "images": [], "blocks": []}

    # 长文章压缩：保留全部标题块 + 均匀采样段落，避免超出 API 上下文
    MAX_BLOCKS = 30
    compact = [dict(b, text=b["text"][:80]) for b in blocks]
    if len(compact) > MAX_BLOCKS:
        headings = [b for b in compact if b["type"].startswith("h")]
        paragraphs = [b for b in compact if not b["type"].startswith("h")]
        slots = max(1, MAX_BLOCKS - len(headings))
        step = max(1, len(paragraphs) // slots)
        sampled = paragraphs[::step][:slots]
        trimmed = sorted(headings + sampled, key=lambda b: b["block_index"])
    else:
        trimmed = compact

    prompt = load_prompt(
        "image_workflow/visual_plan.md",
        max_images=max_images,
        title=title,
        blocks_json=json.dumps(trimmed, ensure_ascii=False),
    )
    raw_response = ""
    parse_error = ""
    try:
        raw_response = llm_reply(prompt, temperature=0.3, timeout=300)
        data = _extract_json_object(raw_response)
    except Exception as exc:
        parse_error = str(exc)
        data = {}

    available_blocks = {item["block_index"] for item in blocks}
    raw_images = data.get("images", []) if isinstance(data, dict) else []
    if not isinstance(raw_images, list):
        raw_images = []

    images = []
    used_blocks: set[int] = set()
    rejected_images = []
    for item in raw_images:
        if not isinstance(item, dict):
            rejected_images.append({"item": item, "reason": "not_object"})
            continue
        block_index = int(item.get("insert_after_block", 0) or 0)
        if block_index not in available_blocks or block_index in used_blocks:
            rejected_images.append({"item": item, "reason": "invalid_or_duplicate_block"})
            continue
        prompt_text = str(item.get("prompt", "")).strip()
        alt_text = str(item.get("alt", "")).strip() or "文章配图"
        style_text = str(item.get("visual_style", "")).strip()
        if not prompt_text:
            rejected_images.append({"item": item, "reason": "missing_prompt"})
            continue
        used_blocks.add(block_index)
        images.append({"insert_after_block": block_index, "alt": alt_text, "prompt": prompt_text, "visual_style": style_text})
        if len(images) >= max_images:
            break

    cover = data.get("cover", {}) if isinstance(data, dict) else {}
    if not isinstance(cover, dict):
        cover = {}
    if not str(cover.get("prompt", "")).strip():
        cover = {
            "alt": f"{title}封面图"[:60],
            "prompt": f"为微信公众号文章《{title}》生成一张横版首图封面。风格专业克制，有商业咨询质感，主题围绕企业AI落地、流程资产、人效提升、数据仪表盘或知识工作流。不要真实品牌Logo，不要二维码，不要密集小字。",
        }

    _record_visual_plan_debug(
        {
            "title": title,
            "max_images": max_images,
            "block_count": len(blocks),
            "raw_image_count": len(raw_images),
            "accepted_image_count": len(images),
            "rejected_images": rejected_images,
            "parse_error": parse_error,
            "blocks": blocks,
            "raw_response": raw_response[:12000],
        }
    )

    return {
        "article_summary": str(data.get("article_summary", "")).strip() if isinstance(data, dict) else "",
        "visual_direction": str(data.get("visual_direction", "")).strip() if isinstance(data, dict) else "",
        "cover": cover,
        "images": images,
        "blocks": blocks,
    }


def _record_visual_plan_debug(record: dict[str, Any]) -> None:
    try:
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        record = {"created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), **record}
        with (log_dir / "visual_plan_debug.jsonl").open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _insert_images_after_blocks(markdown: str, images: list[dict[str, Any]]) -> str:
    if not images:
        return markdown
    by_block = {int(item["insert_after_block"]): item for item in images}
    output_lines: list[str] = []
    block_index = 0
    in_code_block = False
    for line in markdown.splitlines():
        stripped = line.strip()
        output_lines.append(line)
        counted = False
        if stripped.startswith("```"):
            in_code_block = not in_code_block
        elif not in_code_block and stripped:
            if stripped.startswith("#"):
                counted = True
            elif not stripped.startswith(("!", "|", ">")):
                counted = stripped.startswith(("- ", "* ", "+ ")) or re.match(r"^\d+[.)、]\s+", stripped) or len(stripped) >= 8
        if counted:
            block_index += 1
            image = by_block.get(block_index)
            if image:
                output_lines.extend(["", f"![{image['alt_text']}]({image['public_url']})", ""])
    return "\n".join(output_lines).strip()


def generate_article_images(payload: dict[str, Any]) -> dict[str, Any]:
    db = DBManager()
    draft_id = int(payload.get("draft_id", -1))
    markdown = str(payload.get("markdown", "")).strip()
    if draft_id <= 0:
        raise ValueError("缺少初稿 ID")
    if not markdown:
        raise ValueError("当前 Markdown 为空，无法生成图片")

    draft_rows = db.fetch_all("SELECT id, title FROM platform_drafts WHERE id = ?", (draft_id,))
    if not draft_rows:
        raise ValueError("初稿不存在")

    markdown_title, _ = _strip_title_from_markdown(markdown)
    title = markdown_title or str(draft_rows[0].get("title") or "未命名初稿")
    max_images = max(1, int(payload.get("max_images") or config.IMAGE_GEN_MAX_IMAGES))
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    visual_plan = _build_visual_plan(title, markdown, max_images)
    cover_plan = visual_plan.get("cover", {})
    plans = visual_plan.get("images", [])
    if not plans:
        raise ValueError("没有找到适合插入图片的位置")

    generated_images = []
    cover = generate_image_file(
        prompt=cover_plan["prompt"],
        draft_id=draft_id,
        image_index=0,
        alt_text=cover_plan["alt"],
        run_id=run_id,
    )
    cover_record = {
        "insert_after_block": 0,
        "alt_text": cover.alt_text,
        "prompt": cover.prompt,
        "local_path": cover.local_path,
        "public_url": cover.public_url,
        "role": "cover",
    }

    for index, plan in enumerate(plans, 1):
        image_prompt = load_prompt(
            "image_workflow/inline_image.md",
            title=title,
            alt_text=plan["alt"],
            visual_prompt=plan["prompt"],
            visual_style=plan.get("visual_style", ""),
        )
        generated = generate_image_file(
            prompt=image_prompt,
            draft_id=draft_id,
            image_index=index,
            alt_text=plan["alt"],
            run_id=run_id,
        )
        image_record = {
            "insert_after_block": int(plan["insert_after_block"]),
            "alt_text": generated.alt_text,
            "prompt": generated.prompt,
            "local_path": generated.local_path,
            "public_url": generated.public_url,
            "role": "inline",
        }
        generated_images.append(image_record)

    updated_markdown = _insert_images_after_blocks(markdown, generated_images)
    updated_markdown = _insert_cover_into_markdown(updated_markdown, cover_record)
    complete_draft_id = db.save_complete_draft(draft_id, title, updated_markdown)
    db.add_draft_image(
        {
            "draft_id": draft_id,
            "complete_draft_id": complete_draft_id,
            "image_index": 0,
            "alt_text": cover_record["alt_text"],
            "prompt": cover_record["prompt"],
            "local_path": cover_record["local_path"],
            "public_url": cover_record["public_url"],
            "markdown_position": "cover:top",
        }
    )
    for index, image in enumerate(generated_images, 1):
        db.add_draft_image(
            {
                "draft_id": draft_id,
                "complete_draft_id": complete_draft_id,
                "image_index": index,
                "alt_text": image["alt_text"],
                "prompt": image["prompt"],
                "local_path": image["local_path"],
                "public_url": image["public_url"],
                "markdown_position": f"block:{image['insert_after_block']}",
            }
        )

    return {
        "message": f"已生成封面并插入 {len(generated_images)} 张正文图片",
        "complete_draft_id": complete_draft_id,
        "markdown": updated_markdown,
        "cover": cover_record,
        "images": generated_images,
    }

def collect_news() -> dict[str, Any]:
    candidates = collect_ai_news_candidates()
    return {
        "message": f"采集完成，共 {len(candidates)} 条候选消息。",
        "candidates": _records(candidates),
    }


def update_candidate_status(row_index: int, status: str) -> dict[str, Any]:
    db = DBManager()
    all_candidates = db.fetch_all("SELECT id FROM ai_news_candidates")
    if row_index < 0 or row_index >= len(all_candidates):
        raise ValueError("候选消息不存在")
    
    candidate_id = all_candidates[row_index]['id']
    db.execute_query("UPDATE ai_news_candidates SET status = ? WHERE id = ?", (status, candidate_id))
    
    updated = db.fetch_all("SELECT * FROM ai_news_candidates WHERE id = ?", (candidate_id,))[0]
    return {"message": "状态已更新", "candidate": updated}

def summarize_candidate(row_index: int) -> dict[str, Any]:
    db = DBManager()
    all_candidates = db.fetch_all("SELECT * FROM ai_news_candidates")
    if row_index < 0 or row_index >= len(all_candidates):
        raise ValueError("候选消息不存在")
    
    candidate = all_candidates[row_index]
    title = candidate.get("title", "")
    content = candidate.get("content", "")
    
    prompt = f"请用中文简明扼要地总结以下 AI 资讯的核心内容（不超过 150 字）：\n\n标题：{title}\n内容：{content}"
    try:
        summary = llm_reply(prompt, temperature=0.3)
    except Exception as e:
        raise ValueError(f"总结生成失败: {e}")
        
    return {"message": "总结完成", "summary": summary}

def add_inspiration(payload: dict[str, Any]) -> dict[str, Any]:
    db = DBManager()
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

    db.add_inspiration(new_item)
    updated = load_manual_inspirations()
    return {"message": "灵感已保存", "inspirations": _records(updated)}


def delete_inspiration(index: int) -> dict[str, Any]:
    db = DBManager()
    inspirations = load_manual_inspirations()
    if index < 0 or index >= len(inspirations):
        raise ValueError("灵感不存在")
    
    all_ids = [row['id'] for row in db.fetch_all("SELECT id FROM inspirations")]
    if index < 0 or index >= len(all_ids):
        raise ValueError("灵感不存在")
    
    db.execute_query("DELETE FROM inspirations WHERE id = ?", (all_ids[index],))
    updated = load_manual_inspirations()
    return {"message": "灵感已删除", "inspirations": _records(updated)}

def update_inspiration(payload: dict[str, Any]) -> dict[str, Any]:
    db = DBManager()
    index = int(payload.get("index", -1))
    all_ids = [row['id'] for row in db.fetch_all("SELECT id FROM inspirations")]
    if index < 0 or index >= len(all_ids):
        raise ValueError("灵感不存在")
    
    db.execute_query(
        "UPDATE inspirations SET title = ?, content = ?, url = ?, source = ?, type = ?, tags = ? WHERE id = ?",
        (
            str(payload.get("title", "")).strip(),
            str(payload.get("content", "")).strip(),
            str(payload.get("url", "")).strip(),
            str(payload.get("source", "")).strip(),
            str(payload.get("type", "")).strip(),
            str(payload.get("tags", "")).strip(),
            all_ids[index]
        )
    )
    updated = load_manual_inspirations()
    return {"message": "灵感已更新", "inspirations": _records(updated)}

def update_fact(payload: dict[str, Any]) -> dict[str, Any]:
    db = DBManager()
    fact_id = int(payload.get("id", -1))
    db.execute_query(
        "UPDATE topic_facts SET fact = ?, reason = ? WHERE id = ?",
        (str(payload.get("fact", "")).strip(), str(payload.get("reason", "")).strip(), fact_id)
    )
    return {"message": "事实已更新"}

def update_outline(payload: dict[str, Any]) -> dict[str, Any]:
    db = DBManager()
    outline_id = int(payload.get("id", -1))
    db.execute_query(
        """UPDATE topic_outlines SET title_hook = ?, anxiety_background = ?, technical_breakdown = ?, 
           practical_solution = ?, private_domain_hook = ?, content_angle = ? WHERE id = ?""",
        (
            str(payload.get("title_hook", "")).strip(),
            str(payload.get("anxiety_background", "")).strip(),
            str(payload.get("technical_breakdown", "")).strip(),
            str(payload.get("practical_solution", "")).strip(),
            str(payload.get("private_domain_hook", "")).strip(),
            str(payload.get("content_angle", "")).strip(),
            outline_id
        )
    )
    return {"message": "大纲已更新"}

def update_draft(payload: dict[str, Any]) -> dict[str, Any]:
    db = DBManager()
    draft_id = int(payload.get("id", -1))
    db.execute_query(
        "UPDATE platform_drafts SET title = ?, body = ? WHERE id = ?",
        (str(payload.get("title", "")).strip(), str(payload.get("body", "")).strip(), draft_id)
    )
    return {"message": "初稿已更新"}

def rewrite_draft(payload: dict[str, Any]) -> dict[str, Any]:
    db = DBManager()
    draft_id = int(payload.get("id", -1))
    current_title = str(payload.get("title", "")).strip()
    current_body = str(payload.get("body", "")).strip()
    feedback = str(payload.get("feedback", "")).strip()
    
    if not feedback:
        raise ValueError("人工意见不能为空")
        
    # Fetch the associated outline to provide context to the LLM
    draft_rows = db.fetch_all("SELECT outline_id, platform FROM platform_drafts WHERE id = ?", (draft_id,))
    if not draft_rows:
        raise ValueError("初稿不存在")
        
    outline_id = draft_rows[0]["outline_id"]
    platform = draft_rows[0]["platform"]
    
    outline_context = ""
    if outline_id:
        outline_rows = db.fetch_all("SELECT * FROM topic_outlines WHERE id = ?", (outline_id,))
        if outline_rows:
            o = outline_rows[0]
            outline_context = f"""
【原始大纲参考】
- 标题Hook: {o.get('title_hook', '')}
- 焦虑背景: {o.get('anxiety_background', '')}
- 技术/商业拆解: {o.get('technical_breakdown', '')}
- 实操解法: {o.get('practical_solution', '')}
- 导流钩子: {o.get('private_domain_hook', '')}
"""

    prompt = f"""你是一个资深的商业内容编辑。请根据用户的【人工修改意见】，对当前的【初稿】进行重写。

【平台要求】
目标平台：{platform}
（如果是微信公众号，请保持深度长文格式；如果是视频号/抖音，请保持带有[画面]和[口播]的脚本格式）

{outline_context}

【当前初稿】
标题：{current_title}
正文：
{current_body}

【人工修改意见】
{feedback}

请严格按照人工意见进行修改，保持未被要求修改的部分的原始风格。
输出严格 JSON 对象，字段: title, body。不要输出任何其他解释性文字。
"""
    
    try:
        import json
        import re
        response = llm_reply(prompt, temperature=0.4).strip()
        match = re.search(r"```json\s*(.*?)\s*```", response, re.S | re.I)
        if match:
            response = match.group(1).strip()
        data = json.loads(response)
        
        new_title = data.get("title", current_title)
        new_body = data.get("body", current_body)
        
        return {
            "message": "重写成功",
            "title": new_title,
            "body": new_body
        }
    except Exception as e:
        raise ValueError(f"AI重写失败: {e}")

def approve_draft(payload: dict[str, Any]) -> dict[str, Any]:
    db = DBManager()
    draft_id = int(payload.get("id", -1))
    
    # Fetch the draft details to save it to a file
    draft_rows = db.fetch_all("SELECT * FROM platform_drafts WHERE id = ?", (draft_id,))
    if not draft_rows:
        raise ValueError("初稿不存在")
        
    draft_data = draft_rows[0]
    
    # Update DB status
    db.execute_query(
        "UPDATE platform_drafts SET passed = 1, score = 10.0, issues = '[]' WHERE id = ?",
        (draft_id,)
    )
    
    # Save to file
    from agents.ip_content_pipeline import PlatformDraft
    from utils.file_saver import save_pipeline_outputs
    
    draft = PlatformDraft(
        topic_id=str(draft_data["outline_id"] or draft_id),
        platform=draft_data["platform"],
        title=draft_data["title"],
        body=draft_data["body"],
        word_count=draft_data["word_count"]
    )
    
    # We need a dummy review result to pass to save_pipeline_outputs
    from agents.ip_content_pipeline import ReviewResult
    review = ReviewResult(
        topic_id=draft.topic_id,
        platform=draft.platform,
        passed=True,
        score=10.0,
        issues=[]
    )
    
    output_files = save_pipeline_outputs([], [], [draft], [review], [draft])
    approved_files = [path for key, path in output_files.items() if key.startswith("approved_")]
    
    return {
        "message": "初稿已批准为成品",
        "approved_files": approved_files
    }

def promote_selected_candidates() -> dict[str, Any]:
    from agents.inspiration_pipeline import append_selected_news_to_inspirations
    updated = append_selected_news_to_inspirations()
    return {"message": f"已处理候选消息", "inspirations": _records(updated)}


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
    return {
        "message": "内容生成完成",
        "llm_enabled": config.IP_PIPELINE_USE_LLM,
        "counts": {
            "facts": len(result.facts),
            "outlines": len(result.outlines),
            "drafts": len(result.drafts),
            "approved": len(result.approved),
        },
        "approved_files": [], # Now in DB
        "output_files": {}, # No longer using files
    }


def generate_facts(payload: dict[str, Any]) -> dict[str, Any]:
    db = DBManager()
    inspiration_pool = build_inspiration_pool(None, include_manual=True)
    indices = payload.get("selected_indices", [])
    if not indices:
        raise ValueError("请先勾选灵感")
    selected = inspiration_pool.iloc[indices].copy()
    selected.reset_index(drop=True, inplace=True)
    facts = TrendScout().run(selected)
    for fact in facts:
        source_ids = []
        for title in fact.source_titles:
            rows = db.fetch_all("SELECT id FROM inspirations WHERE title = ? ORDER BY id DESC LIMIT 1", (title,))
            if rows:
                source_ids.append(rows[0]["id"])
        fact_id = db.add_topic_fact(
            {
                "fact": fact.fact,
                "discussion_score": fact.discussion_score,
                "reason": fact.reason,
                "run_id": "manual_step",
            },
            source_ids,
        )
        fact.topic_id = str(fact_id)
    return {"message": f"已生成 {len(facts)} 条事实", "facts": [fact.__dict__ for fact in facts]}

def delete_fact(fact_id: int) -> dict[str, Any]:
    db = DBManager()
    db.execute_query("DELETE FROM topic_facts WHERE id = ?", (fact_id,))
    # Also delete associated mappings in fact_sources
    db.execute_query("DELETE FROM fact_sources WHERE fact_id = ?", (fact_id,))
    return {"message": "事实已删除"}

def delete_outline(outline_id: int) -> dict[str, Any]:
    db = DBManager()
    db.execute_query("DELETE FROM topic_outlines WHERE id = ?", (outline_id,))
    return {"message": "大纲已删除"}

def delete_draft(draft_id: int) -> dict[str, Any]:
    db = DBManager()
    db.execute_query("DELETE FROM platform_drafts WHERE id = ?", (draft_id,))
    return {"message": "初稿已删除"}

def generate_drafts(payload: dict[str, Any]) -> dict[str, Any]:
    db = DBManager()
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
    
    engineer = ScenarioEngineer()
    drafts = engineer.run(outlines)
    for draft in drafts:
        outline_id = int(draft.topic_id) if str(draft.topic_id).isdigit() else None
        draft_id = db.add_platform_draft(
            {
                "outline_id": outline_id,
                "platform": draft.platform,
                "title": draft.title,
                "body": draft.body,
                "word_count": draft.word_count,
                "score": 0.0,
                "passed": False,
                "issues": "",
            }
        )
        draft.topic_id = str(draft_id)
    return {
        "message": f"已生成 {len(drafts)} 条初稿，检索 {len(engineer.research_reports)} 个大纲素材",
        "drafts": [draft.__dict__ for draft in drafts],
        "research": engineer.research_reports,
    }

def generate_outlines(payload: dict[str, Any]) -> dict[str, Any]:
    db = DBManager()
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
    for outline in outlines:
        fact_id = int(outline.topic_id) if str(outline.topic_id).isdigit() else None
        outline_id = db.add_topic_outline(
            {
                "fact_id": fact_id,
                "title_hook": outline.title_hook,
                "anxiety_background": outline.anxiety_background,
                "technical_breakdown": outline.technical_breakdown,
                "practical_solution": outline.practical_solution,
                "private_domain_hook": outline.private_domain_hook,
                "content_angle": outline.content_angle,
            }
        )
        outline.topic_id = str(outline_id)
    return {"message": f"已生成 {len(outlines)} 个大纲", "outlines": [outline.__dict__ for outline in outlines]}
