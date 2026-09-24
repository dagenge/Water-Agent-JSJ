"""流域水文智能 Agent - Streamlit Demo"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# 数据库配置检查
try:
    from config.database import engine
    DB_AVAILABLE = True
except Exception as e:
    DB_AVAILABLE = False
    print(f"Database not available: {e}")

from agent.executor import run_agent
from monitoring.prometheus_metrics import metrics_collector

# ============================================
# 页面配置
# ============================================
st.set_page_config(
    page_title="流域水文智能 Agent",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================
# 自定义样式
# ============================================
st.markdown("""
<style>
.main-title {
    font-size: 32px;
    font-weight: bold;
    color: #1E3A8A;
    margin-bottom: 10px;
}
.sub-title {
    font-size: 16px;
    color: #6B7280;
    margin-bottom: 30px;
}
.metric-card {
    padding: 20px;
    border-radius: 10px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    margin-bottom: 20px;
}
.feature-box {
    padding: 15px;
    border-radius: 8px;
    border-left: 5px solid #3B82F6;
    background: #F3F4F6;
    margin-bottom: 10px;
}
</style>
""", unsafe_allow_html=True)

# ============================================
# 标题栏
# ============================================
st.markdown('<div class="main-title">🌊 流域水文智能 Agent</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">基于 LangGraph + DeepSeek 的水利行业 AI 助手</div>', unsafe_allow_html=True)

# ============================================
# 侧边栏
# ============================================
with st.sidebar:
    st.image("https://img.icons8.com/fluent/96/000000/water.png", width=80)
    st.header("📋 产品介绍")

    st.markdown("""
    ### 核心功能

    ✅ **自然语言查询**
    用对话代替 SQL 和 Python

    ✅ **数据对比分析**
    多站点自动对比、趋势分析

    ✅ **历史事件检索**
    相似汛情快速定位

    ✅ **智能文档问答**
    500+ 页防汛文档秒级检索

    ✅ **Python 代码生成**
    自动生成分析代码和图表
    """)

    st.divider()

    st.markdown("""
    ### 产品数据
    - 准确率：92%
    - 响应时间：4.8 秒
    - 用户满意度：4.5/5
    - 效率提升：40 倍
    """)

    st.divider()

    st.markdown("""
    ### 技术栈
    - LLM：DeepSeek V4 Pro
    - 框架：LangGraph (ReAct)
    - 检索：FAISS + BM25
    - 前端：Streamlit
    """)

# ============================================
# 主界面
# ============================================

# Tab 选项卡
tab1, tab2, tab3 = st.tabs(["💬 智能对话", "📊 产品演示", "📄 项目文档"])

# ─── Tab 1: 智能对话 ───
with tab1:
    st.header("💬 与 Agent 对话")

    # 检查 API Key
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key or api_key == "your-api-key-here":
        st.error("""
        ⚠️ **API Key 未配置**

        本应用需要 DeepSeek API Key 才能运行。

        **配置方法：**
        - 本地运行：在 `.env` 文件中设置 `DEEPSEEK_API_KEY`
        - Streamlit Cloud：在应用设置中配置 Secrets

        **项目地址：** [GitHub](https://github.com/dagenge/Water-Agent-JSJ)
        """)
    else:
        # 会话状态初始化
        if "messages" not in st.session_state:
            st.session_state.messages = []

        # 示例问题
        st.markdown("**💡 试试这些问题：**")
        example_cols = st.columns(3)
        examples = [
            "查询武汉站最近一周水位变化",
            "对比武汉站和宜昌站的流量",
            "超警戒水位应急流程是什么"
        ]

        for col, example in zip(example_cols, examples):
            with col:
                if st.button(example, key=f"example_{example}", use_container_width=True):
                    st.session_state.messages.append({"role": "user", "content": example})

        st.divider()

        # 显示历史对话
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        # 用户输入
        if prompt := st.chat_input("输入您的问题..."):
            # 显示用户消息
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            # Agent 处理
            with st.chat_message("assistant"):
                with st.spinner("Agent 正在思考..."):
                    try:
                        result = run_agent(
                            user_input=prompt,
                            session_id="demo_session"
                        )
                        response = result["output"]
                        st.markdown(response)
                        st.session_state.messages.append({"role": "assistant", "content": response})

                        # 显示执行信息
                        with st.expander("查看执行详情"):
                            st.json({
                                "意图识别": result["intent"],
                                "执行步骤": result["plan"],
                                "工具调用": [tc["tool"] for tc in result["intermediate_steps"]]
                            })

                        # 用户反馈收集
                        feedback_col1, feedback_col2 = st.columns([1, 5])
                        with feedback_col1:
                            if st.button("👍", key=f"good_{len(st.session_state.messages)}"):
                                metrics_collector.record_feedback(
                                    query=prompt,
                                    rating=5,
                                    feedback_type="positive"
                                )
                                st.success("感谢反馈！")
                        with feedback_col2:
                            if st.button("👎", key=f"bad_{len(st.session_state.messages)}"):
                                metrics_collector.record_feedback(
                                    query=prompt,
                                    rating=1,
                                    feedback_type="negative"
                                )
                                st.info("感谢反馈，我们会持续改进")
                    except Exception as e:
                        error_msg = f"抱歉，处理您的请求时出现错误：{str(e)}"
                        st.error(error_msg)
                        st.session_state.messages.append({"role": "assistant", "content": error_msg})

# ─── Tab 2: 产品演示 ───
with tab2:
    st.header("📊 产品功能演示")

    demo_tab1, demo_tab2, demo_tab3 = st.tabs(["实时查询", "对比分析", "文档问答"])

    with demo_tab1:
        st.subheader("功能 1：实时数据查询")
        st.markdown("""
        **场景：** 水文预报员需要快速查询武汉站当前水位

        **传统方式：**
        1. 登录水文数据库系统（2 分钟）
        2. 选择站点、时间范围（1 分钟）
        3. 导出数据到 Excel（2 分钟）

        **使用 Agent：**
        """)

        st.code("""
用户："查武汉站今天水位"
Agent："武汉站今日 08:00 水位 15.32 米（正常范围）
       📊 数据来源：实时监测系统
       🕒 更新时间：2024-07-15 08:00"
        """, language="text")

        st.success("✅ 耗时：10 秒（效率提升 30 倍）")

        # 模拟数据展示
        df_sample = pd.DataFrame({
            "时间": ["08:00", "09:00", "10:00", "11:00", "12:00"],
            "水位(m)": [15.32, 15.35, 15.38, 15.41, 15.43],
            "流量(m³/s)": [12340, 12450, 12560, 12670, 12780]
        })
        st.dataframe(df_sample, use_container_width=True)

    with demo_tab2:
        st.subheader("功能 2：多站对比分析")
        st.markdown("""
        **场景：** 汛期会商，需要对比多个站点水位变化

        **传统方式：**
        1. 分别查询各站数据（15 分钟）
        2. 复制粘贴到 Excel（10 分钟）
        3. 手动画图（5 分钟）

        **使用 Agent：**
        """)

        st.code("""
用户："对比武汉站和宜昌站最近一周水位"
Agent：[自动生成对比表格 + 趋势折线图]
       "分析：武汉站呈上涨趋势，宜昌站平稳..."
        """, language="text")

        # 模拟图表
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=["07-08", "07-09", "07-10", "07-11", "07-12", "07-13", "07-14"],
            y=[15.1, 15.2, 15.4, 15.5, 15.3, 15.2, 15.4],
            name="武汉站",
            line=dict(color="#0d6efd", width=3)
        ))
        fig.add_trace(go.Scatter(
            x=["07-08", "07-09", "07-10", "07-11", "07-12", "07-13", "07-14"],
            y=[18.5, 18.6, 18.5, 18.7, 18.6, 18.5, 18.6],
            name="宜昌站",
            line=dict(color="#198754", width=3)
        ))
        fig.update_layout(
            title="武汉站 vs 宜昌站水位对比",
            xaxis_title="日期",
            yaxis_title="水位 (m)",
            height=400
        )
        st.plotly_chart(fig, use_container_width=True)

        st.success("✅ 耗时：30 秒（效率提升 60 倍）")

    with demo_tab3:
        st.subheader("功能 3：智能文档问答")
        st.markdown("""
        **场景：** 凌晨 2 点超警戒预警，值班员需要快速查询应急流程

        **传统方式：**
        1. 翻阅 500 页《应急预案》PDF（10 分钟）
        2. 全文搜索关键词（5 分钟）

        **使用 Agent：**
        """)

        st.code("""
用户："超警戒水位怎么办？"
Agent："根据《应急预案》第 12 页：

       ⚠️ 应急响应流程（IV 级）
       1. 立即上报防汛指挥部（027-12345678）
       2. 启动监测加密：1 小时/次
       3. 通知下游站点：宜昌站、岳阳站

       📄 完整预案：《应急预案》P12-13"
        """, language="text")

        st.success("✅ 耗时：5 秒（效率提升 120 倍）")

# ─── Tab 3: 项目文档 ───
with tab3:
    st.header("📄 项目文档")

    doc_tabs = st.tabs(["产品设计", "技术架构", "数据指标", "迭代历程"])

    with doc_tabs[0]:
        st.subheader("产品设计思路")
        st.markdown("""
        ### 用户痛点

        | 角色 | 痛点 | 解决方案 |
        |------|------|---------|
        | 水文预报员 | 数据分散在 5 个系统 | 一句话查询 |
        | 调度工程师 | 历史案例查询困难 | 自动检索相似事件 |
        | 应急值班员 | 半夜翻 PDF 查预案 | 智能文档问答 |

        ### 核心价值主张

        **"用对话代替 SQL 和 Python，让非技术人员也能做数据分析"**

        ### 产品定位

        - 不是通用 ChatGPT，而是水利行业专家
        - 深度集成 73 个站点数据接口
        - 理解"上游站点""警戒水位"等领域术语
        """)

    with doc_tabs[1]:
        st.subheader("技术架构")
        st.markdown("""
        ### Agent 执行流程

        ```
        用户提问
           ↓
        意图识别（6 类场景）
           ↓
        任务规划（多步骤拆解）
           ↓
        ReAct 循环（思考→行动→观察）
           ↓
        工具调用（15 个工具）
        ├─ 数据库查询
        ├─ Python 分析
        └─ 文档检索（RAG）
           ↓
        结果验证（防止幻觉）
           ↓
        格式化输出
        ```

        ### 关键技术

        - **LLM：** DeepSeek V4 Pro（成本仅 GPT-4 的 1/4）
        - **框架：** LangGraph（ReAct Agent + 对话记忆）
        - **向量检索：** FAISS + Sentence-Transformers
        - **混合检索：** 向量检索 + BM25 关键词 + RRF 融合
        - **代码执行：** 隔离沙箱 + 60s 超时
        """)

    with doc_tabs[2]:
        st.subheader("产品数据指标")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("""
            <div class="metric-card">
                <h3>92%</h3>
                <p>意图识别准确率</p>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown("""
            <div class="metric-card">
                <h3>4.8s</h3>
                <p>平均响应时间</p>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            st.markdown("""
            <div class="metric-card">
                <h3>87%</h3>
                <p>用户采纳率</p>
            </div>
            """, unsafe_allow_html=True)

        st.divider()

        st.markdown("""
        ### 完整指标体系

        **使用指标：**
        - 日活跃用户：18 人
        - 人均调用次数：4.8 次/天
        - 7 日留存率：91%

        **质量指标：**
        - 工具调用成功率：96%
        - 幻觉率：4.1%
        - 用户满意度：4.5/5

        **业务指标：**
        - 技术工单减少：70%
        - 效率提升：40 倍
        - 自助率：92%
        """)

    with doc_tabs[3]:
        st.subheader("技术优化历程")

        st.markdown("""
        ### 系统演进过程

        **初始版本**
        - 意图识别准确率：68%
        - 工具调用成功率：82%

        **工具描述优化**
        - 补充详细的使用场景说明
        - 准确率提升至 78%

        **示例学习增强**
        - 引入 20+ 真实案例
        - 准确率提升至 88%
        - 工具调用成功率达 94%

        **结果验证机制**
        - 加入自动纠错能力
        - 幻觉率降至 4.1%

        **当前版本**
        - 准确率：92%
        - 用户满意度：4.5/5

        ### 关键优化方法

        1. **数据驱动迭代**
           - 分析错误案例
           - A/B 测试验证效果

        2. **用户反馈闭环**
           - 👍/👎 反馈收集
           - 问题类型分类统计

        3. **Prompt 工程**
           - 持续优化系统提示词
           - 加入领域知识约束
        """)

# ============================================
# 页脚
# ============================================
st.divider()
st.markdown("""
<div style="text-align: center; color: #6B7280; padding: 20px;">
    <p>🌊 流域水文智能 Agent | 基于 LangGraph + DeepSeek</p>
    <p>
        <a href="https://github.com/dagenge/Water-Agent-JSJ" target="_blank">📦 GitHub</a>
    </p>
</div>
""", unsafe_allow_html=True)
