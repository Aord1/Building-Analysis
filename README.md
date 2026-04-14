# 大模型游客分析平台

基于大语言模型的建筑游览数字化分析平台，自动分析游客笔记情感倾向、图像兴趣分布，并生成管理优化建议。

## 功能特性

### 核心功能
- **HTML 笔记导入**：支持单文件、多文件、批量文件夹上传
- **情感分析**：基于 NLP 的游客情感倾向分析，支持正向/中性/负向分类
- **图像兴趣识别**：使用 VLM（视觉语言模型）识别游客关注的图像内容
- **智能建议生成**：基于分析结果自动生成路线优化和文化展示建议

### 可视化展示
- 情感分布饼状图（带中文标签）
- 图像兴趣 Top 标签条形图
- 优先级颜色区分（紧急/高/中/低）
- 大模型对话式回答展示

## 技术架构

```
build_analysis/
├── frontend/          # 前端界面
│   ├── index.html    # 主页面
│   ├── styles.css    # 样式文件
│   └── app.js        # 前端逻辑
├── backend/          # 后端 API 服务
│   └── server.py     # HTTP API 服务器
├── src/              # 核心分析模块
│   ├── analysis/     # 分析算法
│   │   ├── analyze_text_sentiment.py      # 情感分析
│   │   ├── classify_with_vlm.py           # VLM 图像分类
│   │   ├── generate_management_recommendations.py  # 建议生成
│   │   └── build_image_manifest.py        # 图像清单构建
│   └── importers/    # 数据导入
│       └── xhs_html_importer.py           # HTML 笔记导入
├── configs/          # 配置文件
├── data/             # 数据存储
└── docs/             # 文档
```

## 快速开始

### 环境要求
- Python 3.9+
- 支持现代浏览器的客户端

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置

创建 `.env` 文件：

```env
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
```

### 启动服务

1. **启动后端 API 服务**：

```bash
python backend/server.py --port 8000
```

2. **打开前端页面**：

直接打开 `frontend/index.html` 或使用本地服务器：

```bash
cd frontend
python -m http.server 8080
```

然后访问 http://localhost:8080

## 使用指南

### 上传分析

1. **单文件/多文件上传**：选择蓝色区域的文件输入框，选择一个或多个 HTML 文件
2. **批量文件夹上传**：选择紫色区域的文件夹输入框，选择包含多个 HTML 文件的文件夹
3. 点击"🚀 上传并自动分析"按钮

### 查看结果

- **对话式回答**：上传后首先展示大模型对每篇笔记的图像分析回答
- **本次上传建议**：展示基于本次上传数据的图像兴趣和情感分布
- **全量数据**：切换到"全量数据与管理建议"页面查看汇总分析

### 数据管理

- **刷新数据**：重新加载所有分析报告
- **全量一键运行**：重新执行完整的分析流程
- **清空已记录HTML**：删除已上传的 HTML 文件记录
- **清空全部data**：清空所有数据和分析结果

## 分析指标说明

### 情感分析
- **正向情感**：游客表达满意、惊喜、推荐等积极情绪
- **中性情感**：客观描述、无明显情感倾向
- **负向情感**：表达不满、失望、抱怨等消极情绪
- **正向指数**：整体正向情感的加权占比（0-1）

### 图像兴趣标签
| 英文标签 | 中文含义 |
|---------|---------|
| courtyard_garden | 庭院园林 |
| garden_plants | 园林植物 |
| architecture_overview | 建筑全景 |
| architectural_detail | 建筑细节 |
| plaque_inscription | 匾额题刻 |
| interior_space | 室内空间 |
| cultural_relic | 文物陈设 |
| visitor_crowd | 游客人流 |
| landscape_view | 景观视野 |
| decorative_art | 装饰艺术 |

### 建议优先级
- **🔴 紧急**：需要立即处理的问题
- **🟠 高**：重要优化建议
- **🔵 中**：一般性改进建议
- **🟢 低**：可选优化项

## API 接口

后端提供以下 REST API：

| 接口 | 方法 | 说明 |
|-----|------|------|
| `/health` | GET | 健康检查 |
| `/api/dashboard` | GET | 获取仪表盘数据 |
| `/api/sentiment` | GET | 获取情感分析数据 |
| `/api/recommendations` | GET | 获取管理建议 |
| `/api/upload-html` | POST | 上传 HTML 文件 |
| `/api/recompute` | POST | 重新计算报告 |
| `/api/run-pipeline` | POST | 运行完整流程 |
| `/api/clear-html-files` | POST | 清空 HTML 文件 |
| `/api/clear-data-files` | POST | 清空所有数据 |

## 开发说明

### 添加新的图像兴趣标签

编辑 `configs/interest_taxonomy.json`，添加新的标签定义：

```json
{
  "new_label": {
    "zh": "新标签中文名",
    "description": "标签描述"
  }
}
```

然后在 `frontend/app.js` 的 `LABEL_ZH_MAP` 中添加对应的中文映射。

### 自定义情感分析词典

编辑 `src/analysis/analyze_text_sentiment.py`，修改 `POSITIVE_TERMS` 和 `NEGATIVE_TERMS` 字典。

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request。

## 联系方式

如有问题，请通过 GitHub Issues 联系。
