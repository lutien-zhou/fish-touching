# -*- coding: utf-8 -*-
"""本地图片预览代理：仅监听 127.0.0.1。

- /i/<N>   返回一个极简 HTML 查看器：图片自适应窗口宽度、长图可滚动，
           怪比例（很长/很扁）也能完整显示，不会被截断。
- /raw/<N> 返回图片二进制本体（去掉强制下载头），供查看器内嵌引用。
"""

import threading
import http.server
import socketserver

_VIEWER = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>图片#{n}</title><style>
html,body{{margin:0;height:100%;background:#111}}
.wrap{{min-height:100%;display:flex;align-items:flex-start;justify-content:center;padding:8px;box-sizing:border-box}}
img{{max-width:100%;height:auto;display:block}}
</style></head><body><div class="wrap"><img src="/raw/{n}"></div></body></html>"""


def start_proxy(resolver):
    """resolver(n) -> (bytes, content_type) | None。返回监听端口。"""

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _num(self):
            try:
                return int(self.path.rsplit("/", 1)[-1])
            except Exception:
                return None

        def do_GET(self):
            n = self._num()
            if n is None:
                self.send_response(404); self.end_headers(); return

            # 裸图：/raw/N
            if self.path.startswith("/raw/"):
                try:
                    result = resolver(n)
                    if not result:
                        self.send_response(404); self.end_headers(); return
                    data, ct = result
                    self.send_response(200)
                    self.send_header("content-type", ct or "image/png")
                    self.send_header("content-length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                except Exception:
                    self.send_response(502); self.end_headers()
                return

            # 查看器：/i/N（其它路径也兜底成查看器）
            html = _VIEWER.format(n=n).encode("utf-8")
            self.send_response(200)
            self.send_header("content-type", "text/html; charset=utf-8")
            self.send_header("content-length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)

    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler)
    httpd.daemon_threads = True
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return port
