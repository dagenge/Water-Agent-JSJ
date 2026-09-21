# 部署指南

## 快速部署到 Streamlit Cloud

### 1. 准备 GitHub 仓库

```bash
cd H:\Work\项目经历\Project_JSJ_Agent

# 初始化 Git（如果还未初始化）
git init

# 添加文件
git add .gitignore .env.example requirements_streamlit.txt streamlit_demo.py .streamlit/config.toml README.md
git add agent/

# 提交
git commit -m "Add Streamlit demo for online deployment

- Simplified frontend for PM interview demos
- Product-focused UI with metrics and iteration history
- Streamlined dependencies for cloud deployment

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"

# 创建 GitHub 仓库后关联（替换为你的仓库地址）
git remote add origin https://github.com/你的用户名/Water-Agent-JSJ.git
git branch -M main
git push -u origin main
```

### 2. 部署到 Streamlit Cloud

1. 访问 https://share.streamlit.io/
2. 点击 "New app"
3. 选择你的 GitHub 仓库
4. 配置：
   - **Main file path**: `streamlit_demo.py`
   - **Python version**: 3.9
   - **Requirements file**: `requirements_streamlit.txt`

5. 添加环境变量（Secrets）：
   点击 "Advanced settings" → "Secrets"，粘贴：
   ```toml
   DEEPSEEK_API_KEY = "your-actual-api-key-here"
   DEEPSEEK_BASE_URL = "https://api.deepseek.com"
   DEEPSEEK_MODEL = "deepseek-chat"
   ```

6. 点击 "Deploy"

### 3. 获取演示链接

部署成功后，你会得到类似：
```
https://你的用户名-water-agent-jsj-streamlit-demo-abc123.streamlit.app
```

这个链接可以：
- 直接分享给面试官
- 写入简历
- 放在 GitHub README 的演示按钮中

## 本地测试

```bash
# 激活虚拟环境
conda activate jsj_research

# 配置 API Key
cp .env.example .env
# 编辑 .env 填入真实 API Key

# 运行
streamlit run streamlit_demo.py
```

访问 http://localhost:8501

## 注意事项

### Streamlit Cloud 限制
- 免费版 1GB 内存
- CPU 限制
- 不支持大型模型文件（已在 .gitignore 排除）

### 数据库处理
如果需要真实数据库：
1. 创建示例数据库（仅包含少量样本数据）
2. 或使用远程数据库（配置 DATABASE_URL）
3. 当前版本在无 API Key 时会显示友好提示，不影响产品展示

### API Key 安全
- **永远不要**在代码中硬编码 API Key
- **永远不要**提交 .env 文件到 Git
- 使用 Streamlit Secrets 管理敏感信息

## 面试使用建议

### 如果 API Key 有额度限制
在 `streamlit_demo.py` 中已添加 API Key 检查逻辑：
- 当 API Key 未配置时，显示友好提示
- 告知面试官可以查看 GitHub 代码和产品文档 Tab
- 产品演示 Tab 使用模拟数据，不依赖 API

### 演示策略
1. **首先展示**：产品演示 Tab（模拟数据，稳定可靠）
2. **核心讲解**：项目文档 Tab（产品设计、技术架构、数据指标）
3. **可选互动**：智能对话 Tab（如果 API Key 可用）

### 简历中的描述
```
🌊 广东省流域水文智能 Agent
- 技术栈：LangGraph + DeepSeek + FAISS + BM25
- 在线演示：https://你的链接.streamlit.app
- 源码：https://github.com/你的用户名/Water-Agent-JSJ
- 成果：准确率 92%，响应时间 4.8s，效率提升 40 倍
```
