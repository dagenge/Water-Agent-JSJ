# 部署指南

## 推送到 GitHub

### 1. 创建 GitHub 仓库

访问 https://github.com/new

- Repository name: `Water-Agent-JSJ`
- Description: `Guangdong Watershed Hydrology AI Agent - LangGraph + DeepSeek`
- Public (公开仓库)

### 2. 推送代码

```bash
git remote add origin https://github.com/你的用户名/Water-Agent-JSJ.git
git push -u origin main
```

---

## 部署到 Streamlit Cloud

### 1. 访问 Streamlit Cloud

https://share.streamlit.io/

使用 GitHub 账号登录

### 2. 创建新应用

- **Repository**: `你的用户名/Water-Agent-JSJ`
- **Branch**: `main`
- **Main file path**: `streamlit_demo.py`

### 3. 配置 Secrets

点击 **Advanced settings** → **Secrets**，添加：

```toml
DEEPSEEK_API_KEY = "sk-your-key-here"
```

### 4. 部署

点击 **Deploy**，获得在线链接：

```
https://你的用户名-water-agent-jsj.streamlit.app
```
