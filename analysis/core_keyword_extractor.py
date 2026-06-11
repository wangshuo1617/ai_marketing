# analysis/core_keyword_extractor.py

import pandas as pd
import re
from collections import Counter
from utils.llm_reply import llm_reply
from utils.prompt_loader import load_prompt

def extract_core_keywords_from_content(keyword_db: pd.DataFrame, top_n=20) -> pd.DataFrame:
    """
    从搜索到的内容中提炼出最火的核心词
    """
    print("  -> 步骤 1.5: 从热门内容中提炼核心词...")
    
    if keyword_db.empty:
        print("    - 关键词数据库为空，无法提炼核心词")
        return pd.DataFrame()
    
    # 1. 统计词频
    all_titles = ' '.join(keyword_db['title'].astype(str))
    all_content = ' '.join(keyword_db['content'].astype(str))
    all_text = all_titles + ' ' + all_content
    
    # 2. 使用LLM提取核心关键词
    core_keywords = extract_keywords_with_llm(all_text, top_n)
    
    # 3. 为每个核心词计算热度指标
    core_keyword_data = []
    for keyword in core_keywords:
        # 计算在标题和内容中的出现频率
        title_freq = sum(1 for title in keyword_db['title'] if keyword in str(title))
        content_freq = sum(1 for content in keyword_db['content'] if keyword in str(content))
        total_freq = title_freq + content_freq
        
        # 计算相关文章数
        related_articles = sum(1 for title in keyword_db['title'] 
                             for content in keyword_db['content'] 
                             if keyword in str(title) or keyword in str(content))
        
        # 计算热度分数 (基于频率和相关文章数)
        heat_score = (total_freq * 0.6) + (related_articles * 0.4)
        
        core_keyword_data.append({
            '核心词': keyword,
            '标题出现次数': title_freq,
            '内容出现次数': content_freq,
            '总出现次数': total_freq,
            '相关文章数': related_articles,
            '热度分数': round(heat_score, 2)
        })
    
    # 4. 创建核心词DataFrame并排序
    core_keywords_df = pd.DataFrame(core_keyword_data)
    core_keywords_df.sort_values(by='热度分数', ascending=False, inplace=True)
    core_keywords_df.reset_index(drop=True, inplace=True)
    core_keywords_df['排名'] = core_keywords_df.index + 1
    
    print(f"    - 成功提炼出 {len(core_keywords_df)} 个核心词")
    print(f"    - 热度最高的核心词: {core_keywords_df.iloc[0]['核心词']} (热度分数: {core_keywords_df.iloc[0]['热度分数']})")
    
    return core_keywords_df

def extract_keywords_with_llm(text: str, top_n=20) -> list:
    """
    使用LLM从文本中提取核心关键词
    """
    # 限制文本长度，避免超出LLM限制
    if len(text) > 3000:
        text = text[:3000]
    
    prompt = load_prompt(
        "keyword_workflow/extract_core_keywords.md",
        top_n=top_n,
        text=text,
    )
    
    try:
        response = llm_reply(prompt).strip()
        # 提取关键词，去除空行和格式
        keywords = [line.strip().strip('- ').strip() for line in response.split('\n') if line.strip()]
        # 过滤掉太短或无效的关键词
        valid_keywords = [kw for kw in keywords if len(kw) >= 2 and len(kw) <= 20 and not kw.startswith('-')]
        return valid_keywords[:top_n]
    except Exception as e:
        print(f"    - LLM提取关键词时出错: {e}")
        # 备用方案：使用简单的词频统计
        return extract_keywords_by_frequency(text, top_n)

def extract_keywords_by_frequency(text: str, top_n=20) -> list:
    """
    基于词频统计提取关键词（备用方案）
    """
    # 定义停用词
    stop_words = {'的', '是', '在', '有', '和', '与', '或', '但', '而', '如果', '因为', '所以', '这个', '那个', '什么', '怎么', '如何', '为什么', '哪个', '哪些', '一个', '一些', '很多', '更多', '最', '更', '非常', '特别', '尤其', '主要', '重要', '关键', '核心', '基础', '高级', '专业', '实用', '有效', '高效', '快速', '智能', '自动化', '数字化', '智能化', '系统', '平台', '工具', '软件', '服务', '解决方案', '产品', '技术', '方法', '策略', '方案', '计划', '项目', '工作', '业务', '行业', '企业', '公司', '团队', '部门', '人员', '用户', '客户', '消费者', '市场', '营销', '销售', '管理', '运营', '分析', '数据', '信息', '内容', '文章', '报告', '研究', '调查', '统计', '趋势', '发展', '增长', '提升', '优化', '改善', '增强', '提高', '降低', '减少', '控制', '管理', '监控', '跟踪', '记录', '存储', '处理', '计算', '预测', '评估', '测试', '验证', '确认', '检查', '审核', '审查', '分析', '研究', '调查', '了解', '掌握', '熟悉', '精通', '擅长', '专业', '经验', '能力', '技能', '知识', '理论', '实践', '应用', '使用', '操作', '运行', '执行', '实施', '部署', '配置', '设置', '调整', '修改', '更新', '升级', '维护', '支持', '服务', '帮助', '指导', '培训', '教育', '学习', '培训', '课程', '教材', '资料', '文档', '手册', '指南', '教程', '案例', '示例', '样本', '模板', '框架', '模型', '算法', '公式', '规则', '标准', '规范', '流程', '步骤', '阶段', '过程', '方法', '技巧', '窍门', '秘诀', '要点', '重点', '关键', '核心', '主要', '重要', '必要', '必须', '应该', '可以', '能够', '可能', '也许', '大概', '大约', '左右', '上下', '前后', '内外', '大小', '多少', '高低', '快慢', '好坏', '优劣', '强弱', '轻重', '远近', '新旧', '老幼', '男女', '老少', '中外', '古今', '东西', '南北', '上下', '左右', '前后', '内外', '大小', '多少', '高低', '快慢', '好坏', '优劣', '强弱', '轻重', '远近', '新旧', '老幼', '男女', '老少', '中外', '古今', '东西', '南北'}
    
    # 提取中文词汇
    chinese_words = re.findall(r'[\u4e00-\u9fa5]{2,8}', text)
    # 提取英文词汇
    english_words = re.findall(r'\b[A-Za-z]{2,10}\b', text)
    
    # 合并词汇
    all_words = chinese_words + english_words
    
    # 过滤停用词
    filtered_words = [word for word in all_words if word.lower() not in stop_words]
    
    # 统计词频
    word_counts = Counter(filtered_words)
    
    # 返回频率最高的词汇
    return [word for word, count in word_counts.most_common(top_n)]

def analyze_keyword_trends(core_keywords_df: pd.DataFrame) -> dict:
    """
    分析核心词的趋势和特点
    """
    if core_keywords_df.empty:
        return {}
    
    analysis = {
        '总核心词数量': len(core_keywords_df),
        '平均热度分数': round(core_keywords_df['热度分数'].mean(), 2),
        '最高热度分数': round(core_keywords_df['热度分数'].max(), 2),
        '最低热度分数': round(core_keywords_df['热度分数'].min(), 2),
        '热度分布': {
            '高热词(>8分)': len(core_keywords_df[core_keywords_df['热度分数'] > 8]),
            '中热词(5-8分)': len(core_keywords_df[(core_keywords_df['热度分数'] >= 5) & (core_keywords_df['热度分数'] <= 8)]),
            '低热词(<5分)': len(core_keywords_df[core_keywords_df['热度分数'] < 5])
        },
        '热门核心词TOP5': core_keywords_df.head(5)['核心词'].tolist()
    }
    
    return analysis 