# -*- coding: utf-8 -*-
"""
astrbot_plugin_napcat — NapCat 工具
基于 NapCat 协议为 AstrBot 提供 QQ 平台操作能力。
"""
import asyncio
import json
from datetime import datetime
from typing import Optional, Dict

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


def _ok(detail: str = "", result: str = "") -> str:
    return json.dumps({"ok": True, "detail": detail, "result": result}, ensure_ascii=False)


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

    def _guard(self, key: str, name: str) -> str | None:
        '''检查权限配置，返回 None 表示放行，否则返回拒绝原因字符串。'''
        if not self._cfg().get(key, False):
            return json.dumps({"ok": False, "detail": f"「{name}」已被管理员禁用，如需使用请在插件配置中开启 {key}"}, ensure_ascii=False)
        return None

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
    async def send_message(self, event: AstrMessageEvent, target_id: str, message: str, chat_type: str = "group") -> str:
        '''向指定群聊或好友发送消息。

        Args:
            target_id(string): 目标群号或QQ号
            message(string): 要发送的消息内容
            chat_type(string): group=群聊(默认) / private=私聊
        '''
        self._set_client(event)
        r = await messaging.send_message(self.client, target_id, message, chat_type)
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="send_poke")
    async def send_poke(self, event: AstrMessageEvent, target_qq: str) -> str:
        '''发送戳一戳（窗口抖动/双击头像效果）。

        Args:
            target_qq(string): 目标QQ号
        '''
        self._set_client(event)
        r = await messaging.send_poke(self.client, target_qq)
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="send_like")
    async def send_like(self, event: AstrMessageEvent, user_id: str, times: int = 1) -> str:
        '''给指定用户发送名片赞。

        Args:
            user_id(string): 目标QQ号
            times(number): 点赞次数，默认1，最多20
        '''
        self._set_client(event)
        r = await messaging.send_like(self.client, user_id, times)
        return json.dumps(r, ensure_ascii=False)

    # ═══ 联系人 ═══

    @filter.llm_tool(name="search_contacts")
    async def search_contacts(self, event: AstrMessageEvent, keyword: str, search_type: str = "all") -> str:
        '''按关键词搜索好友和群聊（支持名称或QQ号模糊匹配）。

        Args:
            keyword(string): 搜索关键词（群名、好友昵称、QQ号均可）
            search_type(string): all=全部(默认) / friend=仅好友 / group=仅群聊
        '''
        self._set_client(event)
        r = await contacts_mod.search_contacts(self.client, self._contacts or {}, keyword, search_type)
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="list_contacts")
    async def list_contacts(self, event: AstrMessageEvent, contact_type: str = "all") -> str:
        '''列出好友或群聊列表。

        Args:
            contact_type(string): all=全部(默认) / friend=仅好友 / group=仅群聊
        '''
        self._set_client(event)
        r = await contacts_mod.list_contacts(self._contacts or {}, contact_type)
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="get_user_group_role")
    async def get_user_group_role(self, event: AstrMessageEvent, user_id: str, group_id: str) -> str:
        '''查询指定用户在群的成员身份（群主/管理员/普通成员）。

        Args:
            user_id(string): 要查询的QQ号
            group_id(string): 群号
        '''
        self._set_client(event)
        r = await contacts_mod.get_user_group_role(self.client, user_id, group_id)
        return json.dumps(r, ensure_ascii=False)

    # ═══ QQ状态 ═══

    @filter.llm_tool(name="update_qq_status")
    async def update_qq_status(self, event: AstrMessageEvent, status: str, duration_minutes: int = 30) -> str:
        '''设置QQ在线状态，到期自动恢复为在线。

        Args:
            status(string): 状态码：online(在线) / qme(Q我吧) / away(离开) / busy(忙碌) / dnd(请勿打扰) / invisible(隐身) / listening(听歌中) / sleeping(睡觉中) / studying(学习中)
            duration_minutes(number): 持续多少分钟后自动恢复在线，默认30
        '''
        self._set_client(event)
        r = await status_mod.update_qq_status(self.status_ctrl, status, duration_minutes)
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="get_qq_status")
    async def get_qq_status(self, event: AstrMessageEvent) -> str:
        '''查看机器人当前的QQ在线状态及剩余时间。'''
        r = status_mod.get_qq_status(self.status_ctrl)
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="get_fun_status_list")
    async def get_fun_status_list(self, event: AstrMessageEvent) -> str:
        '''获取所有可用的娱乐状态列表（听歌中、睡觉中、学习中等）。'''
        r = await status_mod.get_fun_status_list()
        return json.dumps(r, ensure_ascii=False)

    # ═══ 群成员控制 ═══

    @filter.llm_tool(name="set_group_ban")
    async def set_group_ban(self, event: AstrMessageEvent, user_id: str, duration: int) -> str:
        '''禁言或解禁指定群成员。duration=0为解除禁言。

        Args:
            user_id(string): 要禁言的QQ号
            duration(number): 禁言时长（秒），0表示解除禁言
        '''
        self._set_client(event); self._set_gid(event)
        if r := self._guard("allow_ban", "禁言"): return r
        r = await group_members.set_group_ban(self.client, self._gid(), user_id, duration)
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="set_group_kick")
    async def set_group_kick(self, event: AstrMessageEvent, user_id: str, reject_add_request: bool = False) -> str:
        '''将指定成员踢出当前群聊。

        Args:
            user_id(string): 要踢出的QQ号
            reject_add_request(boolean): 是否同时拒绝该用户再次申请加群，默认false
        '''
        self._set_client(event); self._set_gid(event)
        if r := self._guard("allow_kick", "踢人"): return r
        r = await group_members.set_group_kick(self.client, self._gid(), user_id, reject_add_request)
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="set_group_card")
    async def set_group_card(self, event: AstrMessageEvent, user_id: str, card: str) -> str:
        '''修改指定成员的群名片（群昵称）。

        Args:
            user_id(string): 目标QQ号
            card(string): 新的群名片内容
        '''
        self._set_client(event); self._set_gid(event)
        r = await group_members.set_group_card(self.client, self._gid(), user_id, card)
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="set_group_admin")
    async def set_group_admin(self, event: AstrMessageEvent, user_id: str, enable: bool) -> str:
        '''设置或取消指定成员的管理员权限。

        Args:
            user_id(string): 目标QQ号
            enable(boolean): true=设为管理员 / false=取消管理员
        '''
        self._set_client(event); self._set_gid(event)
        if r := self._guard("allow_set_admin", "设置管理员"): return r
        r = await group_members.set_group_admin(self.client, self._gid(), user_id, enable)
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="set_group_special_title")
    async def set_group_special_title(self, event: AstrMessageEvent, user_id: str, special_title: str) -> str:
        '''设置群成员专属头衔（仅群主可用，最长6字符）。

        Args:
            user_id(string): 目标QQ号
            special_title(string): 专属头衔文字，留空为取消头衔
        '''
        self._set_client(event); self._set_gid(event)
        r = await group_members.set_group_special_title(self.client, self._gid(), user_id, special_title)
        return json.dumps(r, ensure_ascii=False)

    # ═══ 群文件&公告 ═══

    @filter.llm_tool(name="send_group_notice")
    async def send_group_notice(self, event: AstrMessageEvent, content: str) -> str:
        '''在当前群聊中发布新公告。

        Args:
            content(string): 公告正文内容
        '''
        self._set_client(event); self._set_gid(event)
        r = await group_files.send_group_notice(self.client, self._gid(), content)
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="delete_group_notice")
    async def delete_group_notice(self, event: AstrMessageEvent, notice_id: str) -> str:
        '''删除指定ID的群公告。

        Args:
            notice_id(string): 公告ID（可通过 get_group_notice_list 获取）
        '''
        self._set_client(event); self._set_gid(event)
        if r := self._guard("allow_delete_notice", "删除群公告"): return r
        r = await group_files.delete_group_notice(self.client, self._gid(), notice_id)
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="get_group_notice_list")
    async def get_group_notice_list(self, event: AstrMessageEvent) -> str:
        '''获取当前群聊的所有公告列表。'''
        self._set_client(event); self._set_gid(event)
        r = await group_files.get_group_notice_list(self.client, self._gid())
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="list_group_files")
    async def list_group_files(self, event: AstrMessageEvent) -> str:
        '''查看当前群聊的群文件目录。'''
        self._set_client(event); self._set_gid(event)
        r = await group_files.list_group_files(self.client, self._gid())
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="delete_group_file")
    async def delete_group_file(self, event: AstrMessageEvent, file_id: str, busid: int = 102) -> str:
        '''删除群文件中的指定文件。

        Args:
            file_id(string): 文件ID（可通过 list_group_files 获取）
            busid(number): 文件类型标识，默认102
        '''
        self._set_client(event); self._set_gid(event)
        if r := self._guard("allow_delete_file", "删除群文件"): return r
        r = await group_files.delete_group_file(self.client, self._gid(), file_id, busid)
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="upload_group_file")
    async def upload_group_file(self, event: AstrMessageEvent, file_path: str, name: str = "") -> str:
        '''上传本地文件到群共享。

        Args:
            file_path(string): 本地文件的绝对路径
            name(string): 上传后在群文件中显示的名称，留空则使用原文件名
        '''
        self._set_client(event); self._set_gid(event)
        r = await group_files.upload_group_file(self.client, self._gid(), file_path, name)
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="create_group_file_folder")
    async def create_group_file_folder(self, event: AstrMessageEvent, name: str) -> str:
        '''在群文件根目录下创建新文件夹。

        Args:
            name(string): 文件夹名称
        '''
        self._set_client(event); self._set_gid(event)
        r = await group_files.create_group_file_folder(self.client, self._gid(), name)
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="delete_group_folder")
    async def delete_group_folder(self, event: AstrMessageEvent, folder_id: str) -> str:
        '''删除群文件中的文件夹（会同时删除文件夹内所有文件）。

        Args:
            folder_id(string): 文件夹ID
        '''
        self._set_client(event); self._set_gid(event)
        if r := self._guard("allow_delete_folder", "删除群文件夹"): return r
        r = await group_files.delete_group_folder(self.client, self._gid(), folder_id)
        return json.dumps(r, ensure_ascii=False)

    # ═══ 群设置&查询 ═══

    @filter.llm_tool(name="set_group_whole_ban")
    async def set_group_whole_ban(self, event: AstrMessageEvent, enable: bool) -> str:
        '''开启或关闭当前群聊的全体禁言。

        Args:
            enable(boolean): true=开启全体禁言 / false=关闭全体禁言
        '''
        self._set_client(event); self._set_gid(event)
        if r := self._guard("allow_whole_ban", "全体禁言"): return r
        r = await group_settings.set_group_whole_ban(self.client, self._gid(), enable)
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="set_group_name")
    async def set_group_name(self, event: AstrMessageEvent, group_name: str) -> str:
        '''修改当前群聊的名称。

        Args:
            group_name(string): 新的群名称
        '''
        self._set_client(event); self._set_gid(event)
        if r := self._guard("allow_set_group_name", "修改群名称"): return r
        r = await group_settings.set_group_name(self.client, self._gid(), group_name)
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="set_group_add_option")
    async def set_group_add_option(self, event: AstrMessageEvent, option: str) -> str:
        '''设置当前群的加群验证方式。

        Args:
            option(string): allow=允许任何人 / verify=需要验证消息 / deny=禁止加群
        '''
        self._set_client(event); self._set_gid(event)
        if r := self._guard("allow_set_add_option", "设置加群方式"): return r
        r = await group_settings.set_group_add_option(self.client, self._gid(), option)
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="send_group_sign")
    async def send_group_sign(self, event: AstrMessageEvent) -> str:
        '''在当前群聊进行打卡/签到操作。'''
        self._set_client(event); self._set_gid(event)
        r = await group_settings.send_group_sign(self.client, self._gid())
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="get_group_members_info")
    async def get_group_members_info(self, event: AstrMessageEvent) -> str:
        '''获取当前群聊的完整成员列表（含QQ号、群名片、身份等信息）。'''
        self._set_client(event); self._set_gid(event)
        r = await group_settings.get_group_members_info(self.client, self._gid())
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="get_group_honor_info")
    async def get_group_honor_info(self, event: AstrMessageEvent, type: str = "all") -> str:
        '''查看当前群的荣誉信息（龙王、群聊之火、快乐源泉等）。

        Args:
            type(string): 荣誉类型：talkative(龙王) / performer(群聊之火) / emotion(快乐源泉) / all(全部，默认)
        '''
        self._set_client(event); self._set_gid(event)
        r = await group_settings.get_group_honor_info(self.client, self._gid(), type)
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="get_group_shut_list")
    async def get_group_shut_list(self, event: AstrMessageEvent) -> str:
        '''获取当前群聊中被禁言的成员列表。'''
        self._set_client(event); self._set_gid(event)
        r = await group_settings.get_group_shut_list(self.client, self._gid())
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="get_group_at_all_remain")
    async def get_group_at_all_remain(self, event: AstrMessageEvent) -> str:
        '''查询当前群聊今日 @全体成员 的剩余可用次数。'''
        self._set_client(event); self._set_gid(event)
        r = await group_settings.get_group_at_all_remain(self.client, self._gid())
        return json.dumps(r, ensure_ascii=False)

    # ═══ AI语音 ═══

    @filter.llm_tool(name="get_ai_characters")
    async def get_ai_characters(self, event: AstrMessageEvent) -> str:
        '''获取QQ官方TTS所有可用的AI语音角色列表（如luoli、yujie等）。'''
        self._set_client(event)
        r = await voice.get_ai_characters(self.client)
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="send_ai_voice")
    async def send_ai_voice(self, event: AstrMessageEvent, text: str, character_id: str = "") -> str:
        '''在当前群聊发送AI语音消息（QQ官方TTS）。文本过长会自动截断。

        Args:
            text(string): 要让AI朗读的文本内容
            character_id(string): 语音角色ID，留空则使用插件配置的默认角色。可用角色通过 get_ai_characters 查询
        '''
        self._set_client(event); self._set_gid(event)
        r = await voice.send_ai_voice(self.client, self._cfg(), self._gid(), text, character_id)
        return json.dumps(r, ensure_ascii=False)

    # ═══ 个人资料 ═══

    @filter.llm_tool(name="set_qq_profile")
    async def set_qq_profile(self, event: AstrMessageEvent, nickname: str = "", personal_note: str = "") -> str:
        '''修改机器人自身的QQ个人资料（昵称和/或个性签名）。

        Args:
            nickname(string): 新昵称，留空则不修改
            personal_note(string): 新个性签名，留空则不修改
        '''
        self._set_client(event)
        if r := self._guard("allow_set_profile", "修改个人资料"): return r
        r = await profile.set_qq_profile(self.client, nickname, personal_note)
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="set_qq_avatar")
    async def set_qq_avatar(self, event: AstrMessageEvent, file: str) -> str:
        '''修改机器人自身的QQ头像。

        Args:
            file(string): 图片路径（本地绝对路径 / base64://格式 / http(s)://URL）
        '''
        self._set_client(event)
        if r := self._guard("allow_set_avatar", "修改QQ头像"): return r
        r = await profile.set_qq_avatar(self.client, file)
        return json.dumps(r, ensure_ascii=False)

    # ═══ 历史消息 ═══

    @filter.llm_tool(name="get_group_msg_history")
    async def get_group_msg_history(self, event: AstrMessageEvent, group_id: str = "", count: int = 20) -> str:
        '''获取指定群聊或当前群聊的历史消息记录。

        Args:
            group_id(string): 群号，留空则获取当前群聊的历史消息
            count(number): 获取条数，默认20条
        '''
        self._set_client(event); self._set_gid(event)
        gid = int(group_id) if group_id else self._gid()
        r = await history.get_group_msg_history(self.client, gid, count)
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="get_friend_msg_history")
    async def get_friend_msg_history(self, event: AstrMessageEvent, user_id: str, count: int = 20) -> str:
        '''获取与指定好友的私聊历史消息记录。

        Args:
            user_id(string): 好友QQ号
            count(number): 获取条数，默认20条
        '''
        self._set_client(event)
        r = await history.get_friend_msg_history(self.client, user_id, count)
        return json.dumps(r, ensure_ascii=False)
