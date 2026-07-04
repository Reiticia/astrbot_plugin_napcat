# -*- coding: utf-8 -*-
"""消息操作：发送消息、戳一戳、点赞。"""


async def send_message(client, target_id: str, message: str, chat_type: str = 'group') -> dict:
    action = 'send_group_msg' if chat_type == 'group' else 'send_private_msg'
    key = 'group_id' if chat_type == 'group' else 'user_id'
    await client.call_action(action, **{key: int(target_id), 'message': message})
    return {'ok': True, 'detail': '已发送'}


async def send_poke(client, target_qq: str) -> dict:
    await client.call_action('send_poke', user_id=int(target_qq))
    return {'ok': True, 'detail': '已发送戳一戳'}


async def send_like(client, user_id: str, times: int = 1) -> dict:
    for _ in range(min(times, 20)):
        await client.call_action('send_like', user_id=int(user_id), times=1)
    return {'ok': True, 'detail': f'已点赞 {min(times, 20)} 次'}
