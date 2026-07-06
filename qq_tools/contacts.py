# -*- coding: utf-8 -*-
"""联系人：搜索、列表、群成员身份。"""
from .utils import truncate


async def search_contacts(client, contacts_cache: dict, keyword: str,
                          search_type: str = 'all', limit: int = 2000) -> dict:
    hits = []
    if search_type in ('all', 'group'):
        for g in contacts_cache.get('groups', []):
            if keyword.lower() in str(g.get('group_name', '')).lower() or keyword == str(g.get('group_id', '')):
                hits.append(f"群｜{g.get('group_name')}（{g.get('group_id')}）")
    if search_type in ('all', 'friend'):
        for f in contacts_cache.get('friends', []):
            name = f"{f.get('remark', '')}{f.get('nickname', '')}"
            if keyword.lower() in name.lower() or keyword == str(f.get('user_id', '')):
                hits.append(f"好友｜{f.get('nickname')}（{f.get('user_id')}）")
    return {'ok': True, 'result': truncate('\n'.join(hits) if hits else '未找到匹配的联系人', limit)}


async def list_contacts(contacts_cache: dict, contact_type: str = 'all', limit: int = 2000) -> dict:
    lines = []
    if contact_type in ('all', 'group'):
        for g in contacts_cache.get('groups', []):
            lines.append(f"群｜{g.get('group_name')}（{g.get('group_id')}）")
    if contact_type in ('all', 'friend'):
        for f in contacts_cache.get('friends', []):
            lines.append(f"好友｜{f.get('nickname')}（{f.get('user_id')}）")
    return {'ok': True, 'result': truncate('\n'.join(lines) if lines else '列表为空', limit)}


async def get_user_group_role(client, user_id: str, group_id: str) -> dict:
    info = await client.call_action('get_group_member_info',
                                     group_id=int(group_id), user_id=int(user_id))
    role = {'owner': '群主', 'admin': '管理员'}.get(info.get('role', ''), '成员')
    return {'ok': True, 'result': f'{user_id} 在本群是：{role}'}
