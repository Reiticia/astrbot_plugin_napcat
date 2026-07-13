# -*- coding: utf-8 -*-
"""消息操作：发送消息、戳一戳、点赞。"""
import re

from astrbot.api.message_components import At, Face, Plain

# `<mention id="xxx"/>` / `[At: xxx]` → At 组件
_MENTION_XML_RE = re.compile(
    r"""<mention\s+id\s*=\s*['"](?P<mention_xml>[^'"]+)['"]\s*/?>""",
    re.IGNORECASE,
)
_MENTION_NATIVE_RE = re.compile(
    r"\[At:\s*(?P<mention_native>\d+)\]", re.IGNORECASE
)
# `<face id="xxx"/>` / `[Face: xxx]` → Face 组件
_FACE_XML_RE = re.compile(
    r"""<face\s+id\s*=\s*['"]?(?P<face_id>\d+)['"]?\s*/?>""",
    re.IGNORECASE,
)
_FACE_NATIVE_RE = re.compile(
    r"\[Face:\s*(?P<face_native>\d+)\]", re.IGNORECASE
)
# `<quote id="xxx"/>` / `[Quote: xxx]` → 移除（send_message 场景下引用无意义）
_QUOTE_RE = re.compile(
    r"""<quote\s+id\s*=\s*['"][^'"]+['"]\s*/?>|\[Quote:\s*[^\]]+\]""", re.IGNORECASE
)

# 合并后的标签匹配正则（用于迭代匹配）
_TAG_RE = re.compile(
    "|".join([
        _MENTION_XML_RE.pattern,
        _MENTION_NATIVE_RE.pattern,
        _FACE_XML_RE.pattern,
        _FACE_NATIVE_RE.pattern,
    ]),
    re.IGNORECASE,
)


def parse_components(text: str) -> list:
    """将消息文本中的 At/Face 控制标签转为 AstrBot 消息组件列表。

    处理流程：
    1. 移除 <quote/> 标签（工具发送场景下无需引用）。
    2. 用合并正则依次匹配所有标签，标签之间的内容作 Plain 文本，
       匹配到的 At/Face 标签转为对应组件对象。
    3. 纯文本（无任何标签）原样返回。
    """
    if not text:
        return [Plain(text="")]

    # 先移除 quote 标签
    text = _QUOTE_RE.sub("", text)

    components: list = []
    last_end = 0

    for m in _TAG_RE.finditer(text):
        if m.start() > last_end:
            segment = text[last_end : m.start()]
            if segment:
                components.append(Plain(text=segment))

        gd = m.groupdict()
        if gd.get("mention_xml") is not None:
            components.append(At(qq=gd["mention_xml"]))
        elif gd.get("mention_native") is not None:
            components.append(At(qq=gd["mention_native"]))
        elif gd.get("face_id") is not None:
            components.append(Face(id=int(gd["face_id"])))
        elif gd.get("face_native") is not None:
            components.append(Face(id=int(gd["face_native"])))

        last_end = m.end()

    if last_end < len(text):
        tail = text[last_end:]
        if tail:
            components.append(Plain(text=tail))

    return components if components else [Plain(text=text)]


async def send_message(client, target_id: str, message: str, chat_type: str = 'group') -> dict:
    action = 'send_group_msg' if chat_type == 'group' else 'send_private_msg'
    key = 'group_id' if chat_type == 'group' else 'user_id'
    await client.call_action(action, **{key: int(target_id), 'message': message})
    return {'ok': True, 'detail': '已发送'}


async def send_poke(client, target_qq: str, group_id: int = 0) -> dict:
    """发送戳一戳。group_id > 0 时为群内戳一戳，否则为私聊戳一戳。"""
    kwargs = {'user_id': int(target_qq)}
    if group_id > 0:
        kwargs['group_id'] = group_id
    await client.call_action('send_poke', **kwargs)
    ctx = f'群 {group_id} 中' if group_id > 0 else '私聊'
    return {'ok': True, 'detail': f'已向 {target_qq} 发送戳一戳（{ctx}）'}


async def send_like(client, user_id: str, times: int = 1) -> dict:
    for _ in range(min(times, 20)):
        await client.call_action('send_like', user_id=int(user_id), times=1)
    return {'ok': True, 'detail': f'已点赞 {min(times, 20)} 次'}