# AI咨询内容工作台

## 项目概述

这是一个面向 AI 咨询业务的本地内容工作台。它帮你采集 AI 消息候选，记录你的项目经验和实践感悟，再把这些灵感转化成能吸引老板、管理者和业务负责人的 AI 商业分析内容，输出微信公众号、视频号和抖音稿件。

旧 SEO/关键词流程已经不再作为主线。当前主线只服务这件事：用 AI 商业洞察内容吸引潜在客户，并自然转化到 AI 咨询业务。

## 当前流程

```text
AI消息候选采集
-> 人工筛选值得写的消息
-> 录入个人实践感悟/客户项目复盘
-> 灵感池
-> 内容种子提取
-> 商业洞察选题
-> 多平台内容生成
-> 一致性质检
-> 待发布稿件
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置模型

复制 `.env.example` 为 `.env`，填写 147API Key 和模型名：

```env
AI_BASE_URL=https://api.147ai.cn
AI_API_KEY=your_147api_key_here
AI_MODEL=gemini-2.5-pro-thinking-8192
AI_REQUEST_TIMEOUT=120

AI_TEMPERATURE=0.4
AI_TEMPERATURE_SCOUT=0.2
AI_TEMPERATURE_TRANSLATOR=0.5
AI_TEMPERATURE_WECHAT_ARTICLE=0.4
AI_TEMPERATURE_WECHAT_CHANNELS=0.65
AI_TEMPERATURE_DOUYIN=0.7
AI_TEMPERATURE_GATEKEEPER=0.1
```

如果只是先体验流程，`config.py` 中 `IP_PIPELINE_USE_LLM = False` 时会使用规则兜底，不会真实调用模型。

### 3. 启动前端工作台

```bash
python main.py
```

默认会启动本地前端：

```text
http://127.0.0.1:8010
```

如果端口仍然冲突，可以用环境变量指定：

```powershell
$env:WEB_PORT=8011; python main.py
```

也可以显式启动：

```bash
python main.py --workflow web
```

如果希望服务异常退出后自动重启，可以使用监控脚本：

```powershell
.\scripts\start-watch.ps1
```

或者双击/运行：

```bat
start-watch.bat
```

常用参数：

```powershell
.\scripts\start-watch.ps1 -Port 8011
.\scripts\start-watch.ps1 -KillExistingPortProcess
```

日志会写入：

```text
logs/web-watch.log
```

## 前端怎么用

1. 点击“采集AI消息”，系统会从配置的数据源抓取 AI 消息候选。
2. 在“AI消息候选”里选择值得写的消息。
3. 点击“加入灵感池”，选中的消息会进入灵感池。
4. 在“我的实践感悟”里录入你的客户项目复盘、业务观察、反常识发现。
5. 点击“生成内容”，系统会生成公众号、视频号、抖音稿件。
6. 通过质检的稿件会出现在 `output/ip_content_pipeline/approved/`。

## 命令行用法

```bash
python main.py --workflow web
```

启动前端工作台。

```bash
python main.py --workflow collect_news
```

只采集 AI 消息候选，保存到 `output/ai_news_candidates.csv`。

```bash
python main.py --workflow promote_news
```

把 `output/ai_news_candidates.csv` 中 `status=selected` 的消息加入灵感池。

```bash
python main.py --workflow ip
```

直接从当前灵感池生成内容。

## 主要目录

```text
collectors/
  ai_news_collector.py        # AI消息候选采集

agents/
  inspiration_pipeline.py     # 灵感池构建
  ip_content_pipeline.py      # Scout/Translator/Engineer/Gatekeeper 内容流水线

web/
  static/index.html           # 前端页面
  static/styles.css           # 前端样式
  static/app.js               # 前端交互
  workspace_service.py        # 前端调用的业务服务

prompts/ip_pipeline/
  trend_scout.md              # 内容种子提取提示词
  business_translator.md      # 商业洞察转化提示词
  scenario_engineer.md        # 多平台生成提示词
  gatekeeper.md               # 质检提示词

input/
  inspiration_sources.csv     # 手动灵感来源，前端会自动读写

output/
  ai_news_candidates.csv      # AI消息候选池
  inspiration_pool.csv        # 灵感池
  ip_content_pipeline/        # 内容流水线输出
```

## 提示词编辑

主要改这里：

| 文件 | 用途 |
|------|------|
| `prompts/ip_pipeline/trend_scout.md` | 从消息和经验中提取内容种子 |
| `prompts/ip_pipeline/business_translator.md` | 把内容种子转成老板向商业洞察选题 |
| `prompts/ip_pipeline/scenario_engineer.md` | 生成公众号、视频号、抖音初稿 |
| `prompts/ip_pipeline/gatekeeper.md` | 检查人设、事实常识和导流动作 |

模板里的 `{变量名}` 是代码填充用的占位符，修改提示词时不要删除。

## 测试

```bash
python -m py_compile main.py web_app.py web\workspace_service.py collectors\ai_news_collector.py agents\inspiration_pipeline.py agents\ip_content_pipeline.py
python test_news_collection_workflow.py
python test_inspiration_workflow.py
python test_ip_content_pipeline.py
```
