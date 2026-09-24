# 产品数据看板搭建方案（产品经理视角）

## 一、为什么需要数据看板？

### 1.1 业务背景

**痛点：** Agent 上线后，领导和用户经常问：
- "这个 Agent 到底有没有用？"
- "用户满意吗？哪里需要改进？"
- "系统稳定吗？出了问题能快速发现吗？"

**解决：** 搭建数据看板，**让产品的健康状况可视化、可量化**

---

## 二、核心指标体系（分层设计）

### 2.1 指标金字塔

```
                      【北极星指标】
                    用户采纳率 87%
                  7日留存率 91%
                          ↑
        ┌─────────────────┴─────────────────┐
        |                                   |
   【使用指标】                         【质量指标】
  日活 18 人                        准确率 92%
  人均调用 4.8 次/天                  幻觉率 4.1%
  自助率 92%                        响应时间 4.8s
        ↑                                   ↑
        └───────────────┬───────────────────┘
                        |
                   【技术指标】
                工具调用成功率 96%
                系统可用性 99.5%
                P95延迟 7.2s
```

### 2.2 指标详解

#### 北极星指标（核心价值）

| 指标 | 定义 | 目标值 | 说明 |
|-----|------|--------|------|
| **用户采纳率** | 注册用户中使用过Agent的比例 | >80% | 衡量产品是否真正被需要 |
| **7日留存率** | 首次使用后第7天仍在使用的比例 | >85% | 衡量产品是否有持续价值 |

#### 使用指标（产品活跃度）

| 指标 | 定义 | 采集方式 |
|-----|------|---------|
| **日活跃用户（DAU）** | 每天使用Agent的独立用户数 | Streamlit `session_id` 去重统计 |
| **人均调用次数** | 每个用户平均提问次数 | 总调用数 / DAU |
| **自助率** | 未求助技术人员解决的问题占比 | (总问题数 - 技术工单数) / 总问题数 |
| **功能渗透率** | 各功能的使用占比 | 数据查询 65%、文档问答 25%、代码生成 10% |

#### 质量指标（产品好不好用）

| 指标 | 定义 | 采集方式 |
|-----|------|---------|
| **准确率** | Agent回答正确的比例 | 人工抽样标注 + 用户反馈 |
| **幻觉率** | Agent编造事实的比例 | 一致性校验拦截数 / 总回答数 |
| **响应时间** | 从提问到收到答案的耗时 | 后端日志记录（P50/P95/P99） |
| **用户满意度** | 用户评分平均值 | Streamlit 👍/👎 反馈按钮 |

#### 技术指标（系统健康度）

| 指标 | 定义 | 监控方式 |
|-----|------|---------|
| **工具调用成功率** | 工具执行成功的比例 | 后端日志统计异常 |
| **系统可用性** | 服务正常运行时间占比 | 健康检查接口 + 告警 |
| **错误率** | 请求失败的比例 | HTTP 5xx / 总请求数 |

---

## 三、数据采集方案（怎么获取数据）

### 3.1 数据采集架构

```
用户交互（Streamlit）
    ↓ 埋点
日志文件（logs/agent_YYYYMMDD.log）
    ↓ 定时任务（每小时）
解析 + 聚合 → SQLite（metrics.db）
    ↓ Streamlit定时刷新
数据看板（可视化展示）
```

### 3.2 日志埋点设计

**核心原则：关键路径全埋点，细节按需埋点**

```python
# agent/logger.py 示例

import logging
import json
from datetime import datetime

class MetricsLogger:
    def __init__(self):
        self.logger = logging.getLogger("metrics")
        handler = logging.FileHandler(f"logs/agent_{datetime.now():%Y%m%d}.log")
        handler.setFormatter(logging.Formatter('%(message)s'))
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def log_query(self, session_id: str, user_input: str, intent: str):
        """记录用户提问"""
        self.logger.info(json.dumps({
            "type": "query",
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "user_input": user_input,
            "intent": intent,  # 意图识别结果
        }, ensure_ascii=False))
    
    def log_tool_call(self, session_id: str, tool_name: str, success: bool, duration_ms: float):
        """记录工具调用"""
        self.logger.info(json.dumps({
            "type": "tool_call",
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "tool_name": tool_name,
            "success": success,
            "duration_ms": duration_ms,
        }))
    
    def log_response(self, session_id: str, response_time_ms: float, user_feedback: str = None):
        """记录响应和用户反馈"""
        self.logger.info(json.dumps({
            "type": "response",
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "response_time_ms": response_time_ms,
            "user_feedback": user_feedback,  # "thumbs_up" / "thumbs_down" / None
        }))
```

**日志示例：**
```json
{"type": "query", "timestamp": "2024-07-15T10:30:45", "session_id": "abc123", "user_input": "查询武汉站水位", "intent": "data_query"}
{"type": "tool_call", "timestamp": "2024-07-15T10:30:46", "session_id": "abc123", "tool_name": "query_station_list", "success": true, "duration_ms": 245}
{"type": "response", "timestamp": "2024-07-15T10:30:50", "session_id": "abc123", "response_time_ms": 4800, "user_feedback": "thumbs_up"}
```

### 3.3 数据聚合脚本

**定时任务（每小时运行）：**

```python
# monitoring/aggregate_metrics.py

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

def parse_logs(log_file: str):
    """解析日志文件，提取指标"""
    queries = []
    tool_calls = []
    responses = []
    
    with open(log_file) as f:
        for line in f:
            data = json.loads(line)
            if data["type"] == "query":
                queries.append(data)
            elif data["type"] == "tool_call":
                tool_calls.append(data)
            elif data["type"] == "response":
                responses.append(data)
    
    return queries, tool_calls, responses

def aggregate_daily_metrics(date: str):
    """聚合指定日期的指标"""
    log_file = f"logs/agent_{date.replace('-', '')}.log"
    queries, tool_calls, responses = parse_logs(log_file)
    
    # 计算指标
    metrics = {
        "date": date,
        "dau": len(set(q["session_id"] for q in queries)),  # 去重session_id
        "total_queries": len(queries),
        "avg_response_time": sum(r["response_time_ms"] for r in responses) / len(responses),
        "tool_success_rate": sum(1 for t in tool_calls if t["success"]) / len(tool_calls) * 100,
        "positive_feedback_rate": sum(1 for r in responses if r["user_feedback"] == "thumbs_up") / len(responses) * 100,
    }
    
    # 写入数据库
    conn = sqlite3.connect("monitoring/metrics.db")
    conn.execute("""
        INSERT INTO daily_metrics (date, dau, total_queries, avg_response_time, tool_success_rate, positive_feedback_rate)
        VALUES (?, ?, ?, ?, ?, ?)
    """, tuple(metrics.values()))
    conn.commit()
    conn.close()
    
    print(f"✅ {date} 指标聚合完成")

if __name__ == "__main__":
    # 聚合昨天的数据
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    aggregate_daily_metrics(yesterday)
```

**Cron 定时任务：**
```bash
# 每小时运行一次
0 * * * * cd /path/to/project && python monitoring/aggregate_metrics.py
```

---

## 四、数据看板设计（怎么展示）

### 4.1 看板布局（三屏设计）

**屏幕 1：概览大屏（领导视角）**

```
┌─────────────────────────────────────────────────────┐
│  流域水文 Agent 运行概览       2024-07-15 10:30     │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│  │ 日活用户  │  │ 7日留存   │  │ 用户满意度 │          │
│  │   18     │  │  91%     │  │  4.5/5   │          │
│  │  ↑ 12%   │  │  ↑ 3%    │  │  ↑ 0.3   │          │
│  └──────────┘  └──────────┘  └──────────┘          │
│                                                     │
│  【本周趋势】                                        │
│  用户调用量 ▁▂▃▅▆▇█ (折线图)                         │
│  工具调用成功率 ▇▇▆▇▇▇▇ (面积图)                     │
│                                                     │
│  【功能使用分布】                                     │
│  ■■■■■■■■■ 65% 数据查询                             │
│  ■■■■ 25% 文档问答                                  │
│  ■■ 10% 代码生成                                    │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**屏幕 2：质量监控（运营视角）**

```
┌─────────────────────────────────────────────────────┐
│  质量指标详情                                        │
├─────────────────────────────────────────────────────┤
│                                                     │
│  准确率趋势（过去7天）                                │
│  100% ┤                                            │
│   90% ┤     ●───●───●───●  ← 目标线 92%            │
│   80% ┤ ●───●                                      │
│   70% └─────────────────────────────               │
│                                                     │
│  响应时间分布（P50/P95/P99）                          │
│  ┌─────────────────────────────┐                  │
│  │ P50: 3.2s │ P95: 7.2s │ P99: 12.5s │          │
│  │ ▓▓▓▓▓▓    │ ▓▓▓▓▓▓▓▓▓ │ ▓▓▓▓▓▓▓▓▓▓▓│          │
│  └─────────────────────────────┘                  │
│                                                     │
│  近期 Badcase（最近10条）                            │
│  ❌ 2024-07-15 09:45 "武汉站流量" → 误识别为水位     │
│  ❌ 2024-07-15 08:30 "定曲河事件" → 查询超时         │
│  ❌ 2024-07-14 16:20 "对比分析" → 工具调用失败        │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**屏幕 3：技术监控（开发视角）**

```
┌─────────────────────────────────────────────────────┐
│  系统健康度                                          │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│  │ 系统可用性 │  │ 工具成功率 │  │ 错误率   │          │
│  │ 99.5%    │  │  96.2%   │  │  0.5%    │          │
│  └──────────┘  └──────────┘  └──────────┘          │
│                                                     │
│  工具调用分布（过去24小时）                            │
│  query_station_list      ▓▓▓▓▓▓▓▓▓▓ 45%            │
│  query_btpzh_rainfall    ▓▓▓▓▓▓ 30%                │
│  execute_python_analysis ▓▓▓ 15%                   │
│  query_dqh_events        ▓▓ 10%                    │
│                                                     │
│  错误日志（最近5条）                                  │
│  ⚠️ 2024-07-15 10:15 ConnectionError: DB timeout   │
│  ⚠️ 2024-07-15 09:30 ToolCallError: Invalid param  │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### 4.2 实现技术栈

**方案 1：Streamlit（快速原型）**

```python
# monitoring/dashboard.py

import streamlit as st
import pandas as pd
import plotly.express as px
import sqlite3

st.set_page_config(page_title="Agent 数据看板", layout="wide")

# 读取数据
conn = sqlite3.connect("monitoring/metrics.db")
df = pd.read_sql("SELECT * FROM daily_metrics ORDER BY date DESC LIMIT 30", conn)

# 第一行：KPI 卡片
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("日活用户", df.iloc[0]["dau"], delta=f"+{df.iloc[0]['dau'] - df.iloc[1]['dau']}")
with col2:
    st.metric("平均响应时间", f"{df.iloc[0]['avg_response_time']:.1f}s", delta=f"-{df.iloc[1]['avg_response_time'] - df.iloc[0]['avg_response_time']:.1f}s")
with col3:
    st.metric("用户满意度", "4.5/5", delta="+0.3")

# 第二行：趋势图
fig = px.line(df, x="date", y="total_queries", title="用户调用量趋势")
st.plotly_chart(fig, use_container_width=True)

# 第三行：工具调用分布
tool_stats = pd.read_sql("SELECT tool_name, COUNT(*) as count FROM tool_calls WHERE date >= date('now', '-7 days') GROUP BY tool_name", conn)
fig = px.bar(tool_stats, x="tool_name", y="count", title="工具调用分布（过去7天）")
st.plotly_chart(fig, use_container_width=True)
```

**方案 2：Grafana + Prometheus（生产级）**

```yaml
# docker-compose.yml

version: '3'
services:
  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"
  
  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
```

**优势对比：**

| 方案 | 优势 | 劣势 | 适用场景 |
|-----|------|------|---------|
| Streamlit | 快速搭建，Python原生 | 性能一般，不支持告警 | 内部看板，快速验证 |
| Grafana | 专业级，支持告警，性能强 | 学习成本高，需维护 | 生产环境，长期监控 |

---

## 五、数据驱动迭代（怎么用数据）

### 5.1 发现问题的流程

**案例：准确率突然下降**

```
1. 看板告警：准确率从 92% 降至 85%（触发阈值）
   ↓
2. 下钻分析：哪个时间段？哪类问题？
   → 发现：7月10日后，"站点查询"类问题准确率骤降
   ↓
3. 查看 Badcase 列表
   → 发现：用户输入"武汉站"，Agent 返回空结果
   ↓
4. 复现问题
   → 原因：7月10日更新了站点数据，"武汉站"改名为"武汉水文站"
   ↓
5. 修复方案
   → 在工具中增加站点名称模糊匹配逻辑
   ↓
6. 验证效果
   → 准确率恢复至 93%，问题解决
```

### 5.2 A/B 测试框架

**场景：优化 Prompt，提升工具选择准确率**

```python
# 实现简单的A/B测试

import random

def get_system_prompt(session_id: str):
    # 根据 session_id 哈希值分流
    version = "B" if hash(session_id) % 2 == 0 else "A"
    
    if version == "A":
        return SYSTEM_PROMPT_V1  # 原版 Prompt
    else:
        return SYSTEM_PROMPT_V2  # 新版 Prompt（增加示例）

# 日志中记录版本
logger.log_query(session_id, user_input, intent, prompt_version=version)

# 分析时按版本分组对比
SELECT 
    prompt_version,
    AVG(tool_success_rate) as success_rate,
    AVG(response_time_ms) as avg_time
FROM tool_calls
WHERE date >= '2024-07-10'
GROUP BY prompt_version;

-- 结果：
-- Version A: 91.5% 成功率，4.8s 平均响应
-- Version B: 95.2% 成功率，5.1s 平均响应
-- 结论：B 版本准确率更高，响应时间略慢（可接受）→ 全量切换 B
```

### 5.3 用户反馈闭环

**实现 👍/👎 反馈机制：**

```python
# streamlit_demo.py 中添加反馈按钮

col1, col2 = st.columns(2)
with col1:
    if st.button("👍 准确", key="thumbs_up"):
        logger.log_feedback(session_id, "thumbs_up", user_input, response)
        st.success("感谢反馈！")
with col2:
    if st.button("👎 不准确", key="thumbs_down"):
        logger.log_feedback(session_id, "thumbs_down", user_input, response)
        feedback_detail = st.text_input("可以告诉我们哪里不对吗？")
        if feedback_detail:
            logger.log_badcase(session_id, user_input, response, feedback_detail)
```

**Badcase 管理流程：**

```
用户点击 👎
    ↓
记录到 badcase 表
    ↓
每周人工标注（正确答案）
    ↓
分析错误类型（意图识别错误？工具选择错误？数据缺失？）
    ↓
针对性优化（调整 Prompt / 增加示例 / 补充数据）
    ↓
在测试集上验证
    ↓
发布新版本
    ↓
看板监控：Badcase 率从 15% 降至 5%
```

---

## 六、产品指标演进历程

### 6.1 MVP 阶段（验证需求）

**核心指标：** 用户是否愿意用？

- ✅ 日活用户数（目标：≥10人）
- ✅ 人均调用次数（目标：≥3次/天）

**数据收集：** 简单埋点（session_id + 调用次数）

**看板：** Excel 手动统计（每周更新）

### 6.2 优化阶段（提升体验）

**核心指标：** 用户用得爽吗？

- ✅ 准确率（目标：>90%）
- ✅ 响应时间（目标：<5s）
- ✅ 用户满意度（目标：>4星）

**数据收集：** 完整日志 + 反馈按钮

**看板：** Streamlit 实时看板（自动刷新）

### 6.3 规模化阶段（稳定可靠）

**核心指标：** 系统扛得住吗？

- ✅ 系统可用性（目标：>99%）
- ✅ 工具调用成功率（目标：>95%）
- ✅ P95 延迟（目标：<8s）

**数据收集：** 完整监控体系 + 告警

**看板：** Grafana + 值班告警（24小时）

---

## 七、面试常见问题应对

### Q1: 你们的数据看板是怎么搭建的？

**回答框架：**

1. **指标设计**："我们设计了分层指标体系，北极星指标是用户采纳率和留存率，下面拆解为使用指标、质量指标和技术指标。"

2. **数据采集**："通过日志埋点采集关键路径数据，每小时聚合一次写入 SQLite，包括用户调用、工具执行、响应时间等。"

3. **可视化展示**："用 Streamlit 快速搭建了数据看板，分为概览大屏、质量监控、技术监控三个视图，满足不同角色需求。"

4. **闭环迭代**："发现准确率下降时，通过 Badcase 分析定位问题，A/B 测试验证优化效果，最终准确率从 85% 提升到 93%。"

### Q2: 如何衡量 Agent 产品的价值？

**回答：**

"我们用两个核心指标：

1. **效率提升**：用户从手动查询（平均15分钟）到 Agent 查询（平均10秒），效率提升 90倍，技术工单减少 70%。

2. **用户满意度**：从 3.8星 提升到 4.5星，7日留存率 91%，说明产品真正解决了用户痛点。"

### Q3: 遇到过哪些数据异常？怎么处理的？

**案例分享：**

"有一次发现工具调用成功率突然从 96% 降到 82%，看板立即告警。

通过下钻分析发现是某个工具的数据库连接超时导致。

排查后发现是数据量增长导致 SQL 查询变慢，优化了索引后恢复正常。

这个案例让我意识到数据看板的价值：**不是等用户投诉，而是主动发现问题**。"

---

## 八、总结

**从产品经理视角，数据看板的核心价值：**

1. **可视化产品健康度**：一眼看出产品是否正常运行
2. **量化改进效果**：每次优化都能用数据证明价值
3. **快速发现问题**：告警机制让问题无处遁形
4. **指导产品决策**：用数据而非直觉做决策

**搭建看板的关键：**
- 指标分层：北极星 → 使用 → 质量 → 技术
- 采集到位：关键路径全覆盖
- 可视化清晰：不同角色看不同视图
- 闭环迭代：发现问题 → 分析 → 优化 → 验证

**面试建议：**
- 强调数据驱动的思维
- 举具体案例（异常发现 + 解决）
- 展示业务理解（为什么选这些指标）
- 避免过度技术细节（Prometheus/Grafana 架构）
