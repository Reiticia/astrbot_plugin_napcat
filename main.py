# -*- coding: utf-8 -*-
"""
astrbot_plugin_napcat — NapCat 工具
=====================================
入口模块：插件生命周期、工具注册（@filter.llm_tool 装饰器）。

目录结构：
  main.py            入口 & Main 类
  qq_tools/          功能模块包
    registry.py      工具注册表
    ...
"""
import asyncio
from datetime import datetime
from typing import Optional

from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent

from .qq_tools.status_ctrl import StatusController
from .qq_tools import messaging
from .qq_tools import contacts as contacts_mod
from .qq_tools import qq_status as status_mod
from .qq_tools import group_members
from .qq_tools import group_files
from .qq_tools import group_settings
from .qq_tools import voice
from .qq_tools import profile
from .qq_tools import history

PLUGIN_ID = "astrbot_plugin_napcat"


class Main(Star):
    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        self.config = config
        self.client = None
        self.current_group_id = 0
        self.status_ctrl = StatusController(lambda: self.client)

        self._contacts: Optional[dict] = None
        self._contacts_ts: Optional[datetime] = None
        self._contacts_lock = asyncio.Lock()

        logger.info(f'[{PLUGIN_ID}] 已加载')

    # ── 上下文 ──

    def _gid(self) -> int:
        return self.current_group_id

    def _cfg(self) -> dict:
        return self.config or {}

    # ── 联系人缓存 ──

    async def _load_contacts(self) -> dict:
        async with self._contacts_lock:
            now = datetime.now()
            if self._contacts and self._contacts_ts and (now - self._contacts_ts).seconds < 300:
                return self._contacts
            try:
                friends = await self.client.call_action('get_friend_list')
                groups = await self.client.call_action('get_group_list')
                self._contacts = {'friends': friends, 'groups': groups}
                self._contacts_ts = now
            except Exception as e:
                logger.error(f'[{PLUGIN_ID}] 联系人加载失败: {e}')
            return self._contacts or {'friends': [], 'groups': []}

    # ── 消息 ──

    @filter.llm_tool(name="send_message")
    async def send_message(self, event: AstrMessageEvent, target_id: str,
                           message: str, chat_type: str = "group") -> dict:
        self.client = event.bot if isinstance(event, AiocqhttpMessageEvent) else self.client
        return await messaging.send_message(self.client, target_id, message, chat_type)

    @filter.llm_tool(name="send_poke")
    async def send_poke(self, event: AstrMessageEvent, target_qq: str) -> dict:
        self.client = event.bot if isinstance(event, AiocqhttpMessageEvent) else self.client
        return await messaging.send_poke(self.client, target_qq)

    @filter.llm_tool(name="send_like")
    async def send_like(self, event: AstrMessageEvent, user_id: str, times: int = 1) -> dict:
        self.client = event.bot if isinstance(event, AiocqhttpMessageEvent) else self.client
        return await messaging.send_like(self.client, user_id, times)

    # ── 联系人 ──

    @filter.llm_tool(name="search_contacts")
    async def search_contacts(self, event: AstrMessageEvent, keyword: str,
                              search_type: str = "all") -> dict:
        self.client = event.bot if isinstance(event, AiocqhttpMessageEvent) else self.client
        return await contacts_mod.search_contacts(
            self.client, self._contacts or {}, keyword, search_type)

    @filter.llm_tool(name="list_contacts")
    async def list_contacts(self, event: AstrMessageEvent, contact_type: str = "all") -> dict:
        self.client = event.bot if isinstance(event, AiocqhttpMessageEvent) else self.client
        return await contacts_mod.list_contacts(self._contacts or {}, contact_type)

    @filter.llm_tool(name="get_user_group_role")
    async def get_user_group_role(self, event: AstrMessageEvent, user_id: str,
                                  group_id: str) -> dict:
        self.client = event.bot if isinstance(event, AiocqhttpMessageEvent) else self.client
        return await contacts_mod.get_user_group_role(self.client, user_id, group_id)

    # ── QQ 状态 ──

    @filter.llm_tool(name="update_qq_status")
    async def update_qq_status(self, event: AstrMessageEvent, status: str,
                               duration_minutes: int = 30) -> dict:
        self.client = event.bot if isinstance(event, AiocqhttpMessageEvent) else self.client
        return await status_mod.update_qq_status(self.status_ctrl, status, duration_minutes)

    @filter.llm_tool(name="get_qq_status")
    async def get_qq_status(self, event: AstrMessageEvent) -> dict:
        return status_mod.get_qq_status(self.status_ctrl)

    @filter.llm_tool(name="get_fun_status_list")
    async def get_fun_status_list(self, event: AstrMessageEvent) -> dict:
        return await status_mod.get_fun_status_list()

    # ── 群成员控制 ──

    @filter.llm_tool(name="set_group_ban")
    async def set_group_ban(self, event: AstrMessageEvent, user_id: str,
                            duration: int) -> dict:
        self.client = event.bot if isinstance(event, AiocqhttpMessageEvent) else self.client
        self._set_gid(event)
        return await group_members.set_group_ban(self.client, self._gid(), user_id, duration)

    @filter.llm_tool(name="set_group_kick")
    async def set_group_kick(self, event: AstrMessageEvent, user_id: str,
                             reject_add_request: bool = False) -> dict:
        self.client = event.bot if isinstance(event, AiocqhttpMessageEvent) else self.client
        self._set_gid(event)
        return await group_members.set_group_kick(self.client, self._gid(), user_id, reject_add_request)

    @filter.llm_tool(name="set_group_card")
    async def set_group_card(self, event: AstrMessageEvent, user_id: str, card: str) -> dict:
        self.client = event.bot if isinstance(event, AiocqhttpMessageEvent) else self.client
        self._set_gid(event)
        return await group_members.set_group_card(self.client, self._gid(), user_id, card)

    @filter.llm_tool(name="set_group_admin")
    async def set_group_admin(self, event: AstrMessageEvent, user_id: str,
                              enable: bool) -> dict:
        self.client = event.bot if isinstance(event, AiocqhttpMessageEvent) else self.client
        self._set_gid(event)
        return await group_members.set_group_admin(self.client, self._gid(), user_id, enable)

    @filter.llm_tool(name="set_group_special_title")
    async def set_group_special_title(self, event: AstrMessageEvent, user_id: str,
                                      special_title: str) -> dict:
        self.client = event.bot if isinstance(event, AiocqhttpMessageEvent) else self.client
        self._set_gid(event)
        return await group_members.set_group_special_title(self.client, self._gid(), user_id, special_title)

    # ── 群文件 & 公告 ──

    @filter.llm_tool(name="send_group_notice")
    async def send_group_notice(self, event: AstrMessageEvent, content: str) -> dict:
        self.client = event.bot if isinstance(event, AiocqhttpMessageEvent) else self.client
        self._set_gid(event)
        return await group_files.send_group_notice(self.client, self._gid(), content)

    @filter.llm_tool(name="delete_group_notice")
    async def delete_group_notice(self, event: AstrMessageEvent, notice_id: str) -> dict:
        self.client = event.bot if isinstance(event, AiocqhttpMessageEvent) else self.client
        self._set_gid(event)
        return await group_files.delete_group_notice(self.client, self._gid(), notice_id)

    @filter.llm_tool(name="get_group_notice_list")
    async def get_group_notice_list(self, event: AstrMessageEvent) -> dict:
        self.client = event.bot if isinstance(event, AiocqhttpMessageEvent) else self.client
        self._set_gid(event)
        return await group_files.get_group_notice_list(self.client, self._gid())

    @filter.llm_tool(name="list_group_files")
    async def list_group_files(self, event: AstrMessageEvent) -> dict:
        self.client = event.bot if isinstance(event, AiocqhttpMessageEvent) else self.client
        self._set_gid(event)
        return await group_files.list_group_files(self.client, self._gid())

    @filter.llm_tool(name="delete_group_file")
    async def delete_group_file(self, event: AstrMessageEvent, file_id: str,
                                busid: int = 102) -> dict:
        self.client = event.bot if isinstance(event, AiocqhttpMessageEvent) else self.client
        self._set_gid(event)
        return await group_files.delete_group_file(self.client, self._gid(), file_id, busid)

    @filter.llm_tool(name="upload_group_file")
    async def upload_group_file(self, event: AstrMessageEvent, file_path: str,
                                name: str = "") -> dict:
        self.client = event.bot if isinstance(event, AiocqhttpMessageEvent) else self.client
        self._set_gid(event)
        return await group_files.upload_group_file(self.client, self._gid(), file_path, name)

    @filter.llm_tool(name="create_group_file_folder")
    async def create_group_file_folder(self, event: AstrMessageEvent, name: str) -> dict:
        self.client = event.bot if isinstance(event, AiocqhttpMessageEvent) else self.client
        self._set_gid(event)
        return await group_files.create_group_file_folder(self.client, self._gid(), name)

    @filter.llm_tool(name="delete_group_folder")
    async def delete_group_folder(self, event: AstrMessageEvent, folder_id: str) -> dict:
        self.client = event.bot if isinstance(event, AiocqhttpMessageEvent) else self.client
        self._set_gid(event)
        return await group_files.delete_group_folder(self.client, self._gid(), folder_id)

    # ── 群设置 & 查询 ──

    @filter.llm_tool(name="set_group_whole_ban")
    async def set_group_whole_ban(self, event: AstrMessageEvent, enable: bool) -> dict:
        self.client = event.bot if isinstance(event, AiocqhttpMessageEvent) else self.client
        self._set_gid(event)
        return await group_settings.set_group_whole_ban(self.client, self._gid(), enable)

    @filter.llm_tool(name="set_group_name")
    async def set_group_name(self, event: AstrMessageEvent, group_name: str) -> dict:
        self.client = event.bot if isinstance(event, AiocqhttpMessageEvent) else self.client
        self._set_gid(event)
        return await group_settings.set_group_name(self.client, self._gid(), group_name)

    @filter.llm_tool(name="set_group_add_option")
    async def set_group_add_option(self, event: AstrMessageEvent, option: str) -> dict:
        self.client = event.bot if isinstance(event, AiocqhttpMessageEvent) else self.client
        self._set_gid(event)
        return await group_settings.set_group_add_option(self.client, self._gid(), option)

    @filter.llm_tool(name="send_group_sign")
    async def send_group_sign(self, event: AstrMessageEvent) -> dict:
        self.client = event.bot if isinstance(event, AiocqhttpMessageEvent) else self.client
        self._set_gid(event)
        return await group_settings.send_group_sign(self.client, self._gid())

    @filter.llm_tool(name="get_group_members_info")
    async def get_group_members_info(self, event: AstrMessageEvent) -> dict:
        self.client = event.bot if isinstance(event, AiocqhttpMessageEvent) else self.client
        self._set_gid(event)
        return await group_settings.get_group_members_info(self.client, self._gid())

    @filter.llm_tool(name="get_group_honor_info")
    async def get_group_honor_info(self, event: AstrMessageEvent, type: str = "all") -> dict:
        self.client = event.bot if isinstance(event, AiocqhttpMessageEvent) else self.client
        self._set_gid(event)
        return await group_settings.get_group_honor_info(self.client, self._gid(), type)

    @filter.llm_tool(name="get_group_shut_list")
    async def get_group_shut_list(self, event: AstrMessageEvent) -> dict:
        self.client = event.bot if isinstance(event, AiocqhttpMessageEvent) else self.client
        self._set_gid(event)
        return await group_settings.get_group_shut_list(self.client, self._gid())

    @filter.llm_tool(name="get_group_at_all_remain")
    async def get_group_at_all_remain(self, event: AstrMessageEvent) -> dict:
        self.client = event.bot if isinstance(event, AiocqhttpMessageEvent) else self.client
        self._set_gid(event)
        return await group_settings.get_group_at_all_remain(self.client, self._gid())

    # ── AI 语音 ──

    @filter.llm_tool(name="get_ai_characters")
    async def get_ai_characters(self, event: AstrMessageEvent) -> dict:
        self.client = event.bot if isinstance(event, AiocqhttpMessageEvent) else self.client
        return await voice.get_ai_characters(self.client)

    @filter.llm_tool(name="send_ai_voice")
    async def send_ai_voice(self, event: AstrMessageEvent, text: str,
                            character_id: str = "") -> dict:
        self.client = event.bot if isinstance(event, AiocqhttpMessageEvent) else self.client
        self._set_gid(event)
        return await voice.send_ai_voice(self.client, self._cfg(), self._gid(), text, character_id)

    # ── 个人资料 ──

    @filter.llm_tool(name="set_qq_profile")
    async def set_qq_profile(self, event: AstrMessageEvent, nickname: str = "",
                             personal_note: str = "") -> dict:
        self.client = event.bot if isinstance(event, AiocqhttpMessageEvent) else self.client
        return await profile.set_qq_profile(self.client, nickname, personal_note)

    @filter.llm_tool(name="set_qq_avatar")
    async def set_qq_avatar(self, event: AstrMessageEvent, file: str) -> dict:
        self.client = event.bot if isinstance(event, AiocqhttpMessageEvent) else self.client
        return await profile.set_qq_avatar(self.client, file)

    # ── 历史消息 ──

    @filter.llm_tool(name="get_group_msg_history")
    async def get_group_msg_history(self, event: AstrMessageEvent,
                                    group_id: str = "", count: int = 20) -> dict:
        self.client = event.bot if isinstance(event, AiocqhttpMessageEvent) else self.client
        self._set_gid(event)
        gid = int(group_id) if group_id else self._gid()
        return await history.get_group_msg_history(self.client, gid, count)

    @filter.llm_tool(name="get_friend_msg_history")
    async def get_friend_msg_history(self, event: AstrMessageEvent,
                                     user_id: str, count: int = 20) -> dict:
        self.client = event.bot if isinstance(event, AiocqhttpMessageEvent) else self.client
        return await history.get_friend_msg_history(self.client, user_id, count)

    # ── 辅助 ──

    def _set_gid(self, event: AstrMessageEvent):
        if isinstance(event, AiocqhttpMessageEvent):
            try:
                raw = getattr(event, 'message_obj', None)
                if raw and hasattr(raw, 'group_id'):
                    self.current_group_id = int(raw.group_id)
            except Exception:
                pass
