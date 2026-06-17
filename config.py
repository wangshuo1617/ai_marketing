# config.py
# 配置文件，存储所有可调整的参数，如URL、关键词、文件路径等。
# 便于非技术人员调整策略，而无需修改核心代码。

import os
from dotenv import load_dotenv

load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

# --- 输出文件路径配置 ---
OUTPUT_DIR = "output"
INSPIRATION_INPUT_PATH = os.path.join("input", "inspiration_sources.csv")
AI_NEWS_CANDIDATES_PATH = os.path.join(OUTPUT_DIR, "ai_news_candidates.csv")
INSPIRATION_POOL_PATH = os.path.join(OUTPUT_DIR, "inspiration_pool.csv")
IP_CONTENT_OUTPUT_DIR = os.path.join(OUTPUT_DIR, "ip_content_pipeline")
IP_APPROVED_OUTPUT_DIR = os.path.join(IP_CONTENT_OUTPUT_DIR, "approved")

# --- IP内容流水线配置 ---
# 是否启用真实LLM调用。建议在 .env 中配置 IP_PIPELINE_USE_LLM=true。
IP_PIPELINE_USE_LLM = _env_bool("IP_PIPELINE_USE_LLM", True)
IP_PIPELINE_MAX_FACTS = 5
IP_GATEKEEPER_MIN_SCORE = 8.0

# --- 文章智能配图配置 ---
IMAGE_GEN_MODEL = os.getenv("IMAGE_GEN_MODEL", "gpt-image-2-client")
IMAGE_GEN_API_KEY = os.getenv("IMAGE_GEN_API_KEY", "")
IMAGE_GEN_BASE_URL = os.getenv("IMAGE_GEN_BASE_URL") or os.getenv("AI_BASE_URL", "https://api.147ai.cn")
IMAGE_GEN_OUTPUT_DIR = os.path.join("web", "static", "generated_images")
IMAGE_GEN_MAX_IMAGES = int(os.getenv("IMAGE_GEN_MAX_IMAGES", "4"))
IMAGE_GEN_QUALITY = os.getenv("IMAGE_GEN_QUALITY", "medium")
IMAGE_GEN_MODERATION = os.getenv("IMAGE_GEN_MODERATION", "low")
IMAGE_GEN_OUTPUT_FORMAT = os.getenv("IMAGE_GEN_OUTPUT_FORMAT", "png")
IMAGE_GEN_DEFAULT_SIZE = os.getenv("IMAGE_GEN_DEFAULT_SIZE", "1536x1024")

IP_CONTENT_PLATFORMS = ["wechat_article", "wechat_channels", "douyin"]
IP_PLATFORM_SPECS = {
    "wechat_article": {
        "name": "微信公众号",
        "target_length": "2000-3000字",
        "style": "严谨、深度、数据驱动、适合收藏和转发。必须结合具体的新闻动态或真实案例展开，有理有据。",
        "must_have": ["吸引人的标题", "引人入胜的开篇", "新闻/案例深度拆解", "对老板的商业启示", "具体的落地执行步骤", "私域导流钩子"],
    },
    "wechat_channels": {
        "name": "视频号",
        "target_length": "400-600字口播脚本（约1.5-2分钟）",
        "style": "克制、有判断、有反转，适合老板和管理者观看。必须包含画面分镜提示。",
        "must_have": ["前三秒黄金Hook", "痛点场景共鸣", "反常识的商业判断", "一个行动建议", "资料领取钩子", "画面分镜描述(如[画面：展示某某图表])"],
    },
    "douyin": {
        "name": "抖音",
        "target_length": "400-600字口播脚本（约1.5-2分钟）",
        "style": "更强开场、更短句、更直接，但不夸张不低俗。必须包含画面分镜提示。",
        "must_have": ["强结论开场", "新闻/案例快速引入", "反常识解释", "可执行建议", "资料领取钩子", "画面分镜描述(如[画面：切近景加粗字幕])"],
    },
}

IP_TREND_SCORE_KEYWORDS = {
    "boss_pain": ["老板", "管理者", "业务", "预算", "利润", "现金流", "增长", "获客", "人效"],
    "consulting": ["咨询", "落地", "改造", "诊断", "流程", "组织", "销售", "客服", "内容", "知识库"],
    "cost": ["降价", "成本", "价格", "API", "token", "开源", "免费", "ROI"],
    "efficiency": ["效率", "自动化", "Agent", "智能体", "替代", "生产力", "提效"],
    "ai": ["AI", "大模型", "模型", "生成式", "多模态", "RAG", "算力"],
    "practice": ["我发现", "客户", "项目", "实践", "复盘", "案例", "踩坑", "经验"],
}
IP_TREND_SCORE_WEIGHTS = {
    "boss_pain": 2.2,
    "consulting": 2.0,
    "cost": 2.0,
    "efficiency": 1.6,
    "ai": 1.2,
    "practice": 2.4,
}
# --- 数据源配置 ---
# AI消息采集源：只保留新闻聚合、社区讨论和独立观察源，避免厂商官方宣传源。
AI_NEWS_SOURCES = [
    {
        "name": "Google News AI Benchmarks",
        "url": "https://news.google.com/rss/search?q=AI%20benchmark%20leaderboard%20OR%20LMArena%20OR%20SWE-bench%20when:30d&hl=en-US&gl=US&ceid=US:en",
        "type": "rss",
    },
    {
        "name": "Google News AI Enterprise",
        "url": "https://news.google.com/rss/search?q=enterprise%20AI%20adoption%20OR%20AI%20implementation%20OR%20AI%20case%20study%20when:30d&hl=en-US&gl=US&ceid=US:en",
        "type": "rss",
    },
    {
        "name": "Techmeme",
        "url": "https://www.techmeme.com/feed.xml",
        "type": "rss",
    },
    {
        "name": "Reddit LocalLLaMA Latest",
        "url": "https://www.reddit.com/r/LocalLLaMA/search.rss?q=AI%20OR%20agent%20OR%20RAG%20OR%20enterprise%20OR%20production&restrict_sr=1&sort=new&t=month",
        "type": "rss",
    },
    {
        "name": "Reddit MachineLearning Latest",
        "url": "https://www.reddit.com/r/MachineLearning/search.rss?q=AI%20OR%20agent%20OR%20LLM%20OR%20production&restrict_sr=1&sort=new&t=month",
        "type": "rss",
    },
    {
        "name": "Hacker News AI Latest",
        "url": "https://hn.algolia.com/api/v1/search_by_date?query=AI%20agent%20LLM%20RAG%20production&tags=story&hitsPerPage=30",
        "type": "hn_algolia",
    },
    {
        "name": "Hacker News AI Benchmarks",
        "url": "https://hn.algolia.com/api/v1/search_by_date?query=AI%20benchmark%20leaderboard%20evaluation&tags=story&hitsPerPage=30",
        "type": "hn_algolia",
    },
    {
        "name": "Hacker News AI Business",
        "url": "https://hn.algolia.com/api/v1/search_by_date?query=AI%20enterprise%20customer%20automation%20cost&tags=story&hitsPerPage=30",
        "type": "hn_algolia",
    },
    {
        "name": "The Gradient",
        "url": "https://thegradient.pub/rss/",
        "type": "rss",
    },
    {
        "name": "Chip Huyen Blog",
        "url": "https://huyenchip.com/feed.xml",
        "type": "rss",
    },
    {
        "name": "Latent Space",
        "url": "https://www.latent.space/feed",
        "type": "rss",
    },
]
AI_NEWS_MAX_ITEMS_PER_SOURCE = 12
AI_NEWS_MIN_PUBLISHED_DATE = "2026-05-01"
AI_NEWS_RELEVANCE_KEYWORDS = [
    "case study", "customer story", "production", "deployment", "implementation",
    "lessons learned", "postmortem", "workflow", "automation", "enterprise",
    "operations", "sales", "support", "customer", "productivity", "ROI", "cost",
    "agent", "agents", "LLM", "RAG", "AI",
    "benchmark", "leaderboard", "LMArena", "Chatbot Arena", "SWE-bench", "evaluation", "eval",
    "案例", "落地", "实践", "复盘", "踩坑", "部署", "生产环境", "企业",
    "销售", "客服", "效率", "成本", "流程", "业务", "组织", "知识库",
]

# --- 爬虫相关配置 ---
# 模拟浏览器头部信息，防止被部分网站屏蔽
SCRAPER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}
