# generation/content_generator.py

import os
import config
from utils import file_saver

def _get_ricce_prompt(role, context, constraints, evaluation, input_data):
    """
    一个辅助函数，用于构建结构化的RICCE提示。
    """
    prompt = f"""
### Role (角色)
{role}

### Input (输入)
{input_data}

### Context (上下文)
{context}

### Constraints (约束)
{constraints}

### Evaluation (评估)
{evaluation}

---
[AI, 请根据以上指令开始生成内容]
"""
    return prompt

def generate_content_assets(topic_data):
    """
    (模拟AI) 根据一个高优先级主题，生成一系列内容资产的草稿。
    """
    
    cluster_name = topic_data['主题簇 (Topic Cluster)']
    keywords = topic_data['代表性关键词 (Representative Keywords)']
    sanitized_cluster_name = "".join(x for x in cluster_name if x.isalnum() or x in " -").rstrip()
    
    generated_files = []

    # 1. 生成"中心"(Hub)内容 - 官网深度文章
    role_hub = "你是一位世界级的MarTech（营销技术）内容战略专家..."
    input_hub = f"你将撰写一篇关于{cluster_name}的3000字终极指南..."
    context_hub = "这篇文章的核心目标是确立12times在该领域的思想领导者地位..."
    constraints_hub = "文章必须使用H2和H3标题构建清晰的层次结构..."
    evaluation_hub = "最终的输出应该是一篇全面、权威的指南..."
    hub_prompt = _get_ricce_prompt(role_hub, context_hub, constraints_hub, evaluation_hub, input_hub)
    hub_filepath = os.path.join(config.CONTENT_GENERATION_DIR, f"01_官网文章_{sanitized_cluster_name}.txt")
    file_saver.save_text(hub_prompt, hub_filepath)
    generated_files.append(hub_filepath)

    # 2. 生成"辐射"(Spoke)内容 - 知乎回答
    role_zhihu = "你是一位乐于分享的行业专家。"
    input_zhihu = f"基于我们关于 '{cluster_name}' 的深度研究（内容提纲见上文）。"
    context_zhihu = f"请根据以上输入内容，为知乎问题关于 {keywords.split(',')[0]} 有哪些好的建议?撰写一篇1000字左右的专业回答。"
    constraints_zhihu = "回答应结构清晰..."
    evaluation_zhihu = "回答应获得高赞..."
    zhihu_prompt = _get_ricce_prompt(role_zhihu, context_zhihu, constraints_zhihu, evaluation_zhihu, input_zhihu)
    zhihu_filepath = os.path.join(config.CONTENT_GENERATION_DIR, f"02_知乎回答_{sanitized_cluster_name}.txt")
    file_saver.save_text(zhihu_prompt, zhihu_filepath)
    generated_files.append(zhihu_filepath)

    # 3. 生成"辐射"(Spoke)内容 - Bilibili视频脚本
    role_bili = "你是一位擅长制作B2B科技内容的视频脚本作家。"
    input_bili = f"基于我们关于 '{cluster_name}' 的深度研究（内容提纲见上文）。"
    context_bili = "请将文章内容，改编成一个5分钟时长的Bilibili视频脚本。"
    constraints_bili = "脚本必须包含一个强有力的钩子...请为每一部分提供清晰的视觉效果建议..."
    evaluation_bili = "脚本应能指导制作出一个高完播率、信息量大的科技解说视频。"
    bili_prompt = _get_ricce_prompt(role_bili, context_bili, constraints_bili, evaluation_bili, input_bili)
    bili_filepath = os.path.join(config.CONTENT_GENERATION_DIR, f"03_B站脚本_{sanitized_cluster_name}.txt")
    file_saver.save_text(bili_prompt, bili_filepath)
    generated_files.append(bili_filepath)

    # 4. 生成"辐射"(Spoke)内容 - 微信视频号脚本
    role_wechannel = "你是一位精通短视频传播的专家。"
    input_wechannel = f"将我们关于 '{cluster_name}' 的核心观点浓缩一下。"
    context_wechannel = "请为微信视频号创作一个1分钟的短视频脚本。"
    constraints_wechannel = "脚本必须直击痛点，节奏明快...需要提供镜头建议和字幕文案。"
    evaluation_wechannel = "视频应具有高点赞和高转发潜力。"
    wechannel_prompt = _get_ricce_prompt(role_wechannel, context_wechannel, constraints_wechannel, evaluation_wechannel, input_wechannel)
    wechannel_filepath = os.path.join(config.CONTENT_GENERATION_DIR, f"04_视频号脚本_{sanitized_cluster_name}.txt")
    file_saver.save_text(wechannel_prompt, wechannel_filepath)
    generated_files.append(wechannel_filepath)

    return generated_files 