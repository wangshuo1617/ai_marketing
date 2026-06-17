"""Four-agent state machine for AI business-analysis IP content production."""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable

import pandas as pd

import config
from utils import file_saver
from utils.db_manager import DBManager
from utils.llm_reply import llm_reply
from utils.prompt_loader import load_prompt
import logging

logger = logging.getLogger("pipeline")


LLMCallable = Callable[..., str]


NODE_TEMPERATURE_ENV = {
    "scout": "AI_TEMPERATURE_SCOUT",
    "translator": "AI_TEMPERATURE_TRANSLATOR",
    "wechat_article": "AI_TEMPERATURE_WECHAT_ARTICLE",
    "wechat_channels": "AI_TEMPERATURE_WECHAT_CHANNELS",
    "douyin": "AI_TEMPERATURE_DOUYIN",
    "gatekeeper": "AI_TEMPERATURE_GATEKEEPER",
}

NODE_TEMPERATURE_DEFAULTS = {
    "scout": 0.2,
    "translator": 0.5,
    "wechat_article": 0.4,
    "wechat_channels": 0.65,
    "douyin": 0.7,
    "gatekeeper": 0.1,
}


class TopicState(str, Enum):
    SCOUTED = "scouted"
    TRANSLATED = "translated"
    DRAFTED = "drafted"
    REVIEW = "review"
    APPROVED = "approved"
    REVISION_REQUIRED = "revision_required"


@dataclass
class SourceItem:
    title: str
    content: str = ""
    url: str = ""
    source: str = "unknown"
    fetch_date: str = ""


@dataclass
class TopicFact:
    topic_id: str
    fact: str
    source_titles: list[str]
    source_urls: list[str]
    evidence_count: int
    discussion_score: float
    reason: str
    state: str = TopicState.SCOUTED.value


@dataclass
class TopicOutline:
    topic_id: str
    title_hook: str
    anxiety_background: str
    technical_breakdown: str
    practical_solution: str
    private_domain_hook: str
    content_angle: str
    state: str = TopicState.TRANSLATED.value


@dataclass
class PlatformDraft:
    topic_id: str
    platform: str
    title: str
    body: str
    word_count: int
    state: str = TopicState.DRAFTED.value


@dataclass
class ReviewResult:
    topic_id: str
    platform: str
    passed: bool
    score: float
    issues: list[str] = field(default_factory=list)
    revision_instruction: str = ""
    state: str = TopicState.APPROVED.value


@dataclass
class PipelineRunResult:
    facts: list[TopicFact]
    outlines: list[TopicOutline]
    drafts: list[PlatformDraft]
    reviews: list[ReviewResult]
    approved: list[PlatformDraft]
    output_files: dict[str, str]


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _slugify(value: str, max_length: int = 40) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z\u4e00-\u9fa5_-]+", "_", value).strip("_")
    return cleaned[:max_length] or "topic"


def _temperature_for_node(node: str) -> float:
    env_name = NODE_TEMPERATURE_ENV[node]
    fallback = os.getenv("AI_TEMPERATURE")
    value = os.getenv(env_name, fallback)
    if value is None or value.strip() == "":
        return NODE_TEMPERATURE_DEFAULTS[node]
    return float(value)


def _call_llm(prompt: str, llm: LLMCallable, temperature: float) -> str:
    try:
        return llm(prompt, temperature=temperature)
    except TypeError:
        return llm(prompt)


def _json_from_llm(
    prompt: str,
    fallback: Any,
    llm: LLMCallable | None = None,
    temperature: float | None = None,
) -> Any:
    if llm is None:
        llm = llm_reply
    try:
        response = _call_llm(prompt, llm, temperature if temperature is not None else 0.4).strip()
        match = re.search(r"```json\s*(.*?)\s*```", response, re.S | re.I)
        if match:
            response = match.group(1).strip()
        return json.loads(response)
    except Exception as exc:
        logger.warning("LLM JSON解析失败，使用规则兜底: %s", exc)
        return fallback


def _contains_any(text: str, words: list[str]) -> bool:
    lower_text = text.lower()
    return any(word.lower() in lower_text for word in words)


class TrendScout:
    """Turns raw scraped items into a small set of discussable bottom-layer facts."""

    def __init__(self, max_facts: int | None = None, llm: LLMCallable | None = None):
        self.max_facts = max_facts or config.IP_PIPELINE_MAX_FACTS
        self.llm = llm

    def run(self, source_items: list[dict[str, Any]] | pd.DataFrame) -> list[TopicFact]:
        normalized_items = self._normalize_items(source_items)
        if not normalized_items:
            return []

        candidates = self._score_items(normalized_items)
        top_items = candidates[: max(self.max_facts * 3, self.max_facts)]
        llm_facts = self._try_llm_extract(top_items)
        if llm_facts:
            return llm_facts[: self.max_facts]
        return self._fallback_extract(top_items)[: self.max_facts]

    def _normalize_items(self, source_items: list[dict[str, Any]] | pd.DataFrame) -> list[SourceItem]:
        if isinstance(source_items, pd.DataFrame):
            rows = source_items.to_dict(orient="records")
        else:
            rows = source_items

        normalized = []
        for row in rows:
            title = _safe_text(row.get("title"))
            content = _safe_text(row.get("content"))
            if not title and not content:
                continue
            item = SourceItem(
                title=title,
                content=content,
                url=_safe_text(row.get("url")),
                source=_safe_text(row.get("source")) or "unknown",
                fetch_date=_safe_text(row.get("fetch_date")),
            )
            setattr(item, "type", _safe_text(row.get("type")))
            normalized.append(item)
        return normalized

    def _score_items(self, items: list[SourceItem]) -> list[tuple[SourceItem, float, str]]:
        score_words = config.IP_TREND_SCORE_KEYWORDS
        scored = []
        for item in items:
            text = f"{item.title} {item.content}"
            score = 1.0
            reasons = []
            for label, words in score_words.items():
                hits = [word for word in words if word.lower() in text.lower()]
                if hits:
                    score += len(hits) * config.IP_TREND_SCORE_WEIGHTS.get(label, 1.0)
                    reasons.append(f"{label}:{'/'.join(hits[:3])}")
            if len(item.content) > 80:
                score += 0.5
            scored.append((item, round(score, 2), "; ".join(reasons) or "标题具备基础讨论价值"))
        scored.sort(key=lambda entry: entry[1], reverse=True)
        return scored

    def _try_llm_extract(self, scored_items: list[tuple[SourceItem, float, str]]) -> list[TopicFact]:
        if self.llm is None and not config.IP_PIPELINE_USE_LLM:
            return []

        packed = [
            {
                "title": item.title,
                "content": item.content[:260],
                "source": item.source,
                "url": item.url,
                "type": getattr(item, "type", "unknown"),
            }
            for item, score, reason in scored_items
        ]
        prompt = load_prompt(
            "ip_pipeline/trend_scout.md",
            max_facts=self.max_facts,
            items_json=json.dumps(packed, ensure_ascii=False),
        )
        fallback: list[dict[str, Any]] = []
        raw_facts = _json_from_llm(prompt, fallback, self.llm, _temperature_for_node("scout"))
        facts = []
        for index, item in enumerate(raw_facts, start=1):
            fact = _safe_text(item.get("fact"))
            if not fact:
                continue
            facts.append(
                TopicFact(
                    topic_id=f"T{index:03d}",
                    fact=fact,
                    source_titles=list(item.get("source_titles", []))[:5],
                    source_urls=list(item.get("source_urls", []))[:5],
                    evidence_count=int(item.get("evidence_count", 1) or 1),
                    discussion_score=float(item.get("discussion_score", 0) or 0),
                    reason=_safe_text(item.get("reason")) or "LLM提取",
                )
            )
        return facts

    def _fallback_extract(self, scored_items: list[tuple[SourceItem, float, str]]) -> list[TopicFact]:
        facts = []
        seen = set()
        for item, score, reason in scored_items:
            fact = self._rewrite_fact(item)
            dedupe_key = fact[:24]
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            facts.append(
                TopicFact(
                    topic_id=f"T{len(facts) + 1:03d}",
                    fact=fact,
                    source_titles=[item.title],
                    source_urls=[item.url] if item.url else [],
                    evidence_count=1,
                    discussion_score=score,
                    reason=reason,
                )
            )
        return facts

    def _rewrite_fact(self, item: SourceItem) -> str:
        text = item.title or item.content[:80]
        if _contains_any(text, ["降价", "成本", "价格", "开源", "API"]):
            return f"AI基础设施成本变化正在影响企业自研与采购决策: {text}"
        if _contains_any(text, ["裁员", "替代", "自动化", "效率"]):
            return f"AI自动化正在重写岗位与流程分工: {text}"
        if _contains_any(text, ["模型", "Agent", "智能体", "工具"]):
            return f"AI工具能力迭代正在降低业务落地门槛: {text}"
        return f"值得转化为商业分析的AI相关事件: {text}"


class BusinessInsightTranslator:
    """Converts facts into business-angle outlines for owners and executives."""

    def __init__(self, llm: LLMCallable | None = None):
        self.llm = llm

    def run(self, facts: list[TopicFact]) -> list[TopicOutline]:
        outlines = []
        for fact in facts:
            outline = self._try_llm_translate(fact) or self._fallback_translate(fact)
            outlines.append(outline)
        return outlines

    def _try_llm_translate(self, fact: TopicFact) -> TopicOutline | None:
        if self.llm is None and not config.IP_PIPELINE_USE_LLM:
            return None

        prompt = load_prompt(
            "ip_pipeline/business_translator.md",
            fact=fact.fact,
            source_titles_json=json.dumps(fact.source_titles, ensure_ascii=False),
        )
        data = _json_from_llm(prompt, {}, self.llm, _temperature_for_node("translator"))
        if not data or not data.get("title_hook"):
            return None
        return TopicOutline(
            topic_id=fact.topic_id,
            title_hook=_safe_text(data.get("title_hook")),
            anxiety_background=_safe_text(data.get("anxiety_background")),
            technical_breakdown=_safe_text(data.get("technical_breakdown")),
            practical_solution=_safe_text(data.get("practical_solution")),
            private_domain_hook=_safe_text(data.get("private_domain_hook")),
            content_angle=_safe_text(data.get("content_angle")),
        )

    def _fallback_translate(self, fact: TopicFact) -> TopicOutline:
        fact_text = fact.fact
        if _contains_any(fact_text, ["成本", "降价", "价格", "API"]):
            title = "还在按旧预算做AI项目的企业，正在多花一笔冤枉钱"
            anxiety = "AI能力的单位成本快速下降，真正的风险不是不用AI，而是继续用上一轮预算逻辑采购和自研。"
            solution = "先盘点高频文本、客服、销售跟进、内容生产四类流程，用轻量API验证ROI，再决定是否私有化或深度集成。"
            angle = "AI成本下降后的预算重算"
        elif _contains_any(fact_text, ["裁员", "岗位", "替代", "自动化"]):
            title = "AI不是替代一个人，而是在替代一整段低效流程"
            anxiety = "很多企业把AI理解成省人头，结果只做了工具采购，没有重构流程，ROI自然算不出来。"
            solution = "把岗位任务拆成信息收集、判断、生成、触达、复盘五段，先让AI接管低风险、高重复节点。"
            angle = "AI自动化与流程重构"
        else:
            title = "这轮AI机会，不在工具清单里，而在业务流程里"
            anxiety = "企业最容易被新工具牵着走，却忽略工具背后正在下降的组织协作成本。"
            solution = "从一个明确业务指标切入，比如获客成本、线索响应速度、内容产能或客户转化率，倒推AI应用场景。"
            angle = "AI工具变化背后的业务机会"

        return TopicOutline(
            topic_id=fact.topic_id,
            title_hook=title,
            anxiety_background=anxiety,
            technical_breakdown=f"这个事实的关键不是新闻本身，而是它说明企业使用AI的边际成本、试错速度和流程颗粒度正在变化。原始事实: {fact_text}",
            practical_solution=solution,
            private_domain_hook="文末可引导领取《企业AI流程改造自查表》，把讨论转化成私域线索。",
            content_angle=angle,
        )


class ScenarioEngineer:
    """Generates platform-specific drafts for WeChat, Channels, and Douyin."""

    def __init__(self, platforms: list[str] | None = None, llm: LLMCallable | None = None):
        self.platforms = platforms or config.IP_CONTENT_PLATFORMS
        self.llm = llm
        self.search_tool = SearchTool()
        self.research_reports: list[dict[str, Any]] = []

    def run(self, outlines: list[TopicOutline]) -> list[PlatformDraft]:
        drafts = []
        self.research_reports = []
        for outline in outlines:
            # 1. Research: Find supporting cases for the outline's key points
            research = self._research_supporting_cases(outline)
            research_context = research["context"]
            self.research_reports.append({
                "topic_id": outline.topic_id,
                "query": research["query"],
                "result_count": research["result_count"],
                "usable_count": research["usable_count"],
                "sources": research["sources"],
            })
            
            for platform in self.platforms:
                draft = self._try_llm_generate(outline, platform, research_context) or self._fallback_generate(outline, platform)
                drafts.append(draft)
        return drafts

    def _research_supporting_cases(self, outline: TopicOutline) -> dict[str, Any]:
        """Multi-query heuristic research: generates 3 targeted queries, merges results, retries if thin."""
        llm = self.llm or llm_reply
        query_gen_prompt = (
            f"基于以下商业选题大纲，生成3个不同维度的中文搜索词，分别用于寻找：\n"
            f"1. Shock维度：真实的业务吃瘪案例或反常识数据（企业/行业/成本类事故）\n"
            f"2. Solution维度：改造后的量化效果数据（产能/时间/成本/容错率对比）\n"
            f"3. 背景维度：支撑该行业趋势的最新新闻或研究报告\n\n"
            f"大纲标题：{outline.title_hook}\n"
            f"核心论点：{outline.technical_breakdown}\n\n"
            f"只输出JSON数组，3个字符串，例如：[\"query1\", \"query2\", \"query3\"]"
        )

        try:
            raw = _call_llm(query_gen_prompt, llm, 0.2).strip()
            queries: list[str] = json.loads(re.search(r"\[.*\]", raw, re.S).group())
        except Exception:
            queries = [f"{outline.title_hook} 企业案例", f"{outline.technical_breakdown} 效果数据"]

        all_parts: list[str] = []
        all_sources: list[dict] = []
        total_results = 0

        for q in queries[:3]:
            q = q.strip().strip('"').strip("'")
            if not q:
                continue
            try:
                logger.info("[Research] Searching: %s", q)
                res = self.search_tool.get_context(q, max_results=3)
                total_results += res["result_count"]
                # get_context returns a formatted "context" string; re-extract parts
                for src in res["sources"]:
                    if src not in all_sources:
                        all_sources.append(src)
                all_parts.append(f"=== Query: {q} ===\n{res['context']}")
                logger.info("[Research] Got %d snippets", res['usable_count'])
            except SearchToolError as exc:
                logger.warning("[Research] Skipped (%s)", exc)

        # Fallback: if total usable snippets are thin, retry with a broader query
        if len(all_sources) < 2:
            fallback_query = f"{outline.content_angle} AI 企业案例 成本效益"
            logger.info("[Research] Fallback search: %s", fallback_query)
            try:
                res = self.search_tool.get_context(fallback_query, max_results=5)
                total_results += res["result_count"]
                all_sources.extend(s for s in res["sources"] if s not in all_sources)
                all_parts.append(f"=== Fallback ===\n{res['context']}")
            except SearchToolError as exc:
                logger.warning("[Research] Fallback also failed (%s)", exc)

        if not all_parts:
            raise SearchToolError("所有搜索维度均未返回可用素材")

        return {
            "query": " | ".join(queries[:3]),
            "result_count": total_results,
            "usable_count": len(all_sources),
            "sources": all_sources,
            "context": "\n\n".join(all_parts),
        }

    def _try_llm_generate(self, outline: TopicOutline, platform: str, research_context: str) -> PlatformDraft | None:
        if self.llm is None and not config.IP_PIPELINE_USE_LLM:
            return None

        specs = config.IP_PLATFORM_SPECS[platform]
        prompt = load_prompt(
            "ip_pipeline/scenario_engineer.md",
            platform=platform,
            platform_specs_json=json.dumps(specs, ensure_ascii=False),
            outline_json=json.dumps(asdict(outline), ensure_ascii=False),
            research_context=research_context, # Pass the research results to the prompt
        )
        data = _json_from_llm(prompt, {}, self.llm, _temperature_for_node(platform))
        if not data or not data.get("body"):
            return None
        body = _safe_text(data.get("body"))
        return PlatformDraft(
            topic_id=outline.topic_id,
            platform=platform,
            title=_safe_text(data.get("title")) or outline.title_hook,
            body=body,
            word_count=len(body),
        )

    def _fallback_generate(self, outline: TopicOutline, platform: str) -> PlatformDraft:
        if platform == "wechat_article":
            body = self._wechat_article(outline)
            title = outline.title_hook
        elif platform == "wechat_channels":
            body = self._short_video(outline, opening="[画面] 主讲人半身出镜，背景是相关新闻截图。\n[口播] 很多老板对AI的判断，卡在一个误区里。")
            title = f"视频号口播_{outline.content_angle}"
        elif platform == "douyin":
            body = self._short_video(outline, opening="[画面] 切近景加粗字幕。\n[口播] 先说结论：这件事会影响你的AI预算。")
            title = f"抖音口播_{outline.content_angle}"
        else:
            body = self._short_video(outline, opening="[画面] 主讲人出镜。\n[口播] 这是一条AI商业判断。")
            title = outline.title_hook
        return PlatformDraft(
            topic_id=outline.topic_id,
            platform=platform,
            title=title,
            body=body,
            word_count=len(body),
        )

    def _wechat_article(self, outline: TopicOutline) -> str:
        return f"""# {outline.title_hook}

我最近和几个客户聊AI落地，发现大家的问题不是认知不够热，而是预算和流程还停留在上一轮。

## 真正的变化是什么
{outline.anxiety_background}

## 为什么这件事值得你关注
{outline.technical_breakdown}

这里的关键不是追热点，而是重新计算三件事：第一，哪些流程的边际成本已经被AI打穿；第二，哪些岗位任务可以被拆成标准化节点；第三，哪些投入还在用过时的采购逻辑续费。

## 一个更现实的判断框架
我经常跟老板们说，不要先问“我们要不要上大模型”，而要先问“哪一段业务动作已经贵得不合理”。如果你的团队每天都在重复查资料、写摘要、整理客户问题、生成跟进话术，这些环节本质上都是信息处理成本。AI真正改变的，就是这类成本的价格和速度。

对你来说，最值得关注的不是模型榜单，而是组织里那些长期没人愿意拆的小流程。它们单独看都不大，但叠在一起，就是人效、响应速度和管理颗粒度的差距。

## 我的建议
{outline.practical_solution}

建议先不要从“大模型战略”这种大词开始，而是从一个可验证的业务闭环开始：线索响应、客户答疑、销售跟进、内容生产、知识库检索。每个场景只看三个指标：节省多少人时、提升多少转化、降低多少试错成本。

更具体一点，你可以按四步走：

1. 先列出团队每周重复超过三次的文本、检索、整理、判断任务。
2. 再给每个任务标注风险等级，低风险任务先自动化，高风险任务保留人工复核。
3. 用一周时间跑最小闭环，不急着做系统集成，先验证结果是否稳定。
4. 最后再决定是采购工具、调用API，还是把能力接进现有CRM、SCRM或内容系统。

这套顺序的好处是，它不会把AI项目变成一次昂贵的信仰消费。每一步都有指标，每个指标都能回到业务结果。

## 最后一句
AI带来的不是一个工具红利，而是一轮流程成本重估。谁先把流程拆细，谁就先拿到真实ROI。

{outline.private_domain_hook}
""".strip()

    def _short_video(self, outline: TopicOutline, opening: str) -> str:
        return f"""{opening}

[画面] 配合紧凑的背景音乐，展示相关数据图表。
[口播] {outline.title_hook}

[画面] 主讲人严肃表情。
[口播] 为什么？{outline.anxiety_background}

[画面] 切换到流程图或白板演示。
[口播] 你不用先关心模型参数，先关心业务账：哪些动作重复、哪些判断依赖经验、哪些内容每天都要人肉生产。

[画面] 主讲人重新出镜，语气诚恳。
[口播] 我的建议是：{outline.practical_solution}

[画面] 放大主讲人面部。
[口播] AI项目别先做大，先做窄。窄到一个流程、一个指标、一个星期能复盘。

[画面] 屏幕下方弹出资料领取提示。
[口播] 想要自查，可以去领《企业AI流程改造自查表》，先把自己的业务流程拆出来。""".strip()


class ConsistencyGatekeeper:
    """Reviews drafts against IP persona, factual common sense, and conversion hook rules."""

    def __init__(self, min_score: float | None = None, llm: LLMCallable | None = None):
        self.min_score = min_score or config.IP_GATEKEEPER_MIN_SCORE
        self.llm = llm

    def run(self, drafts: list[PlatformDraft]) -> list[ReviewResult]:
        reviews = []
        for draft in drafts:
            review = self._try_llm_review(draft) or self._fallback_review(draft)
            reviews.append(review)
        return reviews

    def _try_llm_review(self, draft: PlatformDraft) -> ReviewResult | None:
        if self.llm is None and not config.IP_PIPELINE_USE_LLM:
            return None

        prompt = load_prompt(
            "ip_pipeline/gatekeeper.md",
            platform=draft.platform,
            title=draft.title,
            body=draft.body,
        )
        data = _json_from_llm(prompt, {}, self.llm, _temperature_for_node("gatekeeper"))
        if not data:
            return None
        passed = bool(data.get("passed")) and float(data.get("score", 0) or 0) >= self.min_score
        return ReviewResult(
            topic_id=draft.topic_id,
            platform=draft.platform,
            passed=passed,
            score=float(data.get("score", 0) or 0),
            issues=list(data.get("issues", [])),
            revision_instruction=_safe_text(data.get("revision_instruction")),
            state=TopicState.APPROVED.value if passed else TopicState.REVISION_REQUIRED.value,
        )

    def _fallback_review(self, draft: PlatformDraft) -> ReviewResult:
        issues = []
        score = 10.0
        forbidden_words = ["震惊", "逆天", "财富自由", "躺赚", "闭眼买", "无脑", "神级"]
        if _contains_any(draft.body, forbidden_words) or _contains_any(draft.title, forbidden_words):
            issues.append("存在夸张或低维表达，削弱专业人设。")
            score -= 2.5
        if re.search(r"\d+(\.\d+)?%|\d+倍|token|并发", draft.body, re.I) and not _contains_any(draft.body, ["假设", "约", "公开", "案例", "估算", "原始事实"]):
            issues.append("出现具体数字或工程指标，但缺少来源或限定语。")
            score -= 2.0
        if not _contains_any(draft.body, ["领取", "自查表", "白皮书", "私域", "咨询", "资料"]):
            issues.append("结尾没有自然导流动作。")
            score -= 2.0
        if draft.platform in ["douyin", "wechat_channels"] and draft.word_count > 420:
            issues.append("短视频脚本过长，需要压缩到300字左右。")
            score -= 1.0
        if draft.platform == "wechat_article" and draft.word_count < 600:
            issues.append("公众号稿件偏短，需要补充案例、拆解和执行步骤。")
            score -= 1.0

        passed = score >= self.min_score and not issues
        instruction = "" if passed else "；".join(issues) + " 请按问题重写后复审。"
        return ReviewResult(
            topic_id=draft.topic_id,
            platform=draft.platform,
            passed=passed,
            score=round(score, 2),
            issues=issues,
            revision_instruction=instruction,
            state=TopicState.APPROVED.value if passed else TopicState.REVISION_REQUIRED.value,
        )


class IPContentPipeline:
    """Orchestrates the flow from Inspiration -> Fact -> Outline -> Draft -> Review."""

    def __init__(self, llm: LLMCallable | None = None):
        self.db = DBManager()
        self.scout = TrendScout(llm=llm)
        self.translator = BusinessInsightTranslator(llm=llm)
        self.engineer = ScenarioEngineer(llm=llm)
        self.gatekeeper = ConsistencyGatekeeper(llm=llm)

    def run(self, inspiration_pool: pd.DataFrame) -> PipelineRunResult:
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        logger.info("[Pipeline] Starting run %s...", run_id)

        # 1. Scout: Inspirations -> Facts
        # We pass the dataframe, but the scout needs to know which IDs to link
        # To keep it simple, we'll map the dataframe rows to DB IDs
        facts_data = self.scout.run(inspiration_pool)
        
        # Save Facts to DB and get their IDs
        db_facts = []
        for f in facts_data:
            # Find inspiration IDs that contributed to this fact
            # In the current scout implementation, source_titles are used. 
            # We'll look up IDs by title in the DB.
            source_ids = []
            for title in f.source_titles:
                res = self.db.fetch_all("SELECT id FROM inspirations WHERE title = ?", (title,))
                if res:
                    source_ids.append(res[0]['id'])
            
            fact_id = self.db.add_topic_fact({
                'fact': f.fact,
                'discussion_score': f.discussion_score,
                'reason': f.reason,
                'run_id': run_id
            }, source_ids)
            
            # Update the object with the real DB ID
            f.topic_id = str(fact_id)
            db_facts.append(f)

        # 2. Translate: Facts -> Outlines
        outlines_data = self.translator.run(db_facts)
        db_outlines = []
        for o in outlines_data:
            # Convert topic_id back to int for FK
            fact_id = int(o.topic_id)
            outline_id = self.db.add_topic_outline({
                'fact_id': fact_id,
                'title_hook': o.title_hook,
                'anxiety_background': o.anxiety_background,
                'technical_breakdown': o.technical_breakdown,
                'practical_solution': o.practical_solution,
                'private_domain_hook': o.private_domain_hook,
                'content_angle': o.content_angle
            })
            o.topic_id = str(outline_id)
            db_outlines.append(o)

        # 3. Engineer: Outlines -> Drafts
        drafts_data = self.engineer.run(db_outlines)
        db_drafts = []
        for d in drafts_data:
            outline_id = int(d.topic_id)
            draft_id = self.db.add_platform_draft({
                'outline_id': outline_id,
                'platform': d.platform,
                'title': d.title,
                'body': d.body,
                'word_count': d.word_count,
                'score': 0.0, # Initial
                'passed': False,
                'issues': ""
            })
            # We'll use draft_id as the reference for review
            d.topic_id = str(draft_id) 
            db_drafts.append(d)

        # 4. Gatekeeper: Drafts -> Reviews
        reviews_data = self.gatekeeper.run(db_drafts)
        approved_drafts = []
        
        for r, d in zip(reviews_data, db_drafts):
            draft_id = int(d.topic_id)
            # Update draft with review results
            self.db.execute_query(
                "UPDATE platform_drafts SET score = ?, passed = ?, issues = ? WHERE id = ?",
                (r.score, r.passed, json.dumps(r.issues, ensure_ascii=False), draft_id)
            )
            if r.passed:
                approved_drafts.append(d)

        return PipelineRunResult(
            facts=db_facts,
            outlines=db_outlines,
            drafts=db_drafts,
            reviews=reviews_data,
            approved=approved_drafts,
            output_files={} # No longer using files as primary storage
        )
