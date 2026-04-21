# API 文档

## 基础信息

- **Base URL**: `http://localhost:8000/api`
- **文档**: `http://localhost:8000/api/docs` (Swagger UI)

## 接口列表

### 仪表盘

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/dashboard/stats` | 获取统计数据 |
| GET | `/dashboard/interest-points` | 获取兴趣点分布 |
| GET | `/dashboard/recommendations` | 获取改进建议 |

### 笔记管理

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/notes` | 获取所有笔记 |
| POST | `/notes` | 创建笔记 |
| GET | `/notes/{id}` | 获取单条笔记 |
| POST | `/notes/{id}/analyze` | 分析笔记情感 |

### 文件上传

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/upload/html` | 上传小红书 HTML |
| POST | `/upload/image` | 上传图片 |

### 模型训练

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/ml/train/sentiment` | 训练情感分析模型 |
| POST | `/ml/train/vlm` | 训练 VLM 模型 |
