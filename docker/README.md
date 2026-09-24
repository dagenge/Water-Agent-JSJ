# 流域水文智能 Agent - Docker 部署指南

## 📦 项目架构

```
Docker Stack:
  - PostgreSQL 15 (pgvector 扩展)
  - Prometheus (指标收集)
  - Grafana (可视化面板)
  - Agent 应用 (Streamlit + Metrics Exporter)
```

## 🚀 快速启动

### 1. 环境配置

复制环境变量模板并配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件，设置必需的配置：

```bash
# DeepSeek API Key (必需)
DEEPSEEK_API_KEY=sk-your-actual-api-key

# 数据库配置 (可选，使用默认值)
DB_HOST=postgres
DB_PORT=5432
DB_NAME=water_agent
DB_USER=postgres
DB_PASSWORD=postgres

# Grafana 管理员账号 (可选)
GF_SECURITY_ADMIN_USER=admin
GF_SECURITY_ADMIN_PASSWORD=admin123
```

### 2. 启动服务

```bash
cd docker
docker-compose up -d
```

启动后的服务：

| 服务 | 地址 | 说明 |
|------|------|------|
| Streamlit UI | http://localhost:8501 | Agent 交互界面 |
| Grafana | http://localhost:3000 | 监控面板 (admin/admin123) |
| Prometheus | http://localhost:9090 | 指标查询 |
| Metrics API | http://localhost:8000/metrics | Prometheus 采集端点 |

### 3. 查看日志

```bash
# 查看所有服务日志
docker-compose logs -f

# 查看特定服务
docker-compose logs -f agent
docker-compose logs -f prometheus
docker-compose logs -f grafana
```

### 4. 停止服务

```bash
docker-compose down

# 同时删除数据卷（⚠️ 会清空数据库）
docker-compose down -v
```

## 📊 数据迁移

如果已有 SQLite 数据库，可迁移到 PostgreSQL：

```bash
# 在宿主机运行（需要 Python 环境）
python scripts/migrate_to_postgres.py
```

迁移脚本会：
1. 读取 `data/database/jsj_agent.db`
2. 连接 PostgreSQL (`localhost:5432`)
3. 迁移所有表和数据
4. 保留原 SQLite 文件不变

## 🔧 本地开发模式

不使用 Docker，直接在宿主机运行：

```bash
# 1. 启动 PostgreSQL (Docker)
docker-compose up -d postgres

# 2. 启动应用服务 (本地 Python)
python scripts/start_services.py
```

本地模式访问地址：
- Streamlit: http://localhost:8501
- Metrics: http://localhost:8000/metrics

## 📈 Grafana 面板

首次访问 Grafana (http://localhost:3000)：

1. 登录: `admin` / `admin123`
2. 面板已自动配置，点击 **Dashboards** → **Water Agent Overview**

面板包含 8 个监控指标：
- 总查询数 (1小时)
- 工具调用成功率
- P95 响应时间
- 活跃会话数
- 按意图分类的 QPS
- 响应时间分布 (P50/P95/P99)
- 工具调用分布
- Badcase 趋势

## 🔍 Prometheus 查询示例

访问 http://localhost:9090，尝试以下查询：

```promql
# 查询总数 (最近 5 分钟)
sum(increase(agent_query_total[5m]))

# 工具调用成功率
(sum(rate(agent_tool_call_success_total[5m])) / sum(rate(agent_tool_call_total[5m]))) * 100

# P95 响应时间
histogram_quantile(0.95, rate(agent_query_duration_seconds_bucket[5m]))
```

## 🐛 故障排查

### PostgreSQL 连接失败

```bash
# 检查容器状态
docker-compose ps

# 查看 PostgreSQL 日志
docker-compose logs postgres

# 测试连接
docker-compose exec postgres psql -U postgres -d water_agent -c "SELECT version();"
```

### Agent 启动失败

常见原因：
1. **DEEPSEEK_API_KEY 未设置**: 检查 `.env` 文件
2. **PostgreSQL 未就绪**: 等待数据库健康检查通过
3. **端口冲突**: 修改 `docker-compose.yml` 端口映射

```bash
# 查看 Agent 详细日志
docker-compose logs agent

# 进入容器调试
docker-compose exec agent bash
python -c "from config.database import engine; print(engine.url)"
```

### Grafana 面板无数据

1. 检查 Prometheus 是否正常采集：http://localhost:9090/targets
2. 确认 Agent 应用正在运行并暴露指标：http://localhost:8000/metrics
3. 查看 Grafana 数据源配置：**Configuration** → **Data Sources** → **Prometheus**

## 🔐 生产环境建议

1. **修改默认密码**：`.env` 中的 `DB_PASSWORD` 和 `GF_SECURITY_ADMIN_PASSWORD`
2. **限制端口暴露**：仅暴露必要端口（如 Streamlit 8501）
3. **配置告警通知**：Prometheus Alertmanager 集成（需额外配置）
4. **定期备份数据库**：
   ```bash
   docker-compose exec postgres pg_dump -U postgres water_agent > backup_$(date +%Y%m%d).sql
   ```

## 📁 目录结构

```
docker/
├── docker-compose.yml          # 服务编排
├── Dockerfile                  # Agent 应用镜像
├── docker-entrypoint.sh        # 容器启动脚本
├── .dockerignore              # 构建排除文件
├── postgres/
│   └── init.sql               # 数据库初始化（扩展）
├── prometheus/
│   ├── prometheus.yml         # Prometheus 配置
│   └── rules/
│       └── alerts.yml         # 告警规则
└── grafana/
    ├── provisioning/
    │   ├── datasources/       # 数据源自动配置
    │   └── dashboards/        # 面板自动加载
    └── dashboards/
        └── agent_overview.json  # 监控面板定义
```

## 🔗 相关文档

- [RAG 知识库构建](../docs/rag_construction.md)
- [pgvector 架构设计](../docs/rag_pgvector_architecture.md)
- [产品指标面板设计](../docs/product_metrics_dashboard.md)
