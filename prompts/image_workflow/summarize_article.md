你是微信公众号商业文章的视觉策划。请先真正理解文章，不要只摘抄原文。

标题：{title}

当前全文 Markdown：
{markdown}

候选段落索引：
{paragraphs_json}

请输出严格 JSON：
{{"article_summary":"用 120-180 字总结文章核心论点、业务场景和读者痛点","visual_direction":"用 1-2 句话总结整篇文章适合的视觉方向","paragraphs":[{{"index":数字,"summary":"用一句话总结该段在文章中的作用，不要照抄原文","visual_value":"说明为什么这一段值得配图，以及适合视觉化成什么"}}]}}

要求：
1. paragraphs 只保留真正适合插图的段落，数量可以多于最终插图数量，供下一步挑选。
2. summary 必须是理解后的总结，不要复制候选段落原句。
3. visual_value 要具体，例如“适合画成成本流失 vs 资产沉淀的对比图”，不要写空泛评价。
4. 不要输出 JSON 之外的解释。
