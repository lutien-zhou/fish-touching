# -*- coding: utf-8 -*-
"""配置与凭证存取。

所有数据放在 ~/.fish-touching/ 下，按 provider 命名空间隔离：
  ~/.fish-touching/app.json            # 框架级配置（如上次用的 provider）
  ~/.fish-touching/<provider>/config.json
  ~/.fish-touching/<provider>/<secret> # 凭证文件（权限 600）
"""

import os
import json

ROOT = os.path.expanduser("~/.fish-touching")


class Store:
    """某个命名空间（通常是一个 provider）的配置/凭证存取。"""

    def __init__(self, namespace: str):
        self.namespace = namespace
        self.dir = os.path.join(ROOT, namespace)

    def _ensure(self):
        os.makedirs(self.dir, exist_ok=True)

    # —— JSON 配置 ——
    @property
    def _config_path(self):
        return os.path.join(self.dir, "config.json")

    def load(self) -> dict:
        try:
            with open(self._config_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def save(self, cfg: dict):
        self._ensure()
        with open(self._config_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)

    def update(self, **kw) -> dict:
        cfg = self.load()
        cfg.update(kw)
        self.save(cfg)
        return cfg

    # —— 凭证（任意字符串，如 cookie / token）——
    def read_secret(self, name: str):
        try:
            s = open(os.path.join(self.dir, name), encoding="utf-8").read().strip()
            return s or None
        except Exception:
            return None

    def write_secret(self, name: str, value: str):
        self._ensure()
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(value)
        os.chmod(path, 0o600)


# 框架级配置
_app = Store("_app")


def app_load() -> dict:
    return _app.load()


def app_update(**kw) -> dict:
    return _app.update(**kw)
