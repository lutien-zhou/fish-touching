# -*- coding: utf-8 -*-
"""微博扫码登录：返回 (cookie 字符串, my_uid)。纯标准库实现。"""

import os
import re
import sys
import json
import time
import http.cookiejar
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36")


def _opener():
    jar = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    op.addheaders = [("User-Agent", UA), ("Referer", "https://weibo.com/")]
    return op, jar


def _jsonp(text):
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0)) if m else {}


def _get(op, url):
    with op.open(url, timeout=15) as r:
        return r.read().decode("utf-8", "replace")


def _get_qr(op):
    raw = _get(op, "https://login.sina.com.cn/sso/qrcode/image?entry=weibo&size=180&callback=STK")
    d = _jsonp(raw).get("data", {})
    qrid = d["qrid"]
    image_url = d["image"]
    if image_url.startswith("//"):
        image_url = "https:" + image_url
    qr_content = ""
    m = re.search(r"[?&]data=([^&]+)", image_url)
    if m:
        qr_content = urllib.parse.unquote(m.group(1))
    return qrid, qr_content, image_url


def _show_qr(op, qr_content, image_url):
    if qr_content:
        try:
            import qrcode
            qr = qrcode.QRCode(border=2)
            qr.add_data(qr_content)
            qr.make(fit=True)
            qr.print_ascii(invert=True)
            print("\n用微博 App 扫描上方二维码登录\n")
            return
        except Exception:
            pass
    try:
        import tempfile
        import subprocess
        tmp = os.path.join(tempfile.gettempdir(), "ft_wb_qr.png")
        with op.open(image_url, timeout=15) as r:
            open(tmp, "wb").write(r.read())
        cmd = "open" if sys.platform == "darwin" else "xdg-open"
        subprocess.Popen([cmd, tmp])
        print(f"已弹出二维码图片：{tmp}，用微博 App 扫描登录")
        print("（pip install qrcode 可让二维码直接显示在终端）\n")
    except Exception as e:
        print("无法显示二维码：", e)
        print("二维码内容：", qr_content)


def _poll(op, qrid):
    print("等待扫码…  (Ctrl-C 取消)")
    while True:
        d = _jsonp(_get(op, f"https://login.sina.com.cn/sso/qrcode/check?entry=weibo&qrid={qrid}&callback=STK"))
        code = d.get("retcode")
        if code == 50114001:
            pass
        elif code == 50114002:
            print("\r已扫码，请在手机上确认…        ", end="", flush=True)
        elif code == 20000000:
            print("\r扫码确认成功，正在登录…        ")
            return d["data"]["alt"]
        elif code == 50114004:
            print("\r二维码已过期，请重新运行登录。")
            return None
        time.sleep(2)


def _exchange(op, alt):
    url = ("https://login.sina.com.cn/sso/login.php?entry=weibo&returntype=TEXT"
           "&crossdomain=1&cdult=3&domain=weibo.com&savestate=30&callback=STK_login"
           f"&alt={urllib.parse.quote(alt)}")
    d = _jsonp(_get(op, url))
    for u in (d.get("crossDomainUrlList") or d.get("crossdomainurllist") or []):
        try:
            _get(op, u)
        except Exception:
            pass
    return d


def login():
    """完整扫码流程，返回 (cookie, my_uid) 或 None。"""
    op, jar = _opener()
    qrid, qr_content, image_url = _get_qr(op)
    _show_qr(op, qr_content, image_url)
    alt = _poll(op, qrid)
    if not alt:
        return None
    d = _exchange(op, alt)
    cookie = "; ".join(f"{c.name}={c.value}" for c in jar)
    if "SUB=" not in cookie:
        print("⚠️ 未拿到 SUB cookie，登录可能失败。原始 cookie：", cookie[:200])
        return None
    my_uid = str(d.get("uid") or "")
    return cookie, my_uid
