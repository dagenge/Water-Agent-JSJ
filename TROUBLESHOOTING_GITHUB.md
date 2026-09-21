# GitHub 连接问题解决方案

## 问题诊断

网络可以 ping 通 GitHub (20.205.243.166)，但 git push 时无法连接 443 端口。

## 解决方案（按优先级）

### 方案 1: 配置 Git 使用代理（如果你有代理）

```bash
# 如果使用 HTTP 代理（替换为你的代理地址和端口）
git config --global http.proxy http://127.0.0.1:7890
git config --global https.proxy http://127.0.0.1:7890

# 如果使用 SOCKS5 代理
git config --global http.proxy socks5://127.0.0.1:7890
git config --global https.proxy socks5://127.0.0.1:7890

# 然后重试推送
cd "H:\Work\项目经历\Project_JSJ_Agent"
git push -u origin main
```

### 方案 2: 使用 SSH 替代 HTTPS

如果已配置 SSH key：

```bash
cd "H:\Work\项目经历\Project_JSJ_Agent"

# 移除 HTTPS 远程地址
git remote remove origin

# 添加 SSH 远程地址（替换你的用户名）
git remote add origin git@github.com:你的用户名/Water-Agent-JSJ.git

# 推送
git push -u origin main
```

**配置 SSH key（如果还没有）**：
```bash
# 生成 SSH key
ssh-keygen -t ed25519 -C "your_email@example.com"

# 查看公钥
cat ~/.ssh/id_ed25519.pub

# 复制公钥内容，添加到 GitHub:
# https://github.com/settings/keys → New SSH key
```

### 方案 3: 临时取消代理（如果之前设置过但已失效）

```bash
git config --global --unset http.proxy
git config --global --unset https.proxy

# 重试
cd "H:\Work\项目经历\Project_JSJ_Agent"
git push -u origin main
```

### 方案 4: 使用 GitHub Desktop（图形界面，最简单）

1. 下载安装 GitHub Desktop: https://desktop.github.com/
2. 登录 GitHub 账号
3. File → Add Local Repository → 选择 `H:\Work\项目经历\Project_JSJ_Agent`
4. Publish repository（自动处理认证和推送）

### 方案 5: 直接跳过 GitHub，使用 Streamlit Cloud 的 GitHub 集成

如果无法推送到 GitHub，可以：

1. 访问 https://share.streamlit.io/
2. 点击 "New app"
3. 选择 "Connect to GitHub" → "Authorize"
4. Streamlit Cloud 会自动创建仓库并部署

## 推荐流程

**最快方案**: 方案 1（配置代理）或方案 4（GitHub Desktop）

**测试代理端口**（常见代理端口）：
- 7890 (Clash)
- 7891
- 10809 (V2Ray)
- 1080

```bash
# 测试哪个端口可用
curl -x http://127.0.0.1:7890 https://api.github.com
curl -x http://127.0.0.1:7891 https://api.github.com
curl -x http://127.0.0.1:10809 https://api.github.com
```

找到可用端口后，配置到 Git：
```bash
git config --global http.proxy http://127.0.0.1:可用端口
git config --global https.proxy http://127.0.0.1:可用端口
```

## 验证推送成功

推送成功后，访问仓库检查文件：
```
https://github.com/你的用户名/Water-Agent-JSJ
```

应该看到：
- streamlit_demo.py
- requirements_streamlit.txt
- .gitignore
- agent/ 目录
- 等等

## 下一步

推送成功后，继续部署到 Streamlit Cloud（参考 NEXT_STEPS.md）
