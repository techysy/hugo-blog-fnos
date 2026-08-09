# Hugo Blog 测试记录

> 发版规则：本地验证 OK 后再发正式包；测试包用 `当前版本.第四位累加`（如 0.1.3.1）；测试记录更新点/问题点，正式发布时聚合到 CHANGELOG。

---

## ⚠️ 已知坑 / Pitfall

- **module 主题不能简单切换** — 把 docuapi 这类 module 主题放进 themes/ 并 `theme="docuapi-master"`，hugo 启动会尝试下载 module 依赖并超时（`context deadline exceeded`），导致 hugo 卡住、13133 不监听、博客拒绝连接。正确：用管理面板「从 Hugo Module 安装」（`hugo mod get`）下载依赖。

---

## 0.1.3.7 (2026-08-09)

### 更新点
- **数据目录改回 @appdata** — 文章/博客源放 app 私有目录（`/vol4/@appdata/<app>`），通过管理面板 API 管理，不暴露在公开 @appshare
- **支持 Hugo Module 依赖主题** — 依赖飞牛官方 go 依赖（`go-1.26`，Golang 1.26.4），manifest `install_dep_apps=go-1.26`；cmd/main 检测 go-1.26 路径配置 GOROOT/PATH/GOPROXY；管理面板加"从 Hugo Module 安装"（`hugo mod get`）。**不打包 go**（用官方依赖，fpk 小）。
- （曾打包精简 go ~93MB，后因官方有 go-1.26 依赖改为引用官方）

### 问题点（已解决）
1. **module 主题需 go** — hugo mod get 报 "binary go not found"。用官方 go-1.26 依赖解决。
2. **docuapi 等 module 主题** — 通过 module 安装（hugo mod get）而非上传 zip。

### 验证状态
- [x] cmd/main 检测官方 go-1.26 路径
- [x] manifest 声明 go-1.26 依赖
- [x] 无打包 go（fpk 恢复 ~21MB）

---

## 0.1.3.6 (2026-08-09)

### 更新点
- **管理面板导航移到左侧** — 移除顶部重复 tab，改用左侧边栏导航（写文章/文章列表/主题）
- **移动端汉堡菜单** — 侧边栏加汉堡菜单 + 遮罩层（≤768px 侧边栏滑出，参考 Hermes Core 模式）

### 问题点（已解决）
- （无新增问题）

### 验证状态
- [x] 桌面：左侧边栏导航切换正常，顶部无重复 tab
- [x] 移动端：汉堡按钮显示、侧边栏滑出、遮罩层
- [x] 主题列表、文章分页

---

## 0.1.3.5 (2026-08-09)

### 更新点
- **管理面板 UI 重构（参考 strava）**：
  - 顶部 **tab 分页**切换：写文章 / 文章列表 / 主题（橙色选中态，参考 strava 切换风格）
  - **文章列表分页**：每页 10 篇，翻页控件
  - 修复主题列表 onclick 转义 bug（switchTheme 参数转义错误导致 JS 语法错误）

### 问题点（已解决）
1. **JS 语法错误 "Unexpected string"** — loadThemes 里 `onclick="switchTheme(...)"` 的转义写错（`\''+...`），改为模板字符串插值 `${t.name}` 修复

### 验证状态
- [x] tab 切换（写文章/文章列表/主题）
- [x] 文章列表分页（15 篇分 2 页，翻页正常）
- [x] 主题列表显示

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
