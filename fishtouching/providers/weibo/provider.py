# -*- coding: utf-8 -*-
"""微博私信 provider：实现 Provider 接口。"""

import json
import time
import random
import string
import urllib.parse
import urllib.request

from ...provider import Provider
from ...registry import register
from ...models import Message, Conversation
from ...config import Store
from . import login as wb_login

WEBIM = "https://api.weibo.com/webim"
BASE = WEBIM + "/2/direct_messages"
UPLOAD_URL = WEBIM + "/uploadx.json"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36 Edg/149.0.0.0")
_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
         ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp"}


@register
class WeiboProvider(Provider):
    name = "weibo"
    display_name = "微博私信"
    can_send_image = True

    def __init__(self):
        self.store = Store("weibo")
        cfg = self.store.load()
        self.source = cfg.get("source", "209678993")
        self.poll_interval = int(cfg.get("poll_sec", 5))
        self.my_uid = str(cfg.get("my_uid", ""))
        self._conv_id = str(cfg.get("peer_uid", "")) or None
        self.cookie = self.store.read_secret("cookie") or ""

    # ---------- HTTP ----------
    def _headers(self):
        return {
            "accept": "application/json, text/plain, */*",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
            "cookie": self.cookie,
            "referer": "https://api.weibo.com/chat",
            "user-agent": UA,
            "origin": "https://api.weibo.com",
        }

    def _get(self, url):
        req = urllib.request.Request(url, headers=self._headers(), method="GET")
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8", "replace"))

    def _post(self, url, form):
        h = self._headers()
        h["content-type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=urllib.parse.urlencode(form).encode(),
                                     headers=h, method="POST")
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8", "replace"))

    @staticmethod
    def _now_ms():
        return int(time.time() * 1000)

    @staticmethod
    def _clientid():
        return "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(30))

    # ---------- 登录态 ----------
    def is_authenticated(self):
        if not self.cookie:
            return False
        try:
            d = self._get(f"{BASE}/contacts.json?count=1&special_source=3"
                          f"&source={self.source}&t={self._now_ms()}")
            return isinstance(d, dict) and "contacts" in d
        except Exception:
            return False

    def login(self):
        result = wb_login.login()
        if not result:
            return False
        cookie, my_uid = result
        self.cookie = cookie
        self.store.write_secret("cookie", cookie)
        if my_uid:
            self.my_uid = my_uid
            self.store.update(my_uid=my_uid)
        print(f"\n✅ 微博登录成功，凭证已保存。")
        return True

    # ---------- 会话 ----------
    def list_conversations(self):
        d = self._get(f"{BASE}/contacts.json?count=20&special_source=3"
                      f"&source={self.source}&t={self._now_ms()}")
        out = []
        for c in d.get("contacts", []):
            u = c.get("user", {}) or {}
            uid = str(u.get("idstr") or u.get("id") or "")
            name = u.get("remark") or u.get("screen_name") or u.get("name") or uid
            if uid:
                out.append(Conversation(id=uid, name=name, badge=c.get("unread_count", 0)))
        return out

    def set_conversation(self, conv_id):
        self._conv_id = str(conv_id)
        self.store.update(peer_uid=self._conv_id)

    # ---------- 图片引用 ----------
    def _image_url(self, fid):
        return (f"https://upload.api.weibo.com/2/mss/msget_thumbnail?fid={fid}"
                f"&high=2000&width=2000&size=2000,2000&source={self.source}&imageType=origin")

    def resolve_image(self, ref):
        req = urllib.request.Request(self._image_url(ref),
                                     headers={**self._headers(), "accept": "image/*,*/*"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = r.read()
            ct = (r.headers.get("content-type") or "image/png").split(";")[0]
        return data, ct

    # ---------- 消息解析 ----------
    def _body(self, m):
        att = m.get("att_ids")
        if m.get("media_type") == 1 and isinstance(att, list) and att:
            return "", str(att[0])          # (text, image_ref)
        return (m.get("text") or m.get("content") or ""), None

    def _quote(self, m):
        src = m.get("source_msg")
        if not src:
            return None
        try:
            if isinstance(src, str):
                src = json.loads(src)
            if not isinstance(src, dict):
                return None
            body, img = self._body(src)
            q = "[图片]" if img else body
            q = q.replace("\n", " ").strip()
            return q[:24] + "…" if len(q) > 24 else q
        except Exception:
            return None

    def fetch(self):
        if not self._conv_id:
            return []
        url = (f"{BASE}/conversation.json?convert_emoji=1&count=15&max_id=0"
               f"&uid={self._conv_id}&is_include_group=0&from_contacts=1"
               f"&source={self.source}&t={self._now_ms()}")
        data = self._get(url)
        dms = data.get("direct_messages", []) if isinstance(data, dict) else []

        def key(m):
            try:
                return int(m.get("id") or m.get("mid") or 0)
            except Exception:
                return 0
        out = []
        for m in sorted(dms, key=key):
            mid = m.get("id") or m.get("mid")
            if mid is None:
                continue
            text, img = self._body(m)
            out.append(Message(
                id=str(mid),
                outgoing=(str(m.get("sender_id") or "") == self.my_uid),
                text=text,
                image_ref=img,
                quote=self._quote(m),
            ))
        return out

    # ---------- 发送 ----------
    @staticmethod
    def _resp_id(resp):
        if isinstance(resp, dict):
            mid = resp.get("id") or resp.get("idstr") or resp.get("mid")
            return str(mid) if mid is not None else None
        return None

    def send_text(self, text):
        form = {
            "text": text, "uid": self._conv_id, "is_encoded": "0", "decodetime": "1",
            "extensions": json.dumps({"clientid": self._clientid()}), "source": self.source,
        }
        resp = self._post(f"{BASE}/new.json", form)
        return Message(id=self._resp_id(resp), outgoing=True, text=text)

    def _upload(self, path):
        import os
        with open(path, "rb") as f:
            raw = f.read()
        fname = os.path.basename(path)
        mime = _MIME.get(os.path.splitext(fname)[1].lower(), "image/png")
        boundary = "----WebKitFormBoundary" + self._clientid()
        body = b"".join([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="blob"; filename="{fname}"\r\n'.encode(),
            f"Content-Type: {mime}\r\n\r\n".encode(),
            raw,
            f"\r\n--{boundary}--\r\n".encode(),
        ])
        h = self._headers()
        h["content-type"] = f"multipart/form-data; boundary={boundary}"
        req = urllib.request.Request(f"{UPLOAD_URL}?source={self.source}&uid={self._conv_id}",
                                     data=body, headers=h, method="POST")
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.loads(r.read().decode("utf-8", "replace"))
        return resp.get("fid") or resp.get("fidstr")

    def send_image(self, path):
        fid = self._upload(path)
        if not fid:
            raise RuntimeError("upload failed")
        form = {
            "fids": fid, "text": "分享图片", "uid": self._conv_id, "media_type": "1",
            "extensions": json.dumps({"clientid": self._clientid()}), "source": self.source,
        }
        resp = self._post(f"{BASE}/new.json", form)
        return Message(id=self._resp_id(resp), outgoing=True, image_ref=str(fid))
