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

- 📝 **Auto-render on write** — create posts via the admin panel and Hugo regenerates the site
- 🎛️ **Web admin panel** — write/list posts and switch themes in the browser, no SSH needed
- 🎨 **Theme manager** — upload and switch themes from the admin panel
- 🚀 **Zero-dependency** — single Hugo binary, no Node/Python runtime needed
- 🗄️ **Persistent data** — blog source at `/vol4/@appdata/hugo-blog/`, writable and backup-able
- 🔄 **App Center managed** — start/stop, auto-start on boot, status
- 🌐 **One-click access** — desktop icon opens the blog

## 🚀 Quick Install

1. Download `hugo-blog-x.x.x.fpk` from [Releases](https://github.com/techysy/hugo-blog-fnos/releases)
2. fnOS **App Center → Manual install** → select the fpk
3. Open the **Hugo Blog** desktop icon (port `13133`)

## 📖 Usage

### Write a post (admin panel)

The desktop icon opens the **blog** (port `13133`). To write posts, manually visit the **admin panel** at `http://<NAS-IP>:13134`, fill in title/tags/content in the "Write post" form, click "Save & Publish". Hugo re-renders automatically; refresh the blog to see it.

You can also drop a markdown file into `content/post/`:

```markdown
---
title: "My first post"
date: 2026-08-08
tags: [hugo, fnos]
---

Body here.
```

### Ports

| Service | Port | Purpose |
|---|---|---|
| Blog | `13133` | Site preview (desktop entry) |
| Admin panel | `13134` | Write/list posts (manual access) |

### Data directory

| Item | Value |
|---|---|
| Blog source | `/vol4/@appdata/hugo-blog/blog/` |
| content | `/vol4/@appdata/hugo-blog/blog/content/` |

### Change theme (admin panel)

Open the admin panel (`http://<NAS-IP>:13134`), in the "Theme manager":
1. **Upload theme**: upload a theme zip (containing `theme.toml` or a `layouts` dir)
2. **One-click switch**: click "Use" to switch; Hugo re-renders automatically

You can also drop a theme into `/vol4/@appdata/hugo-blog/blog/themes/<name>/` and set `theme = "<name>"` in `config/_default/config.toml`.

### 🤖 Agent API (query/create posts)

The admin panel port `13134` exposes a REST API so local agents can query and create posts with a token:

```bash
# 1. Get API token (no auth)
TOKEN=$(curl -s http://<NAS-IP>:13134/api/bootstrap | jq -r '.api_token')

# 2. List posts
curl -s -H "Authorization: Bearer $TOKEN" http://<NAS-IP>:13134/api/posts | jq '.posts'

# 3. Blog info
curl -s -H "Authorization: Bearer $TOKEN" http://<NAS-IP>:13134/api/info | jq '.posts,.themes'

# 4. Create a post
curl -s -X POST http://<NAS-IP>:13134/api/new \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"title":"New post","tags":"hugo,fnos","content":"# Body\ncontent..."}'

# 5. Themes / switch
curl -s -H "Authorization: Bearer $TOKEN" http://<NAS-IP>:13134/api/themes | jq '.current'
curl -s -X POST http://<NAS-IP>:13134/api/theme/switch \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"theme":"minimal"}'
```

> 🔐 **Auth**: except `/api/bootstrap`, all `/api/*` require `Authorization: Bearer <token>`. Missing token returns **401**. Token is stored at `/vol4/@appdata/hugo-blog/api_token` (mode 600); delete it and restart to regenerate.
> 💡 After a post is created, Hugo auto re-renders; refresh the blog (13133) to see it.

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
