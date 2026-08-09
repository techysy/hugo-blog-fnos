# Hugo Blog 测试记录

> 发版规则：本地验证 OK 后再发正式包；测试包用 `当前版本.第四位累加`（如 0.1.3.1）；测试记录更新点/问题点，正式发布时聚合到 CHANGELOG。

---

## 0.1.3.4 (2026-08-09)

### 更新点
- **暴露 API 给 agent + 认证** — manager.py 增加 API token 认证：
  - `GET /api/bootstrap` 免认证，返回 `api_token`
  - 其余 `/api/*`（posts/themes/info/new/theme_switch/theme_upload）需 `Authorization: Bearer <token>`
  - token 存数据目录 `api_token`（权限 600）
  - 前端管理面板自动携带 token
- **文档化 API** — README 增加 agent 用法示例

### 问题点（已解决）
- （无新增问题；API 认证本地验证通过）

---

## 0.1.3.3 (2026-08-09)

### 更新点
- **cmd/main 启动 hugo 前同时删除 `.hugo_build.lock` + `public/` 渲染产物** — 避免残留文件（属主非 hugo-blog）导致权限拒绝

### 问题点（已解决）
1. **启动失败（0.1.3.2）** — 根因：`public/` 目录内文件属主是 `yangyu`（SSH 手动渲染测试创建），hugo-blog 用户无法覆盖 → `permission denied`。修复：cmd/main 启动前 `rm -rf public` + `rm -f .hugo_build.lock`。

---

## 0.1.3.2 (2026-08-09)

### 更新点
- **cmd/main 启动 hugo 前删除 `.hugo_build.lock`** — 避免残留 lock（属主非 hugo-blog）导致权限拒绝、启动失败

### 问题点（已解决）
1. **启动失败（0.1.3.1）** — 根因：`.hugo_build.lock` 属主是 `yangyu`（SSH 手动测试创建），hugo-blog 用户无法写 → `permission denied`。修复：cmd/main 启动前 `rm -f .hugo_build.lock`，hugo 以 hugo-blog 用户重新创建。

---

## 0.1.3.1 (2026-08-09)

### 更新点
- **强制使用 `@appshare` 数据目录** — cmd/main 忽略 fnOS 注入的 `TRIM_PKGVAR`（指向 @appdata），固定用 `/vol4/@appshare/hugo-blog/`
- 历史文章迁移到 `@appshare/hugo-blog/blog/content/post/`（35 篇）
- Web 管理面板（写文章 / 主题管理：上传 + 切换）

### 问题点（已解决）
1. **"应用包不符合系统要求"** — 根因：`service_port` 太低（1313）；`desktop_applaunchname` 连字符缺失；`config/resource` JSON 格式。已修复。
2. **文章不显示** — 根因：fnOS 注入 `TRIM_PKGVAR=/vol4/@appdata` 覆盖了 @appshare 默认值。已修复（cmd/main 强制 @appshare）。
3. **"本地应用启动失败"** — 根因：`.hugo_build.lock` 属主是 `yangyu`（SSH 渲染测试残留），hugo-blog 用户无法写。已修复（删除 lock + 统一属主）。

### 验证状态
- [x] hugo 用 @appshare 正常启动，博客显示 35 篇文章
- [x] 主题上传/切换正常
- [x] 写文章正常（管理面板）

### 待验证
- [ ] App Center 启用后能正常启动（需用户确认）
- [ ] 正式发布前最终回归
