# CHANGELOG / 更新日志

---

## v0.1.4.14 (2026-08-16)

### 修复 / Fixed
- **数据目录动态化**：`DATA_DIR` 优先 `TRIM_PKGVAR`，兜底从 fnOS `home` 软链（`/volX/@apphome/<app>`）推导卷，**不写死 `/vol4`**（应用装在非 `/vol4` 卷时路径正确）
- **依赖路径动态化**：`GO_DIR` / `DART_SASS` 用 `APP_VOL` 推导 `@appcenter` 路径，不再硬编码 `/vol4`

---

## v0.1.5 (2026-08-09)

> 聚合 0.1.4.1~0.1.4.13 测试阶段的全部改动。

### 新增 / Added

- **🔄 重建站点按钮** — 仪表盘新增「重建站点」，手动触发 hugo 重建（异步后台执行，修复长耗时超时）；解决 hugo watch 不自动重建时需手动刷新的问题
- **🔑 创建 token 按钮** — 仪表盘新增「创建 token」，替代通过免认证接口 `/api/bootstrap` 获取 token（更安全）；新增 `/api/token/recreate`、`/api/token/view`
- **🛡 主题切换验证回滚** — 切换主题后自动用 hugo 构建验证，失败自动回滚到原主题，避免普通用户装不兼容主题（如文档类主题）把博客搞挂
- **🎨 主题管理改卡片** — 主题列表由表格改为卡片网格，显示主题名/状态/操作；当前使用中主题卡片高亮（不再显示「✓ 使用中」文字）
- **🤖 API 使用指南** — 设置页新增 API 标签：中英双语文档（`/api/doc?lang=zh/en`）+ Markdown 渲染 + 复制 + 查看 token；文档补充新接口（token/recreate、rebuild、doc）
- **ℹ️ 品牌区版本号** — 侧边栏「📝 Hugo Blog」下方显示版本号（由后端 APP_VERSION 提供）
- **📜 日志控制台响应式** — 移动端自适应（控件占满宽度、日志区高度/字号自适应），宽度与服务状态一致

### 变更 / Changed

- **🎛 导航 IA 重构** — 仪表板成为默认主页；侧边栏导航「仪表板/写文章/文章列表/设置」；设置页拆「主题/代理/API」子标签
- **📄 文章列表优化** — 按 front matter date 降序排列；每页 10→20 篇；标题超长截断；移动端隐藏文件名列
- **📊 仪表盘全屏适配** — 填满视口不滚动（日志区内部滚动）
- **🔤 侧边栏字体调大** — 导航项 13→14px、品牌 15→16px、版本号 11→12px
- **🔐 数据/API 安全** — 删除主题错误改为错误码（err_*），前端映射 i18n

### 修复 / Fixes

- **🌐 i18n 修复** — 服务状态卡片多余冒号；日志来源名 i18n（Hugo 日志/管理面板日志）；API 指南中英双语
- **🏷 品牌区间隙** — 「📝 Hugo Blog」与版本号之间加间距
- **📊 仪表盘宽度** — 📜 日志控制台宽度与服务状态一致（移除收窄居中）
- **ℹ️ Hugo 版本号显示** — 仪表盘显示具体版本号（v0.163.3），不再只显示「hugo」

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
