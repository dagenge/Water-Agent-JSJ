# 流域水文智能 Agent

基于 LangGraph + DeepSeek + RAG 的多流域智能水文数据分析系统。

## 🎯 项目特点

- **智能对话**：基于 LangGraph ReAct Agent，支持多轮对话记忆（MemorySaver checkpointer）
- **多流域支持**：覆盖金沙江（DQH + BtPzh）和广东 5 个流域，共 121 个水文站点
- **混合检索**：BGE-small-zh 语义搜索 + BM25 关键词 + RRF 融合排序
- **代码执行沙盒**：隔离进程执行 Python 分析代码（pandas/matplotlib），支持复杂统计和可视化
- **生产监控**：Prometheus 指标采集 + Grafana 实时面板，覆盖响应时间/工具调用/错误率
- **可视化界面**：Streamlit 前端，支持地图展示（Leaflet）、事件查询、降雨过程线绘制

## 🏗️ 架构设计

```
├── Agent 层
│   ├── 意图识别 (6 类零样本分类：RAIN_QUERY/STAT_ANALYSIS/CORRELATION/REPORT_GEN/BASIN_QUERY/GENERAL)
│   ├── 任务规划 (Plan-Then-Execute，LLM 拆解为有序子步骤)
│   ├── ReAct 循环 (LangGraph create_react_agent + MemorySaver 跨轮次记忆)
│   └── 结果自校验 (对照工具返回值验证数字准确性)
│
├── 工具层 (8 个数据查询工具 + 1 个代码执行工具)
│   ├── query_basin_list           # 列出所有流域
│   ├── query_station_list         # 查询站点列表
│   ├── query_dqh_events           # 查询 DQH 汛期事件
│   ├── query_dqh_rainfall         # 查询 DQH 事件降雨时序
│   ├── query_dqh_statistics       # 查询 DQH 事件降雨统计
│   ├── query_btpzh_rainfall       # 按时间范围查询 BtPzh 降雨
│   ├── query_btpzh_statistics     # BtPzh 时段统计（累计/极值）
│   └── execute_python_analysis    # 隔离进程执行 pandas/matplotlib 代码
│
├── 知识库层
│   ├── RAG 混合检索 (BGE-small-zh + BM25 + RRF)
│   ├── PostgreSQL pgvector 扩展 (512 维中文嵌入向量存储)
│   └── 水文知识文档 (markdown 切分，元数据过滤)
│
├── 数据层
│   ├── PostgreSQL 数据库 (basin_metadata / station_metadata / 事件数据表)
│   ├── DQH: 26 张事件表 (dqh_hourly_* / dqh_daily_*)
│   ├── BtPzh: 2 张连续时序表 (btpzh_hourly / btpzh_daily)
│   └── 广东流域: CSV 文件 (Flood/*.csv，动态扫描)
│
└── 监控层
    ├── Prometheus (意图分布/响应时间/工具调用成功率/错误率)
    ├── Grafana (8 个监控面板)
    └── 结构化日志 (JSON 格式，按 session_id 存储)
```

## 🌊 数据覆盖

### 金沙江流域（2 个）
- **定曲河 (DQH)**：4 站（古学/得荣/热打/乡城），11 个汛期小时事件（2008-2024），15 个汛期日事件
- **巴塘—攀枝花 (BtPzh)**：73 站，连续小时数据（2010-12 ~ 2024-08），连续日数据

### 广东流域（5 个）
- **布吉河 (BJH)**：5 站，城市水文监测
- **棠荆 (TJ)**：7 站，完整汛期记录
- **尖山 (JS)**：18 站，连续时序数据
- **河子口 (HZK)**：7 站，小时级 + 日级数据
- **白盆珠水库 (BPZ)**：7 站，水库调度数据

### 数据规模
- **121 个水文站点**（4 + 73 + 44）
- **定曲河**：26 个汛期事件（11 小时 + 15 日）
- **巴塘—攀枝花**：连续时序（2010-12 至 2024-08）
- **广东流域**：多场次洪水过程数据

## 🚀 快速开始

### 前置要求

- Python 3.9+
- DeepSeek API Key（申请地址：https://platform.deepseek.com）

### 安装步骤

```bash
# 1. 克隆仓库
git clone https://github.com/your-username/Project_JSJ_Agent.git
cd Project_JSJ_Agent

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY

# 5. 启动服务
python scripts/start_services.py
```

### 访问服务

- **Streamlit UI**: http://localhost:8501
- **Prometheus Metrics**: http://localhost:8000/metrics

### Docker 部署（可选）

```bash
# 启动全栈服务（包含 Prometheus + Grafana）
cd docker
docker-compose up -d

# 访问 Grafana: http://localhost:3000 (admin/admin123)
```

详细部署文档：[docker/README.md](docker/README.md)

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

### 1. 多流域站点查询

```python
# 用户输入
"查询棠荆有哪些水文站"

# Agent 自动执行:
# 1. 识别意图: BASIN_QUERY
# 2. 理解语义: "棠荆" → 棠荆流域(tj)
# 3. 调用工具: query_station_list(basin_id="tj")
# 4. 返回结果: 7 个站点（tj_C1~tj_C7）
```

### 2. 降雨统计分析

```python
# 用户输入
"统计定曲河 2009050100 事件各站点累计降雨"

# Agent 执行:
# 1. 识别意图: STAT_ANALYSIS
# 2. 任务规划: [查询事件数据] → [统计计算] → [生成表格]
# 3. 调用工具: query_dqh_statistics(event_code="2009050100", resolution="hourly")
# 4. 输出结果: Markdown 表格 + 柱状图
```

### 3. 代码分析沙盒

```python
# 用户输入
"计算定曲河 2009 年汛期面平均雨量过程线并绘图"

# Agent 执行:
# 1. 识别意图: STAT_ANALYSIS
# 2. 生成代码:
#    conn = get_conn()
#    df = pd.read_sql("SELECT * FROM dqh_hourly_2009050100", conn)
#    area_rain = df[['古学','得荣','热打','乡城']].mean(axis=1)
#    plt.bar(df.index, area_rain)
#    save_fig('areal_rain.png')
# 3. 隔离执行: subprocess 安全沙盒（禁止 os.system/eval/网络请求）
# 4. 返回结果: [FIGURE] outputs/areal_rain.png
```

### 4. RAG 知识问答

```python
# 用户输入
"暴雨强度公式的参数怎么确定?"

# RAG 流程:
# 1. 查询改写: "暴雨强度公式 参数拟合 确定方法"
# 2. 混合检索:
#    - BGE-small-zh 语义: 余弦相似度 Top 3
#    - BM25 关键词: TF-IDF 排序 Top 3
# 3. RRF 融合: 按倒数排名加权合并
# 4. LLM 生成: 基于检索上下文生成答案（引用来源文档）
```

## 📁 项目结构

```
Project_JSJ_Agent/
├── agent/                      # Agent 核心逻辑
│   ├── executor.py            # ReAct Agent 执行器 (LangGraph + MemorySaver)
│   ├── intent.py              # 意图识别 (6 类 LLM 分类)
│   ├── tools.py               # 工具注册 (9 个工具)
│   ├── config.py              # 配置常量（流域映射/路径/LLM）
│   └── logger.py              # 结构化日志（按 session_id 存储）
│
├── knowledge/                  # 知识库与检索
│   ├── rag_engine.py          # RAG 混合检索 (BGE + BM25 + RRF)
│   ├── knowledge_tools.py     # 知识库工具 (LangChain Tool)
│   └── docs/                  # 水文知识文档（markdown）
│
├── data/                       # 数据目录
│   ├── database/
│   │   └── jsj_agent.db       # PostgreSQL 数据库（已迁移）
│   └── analysis_output/       # 代码执行输出目录（图表/CSV）
│
├── monitoring/                 # 监控与指标
│   ├── prometheus_metrics.py  # Prometheus 指标收集器
│   └── exporter.py            # HTTP /metrics 端点 (端口 8000)
│
├── frontend/                   # Streamlit 前端
│   ├── streamlit_app.py       # 主界面（5 个 Tab）
│   └── static/                # Leaflet 静态资源
│
├── scripts/                    # 工具脚本
│   ├── start_services.py              # 启动脚本（Exporter + Streamlit）
│   ├── import_guangdong_basins.py     # 广东流域站点数据导入
│   └── init_database.py               # 数据库初始化
│
├── docker/                     # 容器化部署（可选）
│   ├── docker-compose.yml     # 服务编排
│   ├── prometheus/            # Prometheus 配置
│   └── grafana/               # Grafana 面板定义
│
├── logs/                       # 日志目录
│   └── {session_id}.log       # 按会话存储的结构化日志
│
├── requirements.txt            # Python 依赖
├── .env.example               # 环境变量模板
└── README.md
```

## 🔗 技术栈

| 类别 | 技术选型 |
|------|---------|
| **Agent 框架** | LangGraph 0.3, LangChain 0.3 |
| **LLM** | DeepSeek V3 (OpenAI API 兼容) |
| **向量检索** | PostgreSQL pgvector 扩展 |
| **文本嵌入** | BGE-small-zh-v1.5 (sentence-transformers) |
| **关键词检索** | Rank-BM25 0.2 |
| **数据库** | PostgreSQL 14+ |
| **坐标转换** | PyProj (EPSG:32649/32650 → EPSG:4326) |
| **地图可视化** | Leaflet.js + Shapely + GeoPandas |
| **监控** | Prometheus, Grafana, prometheus-client |
| **前端** | Streamlit 1.40, Plotly 6.0 |
| **数据分析** | Pandas, NumPy, Matplotlib |

## 📖 相关文档

- [Docker 部署指南](docker/README.md) - 完整部署流程、故障排查

## 🐛 故障排查

### 服务无法启动

```bash
# 检查端口占用
netstat -ano | findstr :8501
netstat -ano | findstr :8000

# 查看日志
cat logs/streamlit.log
cat logs/prometheus_exporter.log
```

### Agent 响应慢

1. 检查 LLM API 延迟（DeepSeek 服务状态）
2. 查看 Grafana P95 响应时间面板（http://localhost:3000）
3. 检查工具调用成功率：访问 http://localhost:8000/metrics

### 数据库查询失败

```bash
# 检查 PostgreSQL 服务状态
pg_ctl status -D /path/to/data

# 测试连接
psql -h localhost -U your_user -d jsj_agent -c "SELECT COUNT(*) FROM station_metadata;"

# 查看连接数
psql -h localhost -U your_user -d jsj_agent -c "SELECT count(*) FROM pg_stat_activity;"
```

## 📝 扩展开发

### 添加新工具

1. 在 `agent/tools.py` 定义工具函数（使用 `@tool` 装饰器）
2. 添加到 `ALL_TOOLS` 列表
3. 更新 `agent/executor.py` 中的 `SYSTEM_PROMPT` 工具说明
4. 在工具调用处记录 Prometheus 指标

示例：
```python
@tool
def query_new_basin(basin_id: str) -> str:
    """查询新流域的站点信息"""
    rows = _safe_query("SELECT * FROM new_basin WHERE basin_id=?", (basin_id,))
    return _to_md_table(rows)

# 添加到 ALL_TOOLS
ALL_TOOLS = [..., query_new_basin]
```

### 添加新监控指标

1. 在 `monitoring/prometheus_metrics.py` 定义 Counter/Histogram/Gauge
2. 在业务代码中调用 `metrics_collector.record_xxx()`
3. 在 Grafana 面板中添加对应图表

示例：
```python
# 定义指标
self.tool_errors = Counter(
    'agent_tool_errors_total',
    'Tool execution errors',
    ['tool_name', 'error_type']
)

# 记录指标
metrics_collector.tool_errors.labels(tool_name="query_basin", error_type="timeout").inc()
```

## 🤝 贡献

本项目为个人作品集项目，暂不接受外部贡献。

## 📄 许可证

MIT License
