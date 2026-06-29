# -*- coding: utf-8 -*-
"""伪装主题：决定消息和"假填充行"长什么样。

未来可加更多主题（pytest 输出、docker 日志、ssh 会话…），
通过 register_theme 注册，配置里选用。
"""

import time
import random

_THEMES = {}


def register_theme(name):
    def deco(cls):
        _THEMES[name] = cls
        return cls
    return deco


def get_theme(name):
    cls = _THEMES.get(name) or _THEMES.get("buildlog")
    return cls()


def available_themes():
    return list(_THEMES)


class Disguise:
    """伪装主题基类。"""
    name = "base"

    def render(self, kind: str, text: str) -> str:
        """把一条消息渲染成一行（kind: recv/sent/sys）。"""
        raise NotImplementedError

    def fake_line(self, i: int) -> str:
        """老板键模式下的一行假填充内容。"""
        raise NotImplementedError


@register_theme("buildlog")
class BuildLogDisguise(Disguise):
    name = "buildlog"

    MODULES = ["core", "auth", "cache", "router", "worker", "db", "queue",
               "sync", "io", "net", "pool", "task", "vendor", "build"]
    MSGS = ["compiled module", "resolved deps", "cache hit", "flush ok",
            "heartbeat", "gc pause 3ms", "batch committed", "warm up done",
            "checkpoint saved", "reload config", "ack received", "ping 12ms"]

    def render(self, kind, text):
        t = time.strftime("%H:%M:%S")
        text = text.replace("\r", " ").replace("\n", " ⏎ ")
        if kind == "recv":
            return f"{t} [INFO ] worker  recv  {text}"
        if kind == "sent":
            return f"{t} [DEBUG] worker  push  {text}"
        return f"{t} [WARN ] system  {text}"

    def fake_line(self, i):
        t = time.strftime("%H:%M:%S")
        lvl = random.choice(["INFO", "INFO", "INFO", "DEBUG", "WARN"])
        return (f"{t} [{lvl:5}] {random.choice(self.MODULES):7} "
                f"#{1000 + i % 900:<4} {random.choice(self.MSGS)}")
