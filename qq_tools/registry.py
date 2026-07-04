# -*- coding: utf-8 -*-
"""LLM 工具注册表：管理工具定义、注册和分发。"""
from typing import Dict, Callable
from astrbot.api.star import Star


class ToolRegistry:
    def __init__(self, star: Star):
        self._star = star
        self._defs: Dict[str, dict] = {}
        self._handlers: Dict[str, Callable] = {}

    def register(self, name: str, description: str,
                 params: dict, handler: Callable, config_key: str = ''):
        self._defs[name] = {
            'name': name, 'desc': description,
            'params': params, 'cfg': config_key,
        }
        self._handlers[name] = handler

    def register_all(self, config: dict):
        """向 AstrBot 注册所有未禁用的工具。"""
        from astrbot.core.star.star_tools import StarTools
        for name, defn in self._defs.items():
            if defn['cfg'] and not config.get(defn['cfg'], True):
                continue
            tool = StarTools(
                name=defn['name'],
                description=defn['desc'],
                parameters=defn['params'],
                handler=self._handlers[name],
            )
            self._star.context.register_tool(tool)

    async def dispatch(self, tool_name: str, **kwargs) -> dict:
        handler = self._handlers.get(tool_name)
        if not handler:
            return {'ok': False, 'detail': f'未知工具: {tool_name}'}
        return await handler(**kwargs)
