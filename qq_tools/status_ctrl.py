# -*- coding: utf-8 -*-
"""QQ 在线状态控制器：设置状态、定时恢复。"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from .constants import STATUS_PRESETS


class StatusController:
    def __init__(self, client_getter):
        self._get_client = client_getter
        self._current = 'online'
        self._name = '在线'
        self._end_time: Optional[datetime] = None
        self._timer: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    async def set(self, key: str, minutes: int) -> dict:
        info = STATUS_PRESETS.get(key)
        if not info:
            return {'ok': False, 'detail': f'无效状态: {key}'}
        name, code, ext = info
        client = self._get_client()
        async with self._lock:
            await client.call_action('set_online_status',
                                     status=code, ext_status=ext, battery_status=0)
            if key == 'online':
                self._cancel_timer()
                self._current, self._name, self._end_time = 'online', '在线', None
                return {'ok': True, 'detail': '已恢复在线'}
            self._current, self._name = key, name
            self._end_time = datetime.now() + timedelta(minutes=minutes)
            self._cancel_timer()
            self._timer = asyncio.create_task(self._auto_restore(minutes))
            return {'ok': True, 'detail': f'已设为「{name}」({minutes}分钟后自动恢复)'}

    def describe(self) -> dict:
        if self._current == 'online':
            return {'ok': True, 'result': '当前在线'}
        if self._end_time and self._end_time > datetime.now():
            remain = int((self._end_time - datetime.now()).total_seconds() / 60)
            return {'ok': True, 'result': f'当前「{self._name}」，约 {remain} 分钟后恢复'}
        return {'ok': True, 'result': f'当前「{self._name}」'}

    def _cancel_timer(self):
        if self._timer and not self._timer.done():
            self._timer.cancel()

    async def _auto_restore(self, delay_min: int):
        try:
            await asyncio.sleep(delay_min * 60)
            client = self._get_client()
            await client.call_action('set_online_status',
                                     status=10, ext_status=0, battery_status=0)
            async with self._lock:
                self._current, self._name, self._end_time = 'online', '在线', None
                self._timer = None
        except asyncio.CancelledError:
            pass
