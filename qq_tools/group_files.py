# -*- coding: utf-8 -*-
"""群管理 — 群文件和公告。"""
import json
from .utils import truncate


async def send_group_notice(client, group_id: int, content: str) -> dict:
    await client.call_action('_send_group_notice',
        group_id=group_id, content=content)
    return {'ok': True, 'detail': '公告已发布'}


async def delete_group_notice(client, group_id: int, notice_id: str) -> dict:
    await client.call_action('_del_group_notice',
        group_id=group_id, notice_id=notice_id)
    return {'ok': True, 'detail': '公告已删除'}


async def get_group_notice_list(client, group_id: int) -> dict:
    data = await client.call_action('_get_group_notice', group_id=group_id)
    return {'ok': True, 'result': truncate(json.dumps(data, ensure_ascii=False, indent=2))}


async def list_group_files(client, group_id: int) -> dict:
    data = await client.call_action('get_group_file_system_info', group_id=group_id)
    return {'ok': True, 'result': truncate(json.dumps(data, ensure_ascii=False, indent=2))}


async def delete_group_file(client, group_id: int, file_id: str, busid: int = 102) -> dict:
    await client.call_action('delete_group_file',
        group_id=group_id, file_id=file_id, busid=busid)
    return {'ok': True, 'detail': '文件已删除'}


async def upload_group_file(client, group_id: int, file_path: str, name: str = '') -> dict:
    await client.call_action('upload_group_file',
        group_id=group_id, file=file_path, name=name)
    return {'ok': True, 'detail': '文件已上传'}


async def create_group_file_folder(client, group_id: int, name: str) -> dict:
    await client.call_action('create_group_file_folder',
        group_id=group_id, name=name)
    return {'ok': True, 'detail': f'文件夹「{name}」已创建'}


async def delete_group_folder(client, group_id: int, folder_id: str) -> dict:
    await client.call_action('delete_group_folder',
        group_id=group_id, folder_id=folder_id)
    return {'ok': True, 'detail': '文件夹已删除'}
