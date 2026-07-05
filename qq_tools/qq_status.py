# -*- coding: utf-8 -*-
"""QQ 在线状态工具：设置、查询、娱乐状态列表。"""
from .constants import STATUS_PRESETS


async def update_qq_status(status_ctrl, status: str, duration_minutes: int = 30) -> dict:
    return await status_ctrl.set(status, duration_minutes)


def get_qq_status(status_ctrl) -> dict:
    return status_ctrl.describe()


async def get_fun_status_list() -> dict:
    items = [f'{k}: {v[0]}' for k, v in STATUS_PRESETS.items() if v[2] != 0]
    return {'ok': True, 'result': '可用娱乐状态：\n' + '\n'.join(items)}
