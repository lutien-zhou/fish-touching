# -*- coding: utf-8 -*-
"""Provider 接口：所有聊天后端都实现它，core 只跟这个接口打交道。

实现一个新后端 = 写一个 Provider 子类 + 用 @register 注册即可。
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

from .models import Message, Conversation


class Provider(ABC):
    # —— 元信息（子类覆盖）——
    name: str = "base"              # 唯一标识，如 "weibo"
    display_name: str = "Base"      # 展示名
    can_send_image: bool = False    # 是否支持发图
    poll_interval: int = 5          # 轮询间隔（秒）

    # —— 登录态 ——
    @abstractmethod
    def is_authenticated(self) -> bool:
        """当前凭证是否有效。"""

    @abstractmethod
    def login(self) -> bool:
        """交互式登录（在进入 TUI 之前调用，可自由 print/input）。成功返回 True。"""

    # —— 会话 ——
    @abstractmethod
    def list_conversations(self) -> List[Conversation]:
        """列出可选的会话/联系人。"""

    @abstractmethod
    def set_conversation(self, conv_id: str) -> None:
        """设置当前活跃会话。"""

    @property
    def conversation_id(self) -> Optional[str]:
        """当前活跃会话 id（没有则 None）。"""
        return getattr(self, "_conv_id", None)

    # —— 消息收发 ——
    @abstractmethod
    def fetch(self) -> List[Message]:
        """拉取当前会话最近的消息（含已读过的，core 会按 id 去重）。"""

    @abstractmethod
    def send_text(self, text: str) -> None:
        """发送文字。"""

    def send_image(self, path: str) -> None:
        """发送图片（可选能力，can_send_image=True 时实现）。"""
        raise NotImplementedError

    def resolve_image(self, ref: str) -> Tuple[bytes, str]:
        """把图片引用解析成 (二进制数据, content_type)，供本地预览代理使用。"""
        raise NotImplementedError
