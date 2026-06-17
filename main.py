# main.py
# 主执行文件，负责运行 AI 咨询内容业务流程。

import pandas as pd
import os
import argparse
import logging
from datetime import datetime
from pathlib import Path

import config
from agents.ip_content_pipeline import IPContentPipeline
from agents.inspiration_pipeline import append_selected_news_to_inspirations, build_inspiration_pool
from collectors.ai_news_collector import collect_ai_news_candidates
from web_app import run as run_web_app


def setup_logging() -> None:
    log_dir = Path(__file__).resolve().parent / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "app.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def is_empty_source_data(source_data):
    if source_data is None:
        return True
    if isinstance(source_data, pd.DataFrame):
        return source_data.empty
    return len(source_data) == 0


def run_ip_content_workflow(source_data=None):
    """
    运行 灵感池 -> Scout -> Translator -> Engineer -> Gatekeeper 的IP内容自动化流水线。
    """
    print("======================================================")
    print(f"AI商业分析IP内容流水线启动 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("======================================================")

    inspiration_pool = build_inspiration_pool(source_data, include_manual=True)

    if inspiration_pool.empty:
        print("\n未能获得任何灵感来源，程序终止。请检查抓取源或 input/inspiration_sources.csv。")
        return

    print(f"\n[成功] 灵感池已更新，包含 {len(inspiration_pool)} 条 AI 消息/实践感悟。")
    print(f"   文件保存在: {config.INSPIRATION_POOL_PATH}")

    pipeline = IPContentPipeline()
    result = pipeline.run(inspiration_pool)

    print("\n[完成] IP内容流水线已生成输出。")
    print(f"  - 底层事实: {len(result.facts)}")
    print(f"  - 选题大纲: {len(result.outlines)}")
    print(f"  - 平台初稿: {len(result.drafts)}")
    print(f"  - 通过质检: {len(result.approved)}")
    print(f"  - 输出目录: {config.IP_CONTENT_OUTPUT_DIR}")
    print("======================================================")


def run_ai_news_collection():
    """
    采集AI消息候选池，供人工查看、筛选和补充观点。
    """
    print("======================================================")
    print(f"AI消息候选池采集启动 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("======================================================")

    candidates = collect_ai_news_candidates()
    if candidates.empty:
        print("\n未采集到AI消息候选。请检查网络或数据源配置。")
        return candidates

    print(f"\n[完成] 已采集 {len(candidates)} 条AI消息候选。")
    print(f"  - 文件保存在: {config.AI_NEWS_CANDIDATES_PATH}")
    print("  - 你可以挑选值得写的消息，补充到 input/inspiration_sources.csv。")
    print("======================================================")
    return candidates


def promote_selected_news():
    """
    将 output/ai_news_candidates.csv 中 status=selected 的候选消息追加到手动灵感表。
    """
    print("======================================================")
    print("将已选择AI消息加入灵感输入表")
    print("======================================================")

    inspirations = append_selected_news_to_inspirations()
    print(f"[完成] 当前灵感输入表共有 {len(inspirations)} 条。")
    print(f"  - 文件保存在: {config.INSPIRATION_INPUT_PATH}")
    print("======================================================")


if __name__ == "__main__":
    setup_logging()
    # 确保输出目录存在
    os.makedirs(os.path.join('output', 'generated_content'), exist_ok=True)
    os.makedirs(config.IP_CONTENT_OUTPUT_DIR, exist_ok=True)

    parser = argparse.ArgumentParser(description="12times AI内容策略与IP内容流水线")
    parser.add_argument(
        "--workflow",
        choices=["web", "collect_news", "promote_news", "ip"],
        default="web",
        help="web=启动前端工作台，collect_news=采集AI消息候选，promote_news=将selected候选加入灵感表，ip=AI咨询IP内容流水线",
    )
    args = parser.parse_args()

    if args.workflow == "web":
        run_web_app()
    elif args.workflow == "collect_news":
        run_ai_news_collection()
    elif args.workflow == "promote_news":
        promote_selected_news()
    elif args.workflow == "ip":
        run_ip_content_workflow()
    else:
        run_ip_content_workflow()