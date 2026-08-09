# CHANGELOG / 更新日志

---

## v0.1.0 (2026-08-09)

### 初始版本 / Initial Release

- Hugo 静态博客 fnOS 应用（`hugo-blog`）
- 常驻 `hugo server`（端口 `13133`），写 markdown 自动渲染
- 🎛️ **Web 管理面板**（端口 `13134`）— 浏览器里新建/查看文章，无需 SSH
- 🖼️ **Hugo 官方图标**
- 🗄️ 博客源在数据目录 `/vol4/@appdata/hugo-blog/blog/`，可写可备份
- 内置极简主题 `minimal`（开箱即用，可换正式主题）
- 双版本 fpk（url / iframe）

### 迭代修复 / Fixes

- 端口用高端口 `13133`（低端口 1313 导致"不符合系统要求"）
- `desktop_applaunchname` 保留 appname 连字符（`hugo-blog.Application`）
- `config/resource` JSON 格式匹配 fnOS 要求
- 图标 RGBA 格式
