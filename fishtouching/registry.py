# -*- coding: utf-8 -*-
"""Provider 注册表：provider 模块导入时通过 @register 自动登记。"""

_PROVIDERS = {}


def register(cls):
    """类装饰器：把一个 Provider 子类登记进注册表。"""
    _PROVIDERS[cls.name] = cls
    return cls


def available():
    """返回 {name: ProviderClass}。"""
    return dict(_PROVIDERS)


def get(name):
    return _PROVIDERS.get(name)
