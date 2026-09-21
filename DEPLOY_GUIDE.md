# 部署指南

## 第一步：推送到 GitHub

### 1. 创建 GitHub 仓库

访问 https://github.com/new

- Repository name: `Water-Agent-JSJ`
- Description: `Guangdong Watershed Hydrology AI Agent - LangGraph + DeepSeek`
- Public (公开仓库)
- 不勾选 Initialize with README

点击 **Create repository**

### 2. 推送代码

复制你的 GitHub 用户名，执行：

```bash
cd "H:\Work\项目经历\Project_JSJ_Agent"
git remote add origin https://github.com/你的用户名/Water-Agent-JSJ.git
git push -u origin main
```

如果遇到认证问题：
1. 访问 https://github.com/settings/tokens
2. 生成 Personal Access Token (classic)
3. 权限勾选 `repo`
4. 使用 token 替代密码

---

## 第二步：部署到 Streamlit Cloud

### 1. 访问 Streamlit Cloud

https://share.streamlit.io/

使用 GitHub 账号登录

### 2. 创建新应用

点击 **New app**，配置：

- **Repository**: `你的用户名/Water-Agent-JSJ`
- **Branch**: `main`
- **Main file path**: `streamlit_demo.py`
- **Python version**: `3.9`

### 3. 配置 Secrets（可选）

点击 **Advanced settings** → **Secrets**

添加（有 DeepSeek API Key 时）：

```toml
DEEPSEEK_API_KEY = "sk-your-key-here"

# PostgreSQL (Streamlit Cloud 不支持,使用模拟数据)
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "water_agent"
DB_USER = "postgres"
DB_PASSWORD = "postgres"
```

**注意**: Streamlit Cloud 免费版不支持 PostgreSQL，应用会自动使用模拟数据

### 4. 部署

点击 **Deploy**

等待 3-5 分钟，获得演示链接：

```
https://你的用户名-water-agent-jsj-xxxx.streamlit.app
```

---

## 第三步：验证部署

### 功能验证清单

- ✅ 页面正常加载
- ✅ 三个 Tab 都能切换
- ✅ 产品演示数据正常显示
- ✅ 图表渲染正常
- ✅ 对话功能显示 API Key 提示（无 Key 时）

### 演示建议

面试时展示：

1. **Tab 2 (产品演示)**：展示 3 个核心功能和可视化
2. **Tab 3 (项目文档)**：讲解产品迭代和数据指标
3. **Tab 1 (智能对话)**：如有 API Key，现场演示对话

---

## 常见问题

### Q1: git push 失败

**错误**: `remote: Support for password authentication was removed`

**解决**:
1. 生成 Personal Access Token: https://github.com/settings/tokens
2. 使用 token 替代密码
3. 或配置 SSH Key: https://github.com/settings/keys

### Q2: Streamlit 部署失败

**错误**: `ModuleNotFoundError: No module named 'xxx'`

**解决**:
- 检查 `requirements_streamlit.txt` 是否包含该模块
- 确保文件在仓库根目录

### Q3: 页面加载慢

**原因**: FAISS 索引文件较大 (50MB+)

**解决**:
- 当前版本已优化，仅加载必要文件
- 首次加载需 30-60 秒属正常

### Q4: 数据库连接失败

**说明**: Streamlit Cloud 免费版不支持 PostgreSQL

**解决**: 应用已自动回退到模拟数据模式

---

## 简历更新

部署成功后，更新简历：

```markdown
### AI Agent 产品 - 广东省流域水文智能助手

**在线演示**: https://你的用户名-water-agent-jsj.streamlit.app
**GitHub**: https://github.com/你的用户名/Water-Agent-JSJ

**核心成果**:
- 意图识别准确率 92%，响应时间 4.8 秒
- 技术工单减少 70%，效率提升 40 倍
- 用户满意度 4.5/5，7 日留存率 91%

**技术栈**: LangGraph (ReAct) + DeepSeek V4 Pro + FAISS + PostgreSQL
```

---

## 下一步

1. ✅ PostgreSQL 数据库已配置
2. ✅ 代码已提交到本地 Git
3. ⏳ 推送到 GitHub（等待你执行）
4. ⏳ 部署到 Streamlit Cloud
5. ⏳ 更新简历链接

**当前状态**: 代码已准备好，等待你创建 GitHub 仓库并推送
