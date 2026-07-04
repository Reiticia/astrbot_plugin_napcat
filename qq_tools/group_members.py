# -*- coding: utf-8 -*-
"""群管理 — 成员控制：禁言、踢人、名片、管理员、头衔。"""


async def set_group_ban(client, group_id: int, user_id: str, duration: int) -> dict:
    await client.call_action('set_group_ban',
        group_id=group_id, user_id=int(user_id), duration=duration)
    label = f'禁言 {duration} 秒' if duration > 0 else '解除禁言'
    return {'ok': True, 'detail': f'已{label} {user_id}'}


async def set_group_kick(client, group_id: int, user_id: str,
                         reject_add_request: bool = False) -> dict:
    await client.call_action('set_group_kick',
        group_id=group_id, user_id=int(user_id),
        reject_add_request=reject_add_request)
    return {'ok': True, 'detail': f'已移出 {user_id}'}


async def set_group_card(client, group_id: int, user_id: str, card: str) -> dict:
    await client.call_action('set_group_card',
        group_id=group_id, user_id=int(user_id), card=card)
    return {'ok': True, 'detail': '名片已修改'}


async def set_group_admin(client, group_id: int, user_id: str, enable: bool) -> dict:
    await client.call_action('set_group_admin',
        group_id=group_id, user_id=int(user_id), enable=enable)
    return {'ok': True, 'detail': f'已{"设为" if enable else "取消"}管理员'}


async def set_group_special_title(client, group_id: int, user_id: str,
                                  special_title: str) -> dict:
    await client.call_action('set_group_special_title',
        group_id=group_id, user_id=int(user_id),
        special_title=special_title)
    return {'ok': True, 'detail': '头衔已设置'}
