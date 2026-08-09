# CHANGELOG / 更新日志

---

## v0.1.4 (2026-08-09)

### 新增 / Added

- **主题管理增强** — 管理面板新增：
  - **从 git 仓库安装**：`git clone` 到 `themes/`，无需转存 zip（`POST /api/theme/git`）
  - **删除主题**：传统主题删 `themes/<name>/`，module 主题从 go.mod 移除；不能删除当前使用中的主题，含路径穿越检查
  - **依赖自动检测**：检测 go.mod module require、assets SCSS，安装后提示
- **代理设置** — 管理面板新增「设置」项，可配置 `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY`（存 `DATA_DIR/proxy_config`），解决下载 module 主题慢/超时
- **Agent API 认证** — 暴露带认证的 REST API：`GET /api/bootstrap` 免认证返回 `api_token`，其余 `/api/*` 需 `Authorization: Bearer ***`（token 存数据目录，权限 600）

### 变更 / Changed

- **管理面板 UI 重构**：
  - 顶部 **tab 分页**切换：写文章 / 文章列表 / 主题
  - **文章列表分页**（每页 10 篇，翻页控件）
  - 导航移到**左侧边栏**，移动端加**汉堡菜单**（≤768px 侧边栏滑出 + 遮罩层）
- **支持 Hugo Module 主题** — 用飞牛官方 `go-1.26` 依赖（不打包 go，fpk 更小），cmd/main 检测 go 路径配置 GOROOT/PATH/GOPROXY；管理面板「从 Hugo Module 安装」（`hugo mod get`）
- **数据目录改回 `@appdata`** — 博客源放在应用私有目录 `/vol4/@appdata/hugo-blog/`，通过管理面板 API 管理，不暴露在公开 @appshare

### 修复 / Fixes

- **启动失败（残留文件权限）** — 修复 `.hugo_build.lock` 或 `public/` 渲染产物属主非 `hugo-blog` 用户导致的 `permission denied`。现 cmd/main 启动前删除 `.hugo_build.lock` 并清理 `public/`
- **文章分类格式** — 迁移历史文章 `categories` 由字符串改为数组格式，避免主题 `range can't iterate` 报错

---

## v0.1.3 (2026-08-09)

### 修复 / Fixes

- **强制使用 `@appshare` 数据目录** — fnOS 会注入 `TRIM_PKGVAR=/vol4/@appdata/<app>`，旧 cmd/main 用 `${TRIM_PKGVAR:-@appshare}` 被覆盖为 @appdata，导致博客源实际在 @appdata 而非 @appshare。现 cmd/main **忽略 TRIM_PKGVAR，固定用 `/vol4/@appshare/<app>`**，确保博客源统一在应用共享目录。

---

## v0.1.2 (2026-08-09)

### 新增 / Added

- 🎨 **主题管理** — 管理面板新增主题功能：
  - 列出已安装主题 + 一键切换（改 `config/_default/config.toml` 的 theme 字段，Hugo 自动重新渲染）
  - 上传主题 zip 包（解压到 `themes/`，含 theme.toml 或 layouts 校验）

---

## v0.1.1 (2026-08-09)

### 变更 / Changed

- **数据目录统一到 `@appshare`** — 博客源从 `/vol4/@appdata/hugo-blog/blog/` 改为 `/vol4/@appshare/hugo-blog/blog/`（应用共享目录，可在飞牛文件管理直接查看管理）
- 桌面入口指向博客（端口 `13133`），管理面板手动访问（端口 `13134`）
- 使用 Hugo 官方图标

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
