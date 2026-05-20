# TK Listing Agent

AI-powered TikTok Shop Listing Generator — 从搜索到文案到视觉素材的全链路自动生成系统。

## 功能

| 模块 | 能力 |
|------|------|
| 数据搜索 | Apify TikTok Shop 商品搜索 + Bright Data 热门帖子抓取 |
| 文案生成 | DeepSeek 生成英文标题（3版）、5条卖点描述、QA、注意事项、Hashtag |
| 商品图 | Seedream 5.0 图生图，一次生成9张（白底/场景/细节/多角度/模特）|
| 详情长图 | 千问 wan2.7-image 生成13段电商详情模块 → Pillow 自动竖拼 |
| 一键导出 | ZIP 打包：Word报告 + Excel数据 + 商品图 + 详情长图 |

## 技术架构

```
用户输入 → Apify/Bright Data 搜索 → DeepSeek 文案生成
                ↓
         Seedream 5.0 9张商品图
                ↓
         千问 wan2.7-image 13段详情模块
                ↓
         Pillow 竖拼 → 完整详情长图
                ↓
         ZIP 一键导出
```

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 API Keys
cp .env.example .env
# 编辑 .env 填入你的 API Key

# 3. 启动
python app.py

# 4. 打开浏览器 http://127.0.0.1:7861
```

## API 配置

需要在 `.env` 中配置以下服务：

| 服务 | 用途 | 获取方式 |
|------|------|---------|
| Bright Data | TikTok 帖子数据 | brightdata.com |
| DeepSeek | 文案生成 | platform.deepseek.com |
| Apify | TikTok Shop 搜索 | apify.com |
| 火山引擎 ARK | Seedream 5.0 商品图 | console.volcengine.com/ark |
| 阿里云 DashScope | 千问详情图 | dashscope.console.aliyun.com |

## 使用流程

1. **Tab 1** — 填写产品信息，搜索市场数据
2. **Tab 4** — 生成文案（标题/卖点/QA/Hashtag）
3. **Tab 5** — 上传参考图，生成9张商品图
4. **Tab 6** — 一键生成13段详情长图
5. **Tab 7** — 导出 ZIP（Word + Excel + 图片）

## 项目结构

```
tk_listing_agent/
├── app.py                    # Gradio 主界面
├── apify_fetcher.py          # Apify 商品搜索
├── data_fetcher.py           # Bright Data 帖子抓取
├── text_generator.py         # DeepSeek 文案生成
├── image_generator_v2.py     # Seedream + 千问 图片生成
├── requirements.txt          # Python 依赖
├── .env.example              # API Key 配置模板
└── README.md
```

## 技术栈

Python | Gradio | DeepSeek API | Seedream 5.0 | 千问 wan2.7-image | Pillow | Apify | Bright Data
