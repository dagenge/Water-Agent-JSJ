# 流域水文智能 Agent

基于 **LangGraph + DeepSeek** 构建的水利行业 AI 助手，覆盖金沙江流域和广东省四大流域。

## 覆盖范围

| 区域 | 流域 | 站点数 | 覆盖范围 |
|------|------|--------|---------|
| 金沙江 | 巴塘—攀枝花 (btpzh) | 73 | 云南、四川 |
| 金沙江 | 定曲河 (dqh) | 4 | 云南 |
| 广东省 | 布吉河 (bjh) | 5 | 深圳 |
| 广东省 | 白盆珠 (bpz) | 7 | 惠州 |
| 广东省 | 鉴江 (js) | 18 | 茂名 |
| 广东省 | 潭江 (tj) | 7 | 江门 |

**总计**：114 个水文站点

## 核心功能

- ✅ **自然语言查询**：用对话代替 SQL
- ✅ **多站对比分析**：自动生成对比图表
- ✅ **历史事件检索**：相似汛情快速定位
- ✅ **智能文档问答**：防汛文档秒级检索

## 技术栈

| 层级 | 技术 |
|------|------|
| LLM | DeepSeek V4 Pro |
| Agent 框架 | LangGraph (ReAct Agent) |
| 检索引擎 | FAISS + BM25 + RRF 融合 |
| 前端 | Streamlit |
| 数据库 | PostgreSQL + SQLite |

## 项目结构

```
Project_JSJ_Agent/
├── agent/
│   ├── config.py       # LLM 配置
│   ├── intent.py       # 意图识别
│   ├── tools.py        # Agent 工具集
│   ├── executor.py     # Agent 执行引擎
│   └── logger.py       # 日志记录
├── knowledge/
│   ├── rag_engine.py   # RAG 检索引擎
│   └── basins/         # 流域知识库
├── data/
│   ├── database/       # SQLite 数据库
│   └── init_database.py
├── streamlit_demo.py   # Web 应用界面
├── .env.example
└── requirements.txt
```

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/你的用户名/Water-Agent-JSJ.git
cd Water-Agent-JSJ
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置 API Key

```bash
cp .env.example .env
# 编辑 .env 填入 DEEPSEEK_API_KEY
```

### 4. 启动应用

```bash
streamlit run streamlit_demo.py
```

访问：http://localhost:8501

## 在线访问

部署在 Streamlit Cloud：

```
https://你的用户名-water-agent-jsj.streamlit.app
```

## 技术架构
