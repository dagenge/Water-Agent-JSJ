# 流域水文智能 Agent

基于 LangGraph + PostgreSQL + Prometheus + Grafana 的生产级智能水文数据分析系统。

## 🎯 项目特点

- **智能对话**：基于 LangGraph ReAct Agent，支持多轮对话记忆
- **混合检索**：FAISS 语义搜索 + BM25 关键词 + RRF 融合
- **生产监控**：Prometheus 指标采集 + Grafana 可视化面板
- **向量存储**：PostgreSQL + pgvector 扩展，IVFFlat 索引
- **容器化部署**：Docker Compose 一键启动全栈服务

## 🏗️ 架构设计

```
├── Agent 层
│   ├── 意图识别 (6 类零样本分类)
│   ├── 任务规划 (Plan-Then-Execute)
│   ├── ReAct 循环 (LangGraph + MemorySaver)
│   └── 结果自校验 (一致性验证)
│
├── 知识库层
│   ├── RAG 混合检索 (FAISS + BM25 + RRF)
│   ├── pgvector (IVFFlat 索引，O(K+N/10) 查询)
│   └── BGE-small-zh-v1.5 (512 维中文嵌入)
│
├── 数据层
│   ├── PostgreSQL 15 (业务数据 + 向量存储)
│   └── SQLAlchemy ORM (Basin/Station/Observation 模型)
│
└── 监控层
    ├── Prometheus (15s 采集，30 天保留)
    ├── Grafana (8 个监控面板)
    └── Alertmanager (告警规则)
```

## 🌊 数据覆盖

### 广东流域（5 个）
- **棠荆河 (TJ)**：主要站点覆盖
- **尖山河 (JS)**：连续时序数据
- **河子口 (HZK)**：小时级 + 日级数据
- **白盆珠 (BPZ)**：完整汛期记录
- **布吉河 (BJH)**：城市水文监测

### 数据规模
- 73 个水文站点
- 连续小时数据（2010-12 至 2024-08）
- 完整日数据记录
- 15+ 个汛期事件

## 🚀 快速开始

### 方式一：Docker 部署（推荐）

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env，设置 DEEPSEEK_API_KEY

# 2. 启动全栈服务
cd docker
docker-compose up -d

# 3. 访问服务
# Streamlit UI:  http://localhost:8501
# Grafana:       http://localhost:3000 (admin/admin123)
# Prometheus:    http://localhost:9090
```

详细部署文档：[docker/README.md](docker/README.md)

### 方式二：本地开发

```bash
# 1. 安装依赖 (Python 3.9+)
pip install -r requirements.txt

# 2. 启动 PostgreSQL (Docker)
docker-compose up -d postgres

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env，设置 DEEPSEEK_API_KEY 和数据库连接

# 4. 启动服务
python scripts/start_services.py
```

## 📊 监控指标

访问 Grafana 查看实时监控面板（http://localhost:3000）：

| 指标类别 | 指标项 | 告警阈值 |
|---------|--------|---------|
| **用户体验** | P95 响应时间 | > 10s (warning) |
| | 查询错误率 | > 5% (warning) |
| **系统质量** | 工具调用成功率 | < 90% (critical) |
| | Badcase 突增 | > 5/min (warning) |
| **资源使用** | 活跃会话数 | > 100 (warning) |
| | PostgreSQL 连接数 | > 80 (warning) |

## 🔧 核心功能

### 1. 智能问答

```python
# 用户输入
"查询棠荆河 2024 年 7 月最大流量"

# Agent 自动执行:
# 1. 识别意图: QUERY_FLOW_DATA
# 2. 调用工具: query_basin_flow(basin="TJ", year=2024, month=7)
# 3. 提取数据: 最大流量 850 m³/s
# 4. 自校验: 数值与数据库返回一致 ✓
```

### 2. 文档检索 (RAG)

```python
# 用户输入
"暴雨强度公式怎么推导?"

# RAG 流程:
# 1. 查询改写: "暴雨强度-历时-频率关系 推导方法"
# 2. 混合检索:
#    - FAISS 语义: 余弦相似度 > 0.75 的 Top 3
#    - BM25 关键词: TF-IDF 排序 Top 3
# 3. RRF 融合: 按倒数排名加权合并
# 4. LLM 生成: 基于检索上下文生成答案
```

### 3. 多站点对比分析

```python
# 用户输入
"对比河子口和白盆珠站 2024 年汛期水位变化"

# Agent 执行:
# 1. 任务规划: [查询 HZK 站] → [查询 BPZ 站] → [对比分析] → [生成图表]
# 2. 并行调用: query_station_data(station="HZK") × 2
# 3. Python 分析: execute_python_analysis(code=...)
# 4. 输出图表: [FIGURE] outputs/comparison_20240915_143022.png
```

## 📁 项目结构

```
Project_JSJ_Agent/
├── agent/                      # Agent 核心逻辑
│   ├── executor.py            # ReAct Agent 执行器 (LangGraph)
│   ├── intent.py              # 意图识别 (6 类分类)
│   ├── tools.py               # 工具注册 (23 个工具)
│   └── logger.py              # 结构化日志
│
├── knowledge/                  # 知识库与检索
│   ├── rag_engine.py          # RAG 混合检索 (FAISS + BM25 + RRF)
│   ├── knowledge_tools.py     # 知识库工具 (LangChain Tool)
│   └── graph_engine.py        # 图谱引擎 (预留)
│
├── config/                     # 配置与数据模型
│   ├── database.py            # PostgreSQL 连接池
│   ├── models.py              # SQLAlchemy ORM 模型
│   └── __init__.py
│
├── monitoring/                 # 监控与指标
│   ├── prometheus_metrics.py  # Prometheus 指标收集器
│   └── exporter.py            # HTTP /metrics 端点 (端口 8000)
│
├── docker/                     # 容器化部署
│   ├── docker-compose.yml     # 服务编排 (Postgres/Prometheus/Grafana/Agent)
│   ├── Dockerfile             # Agent 应用镜像
│   ├── docker-entrypoint.sh   # 容器启动脚本
│   ├── postgres/init.sql      # pgvector 扩展初始化
│   ├── prometheus/            # Prometheus 配置 + 告警规则
│   └── grafana/               # Grafana 数据源 + 面板定义
│
├── scripts/                    # 工具脚本
│   └── start_services.py      # 本地启动脚本 (Exporter + Streamlit)
│
├── docs/                       # 技术文档
│   ├── rag_construction.md           # RAG 知识库构建原理
│   ├── rag_pgvector_architecture.md  # pgvector + IVFFlat 架构
│   └── product_metrics_dashboard.md  # 产品指标设计 (PM 视角)
│
├── streamlit_demo.py          # Streamlit 交互界面
├── requirements.txt           # Python 依赖
└── .env.example              # 环境变量模板
```

## 🔗 技术栈

| 类别 | 技术选型 |
|------|---------|
| **Agent 框架** | LangGraph 0.3, LangChain 0.3 |
| **LLM** | DeepSeek V3 (OpenAI API 兼容) |
| **向量检索** | FAISS-CPU 1.8, pgvector (IVFFlat) |
| **文本嵌入** | BGE-small-zh-v1.5 (sentence-transformers) |
| **关键词检索** | Rank-BM25 0.2 |
| **数据库** | PostgreSQL 15 (pgvector 扩展), SQLAlchemy 2.0 |
| **监控** | Prometheus, Grafana, prometheus-client |
| **前端** | Streamlit 1.40, Plotly 6.0 |
| **容器化** | Docker, Docker Compose |

## 📖 相关文档

- [RAG 知识库构建原理](docs/rag_construction.md) - 向量化、切分策略、混合检索
- [pgvector 架构设计](docs/rag_pgvector_architecture.md) - IVFFlat 索引原理、性能优化
- [产品指标面板设计](docs/product_metrics_dashboard.md) - 北极星指标、监控分层、PM 视角
- [Docker 部署指南](docker/README.md) - 完整部署流程、故障排查

## 🐛 故障排查

### 数据库连接失败

```bash
# 检查 PostgreSQL 状态
docker-compose ps postgres

# 测试连接
docker-compose exec postgres psql -U postgres -c "SELECT version();"

# 查看日志
docker-compose logs postgres
```

### Metrics 端点无数据

```bash
# 测试 Exporter
curl http://localhost:8000/metrics

# 检查 Prometheus targets
# 访问 http://localhost:9090/targets
```

### Agent 响应慢

1. 检查 LLM API 延迟（DeepSeek 服务状态）
2. 查看 Grafana P95 响应时间面板
3. 检查 PostgreSQL 查询性能：
   ```sql
   SELECT * FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;
   ```

## 📝 扩展开发

### 添加新工具

1. 在 `agent/tools.py` 定义工具函数（使用 `@tool` 装饰器）
2. 添加到 `ALL_TOOLS` 列表
3. 更新 `SYSTEM_PROMPT` 中的工具说明
4. 在 `agent/executor.py` 中记录工具调用指标

### 添加新监控指标

1. 在 `monitoring/prometheus_metrics.py` 定义 Counter/Histogram/Gauge
2. 在业务代码中调用 `metrics_collector.record_xxx()`
3. 在 `docker/prometheus/rules/alerts.yml` 添加告警规则
4. 在 Grafana 面板中添加对应图表

## 🤝 贡献

本项目为个人作品集项目，暂不接受外部贡献。

## 📄 许可证

MIT License
