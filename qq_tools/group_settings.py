# -*- coding: utf-8 -*-
"""群管理 — 信息查询与群设置。"""
import json
from .utils import truncate


async def set_group_whole_ban(client, group_id: int, enable: bool) -> dict:
    await client.call_action('set_group_whole_ban', group_id=group_id, enable=enable)
    return {'ok': True, 'detail': '已开启全体禁言' if enable else '已关闭全体禁言'}


async def set_group_name(client, group_id: int, group_name: str) -> dict:
    await client.call_action('set_group_name', group_id=group_id, group_name=group_name)
    return {'ok': True, 'detail': '群名已修改'}


async def send_group_sign(client, group_id: int) -> dict:
    await client.call_action('send_group_sign', group_id=group_id)
    return {'ok': True, 'detail': '打卡成功'}


async def get_group_members_info(client, group_id: int, limit: int = 2000) -> dict:
    data = await client.call_action('get_group_member_list', group_id=group_id)
    return {'ok': True, 'result': truncate(json.dumps(data, ensure_ascii=False, indent=2), limit)}


async def get_group_honor_info(client, group_id: int, type: str = 'all', limit: int = 2000) -> dict:
    data = await client.call_action('get_group_honor_info', group_id=group_id, type=type)
    return {'ok': True, 'result': truncate(json.dumps(data, ensure_ascii=False, indent=2), limit)}


async def get_group_shut_list(client, group_id: int, limit: int = 2000) -> dict:
    members = await client.call_action('get_group_member_list', group_id=group_id)
    shut = [m for m in members if m.get('shut_up_timestamp', 0) > 0]
    return {'ok': True, 'result': truncate(
        json.dumps(shut, ensure_ascii=False, indent=2), limit) if shut else '没有被禁言的成员'}


async def get_group_at_all_remain(client, group_id: int) -> dict:
    data = await client.call_action('get_group_at_all_remain', group_id=group_id)
    return {'ok': True, 'result': json.dumps(data, ensure_ascii=False)}
