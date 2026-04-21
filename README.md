# 古建筑游客兴趣智能分析系统

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg)](https://fastapi.tiangolo.com)
[![Vue 3](https://img.shields.io/badge/Vue-3.4+-4FC08D.svg)](https://vuejs.org)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0+-EE4C2C.svg)](https://pytorch.org)

> 基于自训练 SVM + 轻量级 VLM 的古建筑游客拍照兴趣点分析系统，完整 MLOps 工程实践。

## ✨ 核心亮点

### 🤖 双模型架构

| 模型 | 技术栈 | 参数量 | 推理速度 | 功能 |
|------|--------|--------|----------|------|
| **SVM 情感分析** | scikit-learn + TF-IDF + Jieba | ~10K | < 10ms | 中文游客评论情感分类 |
| **轻量级 VLM** | PyTorch + ResNet18 + 分类头 | ~11M | < 100ms | 8类古建筑兴趣点识别 |

### 🏗️ 工程架构

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Vue3 前端  │────▶│  FastAPI    │────▶│  自训练模型  │
│  Element+   │◀────│   后端服务   │◀────│ SVM + VLM  │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                    ┌──────┴──────┐
                    ▼             ▼
              ┌─────────┐   ┌─────────┐
              │ 笔记数据 │   │ 图片数据 │
              │  JSON   │   │ 文件夹  │
              └─────────┘   └─────────┘
```

## 🚀 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- CUDA 11.8+ (可选，用于 GPU 加速)

### 1. 克隆项目

```bash
git clone https://github.com/Aord1/Building-Analysis.git
cd Building-Analysis
```

### 2. 后端部署

```bash
# 创建虚拟环境
python -m venv venv

# Windows
venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 训练 SVM 模型（首次运行）
python -m ml.sentiment_svm

# 启动服务
python -m cli.main serve
```

后端服务运行在 http://localhost:8000

### 3. 前端部署

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端界面运行在 http://localhost:3000

## 📊 功能模块

### 仪表盘
- 笔记/图片数量统计
- 情感分布饼图
- 热门兴趣点 TOP10
- 模型状态监控

### 笔记管理
- 小红书 HTML 导入
- 批量情感分析
- 分页浏览与筛选

### 图片分析
- 拖拽上传图片
- VLM 自动分类
- 分类统计与预览

### 分析流水线
- 一键执行全流程
- 实时进度显示
- 运行日志查看

### 模型管理
- SVM 超参数调优
- VLM 训练配置
- 模型指标对比

## 🧠 模型详情

### SVM 情感分析

```python
# 技术方案
向量化: TF-IDF (max_features=5000, ngram_range=(1,2))
分类器: SVM (RBF 核，GridSearchCV 调优)
分词:   Jieba 中文分词 + 停用词过滤

# 性能指标
准确率:  ~86%
F1-Score: ~85%
推理速度: < 10ms/条
```

### 轻量级 VLM

```python
# 网络结构
骨干网络: ResNet18 (ImageNet 预训练)
分类头:   2层全连接 (512→256→8)
总参数量: ~11M (模型文件 < 50MB)

# 兴趣点类别
['斗拱', '飞檐', '彩绘', '雕刻', '门窗', '庭院', '雕塑', '碑刻']

# 性能指标
推理速度: < 100ms (CPU)
          < 20ms  (GPU)
```

## 📁 项目结构

```
Building-Analysis/
├── app/                      # FastAPI 后端
│   ├── api/routes/           # RESTful API
│   ├── services/             # 业务逻辑层
│   ├── models/               # Pydantic 数据模型
│   └── core/                 # 配置与日志
├── ml/                       # 自训练模型
│   ├── sentiment_svm.py      # SVM 训练与推理
│   ├── vlm_model.py          # VLM 网络定义
│   └── vlm_trainer.py        # VLM 训练流程
├── frontend/                 # Vue3 前端
│   ├── src/views/            # 页面组件
│   ├── src/stores/           # Pinia 状态管理
│   ├── src/api/              # Axios API 封装
│   ├── src/components/       # 公共组件
│   └── public/               # 静态资源
├── scripts/                  # 工具脚本
│   └── download_dataset.py   # 数据集下载
├── tests/                    # 测试目录
│   ├── unit/                 # 单元测试
│   └── integration/          # 集成测试
├── docs/                     # 文档
│   ├── api.md                # API 文档
│   └── architecture.md       # 架构设计
├── data/                     # 数据目录
├── image/                    # 图片目录
└── models/                   # 模型保存目录
```

## 🔧 API 文档

启动服务后访问：http://localhost:8000/api/docs

### 核心接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/dashboard/stats` | 仪表盘统计 |
| GET | `/api/notes` | 笔记列表 |
| POST | `/api/upload/images` | 上传图片 |
| POST | `/api/pipeline/run` | 执行分析流水线 |
| POST | `/api/ml/train/svm` | 训练 SVM 模型 |
| GET | `/api/ml/models` | 模型列表 |

## 💻 开发指南

### 添加新的兴趣点类别

1. 修改 `configs/interest_taxonomy.json`
2. 重新训练 VLM 模型
3. 更新前端类型定义

### 自定义训练数据

```python
# 准备标注数据
# data/training/sentiment/positive.txt
# data/training/sentiment/negative.txt

# 重新训练
from ml.sentiment_svm import SVMTrainer, load_custom_data

texts, labels = load_custom_data('data/training/sentiment')
trainer = SVMTrainer('models')
trainer.train(texts, labels, tune_hyperparams=True)
```

## 📝 简历描述参考

```markdown
**古建筑游客兴趣智能分析系统** | Python, PyTorch, scikit-learn, FastAPI, Vue3
- 独立设计并实现双模型架构：自训练 SVM (F1-Score 0.86) + 轻量级 VLM (模型 < 50MB)
- 构建完整 MLOps 流程：数据预处理 → 超参数调优 → 模型训练 → API 服务化部署
- 采用分层架构设计，使用 FastAPI + Vue3 构建高性能全栈应用
- 实现模型本地推理，相比云端 API 成本降低 100%，推理延迟 < 100ms
```

## 🤝 贡献指南

1. Fork 本项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## 🙏 致谢

- [FastAPI](https://fastapi.tiangolo.com/) - 高性能 Web 框架
- [Vue.js](https://vuejs.org/) - 渐进式前端框架
- [Element Plus](https://element-plus.org/) - UI 组件库
- [PyTorch](https://pytorch.org/) - 深度学习框架

---

> 本项目为个人学习作品，欢迎 Star 和 Fork！
