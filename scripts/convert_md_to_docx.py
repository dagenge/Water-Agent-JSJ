"""将产品展示 Markdown 转换为 Word 文档"""

from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.oxml.ns import qn


def add_title(doc, text, level=1):
    """添加标题"""
    heading = doc.add_heading(text, level=level)
    heading.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
    return heading


def add_paragraph(doc, text, bold=False, font_size=11):
    """添加段落"""
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.font.size = Pt(font_size)
    run.font.name = '微软雅黑'
    run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
    if bold:
        run.bold = True
    return p


def add_table_from_data(doc, headers, rows):
    """添加表格"""
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = 'Light Grid Accent 1'

    # 表头
    hdr_cells = table.rows[0].cells
    for i, header in enumerate(headers):
        hdr_cells[i].text = header
        for paragraph in hdr_cells[i].paragraphs:
            for run in paragraph.runs:
                run.font.bold = True
                run.font.size = Pt(10)
                run.font.name = '微软雅黑'

    # 数据行
    for i, row_data in enumerate(rows):
        row_cells = table.rows[i + 1].cells
        for j, cell_data in enumerate(row_data):
            row_cells[j].text = cell_data
            for paragraph in row_cells[j].paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(10)
                    run.font.name = '微软雅黑'

    return table


def create_product_presentation_docx():
    """创建产品展示 Word 文档"""
    doc = Document()

    # 设置默认字体
    doc.styles['Normal'].font.name = '微软雅黑'
    doc.styles['Normal']._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
    doc.styles['Normal'].font.size = Pt(11)

    # ========== 封面 ==========
    title = doc.add_heading('流域水文智能 Agent', level=0)
    title.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

    subtitle = doc.add_paragraph()
    subtitle_run = subtitle.add_run('产品经理面试展示报告')
    subtitle_run.font.size = Pt(16)
    subtitle_run.font.name = '微软雅黑'
    subtitle_run.font.color.rgb = RGBColor(70, 70, 70)
    subtitle.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

    doc.add_paragraph()

    info = doc.add_paragraph()
    info_run = info.add_run('项目定位：To B 智能数据分析平台\n目标用户：水文行业从业者')
    info_run.font.size = Pt(12)
    info.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

    doc.add_page_break()

    # ========== 一、需求分析与痛点定位 ==========
    add_title(doc, '一、需求分析与痛点定位', level=1)

    add_title(doc, '1.1 用户调研背景', level=2)
    add_paragraph(doc, '在与广东省水文局、水利设计院等机构的深度调研中，通过用户访谈、工作流程观察、问卷调查等方式，识别了水文工作者在日常工作中的核心痛点。')

    add_title(doc, '1.2 核心痛点分析', level=2)

    # 痛点表格
    pain_headers = ['痛点', '现状描述', '用户影响', '频率']
    pain_rows = [
        ['数据查询门槛高', '需要熟悉 SQL 和数据库结构', '初级工程师查询效率低 50%', '每日 10+ 次'],
        ['知识分散难查找', '规范、手册散落在 20+ 份文档中', '每次查询耗时 10-30 分钟', '每周 5-10 次'],
        ['分析工作重复', '每次对比分析都要写相同代码', '70% 时间花在重复劳动', '每周 3-5 次']
    ]
    add_table_from_data(doc, pain_headers, pain_rows)
    doc.add_paragraph()

    add_title(doc, '1.3 机会点识别', level=2)
    add_paragraph(doc, '通过分析发现，AI Agent 技术可以将自然语言转化为数据操作，从根本上降低使用门槛。基于此，我们定义了产品的切入点：')
    add_paragraph(doc, '• 自然语言交互替代 SQL 查询，降低技术门槛')
    add_paragraph(doc, '• 知识库集中管理，实现秒级检索')
    add_paragraph(doc, '• 工具化常见分析任务，减少重复编码')

    doc.add_page_break()

    # ========== 二、产品目标与价值主张 ==========
    add_title(doc, '二、产品目标与价值主张', level=1)

    add_title(doc, '2.1 产品愿景', level=2)
    p = add_paragraph(doc, '让水文数据像和人对话一样简单', bold=True, font_size=14)
    p.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
    doc.add_paragraph()

    add_title(doc, '2.2 核心价值', level=2)

    value_headers = ['价值维度', '传统方式', '使用 Agent 后', '提升幅度']
    value_rows = [
        ['查询效率', '写 SQL 10 分钟', '对话 5 秒', '120 倍'],
        ['知识获取', '翻阅文档 30 分钟', '智能检索 10 秒', '180 倍'],
        ['分析速度', '手动编码 30 分钟', '自动生成 30 秒', '60 倍'],
        ['错误率', '10% 人为错误', '< 1% AI 错误', '降低 90%']
    ]
    add_table_from_data(doc, value_headers, value_rows)
    doc.add_paragraph()

    add_title(doc, '2.3 目标用户画像', level=2)

    # 用户画像
    personas = [
        ('初级工程师', '刚入职 1-2 年，不熟悉数据库，需要快速上手', '降低学习成本，提升工作效率'),
        ('预报员', '汛期值班，需要快速查询历史数据辅助决策', '提升应急响应速度，减少失误'),
        ('设计院工程师', '频繁查阅技术规范，需要精准定位参数', '知识获取效率，提升设计质量')
    ]

    for role, scenario, value in personas:
        add_paragraph(doc, f'• {role}', bold=True)
        add_paragraph(doc, f'  场景：{scenario}')
        add_paragraph(doc, f'  价值：{value}')
        doc.add_paragraph()

    doc.add_page_break()

    # ========== 三、方案设计 ==========
    add_title(doc, '三、方案设计', level=1)

    add_title(doc, '3.1 整体架构', level=2)
    add_paragraph(doc, '采用分层架构设计，确保系统的可维护性和可扩展性：')
    doc.add_paragraph()

    add_paragraph(doc, '【用户交互层】', bold=True)
    add_paragraph(doc, 'Streamlit Web UI - 提供直观的对话界面，支持文本输入、图表展示、文件下载')
    doc.add_paragraph()

    add_paragraph(doc, '【Agent 智能层】', bold=True)
    add_paragraph(doc, '• 意图识别：6 类意图分类（查询流量、知识问答、数据分析等）')
    add_paragraph(doc, '• 任务规划：ReAct 循环（思考→行动→观察）')
    add_paragraph(doc, '• 工具调用：23 个专用工具（数据库查询、Python 分析、RAG 检索）')
    add_paragraph(doc, '• 对话记忆：LangGraph MemorySaver 实现多轮对话上下文保持')
    doc.add_paragraph()

    add_paragraph(doc, '【知识与数据层】', bold=True)
    add_paragraph(doc, '• 业务数据库：PostgreSQL 15 + pgvector 扩展，存储水文观测数据')
    add_paragraph(doc, '• RAG 知识库：FAISS 语义检索 + BM25 关键词检索 + RRF 融合')
    doc.add_paragraph()

    add_paragraph(doc, '【监控运营层】', bold=True)
    add_paragraph(doc, '• Prometheus 指标采集：8 个核心指标（响应时间、成功率、活跃会话等）')
    add_paragraph(doc, '• Grafana 可视化：实时监控面板 + 6 条告警规则')
    doc.add_paragraph()

    add_title(doc, '3.2 核心能力', level=2)

    capability_headers = ['能力维度', '实现方案', '技术选型']
    capability_rows = [
        ['自然语言理解', '6 类意图识别（零样本分类）', 'DeepSeek V3 LLM'],
        ['知识检索', 'FAISS + BM25 + RRF 融合', 'BGE-small-zh-v1.5 嵌入模型'],
        ['多轮对话', '会话状态持久化', 'LangGraph MemorySaver'],
        ['结果可信', '一致性自校验机制', '数值范围检查 + 数据溯源'],
        ['生产监控', '完整监控体系', 'Prometheus + Grafana']
    ]
    add_table_from_data(doc, capability_headers, capability_rows)

    doc.add_page_break()

    # ========== 四、功能设计与场景演示 ==========
    add_title(doc, '四、功能设计与场景演示', level=1)

    add_title(doc, '4.1 功能模块', level=2)
    add_paragraph(doc, '【智能问答】基础查询、时序查询、事件查询')
    add_paragraph(doc, '【知识检索】规范查询、方法指导、案例参考')
    add_paragraph(doc, '【数据分析】对比分析、趋势分析、异常检测')
    add_paragraph(doc, '【多轮对话】上下文记忆、追问澄清')
    doc.add_paragraph()

    add_title(doc, '4.2 典型场景一：新员工快速上手', level=2)
    add_paragraph(doc, '用户角色：刚入职的水文工程师（不熟悉数据库）', bold=True)
    add_paragraph(doc, '痛点：需要培训 SQL 才能查询数据，学习周期长')
    doc.add_paragraph()

    add_paragraph(doc, '对话流程：')
    add_paragraph(doc, '用户："查询棠荆河有哪些水文站"')
    add_paragraph(doc, 'Agent：识别意图 → 调用工具 → 返回 5 个站点（TJ01-TJ05）')
    doc.add_paragraph()
    add_paragraph(doc, '用户："TJ01 站 2024 年 8 月最大流量是多少"')
    add_paragraph(doc, 'Agent：识别意图 → 调用数据库查询 → 返回最大流量 850 m³/s（8月15日 14:00）')
    doc.add_paragraph()
    add_paragraph(doc, '用户："和 2023 年同期对比一下"')
    add_paragraph(doc, 'Agent：记忆上文 → 自动补全参数 → 生成对比图表')
    doc.add_paragraph()

    add_paragraph(doc, '价值体现：')
    add_paragraph(doc, '✓ 无需培训 SQL，直接对话完成查询')
    add_paragraph(doc, '✓ 自动记忆上下文，无需重复描述')
    add_paragraph(doc, '✓ 自动生成可视化，省去编码工作')
    doc.add_paragraph()

    add_title(doc, '4.3 典型场景二：汛期应急决策', level=2)
    add_paragraph(doc, '用户角色：防汛指挥中心值班员', bold=True)
    add_paragraph(doc, '痛点：汛期需要快速查询历史数据辅助决策，传统方式耗时长')
    doc.add_paragraph()

    add_paragraph(doc, '对话流程：')
    add_paragraph(doc, '用户："河子口站当前水位多少"')
    add_paragraph(doc, 'Agent：实时查询 → 返回 147.5m（警戒水位 150m）')
    doc.add_paragraph()
    add_paragraph(doc, '用户："历史上超过 150m 的事件有哪些"')
    add_paragraph(doc, 'Agent：查询历史洪水事件 → 返回 3 次（2018/2020/2023）')
    doc.add_paragraph()
    add_paragraph(doc, '用户："2023 年那次峰值流量和持续时间"')
    add_paragraph(doc, 'Agent：查询事件详情 → 峰值 1250 m³/s，持续 18 小时')
    doc.add_paragraph()

    add_paragraph(doc, '价值体现：')
    add_paragraph(doc, '✓ 5 秒完成 4 次复杂查询（人工需 10+ 分钟）')
    add_paragraph(doc, '✓ 历史案例快速调取，辅助决策')
    add_paragraph(doc, '✓ 可扩展到预警模型、淹没分析')
    doc.add_paragraph()

    add_title(doc, '4.4 典型场景三：技术规范查询', level=2)
    add_paragraph(doc, '用户角色：设计院工程师（需要查设计规范）', bold=True)
    add_paragraph(doc, '痛点：规范文档多达 20+ 份，查询效率低')
    doc.add_paragraph()

    add_paragraph(doc, '对话流程：')
    add_paragraph(doc, '用户："暴雨强度公式怎么计算"')
    add_paragraph(doc, 'Agent：RAG 检索 → 返回公式 + 参数说明 + 应用案例')
    doc.add_paragraph()
    add_paragraph(doc, '用户："广东地区 A1 参数一般取多少"')
    add_paragraph(doc, 'Agent：二次检索 → 返回广东沿海 A1=13.2, 内陆 A1=11.8')
    doc.add_paragraph()
    add_paragraph(doc, '用户："给我一个 10 年重现期的计算例子"')
    add_paragraph(doc, 'Agent：组合知识 → 生成完整计算示例')
    doc.add_paragraph()

    add_paragraph(doc, '价值体现：')
    add_paragraph(doc, '✓ 不再翻阅 20+ 份规范文档')
    add_paragraph(doc, '✓ 查询时间从 30 分钟降到 10 秒')
    add_paragraph(doc, '✓ 自动关联相关知识点')

    doc.add_page_break()

    # ========== 五、系统监控与运营 ==========
    add_title(doc, '五、系统监控与运营', level=1)

    add_title(doc, '5.1 监控设计思路', level=2)
    add_paragraph(doc, '为确保系统稳定运行和持续优化，设计了完整的监控体系：')
    doc.add_paragraph()

    add_paragraph(doc, '• 用户体验监控：响应时间、查询成功率')
    add_paragraph(doc, '• 系统质量监控：工具调用成功率、Badcase 趋势')
    add_paragraph(doc, '• 资源使用监控：活跃会话数、数据库连接数')
    doc.add_paragraph()

    add_title(doc, '5.2 核心监控指标', level=2)

    metrics_headers = ['指标类别', '指标项', '目标值', '告警阈值']
    metrics_rows = [
        ['用户体验', 'P95 响应时间', '< 5s', '> 10s'],
        ['', '查询成功率', '> 95%', '< 90%'],
        ['系统质量', '工具调用成功率', '> 95%', '< 90%'],
        ['', 'Badcase 发生率', '< 5%', '> 10%'],
        ['资源使用', '活跃会话数', '< 50', '> 100'],
        ['', '数据库连接数', '< 50', '> 80']
    ]
    add_table_from_data(doc, metrics_headers, metrics_rows)
    doc.add_paragraph()

    add_title(doc, '5.3 Grafana 监控面板', level=2)
    add_paragraph(doc, '设计了 8 个核心监控面板：')
    add_paragraph(doc, '• 总览面板：总查询数、工具成功率、响应时间、活跃会话')
    add_paragraph(doc, '• 查询 QPS 分意图类型：观察不同类型查询的使用频率')
    add_paragraph(doc, '• 响应时间分布（P50/P95/P99）：监控性能稳定性')
    add_paragraph(doc, '• 工具调用分布：识别高频工具和优化方向')
    add_paragraph(doc, '• Badcase 趋势：跟踪错误类型和优化效果')
    doc.add_paragraph()

    add_title(doc, '5.4 告警规则', level=2)

    alert_headers = ['告警名称', '触发条件', '级别', '通知方式']
    alert_rows = [
        ['响应时间过高', 'P95 > 10s 持续 5 分钟', 'Warning', '企业微信'],
        ['工具调用失败率高', '失败率 > 10% 持续 5 分钟', 'Critical', '电话 + 微信'],
        ['查询错误率高', '错误率 > 5% 持续 5 分钟', 'Warning', '企业微信'],
        ['Badcase 突增', '> 5 个/分钟', 'Warning', '企业微信'],
        ['数据库连接数过多', '> 80 个连接', 'Warning', '邮件'],
        ['活跃会话异常', '> 100 个会话', 'Warning', '邮件']
    ]
    add_table_from_data(doc, alert_headers, alert_rows)

    doc.add_page_break()

    # ========== 六、技术实现亮点 ==========
    add_title(doc, '六、技术实现亮点', level=1)

    add_title(doc, '6.1 RAG 混合检索方案', level=2)
    add_paragraph(doc, '问题：单一检索方式存在明显短板')
    add_paragraph(doc, '• FAISS 语义检索：理解同义改写，但会漏掉关键词精确匹配')
    add_paragraph(doc, '• BM25 关键词检索：精确匹配专业术语，但无法理解同义词')
    doc.add_paragraph()

    add_paragraph(doc, '解决方案：混合检索 + RRF 融合')
    add_paragraph(doc, '• 同时执行 FAISS 和 BM25 检索')
    add_paragraph(doc, '• 使用 RRF（Reciprocal Rank Fusion）算法融合两路结果')
    add_paragraph(doc, '• 融合公式：score(doc) = Σ 1 / (k + rank_i(doc))，k=60')
    doc.add_paragraph()

    add_paragraph(doc, '效果验证（实测 100 个查询）：')

    rag_headers = ['方案', '准确率', '召回率', '提升幅度']
    rag_rows = [
        ['纯 FAISS', '72%', '68%', '-'],
        ['纯 BM25', '65%', '71%', '-'],
        ['FAISS + BM25', '87%', '85%', '+15%']
    ]
    add_table_from_data(doc, rag_headers, rag_rows)
    doc.add_paragraph()

    add_title(doc, '6.2 pgvector 向量数据库', level=2)
    add_paragraph(doc, '问题：FAISS 纯内存方案存在瓶颈')
    add_paragraph(doc, '• 查询速度慢：100 万向量需要 5 秒')
    add_paragraph(doc, '• 内存占用大：2GB 内存占用')
    add_paragraph(doc, '• 扩展性差：单机瓶颈，无法水平扩展')
    doc.add_paragraph()

    add_paragraph(doc, '解决方案：PostgreSQL + pgvector + IVFFlat 索引')
    add_paragraph(doc, '• IVFFlat 原理：K-Means 聚类加速查询（O(K+N/10) 复杂度）')
    add_paragraph(doc, '• 统一管理：向量数据和业务数据在同一数据库')
    add_paragraph(doc, '• 水平扩展：支持 PostgreSQL 集群')
    doc.add_paragraph()

    add_paragraph(doc, '效果对比：')

    pg_headers = ['方案', '查询速度', '内存占用', '扩展性']
    pg_rows = [
        ['FAISS 内存', '5000ms', '2GB', '单机瓶颈'],
        ['pgvector IVFFlat', '100ms', '500MB', 'PG 集群']
    ]
    add_table_from_data(doc, pg_headers, pg_rows)
    doc.add_paragraph()

    add_title(doc, '6.3 LangGraph 对话管理', level=2)
    add_paragraph(doc, '问题：多轮对话状态难以管理')
    add_paragraph(doc, '• LangChain 原生 ConversationChain 是无状态的')
    add_paragraph(doc, '• 每次对话需要手动传入完整历史')
    add_paragraph(doc, '• 服务重启后对话无法恢复')
    doc.add_paragraph()

    add_paragraph(doc, '解决方案：LangGraph + MemorySaver')
    add_paragraph(doc, '• 自动持久化：会话状态自动保存到数据库')
    add_paragraph(doc, '• 会话可恢复：服务重启后可继续对话')
    add_paragraph(doc, '• 支持分支回滚：可撤销上一步操作')

    doc.add_page_break()

    # ========== 七、风险分析与应对 ==========
    add_title(doc, '七、风险分析与应对', level=1)

    risk_headers = ['风险类型', '具体风险', '影响程度', '应对措施']
    risk_rows = [
        ['技术风险', 'LLM 幻觉导致错误答案', '高', '一致性校验 + Badcase 监控 + 数据溯源'],
        ['', '向量检索召回率不足', '中', '混合检索 + 持续优化 + 人工标注'],
        ['业务风险', '用户不信任 AI 结果', '高', '展示推理过程 + 数据溯源 + 人工审核'],
        ['', '数据隐私泄露', '高', '私有化部署 + 访问控制 + 审计日志'],
        ['运营风险', '用户使用门槛高', '中', '操作指南 + 培训 + 示例问题'],
        ['', '系统稳定性不足', '中', '完整监控 + 告警 + 容错机制']
    ]
    add_table_from_data(doc, risk_headers, risk_rows)

    doc.add_page_break()

    # ========== 八、总结 ==========
    add_title(doc, '八、总结', level=1)

    add_title(doc, '8.1 核心亮点', level=2)
    add_paragraph(doc, '✓ 产品价值清晰：解决水文行业真实痛点，降低 80% 使用门槛')
    add_paragraph(doc, '✓ 技术方案扎实：RAG 混合检索、pgvector 向量存储、LangGraph 状态管理')
    add_paragraph(doc, '✓ 生产级可用：完整监控体系、一致性校验、告警机制')
    add_paragraph(doc, '✓ 场景设计合理：覆盖新员工培训、汛期应急、规范查询等典型场景')
    doc.add_paragraph()

    add_title(doc, '8.2 产品经理角色体现', level=2)
    add_paragraph(doc, '• 需求分析：深度用户调研，精准定位核心痛点')
    add_paragraph(doc, '• 产品设计：清晰的功能模块划分和场景设计')
    add_paragraph(doc, '• 技术选型：权衡技术方案的可行性和成本')
    add_paragraph(doc, '• 监控运营：建立完整的监控体系，支持产品迭代')
    add_paragraph(doc, '• 风险管理：识别潜在风险并制定应对策略')
    doc.add_paragraph()

    add_title(doc, '8.3 可迁移能力', level=2)
    add_paragraph(doc, '• AI 产品方法论：RAG/Agent 产品从 0 到 1 的完整流程')
    add_paragraph(doc, '• 需求分析能力：用户调研、痛点挖掘、机会点识别')
    add_paragraph(doc, '• 方案设计能力：架构设计、技术选型、风险评估')
    add_paragraph(doc, '• 数据驱动思维：指标体系设计、监控运营、持续优化')

    # 保存文档
    output_path = 'H:\\Work\\项目经历\\Project_JSJ_Agent\\docs\\流域水文智能Agent_产品展示报告.docx'
    doc.save(output_path)
    print(f'Word document generated: {output_path}')

    return output_path


if __name__ == '__main__':
    create_product_presentation_docx()
