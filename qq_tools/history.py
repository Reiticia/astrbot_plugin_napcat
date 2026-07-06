# -*- coding: utf-8 -*-
"""历史消息：群聊和私聊消息回溯。"""
import json
from .utils import truncate


async def get_group_msg_history(client, group_id: int, count: int = 20, limit: int = 2000) -> dict:
    data = await client.call_action('get_group_msg_history', group_id=group_id, count=count)
    return {'ok': True, 'result': truncate(json.dumps(data, ensure_ascii=False, indent=2), limit)}


async def get_friend_msg_history(client, user_id: str, count: int = 20, limit: int = 2000) -> dict:
    data = await client.call_action('get_friend_msg_history', user_id=int(user_id), count=count)
    return {'ok': True, 'result': truncate(json.dumps(data, ensure_ascii=False, indent=2), limit)}
