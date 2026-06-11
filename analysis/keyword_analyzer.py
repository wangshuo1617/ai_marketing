# analysis/keyword_analyzer.py

import pandas as pd
import config
import re
from utils.llm_reply import llm_reply
from utils.prompt_loader import load_prompt

def _get_cluster(title, rules):
    """
    使用LLM根据规则将标题分配到一个主题簇。
    """
    rules_text = chr(10).join([f"- {cluster_name}: {', '.join(keywords)}" for cluster_name, keywords in rules.items()])
    prompt = load_prompt(
        "keyword_workflow/cluster_title.md",
        title=title,
        rules_text=rules_text,
    )
    
    try:
        cluster_name = llm_reply(prompt).strip()
        # 验证返回的主题簇是否在规则中
        if cluster_name in rules or cluster_name == "通用主题 (General Topics)":
            return cluster_name
        else:
            return "通用主题 (General Topics)"
    except Exception as e:
        print(f"LLM聚类出错: {e}")
        return "通用主题 (General Topics)"

def _get_intent_score(title, intent_keywords):
    """
    使用LLM根据关键词匹配计算商业意图分。
    """
    prompt = load_prompt(
        "keyword_workflow/intent_score.md",
        title=title,
        high_keywords=', '.join(intent_keywords['high']),
        medium_keywords=', '.join(intent_keywords['medium']),
        low_keywords=', '.join(intent_keywords['low']),
    )
    
    try:
        score_text = llm_reply(prompt).strip()
        # 提取数字
        score_match = re.search(r'\d+(?:\.\d+)?', score_text)
        if score_match:
            score = float(score_match.group())
            return min(max(score, 0), 10)  # 确保分数在0-10范围内
        else:
            return 5.0
    except Exception as e:
        print(f"LLM意图评分出错: {e}")
        return 5.0

def _get_strategic_score(title, strategic_keywords):
    """
    使用LLM根据关键词匹配计算战略对齐分。
    """
    prompt = load_prompt(
        "keyword_workflow/strategic_score.md",
        title=title,
        high_keywords=', '.join(strategic_keywords['high']),
        medium_keywords=', '.join(strategic_keywords['medium']),
        low_keywords=', '.join(strategic_keywords['low']),
    )
    
    try:
        score_text = llm_reply(prompt).strip()
        # 提取数字
        score_match = re.search(r'\d+(?:\.\d+)?', score_text)
        if score_match:
            score = float(score_match.group())
            return min(max(score, 0), 10)  # 确保分数在0-10范围内
        else:
            return 6.0
    except Exception as e:
        print(f"LLM战略评分出错: {e}")
        return 6.0

def analyze_keywords(keyword_db: pd.DataFrame) -> pd.DataFrame:
    """
    执行整个关键词分析流程：聚类、评分、排序。
    """
    
    print("  -> 步骤 2.1: 对关键词进行语义聚类 (LLM分析)...")
    keyword_db['cluster'] = keyword_db['title'].apply(
        _get_cluster, rules=config.CLUSTERING_RULES
    )

    clustered_groups = keyword_db.groupby('cluster')

    results = []
    
    print("  -> 步骤 2.2: 计算每个主题簇的价值与意图分 (LLM分析)...")
    for name, group in clustered_groups:
        freq_score = min(len(group) / 5, 10.0) 
        
        avg_intent_score = group['title'].apply(
            _get_intent_score, intent_keywords=config.INTENT_KEYWORDS
        ).mean()

        avg_strategic_score = group['title'].apply(
            _get_strategic_score, strategic_keywords=config.STRATEGIC_ALIGNMENT_KEYWORDS
        ).mean()
        
        total_score = (freq_score * 0.4) + (avg_intent_score * 0.3) + (avg_strategic_score * 0.3)

        all_titles = ' '.join(group['title'])
        representative_keywords = ', '.join(list(set(re.findall(r'\b[A-Z]{2,}\b|\b[\u4e00-\u9fa5]{2,5}\b', all_titles)))[:5])

        results.append({
            '主题簇 (Topic Cluster)': name,
            '相关文章数': len(group),
            '代表性关键词 (Representative Keywords)': representative_keywords,
            '竞争频率分 (0-10)': freq_score,
            '商业意图分 (0-10)': avg_intent_score,
            '战略对齐分 (0-10)': avg_strategic_score,
            '总机会分 (0-10)': total_score,
        })

    if not results:
        return pd.DataFrame()

    priority_matrix = pd.DataFrame(results)
    priority_matrix.sort_values(by='总机会分 (0-10)', ascending=False, inplace=True)
    priority_matrix.reset_index(drop=True, inplace=True)
    priority_matrix['优先级 (Priority)'] = priority_matrix.index + 1
    
    return priority_matrix 