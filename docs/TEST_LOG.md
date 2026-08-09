# Hugo Blog 测试记录

> 发版规则：本地验证 OK 后再发正式包；测试包用 `当前版本.第四位累加`（如 0.1.3.1）；测试记录更新点/问题点，正式发布时聚合到 CHANGELOG。

---

## 0.1.4.12 (2026-08-09)

> 多轮修复合集（基于 0.1.4.8 追加，累加至 0.1.4.12）。

### 更新点
- **🔑 创建 token 按钮** — 重建按钮旁新增「创建 token」，替代通过接口 `/api/bootstrap` 拿 token（更安全）；后端 `/api/token/recreate` 重新生成并立即生效（无需重启）
- **🛡 主题切换验证回滚** — `switch_theme` 切换后自动用 hugo 构建验证；若失败自动回滚到原主题，避免普通用户装不兼容主题（如 hugo-book/hugoplate）把博客搞挂
- **🔄 重建按钮异步化** — `rebuild_site` 改为后台异步触发，修复「60 秒超时」报错；前端延迟刷新状态
- **📄 文章列表按日期排序** — `list_posts` 改为按 front matter 的 date 降序排列（原按文件名排序导致顺序混乱）
- **📊 仪表盘全屏适配** — `#tab-dash` 填满视口，日志控制台占剩余空间，无需下拉
- **🔤 侧边栏字体调大** — 导航项 13→14px、品牌 15→16px、版本号 11→12px
- **🎨 设置页子标签选中样式同步** — `.subtab.active` 改为与侧边栏一致（浅蓝底 + 彩色文字）
- **🃏 主题管理改卡片** — 主题列表由表格改为卡片网格（`themes-grid`），显示主题名、状态、操作（使用/删除），当前使用中主题卡片高亮
- **📊 仪表盘布局调整** — 填满视口不滚动（日志区内部滚动）；📜 日志控制台卡片默认宽度收窄居中（不占满容器）
- **🏷 品牌区间隙修复** — 「📝 Hugo Blog」与版本号之间加间距（margin-top）
- **🌐 仪表盘 i18n 优化** — 日志来源下拉选项（Hugo 日志/管理面板日志）与日期「当前」改为中英文切换
- **🧹 移除主题管理多余文本** — 移除「· : minimal」当前主题提示（curTheme），避免页面冗余文本；📜 日志控制台宽度与服务状态一致
- **📄 文章列表优化** — 每页 10→20 个；标题超长截断；移动端隐藏文件名列只留标题+日期
- **🎨 主题管理去掉「使用中」文本** — 移除「✓ 使用中」文字提醒，当前主题只靠卡片选中高亮
- **🌐 i18n 修复** — 服务状态卡片冒号多余；日志来源名用 i18n（Hugo 日志/管理面板日志）；删除主题错误码 i18n（err_* 映射）；API 指南中英双语 + 补充新接口（token/recreate、rebuild、doc）
- **ℹ️ Hugo 版本号显示** — 仪表盘「Hugo 版本」显示具体版本号（v0.163.3），不再只显示「hugo」
- **🔑 API 指南查看 token** — 新增 `/api/token/view` 接口 + API 使用指南页「查看 token」按钮；API 文档 token 获取改为管理面板查看/创建（不再用 /api/bootstrap）

### 验证状态
- [x] 各改动本地语法验证（py_compile / bash -n）
- [x] fpk 打包成功（url + iframe 双版）
- [ ] App Center 升级到 0.1.4.9 后回归 — **待办**

---

## 0.1.4.8 (2026-08-09)

> 仪表盘「重建站点」按钮（基于 0.1.4.7 追加）。

### 更新点
- **🔄 重建站点按钮** — 仪表盘服务状态区新增「重建站点」按钮，手动触发 hugo 重建（解决 watch 不自动重建的问题）
- 后端：`cmd/main` 新增 `rebuild` 命令（仅重建 hugo，不动 manager）；manager.py 新增 `/api/rebuild` 接口
- 前端：`rebuildSite()` 调用接口，重建后自动刷新服务状态与日志

### 验证状态
- [x] `/api/rebuild` 接口（成功返回 ok + msg，未认证 401）
- [x] 前端重建按钮 + rebuildSite 函数
- [x] fpk 内 cmd/main 含 rebuild（已解包验证）
- [x] JS/Python/bash 语法（node --check / py_compile / bash -n）
- [ ] App Center 升级到 0.1.4.8 后最终回归 — **待办**

---

## 0.1.4.7 (2026-08-09)

> 品牌区版本号（基于 0.1.4.6 追加）。

### 更新点
- **🏷 品牌区版本号** — 侧边栏「📝 Hugo Blog」下方新增版本号显示
- 版本号由后端 `APP_VERSION` 常量提供，`/api/bootstrap` 返回 `version` 字段，前端 initToken 时动态填充

### 验证状态
- [x] 品牌区显示 `v0.1.4.7`
- [x] `/api/bootstrap` 返回 version
- [x] JS 语法（node --check 通过）
- [ ] App Center 升级到 0.1.4.7 后最终回归 — **待办**

---

## 0.1.4.6 (2026-08-09)

> API 文档渲染 + 日志控制台响应式（基于 0.1.4.5 追加）。

### 更新点
- **📜 日志控制台响应式** — 控件区改 `.log-controls` class，日志区改 `.log-view` class；移动端（≤768px）控件占满宽度、日志区高度/字号自适应
- **🤖 API 指南 Markdown 渲染** — 新增后端 `/api/doc` 接口（Python 生成 MD），前端改为从接口获取并**渲染成 Markdown 排版**（标题/代码块/引用/列表），不再是纯文本；保留「复制文档」按钮（复制原始 MD）
- **🔧 解析 JSON 用 python3** — API 文档所有命令从 `jq` 改为 `python3` 解析（fnOS/多数系统自带），补充 jq 可选说明；文档新增「一键测试脚本」可直接运行

### 问题点（已解决）
- **日志控制台无自适应** — 控件区/日志区全内联样式，移动端错乱。已改 CSS class + 媒体查询适配。
- **API 指南纯文本/转义反复出错** — 前端 JS 内联 shell 命令多次转义失败（`${}`、`\n`、单引号嵌套）。改为后端 Python 生成文档 + `/api/doc` 接口，彻底避开前端转义。

### 验证状态
- [x] 日志控制台响应式（桌面端正常，移动端媒体查询就绪）
- [x] API 文档 Markdown 渲染（标题/代码块/引用/列表 + 复制按钮）
- [x] `/api/doc` 接口（3767 字符，含 python3 解析 + 一键脚本）
- [x] JS 语法（node --check 通过）
- [ ] App Center 升级到 0.1.4.6 后最终回归 — **待办**

---

## 0.1.4.5 (2026-08-09)

> 信息架构重构 + API 指南 + 预置主题保护（基于 0.1.4.4 追加）。

### 更新点
- **🧭 信息架构重构** — 仪表板（服务状态 + 控制台）提升为**默认首页**；侧边栏改为：仪表板 / 写文章 / 文章列表 / 设置；「主题」移入设置页
- **⚙️ 设置页子标签** — 设置页内分「主题 / 代理 / API」三个标签页
- **🤖 API 使用指南** — 设置页新增「API」标签，展示可复制的 Markdown API 路由文档（token/服务/文章/主题/日志/代理），含「复制文档」按钮
- **🛡 预置主题保护** — 系统预置主题（minimal）不显示「删除」按钮，后端 `delete_theme` 也拒绝删除预置主题

### 问题点（已解决）
- **minimal 预置主题显示删除按钮** — 前端操作列对预置主题透出删除按钮。修复：预置主题只显示「使用」，后端加 `系统预置主题不能删除` 保护。
- **侧边栏无响应（JS 崩溃）** — buildApiDoc 里 shell 续行反斜杠 `\` 在 Python 三引号字符串中被错误转义，导致生成 JS 语法错误，整个 `<script>` 解析失败、所有函数（含 switchNav）未定义。修复：改用模板字符串 + `-d @file` 方式重写 buildApiDoc，去除续行符和嵌套单引号转义；`T.join` 用 `"\\n"` 保证 JS 换行正确。已用 node --check 验证 JS 语法通过、浏览器侧边栏响应正常。

### 验证状态
- [x] 仪表板为默认首页（nav + tab 均 active dash）
- [x] 设置页三标签（主题/代理/API）
- [x] API 指南 MD 文档生成 + 复制
- [x] 预置主题删除保护（前端隐藏按钮 + 后端拒绝）
- [ ] App Center 升级到 0.1.4.5 后最终回归 — **待办**

---

## 0.1.4.4 (2026-08-09)

> 测试反馈修复 + 历史文章规范化（基于 0.1.4.3 追加）。

### 更新点
- **品牌区保留** — 侧边栏左上角保留「📝 Hugo Blog」品牌标识（顶部主标题仍去掉）
- **日志背景半透明** — 日志控制台黑色背景改为 `rgba(0,0,0,0.82)` 半透明，透出底部主题色，暗夜/日间均不太刺眼
- **仪表板去重复** — 服务状态卡片合并：Hugo 服务+博客端口、管理面板+管理端口 各合并为一张卡，从 8 卡精简为 6 卡
- **历史文章规范化** — 批量处理 35 篇历史文章：
  - 文件名去掉 Jekyll 式 `YYYY-MM-DD-` 日期前缀（重命名 18 篇）
  - 删除 2 篇重复文章（新旧两版保留新版）
  - front matter `date` 统一为 RFC3339 无引号格式（`2026-06-22T00:00:00+08:00`），清理多重 date 字段
  - 处理前已备份到 `/tmp/post_backup_20260809_184957`

### 问题点（已解决）
- **历史文章格式混乱** — 文件名日期前缀 + date 格式多样（带引号/纯日期/空格偏移/多重date）。已统一为 Hugo 标准。
- **仪表板重复** — 服务与端口分开显示导致 4 个「运行中」重复。已合并。

### 验证状态
- [x] 品牌区保留（侧边栏左上角）
- [x] 日志半透明背景
- [x] 仪表板合并（6 卡）
- [x] 文章规范化（33 篇，date 统一 RFC3339，hugo 构建 201 页通过）
- [ ] App Center 升级到 0.1.4.4 后最终回归 — **待办**

---

## 0.1.4.3 (2026-08-09)

> 管理面板二次重构（基于 0.1.4.2 追加）。

### 更新点
- **🗂 设置页拆分** — 设置页内部分「仪表板 / 代理」子标签页；仪表板含**服务状态卡片** + 日志控制台，代理设置单独 tab
- **📊 服务状态仪表板** — `/api/info` 增强返回 hugo/manager 进程、端口监听、hugo 版本、文章/主题统计，前端以彩色状态卡片展示
- **去品牌文案** — 移除侧边栏 brand 和顶部「Hugo Blog 管理」h1
- **🏷 主题标签** — 主题列表区分「系统预置」（minimal）/「已安装」/「Module」标签
- **🚫 重复安装友好提示** — `install_git_theme` 检测目标已存在时返回「主题已存在，可直接切换或先删除」，不再暴露 git `fatal: destination path already exists`
- **⏱ hugo 日志时间戳** — `cmd/main` 启动 hugo 时用 `awk strftime` 给每行加 `[YYYY-MM-DD HH:MM:SS]` 前缀
- **🔄 代理设置聚合** — HTTP/HTTPS 合并为「代理地址 (HTTP/HTTPS 共用)」单一输入

### 问题点（已解决）
- **主题列表空白** — 根因 1：i18n `applyI18n()` 用 innerHTML 覆盖了嵌入 h2 的 `curTheme` span → 移出 h2。根因 2：`loadThemes` 的 `map(t=>{})` 回调参数 `t` 遮蔽了 i18n 函数 `t()` → 改为 `map(th=>{})`。

### 验证状态
- [x] 设置页子 tab（仪表板/代理）切换
- [x] 服务状态卡片（进程/端口/版本/统计）
- [x] 品牌文案移除
- [x] 主题标签（预置/已安装）+ 无脏数据
- [x] hugo 日志时间戳
- [x] 代理聚合
- [ ] App Center 升级到 0.1.4.3 后最终回归 — **待办**

---

## 0.1.4.2 (2026-08-09)

> 管理面板 UI 重构（基于 0.1.4.1 追加）。

### 更新点
- **🌗 日夜主题切换** — 控制面板顶部加日夜切换按钮，持久化（localStorage）
- **🌐 i18n 中英文切换** — 控制面板顶部加语言切换按钮，全部界面文案中英文对照
- **🧭 导航重组** — 侧边栏改为：写文章 / 文章列表 / 主题 / 设置；「日志控制台」移入「设置」tab（与代理合并）
- **🎨 主题页重构**：
  - 「从 git 仓库安装」「从 Hugo Module 安装」合并为单个「在线安装」输入框（自动识别 git URL 或 module 路径）
  - 「上传 zip」放最下面（标注：用于无法使用 GitHub 的场景，优先级最低）
- **🐛 修复主题脏数据** — `list_themes()` 解析 go.mod 时跳过 `require (` 括号行和 `// indirect` 工具依赖，消除「(」脏主题
- **🖤 日志控制台黑色背景** — 日志显示区固定终端风格黑底浅字，不随日夜主题变化

### 问题点（已解决）
- **主题列表脏数据「(」** — 根因：go.mod 解析把 `require (` 括号行当成了 module 主题。修复：跳过括号行 + indirect 注释。

### 验证状态
- [x] 日夜切换（暗色模式验证通过）
- [x] i18n 中英文切换（英文界面验证通过）
- [x] 导航重组（控制台并入设置）
- [x] 主题安装合并 + 上传置底
- [x] 脏数据「(」修复（list_themes 过滤）
- [x] 日志黑色背景（终端风格验证通过）
- [ ] App Center 升级到 0.1.4.2 后最终回归 — **待办**

---

## 0.1.4.1 (2026-08-09)

> 基于 v0.1.4 聚合 + 本次新增三功能（测试版）。

### 更新点
- **📜 管理面板控制台（日志）**：
  - 新增 `/api/logs`、`/api/logs/list`、`/api/logs/download` 接口（带认证）
  - 显示 `hugo.log` + `manager.log` 两个来源，支持日期筛选 / 刷新 / 下载
  - **按日期归档**：启动时把非当天日志滚到 `data/logs/hugo.log.YYYYMMDD`，当前文件只留当天，避免单文件无限增长
- **🎨 Dart Sass 支持（SCSS 主题）**：
  - 打包 dart-sass 到 `server/dart-sass/`，`cmd/main` 启动时加入 PATH
  - 解决 `anatole`/`docuapi` 等 SCSS 主题 `TOCSS-DART` 启动失败问题
- **🔌 应用介绍明确端口**：manifest `desc` + README 写明博客 `13133` / 管理面板 `13134`

### 问题点（已解决）
- **SCSS 主题无法启用** — 根因：hugo server 需外部 dart-sass 编译 SCSS，系统未装 → `TOCSS-DART` 报错 → 应用启动失败。修复：打包 dart-sass 进应用并加入 PATH。

### 验证状态
- [x] 控制台 API（本地 + NAS 测试环境）— 日志读取/归档/下载/认证全部通过
- [x] Dart Sass + anatole-master（SCSS）主题 — hugo server HTTP 200
- [x] cmd/main dart-sass PATH 检测
- [ ] App Center 升级到 0.1.4.1 后最终回归 — **待办**

---

## 📦 正式版聚合 (v0.1.4) — 2026-08-09

0.1.3.1~0.1.3.10 测试阶段的全部改动已**聚合到 CHANGELOG v0.1.4**，manifest 版本先升为 `0.1.4`，后续追加 0.1.4.1 功能后当前版本为 `0.1.4.1`（测试版）。

- [x] CHANGELOG 聚合 v0.1.4（新增/变更/修复三分类）
- [ ] 打包正式 fpk（url + iframe 双版）— 因 0.1.4.1 追加功能，待功能稳定后再发正式 v0.1.4
- [ ] git 打标签 `v0.1.4` + 建 GitHub Release — **待办**

---

## 0.1.3.10 (2026-08-09)

### 更新点
- **强化主题导入**：
  - 新增「从 git 仓库安装」(`POST /api/theme/git`) — git clone 到 themes/，无需转存 zip
  - **自动检测依赖** (`detect_theme_deps`)：检测 go.mod 是否有 module require、assets 是否有 SCSS，安装后提示
  - zip 上传 / git 克隆 / module 安装三合一

### 问题点（已解决）
- **历史文章格式** — 检查全部 35 篇：无 draft、无 date 异常、categories/tags 均为数组格式（之前已修复 categories）

### 验证状态
- [x] git 安装真实 GitHub 主题（LoveIt）成功
- [x] 依赖检测（检测到 LoveIt sass 依赖）

---

## 0.1.3.9 (2026-08-09)

### 更新点
- **主题删除能力** — 管理面板主题列表加「删除」按钮（`POST /api/theme/delete`）：
  - 传统主题：删除 `themes/<name>/`
  - module 主题：从 go.mod 移除
  - 安全：不能删除当前使用中的主题；路径穿越检查

### 问题点（已解决）
- （无新增问题；删除主题本地验证通过）

---

## 0.1.3.8 (2026-08-09)

### 更新点
- **控制面板加代理设置**（⚙️ 设置 导航项）：
  - `GET/POST /api/proxy`（带认证）读写代理配置（HTTP/HTTPS/NO_PROXY），存 `DATA_DIR/proxy_config`
  - cmd/main 启动 hugo 时读取 proxy_config 设置 `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY`，解决下载 module 主题慢/超时

### 问题点（已解决）
- （无新增问题；代理设置本地验证通过）

---

## ⚠️ 已知坑 / Pitfall

- **module 主题不能简单切换** — 把 docuapi 这类 module 主题放进 themes/ 并 `theme="docuapi-master"`，hugo 启动会尝试下载 module 依赖并超时（`context deadline exceeded`），导致 hugo 卡住、13133 不监听、博客拒绝连接。正确：用管理面板「从 Hugo Module 安装」（`hugo mod get`）下载依赖。
- **SCSS 主题需 Dart Sass** — 如 `anatole-master` 主题需要 Dart Sass 编译 SCSS（`TOCSS-DART: you need to install Dart Sass`），当前 hugo extended 不支持 → 渲染失败 → 启动失败。需装 dart-sass 或换无 SCSS 主题（如 minimal）。
- **categories 字符串 vs 数组** — 迁移的历史文章若 `categories: jekyll`（字符串），anatole 等主题需数组 `categories: [jekyll]`，否则 `range can't iterate` 报错。已批量修复 18 篇（备份 /tmp/post_backup）。

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
