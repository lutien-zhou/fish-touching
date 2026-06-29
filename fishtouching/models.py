# -*- coding: utf-8 -*-
"""核心数据模型：provider 与 core 之间传递的通用结构。"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Message:
    """一条聊天消息（provider 产出，core 负责渲染）。

    - id:        会话内稳定唯一 id，core 用它去重
    - outgoing:  True 表示自己发的
    - text:      正文（图片消息可为空）
    - image_ref: 若是图片，给一个 provider 自己能解析的不透明引用，core 交给图片代理
    - quote:     若是引用/回复，被引用内容的简短摘要
    """
    id: str
    outgoing: bool
    text: str = ""
    image_ref: Optional[str] = None
    quote: Optional[str] = None


@dataclass
class Conversation:
    """一个会话/联系人。"""
    id: str
    name: str
    badge: int = 0      # 未读数等角标
