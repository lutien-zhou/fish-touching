# -*- coding: utf-8 -*-
"""本地图片预览代理：仅监听 127.0.0.1。

浏览器访问 /i/<N> 时，调用传入的 resolver(N) 拿到图片二进制，
以内联方式返回（去掉强制下载头），从而在浏览器里直接预览而不是下载。
"""

import threading
import http.server
import socketserver


def start_proxy(resolver):
    """resolver(n) -> (bytes, content_type) | None。返回监听端口。"""

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            try:
                n = int(self.path.rsplit("/", 1)[-1])
            except Exception:
                self.send_response(404); self.end_headers(); return
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

    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler)
    httpd.daemon_threads = True
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return port
