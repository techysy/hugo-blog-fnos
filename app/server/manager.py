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
import secrets
import zipfile
import shutil
import http.server
import socketserver
import urllib.parse
from datetime import datetime
from pathlib import Path

BLOG_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/vol4/@appdata/hugo-blog/blog")
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 13134
# 应用版本 (与 manifest 保持一致, 用于品牌区/仪表板显示)
APP_VERSION = "0.1.4.11"
CONTENT_DIR = BLOG_DIR / "content"
POST_DIR = CONTENT_DIR / "post"
THEMES_DIR = BLOG_DIR / "themes"
CONFIG_DIR = BLOG_DIR / "config" / "_default"
CONFIG_FILE = CONFIG_DIR / "config.toml"
DATA_DIR = BLOG_DIR.parent  # 数据目录 (@appdata/hugo-blog)
TOKEN_FILE = DATA_DIR / "api_token"
HUGO_BIN = os.environ.get("HUGO_BIN", "/vol4/@appcenter/hugo-blog/server/hugo")
# cmd/main 启动脚本路径 (用于重建 hugo)
CMD_MAIN = os.environ.get("CMD_MAIN", "/var/apps/hugo-blog/cmd/main")
MODULE_CACHE = DATA_DIR / ".hugo_modules"
PROXY_FILE = DATA_DIR / "proxy_config"

# 系统预置主题 (打包自带, template/themes/ 下)
PRESET_THEMES = {"minimal"}

# ---------- 日志 (控制台) ----------
# 日志来源: 名称 -> 文件名 (在 DATA_DIR 下)
LOG_SOURCES = {
    "hugo": DATA_DIR / "hugo.log",
    "manager": DATA_DIR / "manager.log",
}
# 归档目录: 按日期归档的日志存这里
LOG_ARCHIVE_DIR = DATA_DIR / "logs"
LOG_EXT = ".log"


def _archive_date():
    """当前日期 YYYYMMDD 和展示用 YYYY-MM-DD."""
    now = datetime.now()
    return now.strftime("%Y%m%d"), now.strftime("%Y-%m-%d")


def archive_logs():
    """启动时归档: 把非当天的日志文件滚到 LOG_ARCHIVE_DIR/hugo.log.YYYYMMDD.

    规则: 当前日志文件若修改日期不是今天, 则归档 (移动) 到归档目录,
    并清空当前文件, 让新日志只记录当天. 避免单文件无限增长.
    """
    today_compact, _ = _archive_date()
    for name, path in LOG_SOURCES.items():
        try:
            if not path.exists():
                continue
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
            mday = mtime.strftime("%Y%m%d")
            # 只有修改日期不是今天才归档 (保留当天日志在工作文件, 供 tail)
            if mday == today_compact:
                continue
            LOG_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
            dest = LOG_ARCHIVE_DIR / f"{name}.log.{mday}"
            # 追加合并 (避免覆盖同名归档)
            content = b""
            try:
                content = path.read_bytes()
            except OSError:
                content = b""
            if dest.exists():
                with dest.open("ab") as f:
                    f.write(content)
            else:
                dest.write_bytes(content)
            # 清空当前日志文件 (保留当天从零开始)
            path.write_bytes(b"")
        except OSError:
            continue


def list_log_dates(name):
    """返回某日志来源可用的日期列表 (含归档 + 当前). 倒序."""
    dates = []
    base = LOG_SOURCES.get(name)
    if not base:
        return dates
    # 归档文件: logs/hugo.log.YYYYMMDD
    try:
        if LOG_ARCHIVE_DIR.exists():
            for f in LOG_ARCHIVE_DIR.glob(f"{name}.log.[0-9]*"):
                m = re.search(rf"{name}\.log\.(\d{{8}})$", f.name)
                if m:
                    d = m.group(1)
                    dates.append((d, _fmt_date(d)))
    except OSError:
        pass
    # 当前工作文件 (仅当非空)
    try:
        if base.exists() and base.stat().st_size > 0:
            dates.append(_archive_date())
    except OSError:
        pass
    # 去重 + 按日期倒序
    seen = set()
    result = []
    for compact, disp in sorted(dates, key=lambda x: x[0], reverse=True):
        if compact not in seen:
            seen.add(compact)
            result.append({"date": compact, "display": disp})
    return result


def _fmt_date(compact):
    """YYYYMMDD -> YYYY-MM-DD."""
    if len(compact) == 8:
        return f"{compact[:4]}-{compact[4:6]}-{compact[6:]}"
    return compact


def read_logs(name, date=None, tail=500):
    """读取日志内容. name: hugo/manager. date: YYYYMMDD 或 None(当前). tail: 返回最后 N 行.

    返回 dict: {source, date, display, total, content}
    """
    base = LOG_SOURCES.get(name)
    if not base:
        return None
    target = base
    display = "当前"
    if date:
        compact = date.replace("-", "")
        target = LOG_ARCHIVE_DIR / f"{name}.log.{compact}"
        display = _fmt_date(compact)
        if not target.exists():
            return {"source": name, "date": date, "display": display, "total": 0, "content": ""}
    try:
        if not target.exists():
            return {"source": name, "date": date, "display": display, "total": 0, "content": ""}
        raw = target.read_text(encoding="utf-8", errors="replace")
        lines = raw.splitlines()
        if tail and tail > 0 and len(lines) > tail:
            lines = lines[-tail:]
        content = "\n".join(lines)
        return {
            "source": name,
            "date": date or "current",
            "display": display,
            "total": len(raw.splitlines()),
            "content": content,
        }
    except OSError as e:
        return {"source": name, "date": date, "display": display, "total": 0,
                "content": f"读取日志失败: {e}"}


def get_service_status():
    """返回服务状态: hugo/manager 进程、端口、版本、数据统计."""
    blog_port = 13133  # hugo 博客端口 (固定)
    status = {
        "hugo": {"running": False, "pid": None},
        "manager": {"running": False, "pid": None},
        "ports": {"blog": blog_port, "admin": PORT},
    }
    # 端口实际监听状态
    status["ports"]["blog"] = _port_open(blog_port)
    status["ports"]["admin"] = _port_open(PORT)
    # hugo / manager 进程 (读 pid 文件 + 端口交叉判断)
    for name, pidfile in (("hugo", DATA_DIR / "hugo.pid"), ("manager", DATA_DIR / "manager.pid")):
        try:
            if pidfile.exists():
                pid = int(pidfile.read_text().strip() or 0)
                if pid and _pid_alive(pid):
                    status[name]["running"] = True
                    status[name]["pid"] = pid
        except (OSError, ValueError):
            pass
    # 兜底: hugo 进程以端口为准
    if not status["hugo"]["running"] and status["ports"]["blog"]:
        status["hugo"]["running"] = True
    if not status["manager"]["running"] and status["ports"]["admin"]:
        status["manager"]["running"] = True
    # hugo 版本
    try:
        import subprocess
        r = subprocess.run([HUGO_BIN, "version"], capture_output=True, text=True, timeout=5)
        status["hugo_version"] = r.stdout.strip().split("\n")[0] if r.stdout else HUGO_BIN
    except Exception:
        status["hugo_version"] = HUGO_BIN
    # 数据统计
    try:
        status["posts"] = len(list_posts())
        status["themes"] = len(list_themes())
        status["current_theme"] = current_theme()
    except Exception:
        pass
    return status


def _port_open(port):
    """检查端口是否有进程监听 (读 /proc/net/tcp)."""
    try:
        h = f":{port:04X}"
        for fn in ("/proc/net/tcp", "/proc/net/tcp6"):
            if not os.path.exists(fn):
                continue
            for line in open(fn, errors="ignore"):
                if h in line and "0A" in line.split()[3]:
                    return True
    except Exception:
        pass
    return False


def _pid_alive(pid):
    """检查进程是否存活."""
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def build_api_doc():
    """生成 API 使用指南 Markdown 文档 (供设置页 API 标签展示/复制)."""
    base = "http://<NAS-IP>:13134"
    lines = [
        "# Hugo Blog 管理面板 API 指南",
        "",
        "> 管理面板端口 **13134**。除 `/api/bootstrap` 外，所有接口需 `Authorization: Bearer <token>`。",
        "> **解析 JSON 用 python3**（fnOS 及多数系统自带），无需 jq；若已装 jq 可把 `python3 -m json.tool` 换成 `jq`。",
        "",
        "## 1. 一键测试脚本 (推荐, 复制即用)",
        "保存为 `test-api.sh`，`chmod +x test-api.sh` 后运行：",
        "```bash",
        "#!/usr/bin/env bash",
        "# Hugo Blog API 一键测试 (curl + python3, 无需 jq)",
        "set -u",
        'BASE="' + base + '"',
        'TOKEN=$(curl -s "$BASE/api/bootstrap" | python3 -c "import sys,json;print(json.load(sys.stdin).get(\'api_token\',\'\'))")',
        'if [ -z "$TOKEN" ]; then echo "获取 token 失败"; exit 1; fi',
        'AUTH="Authorization: Bearer $TOKEN"',
        'echo "Token: ${TOKEN:0:8}..."',
        'echo; echo "== 服务状态 /api/info =="',
        'curl -s -H "$AUTH" "$BASE/api/info" | python3 -m json.tool',
        'echo; echo "== 文章数 /api/posts =="',
        'curl -s -H "$AUTH" "$BASE/api/posts" | python3 -c "import sys,json;d=json.load(sys.stdin);print(\'文章数:\',len(d[\'posts\']))"',
        'echo; echo "== 当前主题 /api/themes =="',
        'curl -s -H "$AUTH" "$BASE/api/themes" | python3 -c "import sys,json;d=json.load(sys.stdin);print(\'当前:\',d[\'current\'])"',
        'echo; echo "== 最近日志 /api/logs =="',
        'curl -s -H "$AUTH" "$BASE/api/logs?source=hugo&tail=20" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d[\'content\'])"',
        'echo; echo "== 测试完成 =="',
        "```",
        "",
        "## 2. 各接口单独调用",
        "",
        "### 2.1 获取 Token",
        "```bash",
        'TOKEN=$(curl -s ' + base + '/api/bootstrap | python3 -c "import sys,json;print(json.load(sys.stdin).get(\'api_token\',\'\'))")',
        'AUTH="Authorization: Bearer $TOKEN"',
        "```",
        "",
        "### 2.2 服务状态",
        "```bash",
        'curl -s -H "$AUTH" ' + base + '/api/info | python3 -m json.tool',
        "```",
        "",
        "### 2.3 文章",
        "```bash",
        'curl -s -H "$AUTH" ' + base + '/api/posts | python3 -c "import sys,json;d=json.load(sys.stdin);print(\'文章数:\',len(d[\'posts\']))"',
        "# 新建文章 (JSON 用文件, 见下方 post.json 示例)",
        'curl -s -X POST ' + base + '/api/new -H "$AUTH" -H "Content-Type: application/json" -d @post.json | python3 -m json.tool',
        "```",
        "",
        "### 2.4 主题",
        "```bash",
        'curl -s -H "$AUTH" ' + base + '/api/themes | python3 -m json.tool',
        "# 切换主题 (JSON 用文件, 见下方 theme.json 示例)",
        'curl -s -X POST ' + base + '/api/theme/switch -H "$AUTH" -H "Content-Type: application/json" -d @theme.json | python3 -m json.tool',
        "# 在线安装: git 仓库 / Hugo Module",
        'curl -s -X POST ' + base + '/api/theme/git -H "$AUTH" -H "Content-Type: application/json" -d @git.json | python3 -m json.tool',
        'curl -s -X POST ' + base + '/api/theme/module -H "$AUTH" -H "Content-Type: application/json" -d @module.json | python3 -m json.tool',
        "# 删除主题",
        'curl -s -X POST ' + base + '/api/theme/delete -H "$AUTH" -H "Content-Type: application/json" -d @delete.json | python3 -m json.tool',
        "```",
        "",
        "### 2.5 日志 (控制台)",
        "```bash",
        'curl -s -H "$AUTH" "' + base + '/api/logs/list?source=hugo" | python3 -m json.tool',
        'curl -s -H "$AUTH" "' + base + '/api/logs?source=hugo&tail=200" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d[\'content\'])"',
        'curl -s -H "$AUTH" -o hugo.log "' + base + '/api/logs/download?source=hugo"',
        "```",
        "",
        "### 2.6 代理设置",
        "```bash",
        'curl -s -H "$AUTH" ' + base + '/api/proxy | python3 -m json.tool',
        "# 设置代理 (HTTP/HTTPS 共用同一地址)",
        'curl -s -X POST ' + base + '/api/proxy -H "$AUTH" -H "Content-Type: application/json" -d @proxy.json | python3 -m json.tool',
        "```",
        "",
        "## JSON 参数文件示例",
        "### post.json",
        "```json",
        "{",
        '  "title": "新文章",',
        '  "tags": "hugo, fnos",',
        '  "content": "# 标题"',
        "}",
        "```",
        "### theme.json",
        "```json",
        "{",
        '  "theme": "minimal"',
        "}",
        "```",
        "### git.json",
        "```json",
        "{",
        '  "url": "https://github.com/user/theme.git"',
        "}",
        "```",
        "### module.json",
        "```json",
        "{",
        '  "module": "github.com/bep/docuapi"',
        "}",
        "```",
        "### delete.json",
        "```json",
        "{",
        '  "theme": "old-theme"',
        "}",
        "```",
        "### proxy.json",
        "```json",
        "{",
        '  "http": "http://192.168.31.31:7890",',
        '  "https": "http://192.168.31.31:7890",',
        '  "no_proxy": "localhost,127.0.0.1"',
        "}",
        "```",
        "",
        "## 认证说明",
        "- token 存于数据目录 `api_token`，删除后重启应用会重新生成。",
        "- 未认证请求返回 `401 unauthorized`。",
    ]
    return "\n".join(lines)


def rebuild_site():
    """触发 hugo 重建 (调用 cmd/main rebuild, 仅重建 hugo 不动 manager).

    异步触发后台重建, 立即返回 (避免 hugo 首次构建超时). 前端稍后刷新确认.
    """
    try:
        import subprocess
        # 后台异步执行, 不阻塞接口; rebuild 会 pkill hugo + 重新 start
        p = subprocess.Popen(
            ["bash", str(CMD_MAIN), "rebuild"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return True, "重建已触发，正在后台执行…", ""
    except Exception as e:
        return False, "", str(e)


def get_proxy():
    """读取代理配置. 返回 {http, https, no_proxy}"""
    http = https = ""
    no_proxy = "localhost,127.0.0.1"
    try:
        if PROXY_FILE.exists():
            for line in PROXY_FILE.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("http="):
                    http = line.split("=", 1)[1].strip()
                elif line.startswith("https="):
                    https = line.split("=", 1)[1].strip()
                elif line.startswith("no_proxy="):
                    no_proxy = line.split("=", 1)[1].strip()
    except OSError:
        pass
    return {"http": http, "https": https, "no_proxy": no_proxy}


def set_proxy(http, https, no_proxy):
    """保存代理配置到 proxy_config 文件"""
    try:
        content = f"http={http}\nhttps={https}\nno_proxy={no_proxy}\n"
        PROXY_FILE.write_text(content, encoding="utf-8")
        return True, None
    except OSError as e:
        return False, str(e)


def get_or_create_token():
    """读取或生成 API token (存在数据目录 api_token 文件, 权限 600)"""
    try:
        if TOKEN_FILE.exists():
            tok = TOKEN_FILE.read_text(encoding="utf-8").strip()
            if tok:
                return tok
        tok = secrets.token_hex(16)
        TOKEN_FILE.write_text(tok, encoding="utf-8")
        try:
            os.chmod(TOKEN_FILE, 0o600)
        except OSError:
            pass
        return tok
    except OSError:
        return ""


API_TOKEN = get_or_create_token()


def recreate_token():
    """重新生成 API token (写入文件并更新内存, 立即生效, 无需重启)."""
    global API_TOKEN
    new = secrets.token_hex(16)
    try:
        TOKEN_FILE.write_text(new, encoding="utf-8")
        os.chmod(TOKEN_FILE, 0o600)
        API_TOKEN = new
        return new, None
    except OSError as e:
        return None, str(e)

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
    # 按 front matter 的 date 降序排列 (最新在前); 无 date 的排最后
    def _sort_key(p):
        d = p["date"].strip().strip("\"'")
        # 取日期时间部分 (YYYY-MM-DDTHH:MM:SS), 去掉时区偏移, 便于字符串比较
        base = d[:19] if d else ""
        return base
    posts.sort(key=_sort_key, reverse=True)
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
    """列出 themes/ 下的主题目录 + go.mod 的 module 主题"""
    themes = []
    if THEMES_DIR.exists():
        for d in sorted(THEMES_DIR.iterdir()):
            if d.is_dir() and not d.name.startswith("."):
                # 主题需含 theme.toml 或 layouts
                is_theme = (d / "theme.toml").exists() or (d / "layouts").exists()
                themes.append({
                    "name": d.name,
                    "valid": is_theme,
                    "preset": d.name in PRESET_THEMES,
                })
    # go.mod 里的 module 依赖 (含 "/" 的才是 module 主题路径; 跳过 indirect 工具依赖)
    go_mod = BLOG_DIR / "go.mod"
    if go_mod.exists():
        for line in go_mod.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            # 跳过 "require (" 括号行 / ")" / 空行
            if not line or line in ("require (", ")", "require"):
                continue
            # 跳过 // indirect 工具依赖 (非主题)
            if "// indirect" in line:
                continue
            # 去掉行尾其它注释
            if "//" in line:
                line = line.split("//", 1)[0].strip()
            if not line:
                continue
            parts = line.replace("require", "").strip().split()
            if not parts:
                continue
            mod = parts[0]
            # 真正的 module 主题路径需含 "/" 和 "."
            if "/" in mod and "." in mod:
                themes.append({"name": mod, "valid": True, "module": True})
    return themes


def _dart_sass_dir():
    """定位打包的 dart-sass 目录 (供 SCSS 主题构建用)."""
    for c in [str(BLOG_DIR.parent / "server" / "dart-sass"), "/vol4/@appcenter/hugo-blog/server/dart-sass"]:
        if os.path.isdir(c) and os.access(os.path.join(c, "sass"), os.X_OK):
            return c
    return None


def _theme_build_check():
    """用 hugo 一次性构建验证当前 config 的主题能否成功构建.

    构建到临时目录, 避免影响运行中 server 的 public. 返回 (ok, 错误信息).
    """
    import subprocess, tempfile
    dart = _dart_sass_dir()
    env = dict(os.environ)
    if dart:
        env["PATH"] = dart + os.pathsep + env.get("PATH", "")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run(
                [HUGO_BIN, "--source", str(BLOG_DIR), "--destination", tmp,
                 "--logLevel", "error", "--ignoreCache", "--quiet"],
                env=env, capture_output=True, text=True, timeout=90,
            )
            out = (r.stdout or "") + (r.stderr or "")
            if r.returncode != 0:
                return False, out.strip().splitlines()[-1] if out.strip() else "构建失败"
            if "ERROR" in out:
                return False, out.strip().splitlines()[-1] if out.strip() else "构建失败"
            return True, None
    except Exception as e:
        return False, str(e)


def switch_theme(name):
    """切换主题 (改 config.toml 的 theme 字段). 支持传统主题名 或 module 路径.

    切换后自动验证能否成功构建; 若失败则回滚到原主题, 避免博客被不兼容主题搞挂.
    """
    if not name or name.startswith("."):
        return False, "主题名无效"
    is_module = "/" in name
    if not is_module:
        target = THEMES_DIR / name
        if not target.is_dir() or (not (target / "theme.toml").exists() and not (target / "layouts").exists()):
            return False, "主题不存在或无效"
    old_theme = current_theme()
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        txt = CONFIG_FILE.read_text(encoding="utf-8") if CONFIG_FILE.exists() else ""
        if re.search(r'^\s*theme\s*=', txt, re.M):
            txt = re.sub(r'^\s*theme\s*=\s*.*$', f'theme = "{name}"', txt, count=1, flags=re.M)
        else:
            # 追加到 config.toml
            txt = txt.rstrip() + f'\ntheme = "{name}"\n'
        CONFIG_FILE.write_text(txt, encoding="utf-8")
    except OSError as e:
        return False, str(e)

    # 验证新主题能否构建; 失败则回滚
    ok, err = _theme_build_check()
    if ok:
        return True, None
    # 回滚到原主题
    try:
        txt = CONFIG_FILE.read_text(encoding="utf-8") if CONFIG_FILE.exists() else ""
        if re.search(r'^\s*theme\s*=', txt, re.M):
            txt = re.sub(r'^\s*theme\s*=\s*.*$', f'theme = "{old_theme}"', txt, count=1, flags=re.M)
        CONFIG_FILE.write_text(txt, encoding="utf-8")
    except OSError:
        pass
    return False, f"主题「{name}」无法构建，已回滚到「{old_theme}」: {err or '构建失败'}"


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


def delete_theme(name):
    """删除主题. 支持传统主题 (themes/<name>) 和 module 主题 (从 go.mod 移除)."""
    name = name.strip()
    if not name or name.startswith("."):
        return False, "主题名无效"
    # 不能删除当前使用中的主题
    if name == current_theme():
        return False, "不能删除当前正在使用的主题"
    # 预置主题禁止删除
    if name in PRESET_THEMES:
        return False, "系统预置主题不能删除"
    # 路径穿越检查
    if ".." in name or "/" in name and not name.startswith("github.com/"):
        return False, "非法主题名"
    is_module = name.startswith("github.com/") or ("/" in name)
    if is_module:
        # 从 go.mod 移除
        go_mod = BLOG_DIR / "go.mod"
        if not go_mod.exists():
            return False, "无 go.mod"
        try:
            lines = [l for l in go_mod.read_text(encoding="utf-8").splitlines()
                     if name not in l]
            go_mod.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return True, None
        except OSError as e:
            return False, str(e)
    else:
        # 传统主题: 删除 themes/<name>
        target = THEMES_DIR / name
        if not target.is_dir():
            return False, "主题不存在"
        try:
            import shutil
            shutil.rmtree(target)
            return True, None
        except OSError as e:
            return False, str(e)


def install_git_theme(git_url):
    """从 git 仓库安装主题 (git clone 到 themes/). 自动检测依赖."""
    git_url = git_url.strip()
    if not git_url:
        return False, "git 路径为空"
    if not (git_url.startswith("http://") or git_url.startswith("https://") or git_url.startswith("git@")):
        return False, "仅支持 http/https/git@ 开头的 git 地址"
    import subprocess
    # 主题名: 从 URL 推断 (仓库名, 去掉 .git)
    name = git_url.rstrip("/").split("/")[-1]
    if name.endswith(".git"):
        name = name[:-4]
    name = re.sub(r"[^a-zA-Z0-9_-]", "-", name)
    if not name:
        return False, "无法从 URL 推断主题名"
    target = THEMES_DIR / name
    # 已存在检查: 避免 git clone 报 "destination path already exists"
    if target.exists():
        return False, f"主题「{name}」已存在，无需重复安装。可直接在列表切换到该主题，或先删除再重新安装。"
    try:
        THEMES_DIR.mkdir(parents=True, exist_ok=True)
        # 用 git clone (走代理配置)
        env = dict(os.environ)
        r = subprocess.run(
            ["git", "clone", "--depth", "1", git_url, str(target)],
            capture_output=True, text=True, env=env, timeout=120,
        )
        if r.returncode != 0:
            return False, r.stderr.strip()[-300:] or "git clone 失败"
        # 检测依赖
        deps = detect_theme_deps(name)
        return True, {"name": name, "deps": deps}
    except subprocess.TimeoutExpired:
        return False, "git clone 超时"
    except Exception as e:
        return False, str(e)


def detect_theme_deps(name):
    """检测主题依赖. 返回 ['module', 'sass'] 或 []"""
    t = THEMES_DIR / name
    deps = []
    # 1. module 依赖: go.mod 有 require (非空)
    go_mod = t / "go.mod"
    if go_mod.exists():
        txt = go_mod.read_text(encoding="utf-8")
        if "require" in txt and re.search(r"require\s*\(", txt):
            deps.append("module")
    # 2. Dart Sass: assets 里有 .scss
    assets = t / "assets"
    if assets.exists():
        scss = list(assets.rglob("*.scss")) + list(assets.rglob("*.sass"))
        if scss:
            deps.append("sass")
    return deps


def install_module_theme(module_path):
    """从 Hugo Module 安装主题 (hugo mod get). module_path 如 github.com/bep/docuapi."""
    module_path = module_path.strip()
    if not module_path:
        return False, "module 路径为空"
    # 安全检查
    if " " in module_path or "\n" in module_path:
        return False, "非法 module 路径"
    # go.mod
    go_mod = BLOG_DIR / "go.mod"
    if not go_mod.exists():
        go_mod.write_text("module github.com/techysy/hugo-blog\n\ngo 1.16\n", encoding="utf-8")
    # 配置 module 环境
    env = dict(os.environ)
    env["HUGO_MODULE_CACHE"] = str(MODULE_CACHE)
    env["GOPROXY"] = "https://goproxy.cn,direct"
    env["GOFLAGS"] = "-mod=mod"
    # 下载 module
    import subprocess
    try:
        r = subprocess.run(
            [HUGO_BIN, "mod", "get", module_path],
            cwd=str(BLOG_DIR), capture_output=True, text=True, env=env, timeout=120,
        )
        if r.returncode != 0:
            return False, r.stderr.strip()[-300:] or "hugo mod get 失败"
    except subprocess.TimeoutExpired:
        return False, "下载 module 超时"
    except Exception as e:
        return False, str(e)
    # 设置 theme
    return switch_theme(module_path)


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

    def _check_auth(self):
        """校验 Authorization: Bearer <token>. 返回 True 通过, False 已发送 401."""
        if not API_TOKEN:
            self._send(500, json.dumps({"error": "token 未初始化"}))
            return False
        auth = self.headers.get("Authorization", "")
        if auth == "Bearer " + API_TOKEN:
            return True
        self._send(401, json.dumps({"error": "unauthorized"}))
        return False

    def log_message(self, format, *args):
        sys.stderr.write(f"[{datetime.now().strftime('%H:%M:%S')}] {self.address_string()} {format % args}\n")

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/":
            self._send(200, INDEX_HTML, "text/html; charset=utf-8")
        elif path == "/api/bootstrap":
            # 免认证: 返回 API token (供 agent / 前端获取)
            self._send(200, json.dumps({
                "api_token": API_TOKEN,
                "blog_dir": str(BLOG_DIR),
                "version": APP_VERSION,
            }))
        elif path == "/api/posts":
            if not self._check_auth():
                return
            self._send(200, json.dumps({"posts": list_posts()}))
        elif path == "/api/themes":
            if not self._check_auth():
                return
            self._send(200, json.dumps({
                "themes": list_themes(),
                "current": current_theme(),
            }))
        elif path == "/api/info":
            if not self._check_auth():
                return
            self._send(200, json.dumps(get_service_status()))
        elif path == "/api/doc":
            # API 使用指南 Markdown 文档
            if not self._check_auth():
                return
            self._send(200, json.dumps({"doc": build_api_doc()}))
        elif path == "/api/proxy":
            if not self._check_auth():
                return
            self._send(200, json.dumps(get_proxy()))
        elif path == "/api/logs/list":
            if not self._check_auth():
                return
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            name = (q.get("source") or ["hugo"])[0]
            if name not in LOG_SOURCES:
                name = "hugo"
            self._send(200, json.dumps({
                "sources": list(LOG_SOURCES.keys()),
                "dates": list_log_dates(name),
                "current": _archive_date()[0],
            }))
        elif path == "/api/logs":
            if not self._check_auth():
                return
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            name = (q.get("source") or ["hugo"])[0]
            if name not in LOG_SOURCES:
                name = "hugo"
            date = (q.get("date") or [None])[0]
            tail = int((q.get("tail") or ["500"])[0])
            result = read_logs(name, date, tail)
            if result is None:
                self._send(404, json.dumps({"error": "未知日志来源"}))
            else:
                self._send(200, json.dumps(result))
        elif path == "/api/logs/download":
            if not self._check_auth():
                return
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            name = (q.get("source") or ["hugo"])[0]
            if name not in LOG_SOURCES:
                name = "hugo"
            date = (q.get("date") or [None])[0]
            result = read_logs(name, date, 0)
            if result is None:
                self._send(404, json.dumps({"error": "未知日志来源"}))
                return
            fname = f"{name}.log"
            if date:
                fname = f"{name}.log.{date.replace('-', '')}"
            body = result.get("content", "").encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="{fname}"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if not self._check_auth():
            return
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
        elif path == "/api/rebuild":
            # 触发 hugo 重建 (手动「重建」按钮)
            ok, msg, err = rebuild_site()
            if ok:
                self._send(200, json.dumps({"ok": True, "msg": msg}))
            else:
                self._send(500, json.dumps({"error": err or msg or "重建失败"}))
        elif path == "/api/token/recreate":
            # 重新生成 API token (手动「创建 token」按钮, 需认证)
            new, err = recreate_token()
            if new:
                self._send(200, json.dumps({"ok": True, "token": new}))
            else:
                self._send(500, json.dumps({"error": err or "创建 token 失败"}))
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
        elif path == "/api/theme/module":
            # 从 Hugo Module 安装主题 (hugo mod get)
            try:
                data = self._read_json()
                ok, result = install_module_theme(data.get("module", ""))
                if ok:
                    self._send(200, json.dumps({"ok": True, "theme": result}))
                else:
                    self._send(400, json.dumps({"error": result}))
            except Exception as e:
                self._send(500, json.dumps({"error": str(e)}))
        elif path == "/api/theme/git":
            # 从 git 仓库安装主题 (git clone + 依赖检测)
            try:
                data = self._read_json()
                ok, result = install_git_theme(data.get("url", ""))
                if ok:
                    self._send(200, json.dumps({"ok": True, "theme": result}))
                else:
                    self._send(400, json.dumps({"error": result}))
            except Exception as e:
                self._send(500, json.dumps({"error": str(e)}))
        elif path == "/api/theme/delete":
            # 删除主题
            try:
                data = self._read_json()
                ok, err = delete_theme(data.get("theme", ""))
                if ok:
                    self._send(200, json.dumps({"ok": True}))
                else:
                    self._send(400, json.dumps({"error": err}))
            except Exception as e:
                self._send(500, json.dumps({"error": str(e)}))
        elif path == "/api/proxy":
            # 设置代理配置
            try:
                data = self._read_json()
                ok, err = set_proxy(
                    data.get("http", "").strip(),
                    data.get("https", "").strip(),
                    data.get("no_proxy", "localhost,127.0.0.1").strip(),
                )
                if ok:
                    self._send(200, json.dumps({"ok": True}))
                else:
                    self._send(400, json.dumps({"error": err}))
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
.sidebar .brand{font-size:16px;font-weight:700;padding:4px 12px 14px;border-bottom:1px solid var(--border);margin-bottom:10px;display:flex;flex-direction:column;align-items:flex-start}
.sidebar .brand-ver{font-size:12px;font-weight:400;color:var(--muted);line-height:1;margin-top:4px}
.nav-item{display:flex;align-items:center;gap:8px;padding:11px 12px;border-radius:8px;cursor:pointer;font-size:14px;color:var(--muted);margin-bottom:2px}
.nav-item.active{background:rgba(56,189,248,.12);color:var(--accent);font-weight:600}
.topbar{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;gap:8px}
.topbar h1{font-size:20px}
/* 汉堡菜单 (移动端) */
.hamburger{display:none;background:none;border:none;font-size:20px;color:var(--text);cursor:pointer;padding:4px 6px}
.main{flex:1;padding:16px;min-width:0;display:flex;flex-direction:column;height:100vh;overflow:hidden;box-sizing:border-box}
.tab-panel{display:none}
.tab-panel.active{display:block}
/* 其他 tab 内容超高时内部滚动 */
#tab-write.active,#tab-posts.active,#tab-settings.active{overflow-y:auto}
/* 仪表盘: 填满视口(不滚动), 日志控制台卡片收窄居中 */
#tab-dash.active{display:flex;flex-direction:column;flex:1;min-height:0;overflow:hidden}
#tab-dash>.panel{flex-shrink:0}
/* 📜 日志控制台卡片: 默认宽度不占满, 收窄居中 */
#tab-dash>.panel:last-child{flex:1;display:flex;flex-direction:column;margin-bottom:0;min-height:0;max-width:1100px;width:100%;margin-left:auto;margin-right:auto}
#tab-dash .log-view{flex:1;min-height:0;max-height:none;overflow-y:auto}
/* 日志控制台 控件区 + 显示区 (响应式) */
.log-controls{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:10px}
.log-controls select,.log-controls button{flex:0 0 auto}
.log-view{background:rgba(0,0,0,0.82);color:#d4d4d4;border:1px solid rgba(255,255,255,.12);border-radius:8px;padding:12px;font-size:12px;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;white-space:pre-wrap;word-break:break-all;max-height:70vh;overflow-y:auto;line-height:1.5}
@media (max-width:768px){
  .sidebar{position:fixed;left:-220px;top:0;bottom:0;z-index:1000;transition:left .25s ease;height:100vh;overflow-y:auto}
  .sidebar.open{left:0}
  .hamburger{display:inline-block}
  .sidebar-overlay.show{display:block}
  /* 日志控制台移动端适配 */
  .log-controls select{flex:1 1 auto;min-width:0}
  .log-controls button{flex:1 1 auto}
  .log-view{max-height:calc(100vh - 240px);font-size:11px;padding:10px}
}
/* 分页控件 */
.pager{display:flex;align-items:center;gap:8px;margin-top:12px;justify-content:center}
.pager button{padding:6px 12px;border:1px solid var(--border);border-radius:6px;background:var(--card2);color:var(--text);cursor:pointer;font-size:12px}
.pager button:disabled{opacity:.4;cursor:not-allowed}
.pager .pager-info{font-size:12px;color:var(--muted)}
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
/* 子标签页 (设置内: 仪表板/代理) */
.subtabs{display:flex;gap:6px;margin-bottom:14px;flex-wrap:wrap}
.subtab{padding:7px 16px;border:1px solid var(--border);border-radius:8px;background:var(--card2);color:var(--muted);cursor:pointer;font-size:13px}
/* 选中样式与侧边栏导航同步 (浅色底 + 彩色文字) */
.subtab.active{background:rgba(56,189,248,.12);color:var(--accent);font-weight:600;border-color:rgba(56,189,248,.3)}
.subpanel{display:none}
.subpanel.active{display:block}
/* 主题卡片 */
.themes-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px;margin-bottom:14px}
.theme-card{background:var(--card2);border:1px solid var(--border);border-radius:12px;padding:14px;display:flex;flex-direction:column;gap:10px}
.theme-card.active{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent)}
.theme-card-head{font-size:14px;font-weight:600;display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.theme-card-status{font-size:12px;color:var(--muted)}
.theme-card-status .status-active{color:var(--accent);font-weight:600}
.theme-card-status .status-invalid{color:var(--brand)}
.theme-card-actions{display:flex;gap:8px;flex-wrap:wrap}
.btn-danger{color:var(--brand)!important}
/* 服务状态卡片 */
.stat-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px;margin-bottom:8px}
.stat-card{background:var(--card2);border:1px solid var(--border);border-radius:10px;padding:12px}
.stat-card .k{font-size:11px;color:var(--muted);margin-bottom:4px}
.stat-card .v{font-size:16px;font-weight:600}
.stat-dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px}
.dot-on{background:#22c55e}.dot-off{background:#ef4444}
.tag{display:inline-block;font-size:11px;padding:1px 7px;border-radius:6px;margin-left:6px}
.tag-preset{background:rgba(56,189,248,.15);color:var(--accent)}
.tag-installed{background:rgba(34,197,94,.15);color:#22c55e}
.tag-module{background:rgba(240,148,0,.15);color:var(--brand)}
</style>
</head>
<body data-theme="light">
<div class="layout">
  <div class="sidebar" id="sidebar">
    <div class="brand">📝 Hugo Blog<div class="brand-ver" id="brandVer">v0.1.4.11</div></div>
    <div class="nav-item active" onclick="switchNav('dash')" data-i18n="nav_dash">📊 仪表板</div>
    <div class="nav-item" onclick="switchNav('write')" data-i18n="nav_write">✍️ 写文章</div>
    <div class="nav-item" onclick="switchNav('posts')" data-i18n="nav_posts">📄 文章列表</div>
    <div class="nav-item" onclick="switchNav('settings')" data-i18n="nav_settings">⚙️ 设置</div>
  </div>
  <div class="sidebar-overlay" id="sidebarOverlay" onclick="toggleSidebar()"></div>
  <div class="main">
    <div class="topbar">
      <div style="display:flex;align-items:center;gap:8px">
        <button class="hamburger" onclick="toggleSidebar()">☰</button>
      </div>
      <div style="display:flex;gap:8px;align-items:center">
        <button class="btn secondary" id="langToggle" onclick="toggleLang()" style="width:auto;padding:6px 10px" title="中/EN">EN</button>
        <button class="btn secondary" id="themeToggle" onclick="toggleTheme()" style="width:auto;padding:6px 10px" title="日夜主题">🌙</button>
        <a class="btn secondary" href="javascript:void(0)" onclick="window.open('http://'+location.hostname+':13133/','_blank');return false" style="text-decoration:none" data-i18n="view_blog">查看博客</a>
      </div>
    </div>
    <div class="tab-panel active" id="tab-dash">
      <div class="panel">
        <h2 data-i18n="dash_title">📊 服务状态</h2>
        <div class="stat-grid" id="statGrid"></div>
        <div style="display:flex;align-items:center;gap:8px;margin-top:14px;flex-wrap:wrap">
          <button class="btn secondary" onclick="rebuildSite()" data-i18n="rebuild_btn">🔄 重建站点</button>
          <button class="btn secondary" onclick="createToken()" data-i18n="token_btn">🔑 创建 token</button>
          <span class="hint" id="rebuildMsg" style="margin:0"></span>
        </div>
        <div class="hint" id="tokenMsg" style="margin-top:8px;display:none"></div>
      </div>
      <div class="panel">
        <h2 data-i18n="console_title">📜 日志控制台</h2>
        <div class="log-controls">
          <select id="logSource" onchange="loadLogDates()" style="width:auto;padding:7px 10px;border:1px solid var(--border);border-radius:8px;background:var(--card2);color:var(--text);font-size:13px">
            <option value="hugo" data-i18n="log_src_hugo">Hugo 日志</option>
            <option value="manager" data-i18n="log_src_manager">管理面板日志</option>
          </select>
          <select id="logDate" onchange="loadLogs()" style="width:auto;padding:7px 10px;border:1px solid var(--border);border-radius:8px;background:var(--card2);color:var(--text);font-size:13px">
            <option value="" data-i18n="current">当前</option>
          </select>
          <button class="btn secondary" onclick="loadLogs()" data-i18n="refresh">🔄 刷新</button>
          <button class="btn secondary" onclick="downloadLog()" data-i18n="download">⬇️ 下载</button>
        </div>
        <div class="hint" id="logInfo" style="margin-bottom:8px"></div>
        <pre id="logView" class="log-view"></pre>
        <div class="hint" style="margin-top:8px" data-i18n="console_hint">日志按日期归档，可查看历史日期。当前日志仅保留当天，历史自动归档到 data/logs/ 目录。</div>
      </div>
    </div>
    <div class="tab-panel" id="tab-write">
      <div class="panel">
        <h2 data-i18n="new_post_title">✍️ 新建文章</h2>
        <label data-i18n="title_label">标题 *</label><input id="title" placeholder="文章标题">
        <label data-i18n="tags_label">标签 (逗号分隔)</label><input id="tags" placeholder="hugo, fnos">
        <label data-i18n="content_label">内容 (Markdown)</label><textarea id="content" placeholder="# 标题&#10;正文..."></textarea>
        <div class="msg" id="msg"></div>
        <button class="btn" onclick="createPost()" style="margin-top:14px" data-i18n="save_publish">保存并发布</button>
        <div class="hint" data-i18n="save_hint">保存后 Hugo 会自动重新渲染，稍等片刻刷新博客即可看到。</div>
      </div>
    </div>
    <div class="tab-panel" id="tab-posts">
      <div class="panel">
        <h2 data-i18n="posts_title">📄 文章列表</h2>
        <table id="postsTable">
          <thead><tr><th data-i18n="th_title">标题</th><th data-i18n="th_date">日期</th><th data-i18n="th_file">文件名</th></tr></thead>
          <tbody></tbody>
        </table>
        <div class="pager" id="pager" style="display:none">
          <button id="prevPage" onclick="changePage(-1)" data-i18n="prev_page">‹ 上一页</button>
          <span class="pager-info" id="pagerInfo"></span>
          <button id="nextPage" onclick="changePage(1)" data-i18n="next_page">下一页 ›</button>
        </div>
      </div>
    </div>
    <div class="tab-panel" id="tab-settings">
      <div class="subtabs">
        <button class="subtab active" onclick="switchSubTab('theme')" data-i18n="nav_theme">🎨 主题</button>
        <button class="subtab" onclick="switchSubTab('proxy')" data-i18n="sub_proxy">⚙️ 代理</button>
        <button class="subtab" onclick="switchSubTab('api')" data-i18n="sub_api">🤖 API</button>
      </div>
      <div class="subpanel active" id="sub-theme">
        <div class="panel">
          <h2 data-i18n="theme_title">🎨 主题管理</h2>
          <div class="hint" id="curTheme" style="margin-bottom:8px"></div>
          <div class="themes-grid" id="themesGrid"></div>
          <div class="msg" id="themeMsg"></div>
          <label data-i18n="install_online_label">在线安装 (git 仓库 或 Hugo Module)</label>
          <div style="display:flex;gap:8px;align-items:center">
            <input id="installInput" placeholder="https://github.com/user/theme.git 或 github.com/bep/docuapi">
            <button class="btn secondary" onclick="installTheme()" style="width:auto;white-space:nowrap" data-i18n="install_btn">安装</button>
          </div>
          <div class="hint" data-i18n="install_hint">git 地址自动克隆，module 路径自动下载；联网后自动检测依赖（module/sass）。</div>
          <label data-i18n="upload_label">上传主题 zip 包 <span style="color:var(--muted);font-weight:400" data-i18n="upload_note">(用于无法使用 GitHub 的场景)</span></label>
          <input type="file" id="themeFile" accept=".zip">
          <button class="btn secondary" onclick="uploadTheme()" style="margin-top:10px" data-i18n="upload_btn">上传主题</button>
          <div class="hint" data-i18n="upload_hint">上传的主题 zip 需包含一个主题目录（含 theme.toml 或 layouts）。</div>
        </div>
      </div>
      <div class="subpanel" id="sub-proxy">
        <div class="panel">
          <h2 data-i18n="proxy_title">⚙️ 代理设置</h2>
          <p class="hint" style="margin-bottom:10px" data-i18n="proxy_hint">用于 Hugo 下载 module 主题依赖（docuapi 等）时走代理。留空表示直连。</p>
          <label data-i18n="proxy_addr_label">代理地址 (HTTP/HTTPS 共用)</label>
          <input id="proxyAddr" placeholder="http://192.168.31.31:7890">
          <label data-i18n="noproxy_label">NO_PROXY <span style="color:var(--muted);font-weight:400" data-i18n="noproxy_optional">(可选)</span></label>
          <input id="proxyNo" value="localhost,127.0.0.1">
          <div class="msg" id="proxyMsg"></div>
          <button class="btn" onclick="saveProxy()" style="margin-top:14px" data-i18n="save_proxy">保存代理设置</button>
          <div class="hint" data-i18n="proxy_restart_hint">保存后重启应用生效（下载 module 时使用）。</div>
        </div>
      </div>
      <div class="subpanel" id="sub-api">
        <div class="panel">
          <h2 data-i18n="api_title">🤖 API 使用指南</h2>
          <p class="hint" style="margin-bottom:10px" data-i18n="api_hint">以下为管理面板 REST API 的 Markdown 文档，可直接复制给 agent 使用。</p>
          <div style="display:flex;gap:8px;align-items:center;margin-bottom:8px">
            <button class="btn secondary" onclick="copyApiDoc()" data-i18n="api_copy">📋 复制文档</button>
          </div>
          <div id="apiDoc" class="api-doc" style="background:var(--card2);border:1px solid var(--border);border-radius:8px;padding:14px;font-size:13px;line-height:1.7;max-height:70vh;overflow-y:auto"></div>
        </div>
      </div>
    </div>
  </div>
</div>
<script>
let apiToken = '';
// ---------- i18n (中/EN) ----------
const I18N = {
  zh: {
    app_title:'Hugo Blog 管理', nav_dash:'📊 仪表板', nav_write:'✍️ 写文章', nav_posts:'📄 文章列表', nav_theme:'🎨 主题', nav_settings:'⚙️ 设置',
    view_blog:'查看博客',
    new_post_title:'✍️ 新建文章', title_label:'标题 *', tags_label:'标签 (逗号分隔)', content_label:'内容 (Markdown)', save_publish:'保存并发布', save_hint:'保存后 Hugo 会自动重新渲染，稍等片刻刷新博客即可看到。',
    posts_title:'📄 文章列表', th_title:'标题', th_date:'日期', th_file:'文件名', prev_page:'‹ 上一页', next_page:'下一页 ›', no_posts:'暂无文章',
    theme_title:'🎨 主题管理', th_theme:'主题', th_status:'状态', th_action:'操作', in_use:'✓ 使用中', available:'可用', invalid:'无效', use:'使用', delete:'删除', no_themes:'暂无主题，请上传', tag_preset:'系统预置', tag_installed:'已安装', tag_module:'Module',
    install_online_label:'在线安装 (git 仓库 或 Hugo Module)', install_btn:'安装', install_hint:'git 地址自动克隆，module 路径自动下载；联网后自动检测依赖（module/sass）。',
    upload_label:'上传主题 zip 包', upload_note:'(用于无法使用 GitHub 的场景)', upload_btn:'上传主题', upload_hint:'上传的主题 zip 需包含一个主题目录（含 theme.toml 或 layouts）。',
    proxy_title:'⚙️ 代理设置', proxy_hint:'用于 Hugo 下载 module 主题依赖（docuapi 等）时走代理。留空表示直连。', proxy_addr_label:'代理地址 (HTTP/HTTPS 共用)', noproxy_label:'NO_PROXY', noproxy_optional:'(可选)', save_proxy:'保存代理设置', proxy_restart_hint:'保存后重启应用生效（下载 module 时使用）。',
    console_title:'📜 日志控制台', refresh:'🔄 刷新', download:'⬇️ 下载', current:'当前', log_src_hugo:'Hugo 日志', log_src_manager:'管理面板日志', console_hint:'日志按日期归档，可查看历史日期。当前日志仅保留当天，历史自动归档到 data/logs/ 目录。',
    sub_proxy:'⚙️ 代理', sub_api:'🤖 API', dash_title:'📊 服务状态',
    api_title:'🤖 API 使用指南', api_hint:'以下为管理面板 REST API 的 Markdown 文档，可直接复制给 agent 使用。', api_copy:'📋 复制文档', api_copied:'✓ 已复制到剪贴板',
    stat_hugo:'Hugo 服务', stat_manager:'管理面板', stat_blog_port:'博客端口', stat_admin_port:'管理端口', stat_version:'Hugo 版本', stat_posts:'文章', stat_themes:'主题', stat_cur_theme:'当前主题', stat_running:'运行中', stat_stopped:'已停止',
    rebuild_btn:'🔄 重建站点', rebuilding:'正在重建…', rebuild_done:'✓ 已重建', rebuild_fail:'重建失败:',
    token_btn:'🔑 创建 token', token_creating:'正在生成新 token…', token_done:'✓ 新 token (立即生效):', token_fail:'创建失败:',
    saving:'保存中…', saved:'✓ 已保存:', rendering:'(Hugo 自动渲染中)', save_fail:'保存失败', deleting:'删除中…', deleted:'✓ 已删除主题:', delete_fail:'删除失败', del_confirm:'确定删除主题「{name}」吗？',
    switching:'切换中…', switched:'✓ 已切换到主题:', switch_fail:'切换失败', uploading:'上传中…', uploaded:'✓ 主题已上传:', upload_fail:'上传失败', pls_zip:'请选择 zip 文件', no_theme:'请输入 git 地址或 module 路径', installing:'安装中… (可能需要一些时间)', installed:'✓ 主题已安装:', deps:'依赖', install_fail:'安装失败', invalid_install:'无法识别：请输入 git 仓库地址 或 Hugo module 路径',
    proxy_saved:'✓ 代理设置已保存（重启应用生效）', proxy_save_fail:'保存失败', loading_log:'加载中…', load_log_fail:'加载日志失败:', log_read_fail:'读取失败', no_log:'无日志内容', no_log_data:'(暂无日志)', load_list_fail:'加载日志列表失败:', log_fmt:'{src} 日志 · {disp} · 共 {total} 行',
  },
  en: {
    app_title:'Hugo Blog Admin', nav_dash:'📊 Dashboard', nav_write:'✍️ Write', nav_posts:'📄 Posts', nav_theme:'🎨 Themes', nav_settings:'⚙️ Settings',
    view_blog:'View Blog',
    new_post_title:'✍️ New Post', title_label:'Title *', tags_label:'Tags (comma separated)', content_label:'Content (Markdown)', save_publish:'Save & Publish', save_hint:'Hugo re-renders automatically; refresh the blog shortly to see changes.',
    posts_title:'📄 Posts', th_title:'Title', th_date:'Date', th_file:'File', prev_page:'‹ Prev', next_page:'Next ›', no_posts:'No posts',
    theme_title:'🎨 Themes', th_theme:'Theme', th_status:'Status', th_action:'Actions', in_use:'✓ In use', available:'Available', invalid:'Invalid', use:'Use', delete:'Delete', no_themes:'No themes, upload one', tag_preset:'Preset', tag_installed:'Installed', tag_module:'Module',
    install_online_label:'Install Online (git repo or Hugo Module)', install_btn:'Install', install_hint:'git URL clones, module path downloads; auto-detects deps (module/sass) when online.',
    upload_label:'Upload theme zip', upload_note:'(for when GitHub is unavailable)', upload_btn:'Upload', upload_hint:'Zip must contain one theme dir (theme.toml or layouts).',
    proxy_title:'⚙️ Proxy Settings', proxy_hint:'Proxy used when Hugo downloads module theme deps (docuapi etc). Leave empty for direct.', proxy_addr_label:'Proxy address (shared HTTP/HTTPS)', noproxy_label:'NO_PROXY', noproxy_optional:'(optional)', save_proxy:'Save Proxy', proxy_restart_hint:'Takes effect after app restart (used when downloading modules).',
    console_title:'📜 Log Console', refresh:'🔄 Refresh', download:'⬇️ Download', current:'Current', log_src_hugo:'Hugo Log', log_src_manager:'Admin Log', console_hint:'Logs are archived by date. Current file keeps today only; history moves to data/logs/.',
    sub_proxy:'⚙️ Proxy', sub_api:'🤖 API', dash_title:'📊 Service Status',
    api_title:'🤖 API Guide', api_hint:'Markdown doc of the admin REST API, copy-paste for an agent.', api_copy:'📋 Copy Doc', api_copied:'✓ Copied to clipboard',
    stat_hugo:'Hugo Service', stat_manager:'Admin Panel', stat_blog_port:'Blog Port', stat_admin_port:'Admin Port', stat_version:'Hugo Version', stat_posts:'Posts', stat_themes:'Themes', stat_cur_theme:'Current Theme', stat_running:'Running', stat_stopped:'Stopped',
    rebuild_btn:'🔄 Rebuild', rebuilding:'Rebuilding…', rebuild_done:'✓ Rebuilt', rebuild_fail:'Rebuild failed:',
    token_btn:'🔑 Create Token', token_creating:'Generating new token…', token_done:'✓ New token (effective now):', token_fail:'Failed:',
    saving:'Saving…', saved:'✓ Saved:', rendering:'(Hugo re-rendering)', save_fail:'Save failed', deleting:'Deleting…', deleted:'✓ Deleted theme:', delete_fail:'Delete failed', del_confirm:'Delete theme "{name}"?',
    switching:'Switching…', switched:'✓ Switched to:', switch_fail:'Switch failed', uploading:'Uploading…', uploaded:'✓ Uploaded:', upload_fail:'Upload failed', pls_zip:'Select a zip file', no_theme:'Enter git URL or module path', installing:'Installing… (may take a while)', installed:'✓ Installed:', deps:'deps', install_fail:'Install failed', invalid_install:'Unrecognized: enter a git repo URL or a Hugo module path',
    proxy_saved:'✓ Proxy saved (takes effect after restart)', proxy_save_fail:'Save failed', loading_log:'Loading…', load_log_fail:'Failed to load log:', log_read_fail:'Read failed', no_log:'No log content', no_log_data:'(no log)', load_list_fail:'Failed to load log list:', log_fmt:'{src} log · {disp} · {total} lines',
  }
};
let currentLang = localStorage.getItem('hugo_lang') || 'zh';
let currentTheme = localStorage.getItem('hugo_theme') || 'light';
function t(key, vars){
  const dict = I18N[currentLang] || I18N.zh;
  let s = dict[key] !== undefined ? dict[key] : (I18N.zh[key] || key);
  if(vars) for(const k in vars) s = s.replace('{'+k+'}', vars[k]);
  return s;
}
function applyI18n(){
  document.querySelectorAll('[data-i18n]').forEach(el=>{
    const k = el.getAttribute('data-i18n');
    if(k) el.innerHTML = t(k);
  });
  document.getElementById('langToggle').textContent = currentLang === 'zh' ? 'EN' : '中文';
}
function toggleLang(){
  currentLang = currentLang === 'zh' ? 'en' : 'zh';
  localStorage.setItem('hugo_lang', currentLang);
  applyI18n();
  // 重新渲染动态内容 (文章/主题列表的文案)
  if(document.getElementById('tab-posts').classList.contains('active')) loadPosts();
  if(document.getElementById('tab-theme').classList.contains('active')) loadThemes();
  loadLogDates();
}
function toggleTheme(){
  currentTheme = currentTheme === 'light' ? 'dark' : 'light';
  localStorage.setItem('hugo_theme', currentTheme);
  document.body.setAttribute('data-theme', currentTheme);
  document.getElementById('themeToggle').textContent = currentTheme === 'dark' ? '☀️' : '🌙';
}
function initPrefs(){
  document.body.setAttribute('data-theme', currentTheme);
  document.getElementById('themeToggle').textContent = currentTheme === 'dark' ? '☀️' : '🌙';
  applyI18n();
}
// 带 Bearer token 的 fetch (所有 API 请求)
async function apiFetch(url, options={}){
  const headers = Object.assign({}, options.headers || {});
  if(apiToken) headers['Authorization'] = 'Bearer ' + apiToken;
  return fetch(url, Object.assign({}, options, {headers}));
}
// 初始化: 从 /api/bootstrap 获取 token
async function initToken(){
  try{
    const r = await fetch('/api/bootstrap');
    const d = await r.json();
    if(d.api_token){ apiToken = d.api_token; initPrefs(); loadStatus(); loadLogDates(); }
    if(d.version){ const bv = document.getElementById('brandVer'); if(bv) bv.textContent = 'v' + d.version; }
  }catch(e){}
}
async function loadPosts(){
  const r = await apiFetch('/api/posts');
  const d = await r.json();
  allPosts = d.posts || [];
  renderPosts();
}
// 文章列表分页
let allPosts = [];
let currentPage = 1;
const PAGE_SIZE = 10;
function renderPosts(){
  const totalPages = Math.max(1, Math.ceil(allPosts.length / PAGE_SIZE));
  if(currentPage > totalPages) currentPage = totalPages;
  const start = (currentPage - 1) * PAGE_SIZE;
  const pagePosts = allPosts.slice(start, start + PAGE_SIZE);
  const tbody = document.querySelector('#postsTable tbody');
  tbody.innerHTML = pagePosts.map(p=>
    `<tr><td>${escapeHtml(p.title)}</td><td>${p.date||'-'}</td><td>${p.filename}</td></tr>`
  ).join('') || '<tr><td colspan="3">'+t('no_posts')+'</td></tr>';
  const pager = document.getElementById('pager');
  if(allPosts.length > PAGE_SIZE){
    pager.style.display = 'flex';
    document.getElementById('pagerInfo').textContent = `${currentPage} / ${totalPages}`;
    document.getElementById('prevPage').disabled = currentPage <= 1;
    document.getElementById('nextPage').disabled = currentPage >= totalPages;
  } else {
    pager.style.display = 'none';
  }
}
function changePage(delta){
  currentPage += delta;
  renderPosts();
}
// 侧边栏导航切换
function switchNav(tab){
  document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
  const navItem = [...document.querySelectorAll('.nav-item')].find(b => b.getAttribute('onclick').includes("'" + tab + "'"));
  if(navItem) navItem.classList.add('active');
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  const panel = document.getElementById('tab-' + tab);
  if(panel) panel.classList.add('active');
  if(tab === 'dash'){ loadStatus(); loadLogDates(); }
  if(tab === 'posts') loadPosts();
  if(tab === 'settings'){ switchSubTab('theme'); loadThemes(); }
  toggleSidebar(false); // 切导航后关闭移动端侧边栏
}
// 设置页内子 tab 切换 (主题/代理)
function switchSubTab(name){
  document.querySelectorAll('.subtab').forEach(b => b.classList.remove('active'));
  const btn = [...document.querySelectorAll('.subtab')].find(b => b.getAttribute('onclick').includes("'"+name+"'"));
  if(btn) btn.classList.add('active');
  document.querySelectorAll('.subpanel').forEach(p => p.classList.remove('active'));
  const sp = document.getElementById('sub-' + name);
  if(sp) sp.classList.add('active');
  if(name === 'theme') loadThemes();
  if(name === 'proxy') loadProxy();
  if(name === 'api') loadApiDoc();
}
// 加载服务状态卡片
async function loadStatus(){
  const grid = document.getElementById('statGrid');
  grid.innerHTML = '…';
  try{
    const r = await apiFetch('/api/info');
    const d = await r.json();
    const dot = on => '<span class="stat-dot ' + (on?'dot-on':'dot-off') + '"></span>';
    const cards = [
      {k:t('stat_hugo')+' · :13133', v:(d.hugo && d.hugo.running) && (d.ports && d.ports.blog) ? dot(true)+t('stat_running') : dot(false)+t('stat_stopped')},
      {k:t('stat_manager')+' · :13134', v:(d.manager && d.manager.running) && (d.ports && d.ports.admin) ? dot(true)+t('stat_running') : dot(false)+t('stat_stopped')},
      {k:t('stat_posts'), v:(d.posts||0)},
      {k:t('stat_themes'), v:(d.themes||0)},
      {k:t('stat_version'), v:(d.hugo_version||'').split(' ')[0]||'-'},
      {k:t('stat_cur_theme'), v:(d.current_theme||'-')},
    ];
    grid.innerHTML = cards.map(c=>'<div class="stat-card"><div class="k">'+c.k+'</div><div class="v">'+c.v+'</div></div>').join('');
  }catch(e){
    grid.innerHTML = '<div class="hint">'+t('load_log_fail')+' '+e+'</div>';
  }
}
// 手动重建站点 (仪表盘「重建」按钮)
async function rebuildSite(){
  const msg = document.getElementById('rebuildMsg');
  if(msg) msg.textContent = t('rebuilding');
  try{
    const r = await apiFetch('/api/rebuild', {method:'POST'});
    const d = await r.json();
    if(d.ok){
      if(msg) msg.textContent = t('rebuild_done'); // 已触发, 后台执行
      // hugo 首次构建可能较慢, 稍等后再刷新状态/日志
      setTimeout(()=>{ loadStatus(); loadLogDates(); }, 8000);
    } else {
      if(msg) msg.textContent = t('rebuild_fail') + ' ' + (d.error||'');
    }
  }catch(e){
    if(msg) msg.textContent = t('rebuild_fail') + ' ' + e;
  }
}
// 创建新 API token (仪表盘「创建 token」按钮)
async function createToken(){
  const el = document.getElementById('tokenMsg');
  if(el){ el.style.display='block'; el.textContent = t('token_creating'); }
  try{
    const r = await apiFetch('/api/token/recreate', {method:'POST'});
    const d = await r.json();
    if(d.ok && d.token){
      if(el) el.textContent = t('token_done') + ' ' + d.token;
    } else {
      if(el) el.textContent = t('token_fail') + ' ' + (d.error||'');
    }
  }catch(e){
    if(el) el.textContent = t('token_fail') + ' ' + e;
  }
}
// 汉堡菜单 (移动端)
function toggleSidebar(force){
  const sb = document.getElementById('sidebar');
  const ov = document.getElementById('sidebarOverlay');
  const open = typeof force === 'boolean' ? force : !sb.classList.contains('open');
  sb.classList.toggle('open', open);
  ov.classList.toggle('show', open);
}
async function createPost(){
  const msg = document.getElementById('msg');
  msg.textContent = t('saving');
  const r = await apiFetch('/api/new', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({
      title: document.getElementById('title').value,
      tags: document.getElementById('tags').value,
      content: document.getElementById('content').value
    })
  });
  const d = await r.json();
  if(d.ok){
    msg.textContent = t('saved') + ' ' + d.path + ' ' + t('rendering');
    document.getElementById('title').value='';
    document.getElementById('tags').value='';
    document.getElementById('content').value='';
    loadPosts();
  } else {
    msg.textContent = '✗ ' + (d.error||t('save_fail'));
  }
}
function escapeHtml(s){return s.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
async function loadThemes(){
  const r = await apiFetch('/api/themes');
  const d = await r.json();
  document.getElementById('curTheme').textContent = d.current ? '· ' + t('th_theme').replace('主题','') + ': ' + d.current : '';
  const grid = document.getElementById('themesGrid');
  grid.innerHTML = (d.themes||[]).map(th=>{
    const active = th.name === d.current;
    let tag = '';
    if(th.module) tag = '<span class="tag tag-module">'+t('tag_module')+'</span>';
    else if(th.preset) tag = '<span class="tag tag-preset">'+t('tag_preset')+'</span>';
    else if(th.valid) tag = '<span class="tag tag-installed">'+t('tag_installed')+'</span>';
    const status = active ? '<span class="theme-status status-active">'+t('in_use')+'</span>' : (th.valid ? '<span class="theme-status">'+t('available')+'</span>' : '<span class="theme-status status-invalid">'+t('invalid')+'</span>');
    let actions = '';
    if(!active && th.valid){
      actions += `<button class="btn secondary" onclick="switchTheme('${th.name}')">${t('use')}</button>`;
      if(!th.preset) actions += ` <button class="btn secondary btn-danger" onclick="deleteTheme('${th.name}')">${t('delete')}</button>`;
    }
    return `<div class="theme-card${active ? ' active' : ''}">
      <div class="theme-card-head">${escapeHtml(th.name)}${tag}</div>
      <div class="theme-card-status">${status}</div>
      <div class="theme-card-actions">${actions}</div>
    </div>`;
  }).join('') || '<div class="hint">'+t('no_themes')+'</div>';
}
async function deleteTheme(name){
  if(!confirm(t('del_confirm', {name}))) return;
  const msg = document.getElementById('themeMsg');
  msg.textContent = t('deleting');
  const r = await apiFetch('/api/theme/delete', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({theme: name})
  });
  const d = await r.json();
  if(d.ok){
    msg.textContent = t('deleted') + ' ' + name;
    loadThemes();
  } else {
    msg.textContent = '✗ ' + (d.error||t('delete_fail'));
  }
}
async function switchTheme(name){
  const msg = document.getElementById('themeMsg');
  msg.textContent = t('switching');
  const r = await apiFetch('/api/theme/switch', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({theme: name})
  });
  const d = await r.json();
  if(d.ok){
    msg.textContent = t('switched') + ' ' + name;
    loadThemes();
  } else {
    msg.textContent = '✗ ' + (d.error||t('switch_fail'));
  }
}
async function uploadTheme(){
  const msg = document.getElementById('themeMsg');
  const file = document.getElementById('themeFile').files[0];
  if(!file){ msg.textContent = t('pls_zip'); return; }
  msg.textContent = t('uploading');
  const fd = new FormData();
  fd.append('file', file);
  const r = await apiFetch('/api/theme/upload', {method:'POST', body: fd});
  const d = await r.json();
  if(d.ok){
    msg.textContent = t('uploaded') + ' ' + d.theme;
    document.getElementById('themeFile').value='';
    loadThemes();
  } else {
    msg.textContent = '✗ ' + (d.error||t('upload_fail'));
  }
}
// 合并安装: 自动识别 git URL 或 Hugo module 路径
async function installTheme(){
  const msg = document.getElementById('themeMsg');
  const val = document.getElementById('installInput').value.trim();
  if(!val){ msg.textContent = t('no_theme'); return; }
  const isGit = /^(https?:\/\/|git@|ssh:\/\/)/.test(val);
  msg.textContent = t('installing');
  let url = '/api/theme/' + (isGit ? 'git' : 'module');
  let body = isGit ? {url: val} : {module: val};
  if(!isGit && !val.includes('/')){ msg.textContent = t('invalid_install'); return; }
  const r = await apiFetch(url, {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify(body)
  });
  const d = await r.json();
  if(d.ok){
    let detail = '';
    if(isGit){
      const deps = (d.theme.deps||[]).join(', ') || 'none';
      detail = d.theme.name + ' (' + t('deps') + ': ' + deps + ')';
    } else {
      detail = d.theme;
    }
    msg.textContent = t('installed') + ' ' + detail;
    document.getElementById('installInput').value='';
    loadThemes();
  } else {
    msg.textContent = '✗ ' + (d.error||t('install_fail'));
  }
}
async function loadProxy(){
  const r = await apiFetch('/api/proxy');
  const d = await r.json();
  // 若 http 与 https 相同则填入单一地址; 否则优先 http
  const addr = (d.http && d.http === d.https) ? d.http : (d.http || d.https || '');
  document.getElementById('proxyAddr').value = addr || '';
  document.getElementById('proxyNo').value = d.no_proxy || 'localhost,127.0.0.1';
}
async function saveProxy(){
  const msg = document.getElementById('proxyMsg');
  msg.textContent = t('saving');
  const addr = document.getElementById('proxyAddr').value.trim();
  const r = await apiFetch('/api/proxy', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({
      http: addr,
      https: addr,
      no_proxy: document.getElementById('proxyNo').value.trim() || 'localhost,127.0.0.1'
    })
  });
  const d = await r.json();
  if(d.ok){
    msg.textContent = t('proxy_saved');
  } else {
    msg.textContent = '✗ ' + (d.error||t('proxy_save_fail'));
  }
}
// ---------- 日志控制台 ----------
let logSources = ['hugo'];
let logDates = [];
async function loadLogDates(){
  const source = document.getElementById('logSource').value || 'hugo';
  try{
    const r = await apiFetch('/api/logs/list?source=' + encodeURIComponent(source));
    const d = await r.json();
    if(d.sources) logSources = d.sources;
    logDates = d.dates || [];
    const dateSel = document.getElementById('logDate');
    const prev = dateSel.value;
    dateSel.innerHTML = '<option value="">'+t('current')+'</option>' + logDates.map(x=>
      `<option value="${x.date}" ${x.date===prev?'selected':''}>${x.display}</option>`
    ).join('');
    // 若之前选中了某个历史日期, 保持; 否则加载当前
    if(prev && logDates.some(x=>x.date===prev)){
      dateSel.value = prev;
    }
    loadLogs();
  }catch(e){ document.getElementById('logView').textContent = t('load_list_fail') + ' ' + e; }
}
async function loadLogs(){
  const source = document.getElementById('logSource').value || 'hugo';
  const date = document.getElementById('logDate').value || '';
  const view = document.getElementById('logView');
  const info = document.getElementById('logInfo');
  view.textContent = t('loading_log');
  try{
    const q = 'source=' + encodeURIComponent(source) + '&tail=2000' + (date ? '&date=' + encodeURIComponent(date) : '');
    const r = await apiFetch('/api/logs?' + q);
    const d = await r.json();
    if(d.content === undefined){
      info.textContent = t('log_read_fail');
      view.textContent = t('no_log');
      return;
    }
    info.textContent = t('log_fmt', {src: source.toUpperCase(), disp: d.display, total: d.total}) + (date ? '' : ' (' + t('refresh') + ' 2000)');
    view.textContent = d.content || t('no_log_data');
    view.scrollTop = view.scrollHeight;
  }catch(e){
    view.textContent = t('load_log_fail') + ' ' + e;
  }
}
function downloadLog(){
  const source = document.getElementById('logSource').value || 'hugo';
  const date = document.getElementById('logDate').value || '';
  const q = 'source=' + encodeURIComponent(source) + (date ? '&date=' + encodeURIComponent(date) : '');
  window.open('/api/logs/download?' + q, '_blank');
}
// ---------- API 使用指南 (Markdown 渲染 + 复制) ----------
let apiDocMd = '';
function escHtml(s){
  return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function renderMarkdown(md){
  const out = [];
  const lines = md.split("\\n");
  let inCode = false, codeBuf = [];
  const flushCode = () => {
    if(codeBuf.length){
      out.push('<pre style="background:rgba(0,0,0,0.82);color:#d4d4d4;border:1px solid rgba(255,255,255,.12);border-radius:8px;padding:10px;overflow-x:auto;white-space:pre-wrap;word-break:break-all;font-size:12px;font-family:ui-monospace,Menlo,Consolas,monospace;line-height:1.6">'+escHtml(codeBuf.join("\\n"))+'</pre>');
      codeBuf = [];
    }
  };
  for(let i=0;i<lines.length;i++){
    const line = lines[i];
    if(/^```/.test(line)){
      if(inCode){ flushCode(); inCode=false; }
      else { inCode=true; codeBuf=[]; }
      continue;
    }
    if(inCode){ codeBuf.push(line); continue; }
    if(/^###\s+/.test(line)){ out.push('<div style="margin:14px 0 6px;font-weight:700;font-size:14px">'+escHtml(line.replace(/^###\s+/,''))+'</div>'); }
    else if(/^##\s+/.test(line)){ out.push('<div style="margin:16px 0 6px;font-weight:700;font-size:15px">'+escHtml(line.replace(/^##\s+/,''))+'</div>'); }
    else if(/^#\s+/.test(line)){ out.push('<div style="margin:16px 0 8px;font-weight:700;font-size:17px">'+escHtml(line.replace(/^#\s+/,''))+'</div>'); }
    else if(/^>\s+/.test(line)){ out.push('<div style="border-left:3px solid var(--accent);padding:4px 10px;color:var(--muted);margin:6px 0;background:var(--card2)">'+escHtml(line.replace(/^>\s+/,''))+'</div>'); }
    else if(/^-\s+/.test(line)){ out.push('<div style="padding:2px 0">• '+escHtml(line.replace(/^-\s+/,''))+'</div>'); }
    else if(/^```/.test(line)){ }
    else if(line.trim()===''){ out.push('<div style="height:6px"></div>'); }
    else { out.push('<div style="padding:1px 0">'+escHtml(line)+'</div>'); }
  }
  flushCode();
  return out.join("\\n");
}
async function loadApiDoc(){
  const el = document.getElementById('apiDoc');
  if(!el) return;
  try{
    if(!apiDocMd){
      const r = await apiFetch('/api/doc');
      const d = await r.json();
      apiDocMd = d.doc || '';
    }
    el.innerHTML = renderMarkdown(apiDocMd);
  }catch(e){ el.textContent = t('load_log_fail') + ' ' + e; }
}
function copyApiDoc(){
  const txt = apiDocMd || '';
  if(!txt) return;
  if(navigator.clipboard && navigator.clipboard.writeText){
    navigator.clipboard.writeText(txt).then(()=>alert(t('api_copied')));
  } else {
    const ta = document.createElement('textarea');
    ta.value = txt; document.body.appendChild(ta); ta.select();
    document.execCommand('copy'); document.body.removeChild(ta);
    alert(t('api_copied'));
  }
}
initToken();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    os.makedirs(POST_DIR, exist_ok=True)
    archive_logs()  # 启动时归档非当天的日志 (控制台按日期归档)
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    httpd = socketserver.ThreadingTCPServer(("0.0.0.0", PORT), Handler)
    print(f"Hugo Blog manager on port {PORT}, blog_dir={BLOG_DIR}")
    httpd.serve_forever()
