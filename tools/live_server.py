"""
live_server.py - local live-reload server for the student guide.

Usage (從 repo 根目錄執行):
    python3 tools/live_server.py --host 0.0.0.0 --port 8008

Then expose it with a tunnel, for example:
    cloudflared tunnel --url http://localhost:8008
"""

import argparse
import os
import subprocess
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)  # repo 根目錄（這支腳本放在 tools/ 底下，網站內容都在根目錄）
BUILD_SCRIPT = os.path.join(HERE, "build_html.py")

# 每一份要即時同步的頁面：(來源 Markdown, 產出 HTML)，路徑都相對於 repo 根目錄。
# 要再加一頁（例如正式上課用的講義，不在這個公開 repo 裡），就在這裡多加一組 tuple，
# 監看／重建／路由會自動套用，不用改其他地方。
PAGES = [
    ("index.md", "index.html"),
    ("docs/PREWORK.md", "docs/PREWORK.html"),
]
DEFAULT_HTML = "index.html"  # 首頁 "/" 導向的頁面

WATCH_PATHS = [os.path.join(ROOT, md) for md, _ in PAGES] + [
    BUILD_SCRIPT,
    os.path.join(ROOT, "images"),
]

build_version = str(time.time())
build_lock = threading.Lock()


LIVE_RELOAD_SNIPPET = """
<script>
(function(){
  var lastVersion = null;
  async function checkVersion(){
    try {
      var res = await fetch('/__version?t=' + Date.now(), {cache: 'no-store'});
      var version = await res.text();
      if (lastVersion && version !== lastVersion) location.reload();
      lastVersion = version;
    } catch (e) {}
  }
  checkVersion();
  setInterval(checkVersion, 1000);
})();
</script>
"""


def snapshot():
    mtimes = {}
    for path in WATCH_PATHS:
        if os.path.isdir(path):
            for root, _, files in os.walk(path):
                for name in files:
                    if name.startswith("."):
                        continue
                    full = os.path.join(root, name)
                    mtimes[full] = os.path.getmtime(full)
        elif os.path.exists(path):
            mtimes[path] = os.path.getmtime(path)
    return mtimes


def build():
    global build_version
    for md_name, _ in PAGES:
        subprocess.run([sys.executable, BUILD_SCRIPT, md_name], cwd=ROOT, check=True)
    with build_lock:
        build_version = str(time.time())
    print("rebuilt: " + ", ".join(html_name for _, html_name in PAGES))


def watch_loop():
    previous = snapshot()
    while True:
        time.sleep(0.8)
        current = snapshot()
        if current != previous:
            previous = current
            try:
                build()
            except Exception as exc:
                print(f"build failed: {exc}", file=sys.stderr)


class LiveHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/__version":
            with build_lock:
                version = build_version
            body = version.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        html_names = {html_name for _, html_name in PAGES}
        if parsed.path in ("", "/"):
            html_name = DEFAULT_HTML
        elif parsed.path.lstrip("/") in html_names:
            html_name = parsed.path.lstrip("/")
        else:
            html_name = None

        if html_name:
            with open(os.path.join(ROOT, html_name), encoding="utf-8") as f:
                html = f.read()
            html = html.replace("</body>", LIVE_RELOAD_SNIPPET + "\n</body>")
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        return super().do_GET()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8008)
    args = parser.parse_args()

    build()
    threading.Thread(target=watch_loop, daemon=True).start()

    server = ThreadingHTTPServer((args.host, args.port), LiveHandler)
    print(f"live guide: http://{args.host}:{args.port}")
    print(f"pages: {', '.join(html_name for _, html_name in PAGES)}")
    print("edit index.md / docs/PREWORK.md / images / build_html.py; connected browsers reload automatically")
    server.serve_forever()


if __name__ == "__main__":
    main()
