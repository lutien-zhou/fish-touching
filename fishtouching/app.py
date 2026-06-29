# -*- coding: utf-8 -*-
"""核心 TUI 引擎：伪装界面 / 老板键 / 输入编辑 / 图片预览，驱动任意 provider。"""

import curses
import locale
import time
import threading
import collections

from . import config
from . import registry
from . import proxy
from .disguise import get_theme

# 触发 provider 们自注册
from . import providers  # noqa: F401


class App:
    def __init__(self, provider, disguise):
        self.provider = provider
        self.disguise = disguise
        self.lines = collections.deque(maxlen=1000)   # (kind, text)
        self.lock = threading.Lock()
        self.seen = set()
        self.img_refs = []        # 图片引用，对应 [图片#N]
        self.status = "starting..."
        self.port = None
        self._first = True

    # ---------- 消息 ----------
    def add_line(self, kind, text):
        with self.lock:
            self.lines.append((kind, text))

    def _local_url(self, n):
        return f"http://127.0.0.1:{self.port}/i/{n}"

    def _display(self, msg):
        s = ""
        if msg.quote is not None:
            s += f"[回复:{msg.quote}] "
        if msg.image_ref:
            self.img_refs.append(msg.image_ref)
            s += f"[图片#{len(self.img_refs)}] {self._local_url(len(self.img_refs))}"
        else:
            s += msg.text
        return s

    def ingest(self, messages):
        fresh = []
        for m in messages:
            if m.id is None or m.id in self.seen:
                continue
            self.seen.add(m.id)
            fresh.append(m)
        if self._first:
            fresh = fresh[-6:]      # 首次只显示最近几条历史
            self._first = False
        for m in fresh:
            self.add_line("sent" if m.outgoing else "recv", self._display(m))

    def poller(self):
        while True:
            try:
                self.ingest(self.provider.fetch())
                self.status = f"ok  poll@{time.strftime('%H:%M:%S')}"
            except Exception as e:
                self.status = f"err: {e.__class__.__name__}（凭证可能过期）"
            time.sleep(self.provider.poll_interval)

    def resolve_image(self, n):
        if 1 <= n <= len(self.img_refs):
            return self.provider.resolve_image(self.img_refs[n - 1])
        return None

    # ---------- 命令 ----------
    def _open_image(self, idx):
        import subprocess
        import sys
        url = self._local_url(idx)
        cmd = "open" if sys.platform == "darwin" else "xdg-open"
        subprocess.Popen([cmd, url])

    def handle_command(self, text):
        """返回 'switch' 表示要切换会话；True 已处理；False 未知命令。"""
        if text == "/switch":
            return "switch"
        if text == "/o" or text.startswith("/o "):
            if not self.img_refs:
                self.add_line("sys", "还没有图片")
            else:
                arg = text[3:].strip()
                idx = int(arg) if arg.isdigit() else len(self.img_refs)
                if 1 <= idx <= len(self.img_refs):
                    self._open_image(idx)
                    self.add_line("sys", f"已在浏览器打开 图片#{idx}")
                else:
                    self.add_line("sys", f"没有 图片#{idx}（共 {len(self.img_refs)} 张）")
            return True
        if text.startswith("/img "):
            self._send_image(text[len("/img "):].strip())
            return True
        if text in ("/v", "/p"):
            p = _clipboard_to_file()
            if p:
                self._send_image(p)
            else:
                self.add_line("sys", "剪贴板里没有图片")
            return True
        return False

    def _send_image(self, path):
        if not self.provider.can_send_image:
            self.add_line("sys", f"{self.provider.display_name} 不支持发图")
            return
        import os
        path = os.path.expanduser(path)

        def _do():
            try:
                self.provider.send_image(path)
            except Exception as e:
                self.add_line("sys", f"[send image failed] {e}")
        threading.Thread(target=_do, daemon=True).start()

    def _send_text(self, text):
        def _do():
            try:
                self.provider.send_text(text)
            except Exception as e:
                self.add_line("sys", f"[send failed] {e}")
        threading.Thread(target=_do, daemon=True).start()

    # ---------- 服务 ----------
    def start_services(self):
        self.port = proxy.start_proxy(self.resolve_image)
        threading.Thread(target=self.poller, daemon=True).start()

    # ---------- 会话切换时清空 ----------
    def reset_for_new_conversation(self):
        self.seen = set()
        self.img_refs = []
        self._first = True
        with self.lock:
            self.lines.clear()

    # ---------- curses 主循环 ----------
    def run_ui(self):
        return curses.wrapper(self._loop)

    def _loop(self, stdscr):
        curses.curs_set(1)
        stdscr.nodelay(True)
        stdscr.keypad(True)
        try:
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_GREEN, -1)
            curses.init_pair(2, curses.COLOR_CYAN, -1)
            curses.init_pair(3, curses.COLOR_YELLOW, -1)
        except Exception:
            pass

        inp = ""
        cur = 0
        boss = False
        tick = 0

        while True:
            h, w = stdscr.getmaxyx()
            stdscr.erase()

            if boss:
                try:
                    curses.curs_set(0)
                except Exception:
                    pass
                for row in range(h):
                    try:
                        stdscr.addnstr(row, 0, self.disguise.fake_line(tick + row), w - 1)
                    except curses.error:
                        pass
            else:
                try:
                    curses.curs_set(1)
                except Exception:
                    pass
                with self.lock:
                    shown = list(self.lines)[-(h - 2):]
                for idx, (kind, text) in enumerate(shown):
                    color = curses.color_pair(2) if kind == "recv" else (
                            curses.color_pair(1) if kind == "sent" else curses.color_pair(3))
                    try:
                        stdscr.addnstr(idx, 0, self.disguise.render(kind, text), w - 1, color)
                    except curses.error:
                        pass
                try:
                    bar = f" {self.status}  (Esc=hide  Ctrl-C=quit) "
                    stdscr.addnstr(h - 2, 0, bar.ljust(w - 1), w - 1, curses.A_REVERSE)
                except curses.error:
                    pass
                try:
                    stdscr.addnstr(h - 1, 0, "> " + inp, w - 1)
                except curses.error:
                    pass
                try:
                    stdscr.move(h - 1, min(2 + _dwidth(inp[:cur]), w - 1))
                except curses.error:
                    pass

            stdscr.refresh()

            try:
                ch = stdscr.get_wch()
            except curses.error:
                ch = None
            except KeyboardInterrupt:
                return None

            if ch is None:
                tick += 1
                time.sleep(0.05)
                continue

            if ch == "\x1b" or ch == 27:           # Esc 老板键
                boss = not boss
                continue
            if boss:
                continue

            if ch in (curses.KEY_BACKSPACE, 127, 8, "\x7f", "\b"):
                if cur > 0:
                    inp = inp[:cur - 1] + inp[cur:]
                    cur -= 1
            elif ch == curses.KEY_DC:
                if cur < len(inp):
                    inp = inp[:cur] + inp[cur + 1:]
            elif ch == curses.KEY_LEFT:
                cur = max(0, cur - 1)
            elif ch == curses.KEY_RIGHT:
                cur = min(len(inp), cur + 1)
            elif ch in (curses.KEY_HOME, 1, "\x01"):
                cur = 0
            elif ch in (curses.KEY_END, 5, "\x05"):
                cur = len(inp)
            elif ch in (curses.KEY_ENTER, 10, 13, "\n", "\r"):
                text = inp.strip()
                inp = ""
                cur = 0
                if text.startswith("/"):
                    r = self.handle_command(text)
                    if r == "switch":
                        return "switch"
                    if r is False:
                        self.add_line("sys", f"未知命令: {text}")
                elif text:
                    self._send_text(text)
            elif isinstance(ch, str) and ch.isprintable():
                inp = inp[:cur] + ch + inp[cur:]
                cur += 1


# ----------------------------- 工具 -----------------------------
def _dwidth(s):
    import unicodedata
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in s)


def _clipboard_to_file():
    """macOS：把剪贴板图片存成临时 PNG，返回路径或 None。"""
    import sys
    if sys.platform != "darwin":
        return None
    import subprocess
    import tempfile
    import os
    tmp = os.path.join(tempfile.gettempdir(), "ft_clip.png")
    script = [
        "osascript",
        "-e", "set thePic to (the clipboard as «class PNGf»)",
        "-e", f'set fp to open for access POSIX file "{tmp}" with write permission',
        "-e", "set eof fp to 0",
        "-e", "write thePic to fp",
        "-e", "close access fp",
    ]
    try:
        r = subprocess.run(script, capture_output=True, text=True, timeout=10)
    except Exception:
        return None
    if r.returncode == 0 and os.path.isfile(tmp) and os.path.getsize(tmp) > 0:
        return tmp
    return None


# ----------------------------- 启动流程 -----------------------------
def _select_provider():
    provs = registry.available()
    if not provs:
        print("没有可用的 provider。")
        return None
    if len(provs) == 1:
        return next(iter(provs.values()))
    # 多个时：优先上次用的，否则让用户选
    last = config.app_load().get("provider")
    if last in provs:
        return provs[last]
    names = list(provs)
    print("选择一个聊天后端：")
    for i, n in enumerate(names, 1):
        print(f"  {i}. {provs[n].display_name}")
    while True:
        s = input("序号 > ").strip()
        if s.isdigit() and 1 <= int(s) <= len(names):
            return provs[names[int(s) - 1]]
        print("无效，重输。")


def _pick_conversation(provider):
    try:
        convs = provider.list_conversations()
    except Exception as e:
        print("获取会话列表失败：", e)
        return False
    if not convs:
        print("没有会话。")
        return False
    print("\n选择聊天对象：")
    for i, c in enumerate(convs, 1):
        badge = f"  ({c.badge} 未读)" if c.badge else ""
        print(f"  {i:>2}. {c.name}{badge}")
    while True:
        s = input("输入序号 > ").strip()
        if s.isdigit() and 1 <= int(s) <= len(convs):
            c = convs[int(s) - 1]
            provider.set_conversation(c.id)
            print(f"已选择：{c.name}")
            return True
        print("序号无效，重输。")


def main():
    locale.setlocale(locale.LC_ALL, "")

    cls = _select_provider()
    if not cls:
        raise SystemExit(1)
    provider = cls()
    config.app_update(provider=provider.name)

    # 登录
    if not provider.is_authenticated():
        print(f"{provider.display_name}：未登录或登录态失效，开始登录…\n")
        if not provider.login():
            raise SystemExit("登录失败。")

    # 选会话
    if not provider.conversation_id:
        if not _pick_conversation(provider):
            raise SystemExit("未选择会话。")

    disguise = get_theme(config.app_load().get("theme", "buildlog"))
    app = App(provider, disguise)
    app.start_services()

    try:
        while True:
            result = app.run_ui()
            if result == "switch":
                if _pick_conversation(provider):
                    app.reset_for_new_conversation()
                continue
            break
    except KeyboardInterrupt:
        pass
