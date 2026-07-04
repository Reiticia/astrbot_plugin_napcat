# -*- coding: utf-8 -*-
"""
astrbot_plugin_napcat — NapCat 工具
基于 NapCat 协议为 AstrBot 提供 QQ 平台操作能力。
"""
import asyncio
from datetime import datetime
from typing import Optional, Dict, List

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
        self._contacts: Optional[Dict] = None
        self._contacts_ts: Optional[datetime] = None
        self._contacts_lock = asyncio.Lock()
        logger.info(f'[{PLUGIN_ID}] 已加载')

    def _gid(self) -> int:
        return self.current_group_id

    def _cfg(self) -> Dict:
        return self.config or {}

    async def _load_contacts(self) -> Dict:
        async with self._contacts_lock:
            now = datetime.now()
            if self._contacts and self._contacts_ts and (now - self._contacts_ts).seconds < 300:
                return self._contacts
            try:
                friends = await self.client.call_action('get_friend_list')
                groups = await self.client.call_action('get_group_list')
                self._contacts = {'friends': friends, 'groups': groups}
                self._contacts_ts = now
            except Exception:
                pass
            return self._contacts or {'friends': [], 'groups': []}

    def _set_client(self, event: AstrMessageEvent):
        if isinstance(event, AiocqhttpMessageEvent):
            self.client = event.bot

    def _set_gid(self, event: AstrMessageEvent):
        if isinstance(event, AiocqhttpMessageEvent):
            try:
                raw = getattr(event, 'message_obj', None)
                if raw and hasattr(raw, 'group_id'):
                    self.current_group_id = int(raw.group_id)
            except Exception:
                pass

    # ═══ 消息 ═══

    @filter.llm_tool(name="send_message")
    async def send_message(self, event: AstrMessageEvent, target_id: str, message: str, chat_type: str = "group") -> Dict:
        """向指定群聊或好友发送消息。target_id:群号或QQ号, message:消息内容, chat_type:group(群聊)/private(私聊),默认group"""
        self._set_client(event)
        return await messaging.send_message(self.client, target_id, message, chat_type)

    @filter.llm_tool(name="send_poke")
    async def send_poke(self, event: AstrMessageEvent, target_qq: str) -> Dict:
        """发送戳一戳。target_qq:目标QQ号"""
        self._set_client(event)
        return await messaging.send_poke(self.client, target_qq)

    @filter.llm_tool(name="send_like")
    async def send_like(self, event: AstrMessageEvent, user_id: str, times: int = 1) -> Dict:
        """给指定用户发送名片赞。user_id:QQ号, times:次数默认1最多20"""
        self._set_client(event)
        return await messaging.send_like(self.client, user_id, times)

    # ═══ 联系人 ═══

    @filter.llm_tool(name="search_contacts")
    async def search_contacts(self, event: AstrMessageEvent, keyword: str, search_type: str = "all") -> Dict:
        """按关键词搜索好友和群聊（支持名称或QQ号模糊匹配）。keyword:搜索词, search_type:all(全部)/friend(好友)/group(群聊),默认all"""
        self._set_client(event)
        return await contacts_mod.search_contacts(self.client, self._contacts or {}, keyword, search_type)

    @filter.llm_tool(name="list_contacts")
    async def list_contacts(self, event: AstrMessageEvent, contact_type: str = "all") -> Dict:
        """列出好友或群聊列表。contact_type:all(全部)/friend(好友)/group(群聊),默认all"""
        self._set_client(event)
        return await contacts_mod.list_contacts(self._contacts or {}, contact_type)

    @filter.llm_tool(name="get_user_group_role")
    async def get_user_group_role(self, event: AstrMessageEvent, user_id: str, group_id: str) -> Dict:
        """查询指定用户在群的成员身份。user_id:QQ号, group_id:群号。返回群主/管理员/成员"""
        self._set_client(event)
        return await contacts_mod.get_user_group_role(self.client, user_id, group_id)

    # ═══ QQ状态 ═══

    @filter.llm_tool(name="update_qq_status")
    async def update_qq_status(self, event: AstrMessageEvent, status: str, duration_minutes: int = 30) -> Dict:
        """设置QQ在线状态，到期自动恢复。status:online/qme/away/busy/dnd/invisible/listening/sleeping/studying, duration_minutes:持续分钟数默认30"""
        self._set_client(event)
        return await status_mod.update_qq_status(self.status_ctrl, status, duration_minutes)

    @filter.llm_tool(name="get_qq_status")
    async def get_qq_status(self, event: AstrMessageEvent) -> Dict:
        """查看机器人当前QQ在线状态"""
        return status_mod.get_qq_status(self.status_ctrl)

    @filter.llm_tool(name="get_fun_status_list")
    async def get_fun_status_list(self, event: AstrMessageEvent) -> Dict:
        """获取可用的娱乐状态列表（听歌中、睡觉中、学习中等）"""
        return await status_mod.get_fun_status_list()

    # ═══ 群成员控制 ═══

    @filter.llm_tool(name="set_group_ban")
    async def set_group_ban(self, event: AstrMessageEvent, user_id: str, duration: int) -> Dict:
        """禁言或解禁群成员。user_id:QQ号, duration:禁言秒数(0=解禁)"""
        self._set_client(event); self._set_gid(event)
        return await group_members.set_group_ban(self.client, self._gid(), user_id, duration)

    @filter.llm_tool(name="set_group_kick")
    async def set_group_kick(self, event: AstrMessageEvent, user_id: str, reject_add_request: bool = False) -> Dict:
        """踢出群成员。user_id:QQ号, reject_add_request:是否拒绝再加群默认false"""
        self._set_client(event); self._set_gid(event)
        return await group_members.set_group_kick(self.client, self._gid(), user_id, reject_add_request)

    @filter.llm_tool(name="set_group_card")
    async def set_group_card(self, event: AstrMessageEvent, user_id: str, card: str) -> Dict:
        """修改群成员名片。user_id:QQ号, card:新群名片"""
        self._set_client(event); self._set_gid(event)
        return await group_members.set_group_card(self.client, self._gid(), user_id, card)

    @filter.llm_tool(name="set_group_admin")
    async def set_group_admin(self, event: AstrMessageEvent, user_id: str, enable: bool) -> Dict:
        """设置或取消管理员。user_id:QQ号, enable:true=设管理/false=取消"""
        self._set_client(event); self._set_gid(event)
        return await group_members.set_group_admin(self.client, self._gid(), user_id, enable)

    @filter.llm_tool(name="set_group_special_title")
    async def set_group_special_title(self, event: AstrMessageEvent, user_id: str, special_title: str) -> Dict:
        """设置专属头衔(仅群主)。user_id:QQ号, special_title:头衔文字(最长6字,空=取消)"""
        self._set_client(event); self._set_gid(event)
        return await group_members.set_group_special_title(self.client, self._gid(), user_id, special_title)

    # ═══ 群文件&公告 ═══

    @filter.llm_tool(name="send_group_notice")
    async def send_group_notice(self, event: AstrMessageEvent, content: str) -> Dict:
        """发布群公告。content:公告正文"""
        self._set_client(event); self._set_gid(event)
        return await group_files.send_group_notice(self.client, self._gid(), content)

    @filter.llm_tool(name="delete_group_notice")
    async def delete_group_notice(self, event: AstrMessageEvent, notice_id: str) -> Dict:
        """删除群公告。notice_id:公告ID(通过get_group_notice_list获取)"""
        self._set_client(event); self._set_gid(event)
        return await group_files.delete_group_notice(self.client, self._gid(), notice_id)

    @filter.llm_tool(name="get_group_notice_list")
    async def get_group_notice_list(self, event: AstrMessageEvent) -> Dict:
        """获取当前群聊公告列表"""
        self._set_client(event); self._set_gid(event)
        return await group_files.get_group_notice_list(self.client, self._gid())

    @filter.llm_tool(name="list_group_files")
    async def list_group_files(self, event: AstrMessageEvent) -> Dict:
        """查看当前群聊群文件目录"""
        self._set_client(event); self._set_gid(event)
        return await group_files.list_group_files(self.client, self._gid())

    @filter.llm_tool(name="delete_group_file")
    async def delete_group_file(self, event: AstrMessageEvent, file_id: str, busid: int = 102) -> Dict:
        """删除群文件。file_id:文件ID(通过list_group_files获取), busid:文件类型默认102"""
        self._set_client(event); self._set_gid(event)
        return await group_files.delete_group_file(self.client, self._gid(), file_id, busid)

    @filter.llm_tool(name="upload_group_file")
    async def upload_group_file(self, event: AstrMessageEvent, file_path: str, name: str = "") -> Dict:
        """上传本地文件到群共享。file_path:本地文件绝对路径, name:群文件显示名(留空用原名)"""
        self._set_client(event); self._set_gid(event)
        return await group_files.upload_group_file(self.client, self._gid(), file_path, name)

    @filter.llm_tool(name="create_group_file_folder")
    async def create_group_file_folder(self, event: AstrMessageEvent, name: str) -> Dict:
        """在群文件根目录创建文件夹。name:文件夹名"""
        self._set_client(event); self._set_gid(event)
        return await group_files.create_group_file_folder(self.client, self._gid(), name)

    @filter.llm_tool(name="delete_group_folder")
    async def delete_group_folder(self, event: AstrMessageEvent, folder_id: str) -> Dict:
        """删除群文件夹(含内部文件)。folder_id:文件夹ID"""
        self._set_client(event); self._set_gid(event)
        return await group_files.delete_group_folder(self.client, self._gid(), folder_id)

    # ═══ 群设置&查询 ═══

    @filter.llm_tool(name="set_group_whole_ban")
    async def set_group_whole_ban(self, event: AstrMessageEvent, enable: bool) -> Dict:
        """全体禁言开关。enable:true=开启/false=关闭"""
        self._set_client(event); self._set_gid(event)
        return await group_settings.set_group_whole_ban(self.client, self._gid(), enable)

    @filter.llm_tool(name="set_group_name")
    async def set_group_name(self, event: AstrMessageEvent, group_name: str) -> Dict:
        """修改群名称。group_name:新群名"""
        self._set_client(event); self._set_gid(event)
        return await group_settings.set_group_name(self.client, self._gid(), group_name)

    @filter.llm_tool(name="set_group_add_option")
    async def set_group_add_option(self, event: AstrMessageEvent, option: str) -> Dict:
        """设置加群方式。option:allow(允许)/verify(验证)/deny(禁止)"""
        self._set_client(event); self._set_gid(event)
        return await group_settings.set_group_add_option(self.client, self._gid(), option)

    @filter.llm_tool(name="send_group_sign")
    async def send_group_sign(self, event: AstrMessageEvent) -> Dict:
        """在当前群聊打卡签到"""
        self._set_client(event); self._set_gid(event)
        return await group_settings.send_group_sign(self.client, self._gid())

    @filter.llm_tool(name="get_group_members_info")
    async def get_group_members_info(self, event: AstrMessageEvent) -> Dict:
        """获取当前群完整成员列表(含QQ号、群名片、身份)"""
        self._set_client(event); self._set_gid(event)
        return await group_settings.get_group_members_info(self.client, self._gid())

    @filter.llm_tool(name="get_group_honor_info")
    async def get_group_honor_info(self, event: AstrMessageEvent, type: str = "all") -> Dict:
        """查看群荣誉信息。type:talkative(龙王)/performer(群聊之火)/emotion(快乐源泉)/all(全部默认)"""
        self._set_client(event); self._set_gid(event)
        return await group_settings.get_group_honor_info(self.client, self._gid(), type)

    @filter.llm_tool(name="get_group_shut_list")
    async def get_group_shut_list(self, event: AstrMessageEvent) -> Dict:
        """获取当前群被禁言的成员列表"""
        self._set_client(event); self._set_gid(event)
        return await group_settings.get_group_shut_list(self.client, self._gid())

    @filter.llm_tool(name="get_group_at_all_remain")
    async def get_group_at_all_remain(self, event: AstrMessageEvent) -> Dict:
        """查询今日@全体成员剩余次数"""
        self._set_client(event); self._set_gid(event)
        return await group_settings.get_group_at_all_remain(self.client, self._gid())

    # ═══ AI语音 ═══

    @filter.llm_tool(name="get_ai_characters")
    async def get_ai_characters(self, event: AstrMessageEvent) -> Dict:
        """获取QQ官方TTS可用AI语音角色列表(如luoli、yujie等)"""
        self._set_client(event)
        return await voice.get_ai_characters(self.client)

    @filter.llm_tool(name="send_ai_voice")
    async def send_ai_voice(self, event: AstrMessageEvent, text: str, character_id: str = "") -> Dict:
        """在群聊发送AI语音消息。text:朗读文本, character_id:角色ID(留空用默认,通过get_ai_characters查询)"""
        self._set_client(event); self._set_gid(event)
        return await voice.send_ai_voice(self.client, self._cfg(), self._gid(), text, character_id)

    # ═══ 个人资料 ═══

    @filter.llm_tool(name="set_qq_profile")
    async def set_qq_profile(self, event: AstrMessageEvent, nickname: str = "", personal_note: str = "") -> Dict:
        """修改机器人昵称/签名。nickname:新昵称(留空不修改), personal_note:新签名(留空不修改)"""
        self._set_client(event)
        return await profile.set_qq_profile(self.client, nickname, personal_note)

    @filter.llm_tool(name="set_qq_avatar")
    async def set_qq_avatar(self, event: AstrMessageEvent, file: str) -> Dict:
        """修改机器人QQ头像。file:本地路径/base64://格式/http(s)://URL"""
        self._set_client(event)
        return await profile.set_qq_avatar(self.client, file)

    # ═══ 历史消息 ═══

    @filter.llm_tool(name="get_group_msg_history")
    async def get_group_msg_history(self, event: AstrMessageEvent, group_id: str = "", count: int = 20) -> Dict:
        """获取群聊历史消息。group_id:群号(留空=当前群), count:条数默认20"""
        self._set_client(event); self._set_gid(event)
        gid = int(group_id) if group_id else self._gid()
        return await history.get_group_msg_history(self.client, gid, count)

    @filter.llm_tool(name="get_friend_msg_history")
    async def get_friend_msg_history(self, event: AstrMessageEvent, user_id: str, count: int = 20) -> Dict:
        """获取好友私聊历史消息。user_id:好友QQ号, count:条数默认20"""
        self._set_client(event)
        return await history.get_friend_msg_history(self.client, user_id, count)
