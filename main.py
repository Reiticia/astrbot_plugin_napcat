# -*- coding: utf-8 -*-
"""
astrbot_plugin_napcat — NapCat 工具
基于 NapCat 协议为 AstrBot 提供 QQ 平台操作能力。
"""
import asyncio
import json
import time
from datetime import datetime
from typing import Optional, Dict

from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.core.config.astrbot_config import AstrBotConfig

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
        self._poke_cooldowns: Dict[str, float] = {}  # target_qq → last_poke_timestamp
        logger.info(f'[{PLUGIN_ID}] 已加载')

    def _gid(self) -> int:
        return self.current_group_id

    def _resolve_gid(self, group_id: str) -> int:
        """解析群号：显式传入 → 事件捕获 → 0。"""
        gid = str(group_id or "").strip()
        return int(gid) if gid else self._gid()

    def _cfg(self) -> Dict:
        return self.config or {}

    def _limit(self) -> int:
        return self._cfg().get("max_output_chars", 2000)

    def _guard(self, key: str, name: str) -> str | None:
        '''检查权限配置，返回 None 表示放行，否则返回拒绝原因字符串。'''
        if not self._cfg().get(key, False):
            return json.dumps({"ok": False, "detail": f"「{name}」已被管理员禁用，如需使用请在插件配置中开启 {key}"}, ensure_ascii=False)
        return None

    def _check_ban_whitelist(self, user_id: str) -> str | None:
        '''检查用户是否在禁言白名单中，在则返回拒绝原因。'''
        whitelist = self._cfg().get("ban_whitelist", [])
        if not whitelist:
            return None
        uid = str(user_id).strip()
        if uid in {str(x).strip() for x in whitelist}:
            return json.dumps(
                {"ok": False, "detail": f"「禁言」失败：用户 {uid} 在禁言保护白名单中，无法被禁言"},
                ensure_ascii=False,
            )
        return None

    async def _load_contacts(self) -> Dict:
        """加载联系人缓存（群列表 + 好友列表），300 秒内命中缓存。"""
        async with self._contacts_lock:
            now = datetime.now()
            if self._contacts and self._contacts_ts and (now - self._contacts_ts).total_seconds() < 300:
                return self._contacts
            try:
                friends_raw = await self.client.call_action('get_friend_list')
                groups_raw = await self.client.call_action('get_group_list')
            except Exception:
                return self._contacts or {'friends': [], 'groups': []}

            # 兼容返回格式：可能是裸列表，也可能是 {data: [...]}
            friends = friends_raw if isinstance(friends_raw, list) else friends_raw.get('data', [])
            groups = groups_raw if isinstance(groups_raw, list) else groups_raw.get('data', [])
            self._contacts = {'friends': friends, 'groups': groups}
            self._contacts_ts = now
            return self._contacts

    async def _get_client(self, event: AstrMessageEvent) -> object | None:
        """获取 NapCat 客户端实例。三层回退策略，兼容 v4.26.0 的 event 包装。

        1. 从 event.bot 获取
        2. 使用上次缓存的 self.client
        3. 通过 self.context.platform_manager 获取平台适配器的 client
        """
        # 一层：从 event 获取
        bot = getattr(event, 'bot', None)
        if bot is not None and hasattr(bot, 'call_action'):
            self.client = bot
            return bot

        # 二层：使用缓存
        if self.client is not None and hasattr(self.client, 'call_action'):
            return self.client

        # 三层：从 platform_manager 获取
        try:
            pm = getattr(self.context, 'platform_manager', None)
            if pm is None:
                return None
            # 尝试 get_insts() 或 _platforms
            platforms = []
            if hasattr(pm, 'get_insts'):
                platforms = pm.get_insts()
            elif hasattr(pm, '_platforms'):
                platforms = list(pm._platforms.values())
            for platform in platforms:
                # 尝试 get_client() 方法
                if hasattr(platform, 'get_client'):
                    client = platform.get_client()
                    if client is not None and hasattr(client, 'call_action'):
                        self.client = client
                        return client
                # 尝试 .client 属性
                if hasattr(platform, 'client') and hasattr(platform.client, 'call_action'):
                    self.client = platform.client
                    return platform.client
        except Exception as e:
            logger.debug(f"[{PLUGIN_ID}] 从 platform_manager 获取 client 失败: {e}")
        return None


    def _set_gid(self, event: AstrMessageEvent):
        """从 event 中提取当前群号。"""
        try:
            raw = getattr(event, 'message_obj', None)
            if raw and hasattr(raw, 'group_id'):
                self.current_group_id = int(raw.group_id)
        except Exception:
            pass

    # ═══ 生命周期：在 LLM 请求前捕获客户端 ═══

    @filter.on_llm_request()
    async def _capture_client(self, event: AstrMessageEvent, req) -> None:
        """在 LLM 请求前从原始事件中捕获 NapCat 客户端引用。

        v4.26.0 的 tool_loop_agent_runner 可能在调用 LLM 工具时传入被包装过的 event，
        导致 event.bot 丢失。此处提前在消息处理阶段捕获，确保后续工具调用时 client 可用。
        """
        await self._get_client(event)
        if not self.client:
            logger.warning(f"[{PLUGIN_ID}] _capture_client 未能获取 client，工具调用可能失败")
        self._set_gid(event)

    # ═══ 消息 ═══

    @filter.llm_tool(name="send_message")
    async def send_message(self, event: AstrMessageEvent, target_id: str, message: str, chat_type: str = "group") -> str:
        '''向指定群聊或好友发送消息。

        Args:
            target_id(string): 目标群号或QQ号
            message(string): 要发送的消息内容
            chat_type(string): group=群聊(默认) / private=私聊
        '''
        await self._get_client(event)
        if not self.client:
            return json.dumps({"ok": False, "detail": "操作失败：未连接到 NapCat"}, ensure_ascii=False)
        r = await messaging.send_message(self.client, target_id, message, chat_type)
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="send_poke")
    async def send_poke(self, event: AstrMessageEvent, target_qq: str, group_id: str = "") -> str:
        '''发送戳一戳（窗口抖动/双击头像效果）。群聊中会戳当前群的成员，私聊中戳好友。

        Args:
            target_qq(string): 目标QQ号
            group_id(string): 群号，留空则使用当前群聊
        '''
        POKE_CD = 10  # 每个用户 10 秒冷却
        await self._get_client(event)
        if not self.client:
            return json.dumps({"ok": False, "detail": "操作失败：未连接到 NapCat"}, ensure_ascii=False)

        # 冷却检查
        last = self._poke_cooldowns.get(target_qq, 0)
        now = time.time()
        remaining = POKE_CD - (now - last)
        if remaining > 0:
            return json.dumps(
                {"ok": False, "detail": f"「戳一戳」冷却中，请 {remaining:.0f} 秒后再戳 {target_qq}"},
                ensure_ascii=False,
            )

        gid = self._resolve_gid(group_id)
        r = await messaging.send_poke(self.client, target_qq, group_id=gid)
        self._poke_cooldowns[target_qq] = now
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="send_like")
    async def send_like(self, event: AstrMessageEvent, user_id: str, times: int = 1) -> str:
        '''给指定用户发送名片赞。

        Args:
            user_id(string): 目标QQ号
            times(number): 点赞次数，默认1，最多20
        '''
        await self._get_client(event)
        if not self.client:
            return json.dumps({"ok": False, "detail": "操作失败：未连接到 NapCat"}, ensure_ascii=False)
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
        await self._get_client(event)
        if not self.client:
            return json.dumps({"ok": False, "detail": "操作失败：未连接到 NapCat"}, ensure_ascii=False)
        contacts = await self._load_contacts()
        r = await contacts_mod.search_contacts(self.client, contacts, keyword, search_type, self._limit())
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="list_contacts")
    async def list_contacts(self, event: AstrMessageEvent, contact_type: str = "all") -> str:
        '''列出好友或群聊列表。

        Args:
            contact_type(string): all=全部(默认) / friend=仅好友 / group=仅群聊
        '''
        await self._get_client(event)
        if not self.client:
            return json.dumps({"ok": False, "detail": "操作失败：未连接到 NapCat"}, ensure_ascii=False)
        contacts = await self._load_contacts()
        r = await contacts_mod.list_contacts(contacts, contact_type, self._limit())
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="get_user_group_role")
    async def get_user_group_role(self, event: AstrMessageEvent, user_id: str, group_id: str) -> str:
        '''查询指定用户在群的成员身份（群主/管理员/普通成员）。

        Args:
            user_id(string): 要查询的QQ号
            group_id(string): 群号
        '''
        await self._get_client(event)
        if not self.client:
            return json.dumps({"ok": False, "detail": "操作失败：未连接到 NapCat"}, ensure_ascii=False)
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
        await self._get_client(event)
        if not self.client:
            return json.dumps({"ok": False, "detail": "操作失败：未连接到 NapCat"}, ensure_ascii=False)
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
    async def set_group_ban(self, event: AstrMessageEvent, user_id: str, duration: int, group_id: str = "") -> str:
        '''禁言或解禁指定群成员。duration=0为解除禁言。

        Args:
            user_id(string): 要禁言的QQ号
            duration(number): 禁言时长（秒），0表示解除禁言
            group_id(string): 群号，留空则使用当前群聊
        '''
        await self._get_client(event)
        if not self.client:
            return json.dumps({"ok": False, "detail": "操作失败：未连接到 NapCat"}, ensure_ascii=False)
        self._set_gid(event)
        r = self._guard("allow_ban", "禁言")
        if r:

            return r
        r = self._check_ban_whitelist(user_id)
        if r:

            return r
        gid = self._resolve_gid(group_id)
        r = await group_members.set_group_ban(self.client, gid, user_id, duration)
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="set_group_kick")
    async def set_group_kick(self, event: AstrMessageEvent, user_id: str, reject_add_request: bool = False, group_id: str = "") -> str:
        '''将指定成员踢出当前群聊。

        Args:
            user_id(string): 要踢出的QQ号
            reject_add_request(boolean): 是否同时拒绝该用户再次申请加群，默认false
            group_id(string): 群号，留空则使用当前群聊
        '''
        await self._get_client(event)
        if not self.client:
            return json.dumps({"ok": False, "detail": "操作失败：未连接到 NapCat"}, ensure_ascii=False)
        self._set_gid(event)
        r = self._guard("allow_kick", "踢人")
        if r:

            return r
        gid = self._resolve_gid(group_id)
        r = await group_members.set_group_kick(self.client, gid, user_id, reject_add_request)
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="set_group_card")
    async def set_group_card(self, event: AstrMessageEvent, user_id: str, card: str, group_id: str = "") -> str:
        '''修改指定成员的群名片（群昵称）。

        Args:
            user_id(string): 目标QQ号
            card(string): 新的群名片内容
            group_id(string): 群号，留空则使用当前群聊
        '''
        await self._get_client(event)
        if not self.client:
            return json.dumps({"ok": False, "detail": "操作失败：未连接到 NapCat"}, ensure_ascii=False)
        self._set_gid(event)
        gid = self._resolve_gid(group_id)
        r = await group_members.set_group_card(self.client, gid, user_id, card)
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="set_group_admin")
    async def set_group_admin(self, event: AstrMessageEvent, user_id: str, enable: bool, group_id: str = "") -> str:
        '''设置或取消指定成员的管理员权限。

        Args:
            user_id(string): 目标QQ号
            enable(boolean): true=设为管理员 / false=取消管理员
            group_id(string): 群号，留空则使用当前群聊
        '''
        await self._get_client(event)
        if not self.client:
            return json.dumps({"ok": False, "detail": "操作失败：未连接到 NapCat"}, ensure_ascii=False)
        self._set_gid(event)
        r = self._guard("allow_set_admin", "设置管理员")
        if r:

            return r
        gid = self._resolve_gid(group_id)
        r = await group_members.set_group_admin(self.client, gid, user_id, enable)
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="set_group_special_title")
    async def set_group_special_title(self, event: AstrMessageEvent, user_id: str, special_title: str, group_id: str = "") -> str:
        '''设置群成员专属头衔（仅群主可用，最长6字符）。

        Args:
            user_id(string): 目标QQ号
            special_title(string): 专属头衔文字，留空为取消头衔
            group_id(string): 群号，留空则使用当前群聊
        '''
        await self._get_client(event)
        if not self.client:
            return json.dumps({"ok": False, "detail": "操作失败：未连接到 NapCat"}, ensure_ascii=False)
        self._set_gid(event)
        gid = self._resolve_gid(group_id)
        r = await group_members.set_group_special_title(self.client, gid, user_id, special_title)
        return json.dumps(r, ensure_ascii=False)

    # ═══ 群文件&公告 ═══

    @filter.llm_tool(name="send_group_notice")
    async def send_group_notice(self, event: AstrMessageEvent, content: str, group_id: str = "") -> str:
        '''在当前群聊中发布新公告。

        Args:
            content(string): 公告正文内容
            group_id(string): 群号，留空则使用当前群聊
        '''
        await self._get_client(event)
        if not self.client:
            return json.dumps({"ok": False, "detail": "操作失败：未连接到 NapCat"}, ensure_ascii=False)
        self._set_gid(event)
        gid = self._resolve_gid(group_id)
        r = await group_files.send_group_notice(self.client, gid, content)
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="delete_group_notice")
    async def delete_group_notice(self, event: AstrMessageEvent, notice_id: str, group_id: str = "") -> str:
        '''删除指定ID的群公告。

        Args:
            notice_id(string): 公告ID（可通过 get_group_notice_list 获取）
            group_id(string): 群号，留空则使用当前群聊
        '''
        await self._get_client(event)
        if not self.client:
            return json.dumps({"ok": False, "detail": "操作失败：未连接到 NapCat"}, ensure_ascii=False)
        self._set_gid(event)
        r = self._guard("allow_delete_notice", "删除群公告")
        if r:

            return r
        gid = self._resolve_gid(group_id)
        r = await group_files.delete_group_notice(self.client, gid, notice_id)
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="get_group_notice_list")
    async def get_group_notice_list(self, event: AstrMessageEvent, group_id: str = "") -> str:
        '''获取当前群聊的所有公告列表。

        Args:
            group_id(string): 群号，留空则使用当前群聊
        '''
        await self._get_client(event)
        if not self.client:
            return json.dumps({"ok": False, "detail": "操作失败：未连接到 NapCat"}, ensure_ascii=False)
        self._set_gid(event)
        gid = self._resolve_gid(group_id)
        r = await group_files.get_group_notice_list(self.client, gid, self._limit())
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="list_group_files")
    async def list_group_files(self, event: AstrMessageEvent, group_id: str = "") -> str:
        '''查看当前群聊的群文件目录。

        Args:
            group_id(string): 群号，留空则使用当前群聊
        '''
        await self._get_client(event)
        if not self.client:
            return json.dumps({"ok": False, "detail": "操作失败：未连接到 NapCat"}, ensure_ascii=False)
        self._set_gid(event)
        gid = self._resolve_gid(group_id)
        r = await group_files.list_group_files(self.client, gid, self._limit())
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="delete_group_file")
    async def delete_group_file(self, event: AstrMessageEvent, file_id: str, busid: int = 102, group_id: str = "") -> str:
        '''删除群文件中的指定文件。

        Args:
            file_id(string): 文件ID（可通过 list_group_files 获取）
            busid(number): 文件类型标识，默认102
            group_id(string): 群号，留空则使用当前群聊
        '''
        await self._get_client(event)
        if not self.client:
            return json.dumps({"ok": False, "detail": "操作失败：未连接到 NapCat"}, ensure_ascii=False)
        self._set_gid(event)
        r = self._guard("allow_delete_file", "删除群文件")
        if r:

            return r
        gid = self._resolve_gid(group_id)
        r = await group_files.delete_group_file(self.client, gid, file_id, busid)
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="upload_group_file")
    async def upload_group_file(self, event: AstrMessageEvent, file_path: str, name: str = "", group_id: str = "") -> str:
        '''上传本地文件到群共享。

        Args:
            file_path(string): 本地文件的绝对路径
            name(string): 上传后在群文件中显示的名称，留空则使用原文件名
            group_id(string): 群号，留空则使用当前群聊
        '''
        await self._get_client(event)
        if not self.client:
            return json.dumps({"ok": False, "detail": "操作失败：未连接到 NapCat"}, ensure_ascii=False)
        self._set_gid(event)
        gid = self._resolve_gid(group_id)
        r = await group_files.upload_group_file(self.client, gid, file_path, name)
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="create_group_file_folder")
    async def create_group_file_folder(self, event: AstrMessageEvent, name: str, group_id: str = "") -> str:
        '''在群文件根目录下创建新文件夹。

        Args:
            name(string): 文件夹名称
            group_id(string): 群号，留空则使用当前群聊
        '''
        await self._get_client(event)
        if not self.client:
            return json.dumps({"ok": False, "detail": "操作失败：未连接到 NapCat"}, ensure_ascii=False)
        self._set_gid(event)
        gid = self._resolve_gid(group_id)
        r = await group_files.create_group_file_folder(self.client, gid, name)
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="delete_group_folder")
    async def delete_group_folder(self, event: AstrMessageEvent, folder_id: str, group_id: str = "") -> str:
        '''删除群文件中的文件夹（会同时删除文件夹内所有文件）。

        Args:
            folder_id(string): 文件夹ID
            group_id(string): 群号，留空则使用当前群聊
        '''
        await self._get_client(event)
        if not self.client:
            return json.dumps({"ok": False, "detail": "操作失败：未连接到 NapCat"}, ensure_ascii=False)
        self._set_gid(event)
        r = self._guard("allow_delete_folder", "删除群文件夹")
        if r:

            return r
        gid = self._resolve_gid(group_id)
        r = await group_files.delete_group_folder(self.client, gid, folder_id)
        return json.dumps(r, ensure_ascii=False)

    # ═══ 群设置&查询 ═══

    @filter.llm_tool(name="set_group_whole_ban")
    async def set_group_whole_ban(self, event: AstrMessageEvent, enable: bool, group_id: str = "") -> str:
        '''开启或关闭当前群聊的全体禁言。

        Args:
            enable(boolean): true=开启全体禁言 / false=关闭全体禁言
            group_id(string): 群号，留空则使用当前群聊
        '''
        await self._get_client(event)
        if not self.client:
            return json.dumps({"ok": False, "detail": "操作失败：未连接到 NapCat"}, ensure_ascii=False)
        self._set_gid(event)
        r = self._guard("allow_whole_ban", "全体禁言")
        if r:

            return r
        gid = self._resolve_gid(group_id)
        r = await group_settings.set_group_whole_ban(self.client, gid, enable)
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="set_group_name")
    async def set_group_name(self, event: AstrMessageEvent, group_name: str, group_id: str = "") -> str:
        '''修改当前群聊的名称。

        Args:
            group_name(string): 新的群名称
            group_id(string): 群号，留空则使用当前群聊
        '''
        await self._get_client(event)
        if not self.client:
            return json.dumps({"ok": False, "detail": "操作失败：未连接到 NapCat"}, ensure_ascii=False)
        self._set_gid(event)
        r = self._guard("allow_set_group_name", "修改群名称")
        if r:

            return r
        gid = self._resolve_gid(group_id)
        r = await group_settings.set_group_name(self.client, gid, group_name)
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="send_group_sign")
    async def send_group_sign(self, event: AstrMessageEvent, group_id: str = "") -> str:
        '''在当前群聊进行打卡/签到操作。

        Args:
            group_id(string): 群号，留空则使用当前群聊
        '''
        await self._get_client(event)
        if not self.client:
            return json.dumps({"ok": False, "detail": "操作失败：未连接到 NapCat"}, ensure_ascii=False)
        self._set_gid(event)
        gid = self._resolve_gid(group_id)
        r = await group_settings.send_group_sign(self.client, gid)
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="get_group_members_info")
    async def get_group_members_info(self, event: AstrMessageEvent, group_id: str = "") -> str:
        '''获取当前群聊的完整成员列表（含QQ号、群名片、身份等信息）。

        Args:
            group_id(string): 群号，留空则使用当前群聊
        '''
        await self._get_client(event)
        if not self.client:
            return json.dumps({"ok": False, "detail": "操作失败：未连接到 NapCat"}, ensure_ascii=False)
        self._set_gid(event)
        gid = self._resolve_gid(group_id)
        r = await group_settings.get_group_members_info(self.client, gid, self._limit())
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="get_group_honor_info")
    async def get_group_honor_info(self, event: AstrMessageEvent, type: str = "all", group_id: str = "") -> str:
        '''查看当前群的荣誉信息（龙王、群聊之火、快乐源泉等）。

        Args:
            type(string): 荣誉类型：talkative(龙王) / performer(群聊之火) / emotion(快乐源泉) / all(全部，默认)
            group_id(string): 群号，留空则使用当前群聊
        '''
        await self._get_client(event)
        if not self.client:
            return json.dumps({"ok": False, "detail": "操作失败：未连接到 NapCat"}, ensure_ascii=False)
        self._set_gid(event)
        gid = self._resolve_gid(group_id)
        r = await group_settings.get_group_honor_info(self.client, gid, type, self._limit())
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="get_group_shut_list")
    async def get_group_shut_list(self, event: AstrMessageEvent, group_id: str = "") -> str:
        '''获取当前群聊中被禁言的成员列表。

        Args:
            group_id(string): 群号，留空则使用当前群聊
        '''
        await self._get_client(event)
        if not self.client:
            return json.dumps({"ok": False, "detail": "操作失败：未连接到 NapCat"}, ensure_ascii=False)
        self._set_gid(event)
        gid = self._resolve_gid(group_id)
        r = await group_settings.get_group_shut_list(self.client, gid, self._limit())
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="get_group_at_all_remain")
    async def get_group_at_all_remain(self, event: AstrMessageEvent, group_id: str = "") -> str:
        '''查询当前群聊今日 @全体成员 的剩余可用次数。

        Args:
            group_id(string): 群号，留空则使用当前群聊
        '''
        await self._get_client(event)
        if not self.client:
            return json.dumps({"ok": False, "detail": "操作失败：未连接到 NapCat"}, ensure_ascii=False)
        self._set_gid(event)
        gid = self._resolve_gid(group_id)
        r = await group_settings.get_group_at_all_remain(self.client, gid)
        return json.dumps(r, ensure_ascii=False)

    # ═══ AI语音 ═══

    @filter.llm_tool(name="get_ai_characters")
    async def get_ai_characters(self, event: AstrMessageEvent) -> str:
        '''获取QQ官方TTS所有可用的AI语音角色列表（如luoli、yujie等）。'''
        await self._get_client(event)
        if not self.client:
            return json.dumps({"ok": False, "detail": "操作失败：未连接到 NapCat"}, ensure_ascii=False)
        r = await voice.get_ai_characters(self.client)
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="send_ai_voice")
    async def send_ai_voice(self, event: AstrMessageEvent, text: str, character_id: str = "", group_id: str = "") -> str:
        '''在当前群聊发送AI语音消息（QQ官方TTS）。文本过长会自动截断。

        Args:
            text(string): 要让AI朗读的文本内容
            character_id(string): 语音角色ID，留空则使用插件配置的默认角色。可用角色通过 get_ai_characters 查询
            group_id(string): 群号，留空则使用当前群聊
        '''
        await self._get_client(event)
        if not self.client:
            return json.dumps({"ok": False, "detail": "操作失败：未连接到 NapCat"}, ensure_ascii=False)
        self._set_gid(event)
        gid = self._resolve_gid(group_id)
        r = await voice.send_ai_voice(self.client, self._cfg(), gid, text, character_id)
        return json.dumps(r, ensure_ascii=False)

    # ═══ 个人资料 ═══

    @filter.llm_tool(name="set_qq_profile")
    async def set_qq_profile(self, event: AstrMessageEvent, nickname: str = "", personal_note: str = "") -> str:
        '''修改机器人自身的QQ个人资料（昵称和/或个性签名）。

        Args:
            nickname(string): 新昵称，留空则不修改
            personal_note(string): 新个性签名，留空则不修改
        '''
        await self._get_client(event)
        if not self.client:
            return json.dumps({"ok": False, "detail": "操作失败：未连接到 NapCat"}, ensure_ascii=False)
        r = self._guard("allow_set_profile", "修改个人资料")
        if r:

            return r
        r = await profile.set_qq_profile(self.client, nickname, personal_note)
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="set_qq_avatar")
    async def set_qq_avatar(self, event: AstrMessageEvent, file: str) -> str:
        '''修改机器人自身的QQ头像。

        Args:
            file(string): 图片路径（本地绝对路径 / base64://格式 / http(s)://URL）
        '''
        await self._get_client(event)
        if not self.client:
            return json.dumps({"ok": False, "detail": "操作失败：未连接到 NapCat"}, ensure_ascii=False)
        r = self._guard("allow_set_avatar", "修改QQ头像")
        if r:

            return r
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
        await self._get_client(event)
        if not self.client:
            return json.dumps({"ok": False, "detail": "操作失败：未连接到 NapCat"}, ensure_ascii=False)
        self._set_gid(event)
        gid = self._resolve_gid(group_id)
        r = await history.get_group_msg_history(self.client, gid, count, self._limit())
        return json.dumps(r, ensure_ascii=False)

    @filter.llm_tool(name="get_friend_msg_history")
    async def get_friend_msg_history(self, event: AstrMessageEvent, user_id: str, count: int = 20) -> str:
        '''获取与指定好友的私聊历史消息记录。

        Args:
            user_id(string): 好友QQ号
            count(number): 获取条数，默认20条
        '''
        await self._get_client(event)
        if not self.client:
            return json.dumps({"ok": False, "detail": "操作失败：未连接到 NapCat"}, ensure_ascii=False)
        r = await history.get_friend_msg_history(self.client, user_id, count, self._limit())
        return json.dumps(r, ensure_ascii=False)
