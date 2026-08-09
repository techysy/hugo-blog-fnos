# Hugo Blog for fnOS

Hugo 静态博客 — 常驻渲染服务，在飞牛 NAS (fnOS) 上写文章自动生成站点。

[![GitHub release](https://img.shields.io/github/v/release/techysy/hugo-blog-fnos?label=Latest&color=blue)](https://github.com/techysy/hugo-blog-fnos/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://github.com/techysy/hugo-blog-fnos/blob/main/LICENSE)
[![fnOS](https://img.shields.io/badge/fnOS-1.1.31xx+-orange.svg)](https://developer.fnnas.com/docs/guide)
[![Hugo](https://img.shields.io/badge/Hugo-v0.163.3-orange.svg)](https://gohugo.io/)

> 把 Hugo 静态博客打包成飞牛应用：App Center 管理启停，写 markdown 文章自动渲染，桌面图标一键访问。

- [English README](./README.en.md)

---

## ✨ 功能亮点

- 📝 **写文章自动渲染** — 管理面板新建文章，Hugo 自动生成站点
- 🎛️ **Web 管理面板** — 浏览器里新建/查看/换主题，无需 SSH
- 🎨 **主题管理** — 管理面板里上传主题、一键切换
- 🚀 **零依赖** — Hugo 单二进制，无需 Node/Python 运行时
- 🗄️ **数据持久化** — 博客源在 `/vol4/@appdata/hugo-blog/`，可写、可备份
- 🔄 **App Center 管理** — 启停、开机自启、状态查看
- 🌐 **一键访问** — 桌面图标打开博客

## 🚀 快速安装

1. 从 [Releases](https://github.com/techysy/hugo-blog-fnos/releases) 下载 `hugo-blog-x.x.x.fpk`
2. 飞牛 **App Center → 手动安装** → 选择 fpk
3. 桌面出现 **Hugo Blog** 图标，点击打开博客（端口 `13133`）

> 🔌 **两个端口**：
> - 博客（桌面图标）：`http://<NAS-IP>:13133`
> - 管理面板（写文章/换主题/控制台日志）：`http://<NAS-IP>:13134`

## 📖 使用说明

### 写文章（管理面板）

桌面图标打开**博客**（端口 `13133`）。写文章需手动访问**管理面板** `http://<NAS-IP>:13134`，在「写文章」表单里填标题、标签、内容，点「保存并发布」。Hugo 自动重新渲染，刷新博客即可看到。

也可直接在数据目录 `content/post/` 放 markdown 文件：

```markdown
---
title: "我的第一篇文章"
date: 2026-08-08
tags: [hugo, fnos]
---

这里是正文内容。
```

### 端口

| 服务 | 端口 | 用途 |
|---|---|---|
| 博客 | `13133` | 站点预览（桌面入口） |
| 管理面板 | `13134` | 新建/查看文章（手动访问） |

### 数据目录

| 项 | 值 |
|---|---|
| 博客源 | `/vol4/@appdata/hugo-blog/blog/` |
| content | `/vol4/@appdata/hugo-blog/blog/content/` |

### 换主题（管理面板）

打开管理面板（`http://<NAS-IP>:13134`），在「主题管理」里：
1. **上传主题**：上传主题 zip 包（含 theme.toml 或 layouts 目录）
2. **从 Hugo Module 安装**：输入 module 路径（如 `github.com/bep/docuapi`），联网下载安装（需依赖飞牛 `go-1.26`）
3. **一键切换**：点击「使用」即可切换主题，Hugo 自动重新渲染

也可直接在数据目录放主题：把主题放到 `/vol4/@appdata/hugo-blog/blog/themes/<name>/`，并在 `config/_default/config.toml` 改 `theme = "<name>"`。

> 📦 **两类主题**：传统 zip 主题（上传到 themes/）和 Hugo Module 主题（如 docuapi，通过 `hugo mod get` 安装）。module 主题需要 `go-1.26` 依赖（安装时自动装）。

### 🤖 Agent API（查询/创建文章）

管理面板端口 `13134` 提供 REST API，本地 agent 可用 token 查询和创建文章：

```bash
# 1. 获取 API token（免认证）
TOKEN=$(curl -s http://<NAS-IP>:13134/api/bootstrap | jq -r '.api_token')

# 2. 查询文章列表
curl -s -H "Authorization: Bearer $TOKEN" http://<NAS-IP>:13134/api/posts | jq '.posts'

# 3. 查询博客信息
curl -s -H "Authorization: Bearer $TOKEN" http://<NAS-IP>:13134/api/info | jq '.posts,.themes'

# 4. 创建文章
curl -s -X POST http://<NAS-IP>:13134/api/new \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"title":"新文章","tags":"hugo,fnos","content":"# 正文\n内容..."}'

# 5. 主题列表 / 切换
curl -s -H "Authorization: Bearer $TOKEN" http://<NAS-IP>:13134/api/themes | jq '.current'
curl -s -X POST http://<NAS-IP>:13134/api/theme/switch \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"theme":"minimal"}'
```

> 🔐 **认证**：除 `/api/bootstrap` 外，所有 `/api/*` 需 `Authorization: Bearer <token>`。未带 token 返回 **401**。token 存于 `/vol4/@appdata/hugo-blog/api_token`（权限 600），删除该文件后重启应用会重新生成。
> 💡 agent 创建文章后，Hugo 自动重新渲染，刷新博客（13133）即可看到。

## 🐛 问题排查

见 [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)。

## 🛠️ 从源码构建

```bash
# 在 NAS 上
mkdir -p ~/build/hugo-blog-fnos
# 同步项目文件到这里
cd ~/build/hugo-blog-fnos
fnpack build            # 生成 hugo-blog.fpk (url 版)
mv hugo-blog.fpk hugo-blog-x.x.x.fpk
sed -i 's/"type": "url"/"type": "iframe"/' app/ui/config   # 切 iframe
fnpack build
mv hugo-blog.fpk hugo-blog-x.x.x-iframe.fpk
```

## 📚 相关项目

- [9Router](https://github.com/techysy/9router-fnos) · [Strava Panel](https://github.com/techysy/strava-panel-fnos) — 更多 fnOS 应用

## License

MIT
