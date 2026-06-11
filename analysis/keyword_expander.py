# analysis/keyword_expander.py

import pandas as pd
import config
from utils.llm_reply import llm_reply
from utils.prompt_loader import load_prompt
import re

def generate_long_tail_keywords(core_keywords, industry_context="AI驱动的私域运营和销售增长"):
    """
    使用LLM根据核心词生成长尾关键词
    """
    prompt = load_prompt(
        "keyword_workflow/generate_long_tail_keywords.md",
        core_keywords=', '.join(core_keywords),
        industry_context=industry_context,
    )
    
    try:
        response = llm_reply(prompt).strip()
        # 提取关键词，去除空行和格式
        keywords = [line.strip().strip('- ').strip() for line in response.split('\n') if line.strip()]
        # 过滤掉太短或无效的关键词
        valid_keywords = [kw for kw in keywords if len(kw) >= 4 and not kw.startswith('-')]
        return valid_keywords[:20]  # 限制数量
    except Exception as e:
        print(f"生成长尾关键词时出错: {e}")
        return []

def generate_scenario_keywords(core_keywords, target_industries=None):
    """
    使用LLM根据核心词生成场景关键词
    """
    if target_industries is None:
        target_industries = ["教育", "金融", "医疗", "零售", "制造业", "房地产", "汽车", "电商"]
    
    prompt = load_prompt(
        "keyword_workflow/generate_scenario_keywords.md",
        core_keywords=', '.join(core_keywords),
        target_industries=', '.join(target_industries),
    )
    
    try:
        response = llm_reply(prompt).strip()
        scenario_keywords = {}
        
        # 解析响应，提取行业和关键词
        lines = response.split('\n')
        for line in lines:
            if ':' in line:
                parts = line.split(':', 1)
                if len(parts) == 2:
                    industry = parts[0].strip()
                    keywords = [kw.strip() for kw in parts[1].split(',') if kw.strip()]
                    scenario_keywords[industry] = keywords
        
        return scenario_keywords
    except Exception as e:
        print(f"生成场景关键词时出错: {e}")
        return {}

def generate_question_keywords(core_keywords):
    """
    使用LLM根据核心词生成问题型关键词
    """
    prompt = load_prompt(
        "keyword_workflow/generate_question_keywords.md",
        core_keywords=', '.join(core_keywords),
    )
    
    try:
        response = llm_reply(prompt).strip()
        questions = [line.strip().strip('- ').strip() for line in response.split('\n') if line.strip()]
        valid_questions = [q for q in questions if len(q) >= 6 and ('?' in q or '？' in q or '如何' in q or '什么' in q or '为什么' in q or '哪个' in q or '怎么' in q)]
        return valid_questions[:15]
    except Exception as e:
        print(f"生成问题关键词时出错: {e}")
        return []

def expand_keywords_from_priority_matrix(priority_matrix):
    """
    根据优先级矩阵中的主题簇，扩展生成更多关键词
    """
    if priority_matrix.empty:
        return pd.DataFrame()
    
    expanded_keywords = []
    
    print("  -> 步骤 2.3: 根据核心主题生成长尾词和场景词...")
    
    for idx, row in priority_matrix.iterrows():
        topic_cluster = row['主题簇 (Topic Cluster)']
        representative_keywords = row['代表性关键词 (Representative Keywords)']
        
        # 提取核心关键词
        core_keywords = [kw.strip() for kw in representative_keywords.split(',') if kw.strip()]
        if not core_keywords:
            continue
            
        print(f"    - 正在扩展主题: {topic_cluster}")
        
        # 生成长尾关键词
        long_tail_keywords = generate_long_tail_keywords(core_keywords[:3])  # 使用前3个核心词
        
        # 生成场景关键词
        scenario_keywords = generate_scenario_keywords(core_keywords[:3])
        
        # 生成问题关键词
        question_keywords = generate_question_keywords(core_keywords[:3])
        
        # 整理结果
        for keyword in long_tail_keywords:
            expanded_keywords.append({
                '原始主题簇': topic_cluster,
                '关键词类型': '长尾词',
                '关键词': keyword,
                '优先级': row['优先级 (Priority)'],
                '总机会分': row['总机会分 (0-10)']
            })
        
        for industry, keywords in scenario_keywords.items():
            for keyword in keywords:
                expanded_keywords.append({
                    '原始主题簇': topic_cluster,
                    '关键词类型': f'场景词_{industry}',
                    '关键词': keyword,
                    '优先级': row['优先级 (Priority)'],
                    '总机会分': row['总机会分 (0-10)']
                })
        
        for question in question_keywords:
            expanded_keywords.append({
                '原始主题簇': topic_cluster,
                '关键词类型': '问题词',
                '关键词': question,
                '优先级': row['优先级 (Priority)'],
                '总机会分': row['总机会分 (0-10)']
            })
    
    if not expanded_keywords:
        return pd.DataFrame()
    
    expanded_df = pd.DataFrame(expanded_keywords)
    expanded_df.sort_values(by=['总机会分', '优先级'], ascending=[False, True], inplace=True)
    expanded_df.reset_index(drop=True, inplace=True)
    
    return expanded_df

def generate_keyword_combinations(core_keywords, modifiers=None):
    """
    生成关键词组合（基于规则的方法作为LLM的补充）
    """
    if modifiers is None:
        modifiers = {
            '效果类': ['提升', '优化', '改善', '增强', '提高', '降低', '减少'],
            '场景类': ['企业', '团队', '部门', '行业', '业务', '项目'],
            '工具类': ['软件', '系统', '平台', '工具', '解决方案', '服务'],
            '时间类': ['实时', '快速', '高效', '智能', '自动化', '持续'],
            '问题类': ['如何', '怎么', '为什么', '什么', '哪个', '哪些']
        }
    
    combinations = []
    
    for core in core_keywords:
        for category, mod_list in modifiers.items():
            for modifier in mod_list:
                # 生成不同组合
                combinations.extend([
                    f"{modifier}{core}",
                    f"{core}{modifier}",
                    f"{modifier}的{core}",
                    f"{core}的{modifier}"
                ])
    
    # 去重并过滤
    unique_combinations = list(set(combinations))
    valid_combinations = [combo for combo in unique_combinations if len(combo) >= 4 and len(combo) <= 20]
    
    return valid_combinations[:50]  # 限制数量

def expand_keywords_from_core_keywords(core_keywords_df: pd.DataFrame, top_n_per_keyword=10):
    """
    根据核心词DataFrame进行关键词扩展
    """
    if core_keywords_df.empty:
        return pd.DataFrame()
    
    expanded_keywords = []
    
    print("  -> 步骤 2.1: 根据核心词生成长尾词和场景词...")
    
    # 选择热度最高的前10个核心词进行扩展
    top_core_keywords = core_keywords_df.head(10)
    
    for idx, row in top_core_keywords.iterrows():
        core_keyword = row['核心词']
        heat_score = row['热度分数']
        rank = row['排名']
        
        print(f"    - 正在扩展核心词: {core_keyword} (热度分数: {heat_score}, 排名: {rank})")
        
        # 生成长尾关键词
        long_tail_keywords = generate_long_tail_keywords([core_keyword], top_n_per_keyword)
        
        # 生成场景关键词
        scenario_keywords = generate_scenario_keywords([core_keyword])
        
        # 生成问题关键词
        question_keywords = generate_question_keywords([core_keyword])
        
        # 整理结果
        for keyword in long_tail_keywords:
            expanded_keywords.append({
                '原始核心词': core_keyword,
                '核心词热度分数': heat_score,
                '核心词排名': rank,
                '关键词类型': '长尾词',
                '关键词': keyword,
                '扩展来源': 'LLM生成'
            })
        
        for industry, keywords in scenario_keywords.items():
            for keyword in keywords:
                expanded_keywords.append({
                    '原始核心词': core_keyword,
                    '核心词热度分数': heat_score,
                    '核心词排名': rank,
                    '关键词类型': f'场景词_{industry}',
                    '关键词': keyword,
                    '扩展来源': 'LLM生成'
                })
        
        for question in question_keywords:
            expanded_keywords.append({
                '原始核心词': core_keyword,
                '核心词热度分数': heat_score,
                '核心词排名': rank,
                '关键词类型': '问题词',
                '关键词': question,
                '扩展来源': 'LLM生成'
            })
    
    if not expanded_keywords:
        return pd.DataFrame()
    
    expanded_df = pd.DataFrame(expanded_keywords)
    expanded_df.sort_values(by=['核心词热度分数', '核心词排名'], ascending=[False, True], inplace=True)
    expanded_df.reset_index(drop=True, inplace=True)
    
    return expanded_df

def calculate_keyword_scores(expanded_keywords_df: pd.DataFrame) -> pd.DataFrame:
    """
    为扩展的关键词计算综合评分
    """
    if expanded_keywords_df.empty:
        return expanded_keywords_df
    
    print("  -> 步骤 2.2: 计算扩展关键词的综合评分...")
    
    scored_keywords = []
    
    for idx, row in expanded_keywords_df.iterrows():
        core_heat_score = row['核心词热度分数']
        keyword_type = row['关键词类型']
        keyword = row['关键词']
        
        # 基础分数：继承核心词的热度分数
        base_score = core_heat_score * 0.4
        
        # 类型权重：不同类型的关键词有不同的商业价值
        type_weights = {
            '长尾词': 0.8,  # 长尾词通常竞争较小，转化率高
            '问题词': 0.9,  # 问题词体现用户明确需求
        }
        
        # 为场景词设置权重
        if keyword_type.startswith('场景词_'):
            type_weight = 0.7  # 场景词针对性强
        else:
            type_weight = type_weights.get(keyword_type, 0.6)
        
        # 关键词长度分数：适中的长度通常更好
        length_score = 0
        if len(keyword) >= 4 and len(keyword) <= 15:
            length_score = 2.0
        elif len(keyword) > 15:
            length_score = 1.0
        else:
            length_score = 0.5
        
        # 商业意图分数：基于关键词内容判断
        intent_score = calculate_intent_score(keyword)
        
        # 战略对齐分数：基于关键词与公司定位的契合度
        strategic_score = calculate_strategic_score(keyword)
        
        # 综合评分
        total_score = (base_score * 0.3) + (length_score * 0.1) + (intent_score * 0.3) + (strategic_score * 0.3)
        total_score = total_score * type_weight
        
        scored_keywords.append({
            '原始核心词': row['原始核心词'],
            '核心词热度分数': row['核心词热度分数'],
            '核心词排名': row['核心词排名'],
            '关键词类型': row['关键词类型'],
            '关键词': row['关键词'],
            '扩展来源': row['扩展来源'],
            '基础分数': round(base_score, 2),
            '长度分数': round(length_score, 2),
            '商业意图分': round(intent_score, 2),
            '战略对齐分': round(strategic_score, 2),
            '综合评分': round(total_score, 2)
        })
    
    scored_df = pd.DataFrame(scored_keywords)
    scored_df.sort_values(by='综合评分', ascending=False, inplace=True)
    scored_df.reset_index(drop=True, inplace=True)
    scored_df['最终排名'] = scored_df.index + 1
    
    return scored_df

def calculate_intent_score(keyword: str) -> float:
    """
    计算关键词的商业意图分数
    """
    intent_keywords = {
        'high': ['价格', '演示', '对比', '评测', '购买', '选型', '推荐', 'vs', 'ROI', '计算', '成本', '收益', '投资', '回报'],
        'medium': ['解决方案', '如何', '最佳实践', '功能', '指南', '案例', '提升', '降低', '优化', '改善', '增强'],
        'low': ['是什么', '定义', '趋势', '新闻', '报告', '入门', '基础知识', '介绍', '概述']
    }
    
    keyword_lower = keyword.lower()
    
    if any(kw in keyword_lower for kw in intent_keywords['high']):
        return 9.0
    elif any(kw in keyword_lower for kw in intent_keywords['medium']):
        return 7.0
    elif any(kw in keyword_lower for kw in intent_keywords['low']):
        return 4.0
    else:
        return 6.0

def calculate_strategic_score(keyword: str) -> float:
    """
    计算关键词的战略对齐分数
    """
    strategic_keywords = {
        'high': ['AI', '智能', '预测', '营收', '私域', '12times', '增长', '自动化', 'SCRM', '线索', '转化'],
        'medium': ['销售', '营销', '客户', '管理', '运营', '分析', '数据', '工具', '平台'],
        'low': ['CRM', '通用', '基础', '入门', '介绍', '概念']
    }
    
    keyword_lower = keyword.lower()
    
    if any(kw in keyword_lower for kw in strategic_keywords['high']):
        return 9.5
    elif any(kw in keyword_lower for kw in strategic_keywords['medium']):
        return 7.5
    elif any(kw in keyword_lower for kw in strategic_keywords['low']):
        return 4.5
    else:
        return 6.0 