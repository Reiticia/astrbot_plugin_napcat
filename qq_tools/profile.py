# -*- coding: utf-8 -*-
"""QQ 个人资料：昵称、签名、头像。"""
from .utils import resolve_image


async def set_qq_profile(client, nickname: str = '', personal_note: str = '') -> dict:
    kwargs = {}
    if nickname:
        kwargs['nickname'] = nickname
    if personal_note:
        kwargs['personal_note'] = personal_note
    if not kwargs:
        return {'ok': False, 'detail': '请至少提供昵称或签名'}
    await client.call_action('set_qq_profile', **kwargs)
    return {'ok': True, 'detail': '个人资料已更新'}


async def set_qq_avatar(client, file: str) -> dict:
    await client.call_action('set_qq_avatar', file=resolve_image(file))
    return {'ok': True, 'detail': '头像已更新'}
