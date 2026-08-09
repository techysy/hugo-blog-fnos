#!/usr/bin/env python3
"""
Hugo Blog 管理面板后端 — 纯 Python 标准库零依赖
提供: 新建文章 / 文章列表 / 博客信息
配合 hugo server 的 watch 模式，新建文章后自动重新渲染。

用法: python3 manager.py <blog_dir> <port>
  blog_dir: 博客数据目录 (含 content/config/themes)
  port:     管理面板端口 (默认 13134)
"""
import os
import re
import sys
import json
import time
import zipfile
import shutil
import http.server
import socketserver
import urllib.parse
from datetime import datetime
from pathlib import Path

BLOG_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/vol4/@appdata/hugo-blog/blog")
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 13134
CONTENT_DIR = BLOG_DIR / "content"
POST_DIR = CONTENT_DIR / "post"
THEMES_DIR = BLOG_DIR / "themes"
CONFIG_DIR = BLOG_DIR / "config" / "_default"
CONFIG_FILE = CONFIG_DIR / "config.toml"

# 生成安全的 slug (文件名)
def slugify(title):
    s = title.strip().lower()
    # 中文保留，特殊字符转连字符
    s = re.sub(r"[^\w\u4e00-\u9fff]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "post"


def list_posts():
    """列出 content/post 下的所有文章 (含 front matter 的 title/date)"""
    posts = []
    if POST_DIR.exists():
        for f in sorted(POST_DIR.glob("*.md"), reverse=True):
            title = f.stem.replace("-", " ").title()
            date = ""
            raw = ""
            try:
                raw = f.read_text(encoding="utf-8", errors="ignore")
                m = re.match(r"^---\n(.*?)\n---\n", raw, re.S)
                if m:
                    fm = m.group(1)
                    t = re.search(r"title:\s*[\"']?([^\"'\n]+)", fm)
                    d = re.search(r"date:\s*([^\n]+)", fm)
                    if t: title = t.group(1).strip()
                    if d: date = d.group(1).strip()
            except OSError:
                pass
            posts.append({
                "filename": f.name,
                "title": title,
                "date": date,
                "size": len(raw),
            })
    return posts


def create_post(title, content, tags=""):
    """新建文章，写入 content/post/<slug>.md"""
    if not title.strip():
        return None, "标题不能为空"
    slug = slugify(title)
    filename = f"{datetime.now().strftime('%Y%m%d')}-{slug}.md"
    # 避免覆盖
    path = POST_DIR / filename
    n = 1
    while path.exists():
        path = POST_DIR / f"{datetime.now().strftime('%Y%m%d')}-{slug}-{n}.md"
        n += 1
    tags_list = [t.strip() for t in tags.split(",") if t.strip()]
    tags_yaml = ""
    if tags_list:
        tags_yaml = "tags:\n" + "".join(f'  - "{t}"\n' for t in tags_list)
    fm = (
        "---\n"
        f'title: "{title}"\n'
        f'date: {datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00")}\n'
        f"{tags_yaml}"
        "---\n\n"
        f"{content}\n"
    )
    POST_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(fm, encoding="utf-8")
    return str(path.relative_to(BLOG_DIR)), None


# ---------- 主题管理 ----------

def current_theme():
    """从 config.toml 读当前主题"""
    try:
        txt = CONFIG_FILE.read_text(encoding="utf-8")
        m = re.search(r'^\s*theme\s*=\s*["\']([^"\']+)["\']', txt, re.M)
        if m:
            return m.group(1).strip()
    except OSError:
        pass
    return ""


def list_themes():
    """列出 themes/ 下的主题目录"""
    themes = []
    if THEMES_DIR.exists():
        for d in sorted(THEMES_DIR.iterdir()):
            if d.is_dir() and not d.name.startswith("."):
                # 主题需含 theme.toml 或 layouts
                is_theme = (d / "theme.toml").exists() or (d / "layouts").exists()
                themes.append({
                    "name": d.name,
                    "valid": is_theme,
                })
    return themes


def switch_theme(name):
    """切换主题 (改 config.toml 的 theme 字段)"""
    if not name or name.startswith(".") or "/" in name:
        return False, "主题名无效"
    target = THEMES_DIR / name
    if not target.is_dir() or (not (target / "theme.toml").exists() and not (target / "layouts").exists()):
        return False, "主题不存在或无效"
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        txt = CONFIG_FILE.read_text(encoding="utf-8") if CONFIG_FILE.exists() else ""
        if re.search(r'^\s*theme\s*=', txt, re.M):
            txt = re.sub(r'^\s*theme\s*=\s*.*$', f'theme = "{name}"', txt, count=1, flags=re.M)
        else:
            # 追加到 config.toml
            txt = txt.rstrip() + f'\ntheme = "{name}"\n'
        CONFIG_FILE.write_text(txt, encoding="utf-8")
        return True, None
    except OSError as e:
        return False, str(e)


def upload_theme(zip_data, filename):
    """上传主题 zip 包并解压到 themes/"""
    if not zip_data:
        return False, "空文件"
    try:
        import io
        with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
            # 安全检查: 拒绝路径穿越
            names = zf.namelist()
            for n in names:
                if n.startswith(("/", "..")) or ".." in n.split("/"):
                    return False, "非法路径"
            # 目标目录
            dest = THEMES_DIR
            dest.mkdir(parents=True, exist_ok=True)
            # 判断 zip 根是否含主题名目录
            root_parts = names[0].split("/") if names else [""]
            # 解压，若根是单个目录则取其名
            tmp = dest / ".tmp_upload"
            if tmp.exists():
                shutil.rmtree(tmp)
            tmp.mkdir(parents=True, exist_ok=True)
            zf.extractall(tmp)
            # 找到解压后的主题目录
            entries = [p for p in tmp.iterdir()]
            if len(entries) == 1 and entries[0].is_dir():
                theme_dir = entries[0]
                # 移入 themes/ 下
                target = dest / theme_dir.name
                if target.exists():
                    shutil.rmtree(target)
                shutil.move(str(theme_dir), str(target))
                shutil.rmtree(tmp)
                return True, theme_dir.name
            else:
                shutil.rmtree(tmp)
                return False, "zip 根目录应包含一个主题目录"
    except zipfile.BadZipFile:
        return False, "无效的 zip 文件"
    except Exception as e:
        return False, str(e)


class Handler(http.server.BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def log_message(self, format, *args):
        sys.stderr.write(f"[{datetime.now().strftime('%H:%M:%S')}] {self.address_string()} {format % args}\n")

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/":
            self._send(200, INDEX_HTML, "text/html; charset=utf-8")
        elif path == "/api/posts":
            self._send(200, json.dumps({"posts": list_posts()}))
        elif path == "/api/themes":
            self._send(200, json.dumps({
                "themes": list_themes(),
                "current": current_theme(),
            }))
        elif path == "/api/info":
            self._send(200, json.dumps({
                "blog_dir": str(BLOG_DIR),
                "posts": len(list_posts()),
            }))
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/new":
            try:
                data = self._read_json()
                rel_path, err = create_post(
                    data.get("title", ""),
                    data.get("content", ""),
                    data.get("tags", ""),
                )
                if err:
                    self._send(400, json.dumps({"error": err}))
                else:
                    self._send(200, json.dumps({"ok": True, "path": rel_path}))
            except Exception as e:
                self._send(500, json.dumps({"error": str(e)}))
        elif path == "/api/theme/switch":
            try:
                data = self._read_json()
                ok, err = switch_theme(data.get("theme", ""))
                if ok:
                    self._send(200, json.dumps({"ok": True}))
                else:
                    self._send(400, json.dumps({"error": err}))
            except Exception as e:
                self._send(500, json.dumps({"error": str(e)}))
        elif path == "/api/theme/upload":
            # 处理 multipart/form-data 文件上传 (手写解析, 零依赖)
            try:
                ctype = self.headers.get("Content-Type", "")
                if "multipart/form-data" not in ctype:
                    self._send(400, json.dumps({"error": "需要 multipart/form-data"}))
                    return
                boundary = ctype.split("boundary=")[-1].strip().strip('"')
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                # 拆分 multipart 各 part
                parts = body.split(("--" + boundary).encode())
                file_data = None
                for part in parts:
                    part = part.strip()
                    if not part or part == b"--":
                        continue
                    # part: headers\r\n\r\ncontent
                    if b"\r\n\r\n" in part:
                        header, content = part.split(b"\r\n\r\n", 1)
                        # 移除结尾的 \r\n
                        if content.endswith(b"\r\n"):
                            content = content[:-2]
                        if b'name="file"' in header:
                            file_data = content
                if not file_data:
                    self._send(400, json.dumps({"error": "未找到文件字段"}))
                    return
                ok, result = upload_theme(file_data, "theme.zip")
                if ok:
                    self._send(200, json.dumps({"ok": True, "theme": result}))
                else:
                    self._send(400, json.dumps({"error": result}))
            except Exception as e:
                self._send(500, json.dumps({"error": str(e)}))
        else:
            self._send(404, json.dumps({"error": "not found"}))


INDEX_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Hugo Blog 管理</title>
<style>
:root{--bg:#0f1420;--card:#1a2130;--card2:#202a3d;--text:#e8edf5;--muted:#8a97ab;--brand:#f09400;--accent:#38bdf8;--border:rgba(255,255,255,.08)}
[data-theme="light"]{--bg:#f5f6fa;--card:#fff;--card2:#eef1f6;--text:#1a2130;--muted:#6b7686;--brand:#e08100;--accent:#0284c7;--border:rgba(0,0,0,.08)}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;min-height:100vh}
.layout{display:flex;min-height:100vh}
.sidebar{width:200px;background:var(--card);border-right:1px solid var(--border);padding:16px 10px;flex-shrink:0}
.sidebar .brand{font-size:15px;font-weight:700;padding:4px 12px 14px;border-bottom:1px solid var(--border);margin-bottom:10px;display:flex;align-items:center;gap:8px}
.nav-item{display:flex;align-items:center;gap:8px;padding:10px 12px;border-radius:8px;cursor:pointer;font-size:13px;color:var(--muted);margin-bottom:2px}
.nav-item.active{background:rgba(56,189,248,.12);color:var(--accent);font-weight:600}
.main{flex:1;padding:16px;min-width:0}
.topbar{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px}
.topbar h1{font-size:20px}
.btn{padding:8px 14px;border:none;border-radius:8px;background:var(--brand);color:#fff;font-size:13px;font-weight:600;cursor:pointer}
.btn.secondary{background:var(--card2);color:var(--text)}
.panel{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:18px;margin-bottom:16px}
.panel h2{font-size:14px;margin-bottom:12px}
label{display:block;font-size:12px;color:var(--muted);margin:10px 0 4px}
input,textarea{width:100%;padding:9px 12px;border:1px solid var(--border);border-radius:8px;background:var(--card2);color:var(--text);font-size:13px;font-family:inherit}
textarea{min-height:120px;resize:vertical}
.msg{font-size:13px;margin-top:10px;color:var(--accent)}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--border)}
th{color:var(--muted);font-weight:500;font-size:12px}
.hint{font-size:12px;color:var(--muted);margin-top:8px;line-height:1.6}
</style>
</head>
<body data-theme="light">
<div class="layout">
  <div class="sidebar">
    <div class="brand">📝 Hugo Blog</div>
    <div class="nav-item active" onclick="location='/'">✍️ 写文章</div>
    <div class="nav-item" onclick="location='/'">📄 文章列表</div>
  </div>
  <div class="main">
    <div class="topbar">
      <h1>Hugo Blog 管理</h1>
      <div style="display:flex;gap:8px">
        <a class="btn secondary" href="http://" onclick="location='http://'+location.hostname+':13133/';return false" target="_blank" style="text-decoration:none">查看博客</a>
      </div>
    </div>
    <div class="panel">
      <h2>✍️ 新建文章</h2>
      <label>标题 *</label><input id="title" placeholder="文章标题">
      <label>标签 (逗号分隔)</label><input id="tags" placeholder="hugo, fnos">
      <label>内容 (Markdown)</label><textarea id="content" placeholder="# 标题&#10;正文..."></textarea>
      <div class="msg" id="msg"></div>
      <button class="btn" onclick="createPost()" style="margin-top:14px">保存并发布</button>
      <div class="hint">保存后 Hugo 会自动重新渲染，稍等片刻刷新博客即可看到。</div>
    </div>
    <div class="panel">
      <h2>📄 文章列表</h2>
      <table id="postsTable">
        <thead><tr><th>标题</th><th>日期</th><th>文件名</th></tr></thead>
        <tbody></tbody>
      </table>
    </div>
    <div class="panel">
      <h2>🎨 主题管理 <span id="curTheme" style="font-size:12px;color:var(--muted);font-weight:400"></span></h2>
      <table id="themesTable">
        <thead><tr><th>主题</th><th>状态</th><th>操作</th></tr></thead>
        <tbody></tbody>
      </table>
      <div class="msg" id="themeMsg"></div>
      <label>上传主题 (zip 包)</label>
      <input type="file" id="themeFile" accept=".zip">
      <button class="btn" onclick="uploadTheme()" style="margin-top:10px">上传主题</button>
      <div class="hint">上传的主题 zip 需包含一个主题目录（含 theme.toml 或 layouts）。</div>
    </div>
  </div>
</div>
<script>
async function loadPosts(){
  const r = await fetch('/api/posts');
  const d = await r.json();
  const tbody = document.querySelector('#postsTable tbody');
  tbody.innerHTML = (d.posts||[]).map(p=>
    `<tr><td>${escapeHtml(p.title)}</td><td>${p.date||'-'}</td><td>${p.filename}</td></tr>`
  ).join('') || '<tr><td colspan="3">暂无文章</td></tr>';
}
async function createPost(){
  const msg = document.getElementById('msg');
  msg.textContent = '保存中…';
  const r = await fetch('/api/new', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({
      title: document.getElementById('title').value,
      tags: document.getElementById('tags').value,
      content: document.getElementById('content').value
    })
  });
  const d = await r.json();
  if(d.ok){
    msg.textContent = '✓ 已保存: ' + d.path + ' (Hugo 自动渲染中)';
    document.getElementById('title').value='';
    document.getElementById('tags').value='';
    document.getElementById('content').value='';
    loadPosts();
  } else {
    msg.textContent = '✗ ' + (d.error||'保存失败');
  }
}
function escapeHtml(s){return s.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
async function loadThemes(){
  const r = await fetch('/api/themes');
  const d = await r.json();
  document.getElementById('curTheme').textContent = d.current ? '· 当前: ' + d.current : '';
  const tbody = document.querySelector('#themesTable tbody');
  tbody.innerHTML = (d.themes||[]).map(t=>{
    const active = t.name === d.current;
    return `<tr>
      <td>${escapeHtml(t.name)}</td>
      <td>${active ? '<span style="color:var(--accent)">✓ 使用中</span>' : (t.valid ? '可用' : '<span style="color:var(--brand)">无效</span>')}</td>
      <td>${t.valid && !active ? '<button class="btn secondary" onclick="switchTheme(\''+escapeHtml(t.name)+'\')">使用</button>' : ''}</td>
    </tr>`;
  }).join('') || '<tr><td colspan="3">暂无主题，请上传</td></tr>';
}
async function switchTheme(name){
  const msg = document.getElementById('themeMsg');
  msg.textContent = '切换中…';
  const r = await fetch('/api/theme/switch', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({theme: name})
  });
  const d = await r.json();
  if(d.ok){
    msg.textContent = '✓ 已切换到主题: ' + name + ' (Hugo 自动重新渲染)';
    loadThemes();
  } else {
    msg.textContent = '✗ ' + (d.error||'切换失败');
  }
}
async function uploadTheme(){
  const msg = document.getElementById('themeMsg');
  const file = document.getElementById('themeFile').files[0];
  if(!file){ msg.textContent = '请选择 zip 文件'; return; }
  msg.textContent = '上传中…';
  const fd = new FormData();
  fd.append('file', file);
  const r = await fetch('/api/theme/upload', {method:'POST', body: fd});
  const d = await r.json();
  if(d.ok){
    msg.textContent = '✓ 主题已上传: ' + d.theme + '，可在上方列表切换到该主题';
    document.getElementById('themeFile').value='';
    loadThemes();
  } else {
    msg.textContent = '✗ ' + (d.error||'上传失败');
  }
}
loadPosts();
loadThemes();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    os.makedirs(POST_DIR, exist_ok=True)
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    httpd = socketserver.ThreadingTCPServer(("0.0.0.0", PORT), Handler)
    print(f"Hugo Blog manager on port {PORT}, blog_dir={BLOG_DIR}")
    httpd.serve_forever()
