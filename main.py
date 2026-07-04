# -*- coding: utf-8 -*-
"""
astrbot_plugin_qq_ops — QQ 平台操作
=====================================
入口模块：插件生命周期、上下文管理、工具注册。

目录结构：
  main.py            入口 & Main 类
  qq_tools/          功能模块包
    registry.py      工具注册表
    utils.py         公共工具函数
    constants.py     QQ 状态常量
    status_ctrl.py   QQ 在线状态控制器
    messaging.py     消息收发 / 戳一戳 / 点赞
    contacts.py      联系人搜索 / 列表 / 身份
    qq_status.py     QQ 状态工具
    group_members.py 群成员控制（禁言/踢人/名片/管理员/头衔）
    group_files.py   群文件 & 群公告
    group_settings.py 群设置 & 信息查询
    email_sender.py  QQ 邮件
    voice.py         AI 语音
    profile.py       个人资料
    history.py       历史消息
"""
import asyncio
from datetime import datetime
from typing import Optional

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent

from .qq_tools.registry import ToolRegistry
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

PLUGIN_ID = "astrbot_plugin_qq_ops"


class Main(Star):
    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        self.config = config
        self.client = None
        self.current_group_id = 0

        self.tools = ToolRegistry()
        self.status_ctrl = StatusController(lambda: self.client)

        self._contacts: Optional[dict] = None
        self._contacts_ts: Optional[datetime] = None
        self._contacts_lock = asyncio.Lock()

    async def start(self):
        self._register_tools()
        logger.info(f'[{PLUGIN_ID}] 已启动 — {len(self.tools._defs)} 个工具就绪')

    async def _on_message(self, event: AstrMessageEvent):
        if isinstance(event, AiocqhttpMessageEvent):
            self.client = event.bot
            try:
                raw = getattr(event, 'message_obj', None)
                if raw and hasattr(raw, 'group_id'):
                    self.current_group_id = int(raw.group_id)
            except Exception:
                pass

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

    def _register_tools(self):
        t = self.tools
        cfg = self.config or {}
        gid = lambda: self.current_group_id

        # ── 消息 ──
        t.register('send_message', '向群聊或好友发送消息',
                   {'target_id': 'string', 'message': 'string', 'chat_type': 'string'},
                   lambda **kw: messaging.send_message(self.client, **kw), 'enable_send_message')
        t.register('send_poke', '发送戳一戳',
                   {'target_qq': 'string'},
                   lambda **kw: messaging.send_poke(self.client, **kw), 'enable_send_poke')
        t.register('send_like', '给用户点赞',
                   {'user_id': 'string', 'times': 'integer'},
                   lambda **kw: messaging.send_like(self.client, **kw), 'enable_send_like')

        # ── 联系人 ──
        t.register('search_contacts', '按名称/QQ号模糊搜索好友和群',
                   {'keyword': 'string', 'search_type': 'string'},
                   lambda **kw: contacts_mod.search_contacts(
                       self.client, self._contacts or {}, **kw), 'enable_search_contacts')
        t.register('list_contacts', '列出好友或群聊列表',
                   {'contact_type': 'string'},
                   lambda **kw: contacts_mod.list_contacts(
                       self._contacts or {}, **kw), 'enable_list_contacts')
        t.register('get_user_group_role', '查询群成员身份',
                   {'user_id': 'string', 'group_id': 'string'},
                   lambda **kw: contacts_mod.get_user_group_role(self.client, **kw),
                   'enable_get_user_group_role')

        # ── QQ 状态 ──
        t.register('update_qq_status', '设置QQ在线状态（在线/离开/忙碌/隐身/听歌中/睡觉中/学习中）',
                   {'status': 'string', 'duration_minutes': 'integer'},
                   lambda **kw: status_mod.update_qq_status(self.status_ctrl, **kw),
                   'enable_update_qq_status')
        t.register('get_qq_status', '查看当前QQ状态', {},
                   lambda **kw: status_mod.get_qq_status(self.status_ctrl),
                   'enable_get_qq_status')
        t.register('get_fun_status_list', '获取娱乐状态列表', {},
                   lambda **kw: status_mod.get_fun_status_list(),
                   'enable_get_fun_status_list')

        # ── 群管理：成员控制 ──
        t.register('set_group_ban', '禁言/解禁群成员',
                   {'user_id': 'string', 'duration': 'integer'},
                   lambda **kw: group_members.set_group_ban(self.client, gid(), **kw),
                   'enable_set_group_ban')
        t.register('set_group_kick', '踢出群成员',
                   {'user_id': 'string', 'reject_add_request': 'boolean'},
                   lambda **kw: group_members.set_group_kick(self.client, gid(), **kw),
                   'enable_set_group_kick')
        t.register('set_group_card', '修改群名片',
                   {'user_id': 'string', 'card': 'string'},
                   lambda **kw: group_members.set_group_card(self.client, gid(), **kw),
                   'enable_set_group_card')
        t.register('set_group_admin', '设置/取消管理员',
                   {'user_id': 'string', 'enable': 'boolean'},
                   lambda **kw: group_members.set_group_admin(self.client, gid(), **kw),
                   'enable_set_group_admin')
        t.register('set_group_special_title', '设置专属头衔',
                   {'user_id': 'string', 'special_title': 'string'},
                   lambda **kw: group_members.set_group_special_title(self.client, gid(), **kw),
                   'enable_set_group_special_title')

        # ── 群管理：文件 & 公告 ──
        t.register('send_group_notice', '发布群公告',
                   {'content': 'string'},
                   lambda **kw: group_files.send_group_notice(self.client, gid(), **kw),
                   'enable_send_group_notice')
        t.register('delete_group_notice', '删除群公告',
                   {'notice_id': 'string'},
                   lambda **kw: group_files.delete_group_notice(self.client, gid(), **kw),
                   'enable_delete_group_notice')
        t.register('get_group_notice_list', '查看群公告列表', {},
                   lambda **kw: group_files.get_group_notice_list(self.client, gid()),
                   'enable_get_group_notice_list')
        t.register('list_group_files', '查看群文件', {},
                   lambda **kw: group_files.list_group_files(self.client, gid()),
                   'enable_list_group_files')
        t.register('delete_group_file', '删除群文件',
                   {'file_id': 'string', 'busid': 'integer'},
                   lambda **kw: group_files.delete_group_file(self.client, gid(), **kw),
                   'enable_delete_group_file')
        t.register('upload_group_file', '上传群文件',
                   {'file_path': 'string', 'name': 'string'},
                   lambda **kw: group_files.upload_group_file(self.client, gid(), **kw),
                   'enable_upload_group_file')
        t.register('create_group_file_folder', '创建群文件夹',
                   {'name': 'string'},
                   lambda **kw: group_files.create_group_file_folder(self.client, gid(), **kw),
                   'enable_create_group_file_folder')
        t.register('delete_group_folder', '删除群文件夹',
                   {'folder_id': 'string'},
                   lambda **kw: group_files.delete_group_folder(self.client, gid(), **kw),
                   'enable_delete_group_folder')

        # ── 群管理：设置 & 查询 ──
        t.register('set_group_whole_ban', '全体禁言开关',
                   {'enable': 'boolean'},
                   lambda **kw: group_settings.set_group_whole_ban(self.client, gid(), **kw),
                   'enable_set_group_whole_ban')
        t.register('set_group_name', '修改群名称',
                   {'group_name': 'string'},
                   lambda **kw: group_settings.set_group_name(self.client, gid(), **kw),
                   'enable_set_group_name')
        t.register('set_group_add_option', '设置加群方式',
                   {'option': 'string'},
                   lambda **kw: group_settings.set_group_add_option(self.client, gid(), **kw),
                   'enable_set_group_add_option')
        t.register('send_group_sign', '群打卡', {},
                   lambda **kw: group_settings.send_group_sign(self.client, gid()),
                   'enable_send_group_sign')
        t.register('get_group_members_info', '获取群成员列表', {},
                   lambda **kw: group_settings.get_group_members_info(self.client, gid()),
                   'enable_get_group_members_info')
        t.register('get_group_honor_info', '查看群荣誉（龙王等）',
                   {'type': 'string'},
                   lambda **kw: group_settings.get_group_honor_info(self.client, gid(), **kw),
                   'enable_get_group_honor_info')
        t.register('get_group_shut_list', '获取禁言列表', {},
                   lambda **kw: group_settings.get_group_shut_list(self.client, gid()),
                   'enable_get_group_shut_list')
        t.register('get_group_at_all_remain', '查询@全体剩余次数', {},
                   lambda **kw: group_settings.get_group_at_all_remain(self.client, gid()),
                   'enable_get_group_at_all_remain')

        # ── AI 语音 ──
        t.register('get_ai_characters', '获取可用的AI语音角色', {},
                   lambda **kw: voice.get_ai_characters(self.client),
                   'enable_get_ai_characters')
        t.register('send_ai_voice', '发送AI语音消息（群聊）',
                   {'text': 'string', 'character_id': 'string'},
                   lambda **kw: voice.send_ai_voice(self.client, cfg, gid(), **kw),
                   'enable_send_ai_voice')

        # ── 个人资料 ──
        t.register('set_qq_profile', '修改机器人昵称/签名',
                   {'nickname': 'string', 'personal_note': 'string'},
                   lambda **kw: profile.set_qq_profile(self.client, **kw),
                   'enable_set_qq_profile')
        t.register('set_qq_avatar', '设置QQ头像',
                   {'file': 'string'},
                   lambda **kw: profile.set_qq_avatar(self.client, **kw),
                   'enable_set_qq_avatar')

        # ── 历史消息 ──
        t.register('get_group_msg_history', '获取群历史消息',
                   {'group_id': 'string', 'count': 'integer'},
                   lambda **kw: history.get_group_msg_history(
                       self.client, int(kw.get('group_id', 0)) or gid(), kw.get('count', 20)),
                   'enable_get_group_msg_history')
        t.register('get_friend_msg_history', '获取好友历史消息',
                   {'user_id': 'string', 'count': 'integer'},
                   lambda **kw: history.get_friend_msg_history(self.client, **kw),
                   'enable_get_friend_msg_history')

        t.register_all_to(self, cfg)
