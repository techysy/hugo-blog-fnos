# Hugo Blog for fnOS

Hugo static blog — a resident rendering service that auto-generates your site as you write posts on fnOS (飞牛 NAS).

[![GitHub release](https://img.shields.io/github/v/release/techysy/hugo-blog-fnos?label=Latest&color=blue)](https://github.com/techysy/hugo-blog-fnos/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://github.com/techysy/hugo-blog-fnos/blob/main/LICENSE)
[![fnOS](https://img.shields.io/badge/fnOS-1.1.31xx+-orange.svg)](https://developer.fnnas.com/docs/guide)
[![Hugo](https://img.shields.io/badge/Hugo-v0.163.3-orange.svg)](https://gohugo.io/)

> Package your Hugo blog as a fnOS app: manage start/stop in App Center, write markdown posts that render automatically, open it with one click from the desktop.

- [中文 README](./README.md)

---

## ✨ Features

- 📝 **Auto-render on write** — drop markdown into `content/post/` and Hugo regenerates the site
- 🚀 **Zero-dependency** — single Hugo binary, no Node/Python runtime needed
- 🗄️ **Persistent data** — blog source at `/vol4/@appshare/hugo-blog/`, writable and backup-able
- 🔄 **App Center managed** — start/stop, auto-start on boot, status
- 🌐 **One-click access** — desktop icon opens the blog

## 🚀 Quick Install

1. Download `hugo-blog-x.x.x.fpk` from [Releases](https://github.com/techysy/hugo-blog-fnos/releases)
2. fnOS **App Center → Manual install** → select the fpk
3. Open the **Hugo Blog** desktop icon (port `1313`)

## 📖 Usage

### Write a post

Create a markdown file in `content/post/`:

```markdown
---
title: "My first post"
date: 2026-08-08
tags: [hugo, fnos]
---

Body here.
```

Save and Hugo **re-renders automatically**; refresh the browser to see it.

### Data directory

| Item | Value |
|---|---|
| Blog source | `/vol4/@appshare/hugo-blog/blog/` |
| content | `/vol4/@appshare/hugo-blog/blog/content/` |
| Port | `1313` |

### Change theme

Put a theme in `/vol4/@appshare/hugo-blog/blog/themes/<name>/` and set `theme = "<name>"` in `config/_default/config.toml`.

## 🐛 Troubleshooting

See [TROUBLESHOOTING.md](./TROUBLESHOOTING.md).

## 🛠️ Build from Source

```bash
# On the NAS
mkdir -p ~/build/hugo-blog-fnos
# Sync project files here
cd ~/build/hugo-blog-fnos
fnpack build            # generates hugo-blog.fpk (url version)
mv hugo-blog.fpk hugo-blog-x.x.x.fpk
sed -i 's/"type": "url"/"type": "iframe"/' app/ui/config   # switch iframe
fnpack build
mv hugo-blog.fpk hugo-blog-x.x.x-iframe.fpk
```

## 📚 Related

- [9Router](https://github.com/techysy/9router-fnos) · [Strava Panel](https://github.com/techysy/strava-panel-fnos) — more fnOS apps

## License

MIT
