# TROUBLESHOOTING / 问题排查

| 问题 | 原因 | 解决 |
|---|---|---|
| 博客打开空白 | 无主题或 `content/` 为空 | 确认 `config/_default/config.toml` 的 `theme` 存在；往 `content/post/` 加文章 |
| 端口 1313 被占用 | 其它服务占用或残留进程 | App Center 停止→启动，或重启 NAS |
| 换主题不生效 | Hugo 缓存 | 改 `config/_default/config.toml` 后重启应用 |
| 文章不显示 | 日期在未来 | 把 `date` 设为今天或更早；Hugo 会排除未来日期文章 |
| 数据目录权限 | 文章写不进 | 确认 `/vol4/@appdata/hugo-blog/blog/content/` 属主为 `hugo-blog` 用户 |
