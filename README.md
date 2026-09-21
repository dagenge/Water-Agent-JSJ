# 金沙江流域水文智能 Agent

基于 **LangChain + LangGraph + DeepSeek** 构建的水文数据分析 Agent，覆盖金沙江两个典型流域：

| 流域 | ID | 站点数 | 数据类型 | 时间范围 |
|------|----|--------|---------|---------|
| 定曲河 | dqh | 4 | 汛期小时/日事件 | 2008–2024（汛期） |
| 巴塘—攀枝花 | btpzh | 73 | 连续小时/日时序 | 2010-12 ~ 2024-08 |

## 技术栈

| 层级 | 技术 |
|------|------|
| LLM | DeepSeek V4 Pro |
| Agent 框架 | LangChain 1.3+ / LangGraph (ReAct + Plan-Then-Execute) |
| Embedding | **BAAI/bge-small-zh-v1.5**（sentence-transformers，真实语义向量，~84MB） |
| 混合检索 | FAISS + BM25 + RRF 融合 |
| 代码执行 | 隔离子进程 + 60s 超时（pandas / matplotlib / numpy） |
| 前端 | Streamlit 5-Tab 大屏 |
| 地图 | Leaflet 1.9.4（本地）+ 高德卫星瓦片 |
| 数据库 | SQLite（DQH 事件表 + BtPzh 宽表） |
| 后端 API | FastAPI（异步 `/chat`） |

## 项目结构

```
Project_JSJ_Agent/
├── agent/
│   ├── config.py       # LLM 配置、路径常量
│   ├── intent.py       # 意图识别（6类）
│   ├── tools.py        # 8个工具（7 SQL + 1 代码执行）
│   ├── executor.py     # Plan-Then-Execute + ReAct + 自校验 + 对话记忆
│   └── logger.py       # 本地 JSONL 日志
├── knowledge/
│   ├── rag_engine.py   # BGEEmbeddings + FAISS + BM25 + RRF
│   ├── graph_engine.py # 水系拓扑（NetworkX）
│   ├── knowledge_tools.py
│   └── basins/
│       ├── dqh/flood_prevention.md
│       └── btpzh/flood_prevention.md
├── data/
│   ├── init_database.py  # 一次性初始化脚本
│   └── database/         # jsj_agent.db（运行后生成）
├── backend/server.py     # FastAPI（异步 /chat）
├── frontend/streamlit_app.py  # 5-Tab 大屏
├── logs/                 # JSONL 运行日志
├── .env.example
└── requirements.txt
```

## 快速开始

### 1. 创建项目虚拟环境并安装依赖

Windows：

```bash
python -m venv .venv
.venv\\Scripts\\python -m pip install --upgrade pip
.venv\\Scripts\\python -m pip install -r requirements.txt
```

Linux/macOS：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
```

### 2. 配置 API Key

```bash
# 复制 .env.example 为 .env，并编辑 .env 填入 DEEPSEEK_API_KEY
```

### 3. 初始化数据库（首次运行，约需 5–10 分钟）

```bash
.venv\\Scripts\\python data/init_database.py  # Windows
# .venv/bin/python data/init_database.py        # Linux/macOS
```

### 4. 启动 Streamlit 前端

```bash
.venv\\Scripts\\python -m streamlit run frontend/streamlit_app.py --server.port 3000
```

访问：http://localhost:3000

### 5. 启动 FastAPI 后端（可选）

```bash
.venv\\Scripts\\python backend/server.py
```

访问：http://localhost:8765/docs

## 关键改进（相较于广东项目）

1. **真实语义 Embedding**：`BAAI/bge-small-zh-v1.5`（512维余弦相似度）替代字符 n-gram hash
2. **Plan-Then-Execute 架构**：Agent 先拆解任务再执行，步骤可见
3. **代码执行工具**：`execute_python_analysis` 允许 Agent 编写 pandas/matplotlib 代码并在隔离进程中运行，真正做数据分析而非仅查询
4. **多轮对话记忆**：`chat_history` 实际传入 `agent.invoke()`
5. **异步 FastAPI**：`/chat` 改为 `run_in_executor`，非阻塞
6. **双数据模态统一**：事件型（DQH）+ 连续时序（BtPzh）统一接口

## 站点坐标说明

BtPzh 的 73 个站点已使用 `遥测站_巴塘以下ArcGIS.xls` 中的经纬度写入数据库，`is_approximate=0`。
DQH 的 4 个站点也已写入精确坐标。地图展示会读取数据库坐标，并将两个 SHP 从 EPSG:32647 转换为 EPSG:4326 后渲染。
