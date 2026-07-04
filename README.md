# NapCat 工具

基于 NapCat 协议为 AstrBot 提供 QQ 平台操作能力：消息收发、群管理、联系人搜索、在线状态控制、个人资料、AI 语音。

- **插件名**：`astrbot_plugin_napcat`
- **版本**：`1.0.0`
- **作者**：`reine-ishyanami`
- **适配 AstrBot 版本**：`>= 4.24.2`
- **仓库地址**：`https://github.com/reine-ishyanami/astrbot_plugin_napcat`

## 项目结构

```
astrbot_plugin_napcat/
├── main.py              # 入口：Main 类、生命周期、工具注册
├── qq_tools/            # 功能模块包
│   ├── __init__.py
│   ├── utils.py         # 公共函数（错误脱敏、截断、图片解析）
│   ├── constants.py     # QQ 状态预设常量
│   ├── status_ctrl.py   # StatusController — QQ 在线状态控制
│   ├── messaging.py     # 消息收发 / 戳一戳 / 点赞
│   ├── contacts.py      # 联系人搜索 / 列表 / 群成员身份
│   ├── qq_status.py     # QQ 状态工具
│   ├── group_members.py # 群成员控制（禁言/踢人/名片/管理员/头衔）
│   ├── group_files.py   # 群文件 & 群公告
│   ├── group_settings.py# 群设置 & 信息查询
│   ├── voice.py         # AI 语音（TTS）
│   ├── profile.py       # 个人资料 & 头像
│   └── history.py       # 历史消息
├── _conf_schema.json    # 配置项定义
├── metadata.yaml        # 插件元信息
└── README.md
```

## 功能特性

- 消息收发：向群聊或好友发送消息，支持戳一戳、点赞
- 联系人管理：模糊搜索好友和群聊、列出联系人、查询群成员身份
- QQ 在线状态：在线/离开/忙碌/隐身/听歌中/睡觉中/学习中，设定时长后自动恢复
- 群管理：禁言、踢人、全体禁言、改名片、管理员、专属头衔、群公告、群文件、群荣誉等
- AI 语音：调用 QQ 官方 TTS，支持多角色朗读
- 个人资料：修改机器人昵称、个性签名、QQ 头像
- 历史消息：获取群聊和私聊的历史消息记录

## 安装

```bash
# 在 AstrBot 插件目录下
git clone https://github.com/reine-ishyanami/astrbot_plugin_napcat.git
```

## 配置项

| 配置键 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `enabled` | `bool` | `true` | 插件总开关 |
| `group_manage_enabled` | `bool` | `true` | 群管理功能总开关，关闭后所有群管工具不可用 |
| `kick_enabled` | `bool` | `true` | 踢人功能独立开关，防止误操作 |
| `max_output_chars` | `int` | `2000` | 工具返回内容最大字符数，0 为不限制 |
| `ai_voice_default_character` | `str` | `""` | AI 语音默认角色 ID（例如 luoli、yujie），可通过 `/ai_characters` 查看可用角色 |
| `ai_voice_max_text_length` | `int` | `500` | AI 语音文本最大长度，腾讯限制约 500 字符 |
| `enable_<工具名>` | `bool` | `true` | 各工具启用开关，共 35 个，默认全部开启 |

## 指令列表

> 必填章节。列出所有已注册的管理员指令。

### 消息操作

| 指令 | 参数 | 权限 | 说明 | 示例 |
| --- | --- | --- | --- | --- |
| `/tool_send_message` | `<目标ID> <消息>` | 管理员 | 向指定群聊或好友发送消息 | `/tool_send_message 123456 会议取消了` |
| `/tool_poke` | `<QQ号>` | 管理员 | 发送戳一戳 | `/tool_poke 123456` |
| `/send_like` | `<QQ号> [次数]` | 管理员 | 给用户发送名片赞 | `/send_like 123456 10` |

### 联系人

| 指令 | 参数 | 权限 | 说明 | 示例 |
| --- | --- | --- | --- | --- |
| `/tool_search` | `<关键词>` | 管理员 | 按名称/QQ号模糊搜索好友和群 | `/tool_search 通知群` |
| `/tool_list` | `[all/friend/group]` | 管理员 | 列出好友列表或群聊列表 | `/tool_list friend` |

### QQ 在线状态

| 指令 | 参数 | 权限 | 说明 | 示例 |
| --- | --- | --- | --- | --- |
| `/tool_status` | `<状态码> <分钟>` | 管理员 | 设置 QQ 状态（online/qme/away/busy/dnd/invisible/listening/sleeping/studying） | `/tool_status listening 60` |
| `/tool_status_get` | 无 | 管理员 | 查看当前 QQ 状态及剩余时间 | `/tool_status_get` |

### 群管理 — 成员控制

| 指令 | 参数 | 权限 | 说明 | 示例 |
| --- | --- | --- | --- | --- |
| `/ban_user` | `<QQ号> <分钟>` | 管理员 | 禁言群成员 | `/ban_user 123456 10` |
| `/unban_user` | `<QQ号>` | 管理员 | 解除禁言 | `/unban_user 123456` |
| `/kick` | `<QQ号>` | 管理员 | 踢出群成员 | `/kick 123456` |
| `/whole_ban` | `<on/off>` | 管理员 | 全体禁言开关 | `/whole_ban on` |
| `/set_card` | `<QQ号> <新名片>` | 管理员 | 修改群成员名片 | `/set_card 123456 小明` |
| `/set_admin` | `<QQ号> <on/off>` | 管理员 | 设置或取消管理员 | `/set_admin 123456 on` |
| `/set_title` | `<QQ号> <头衔>` | 管理员 | 设置群成员专属头衔（需群主权限） | `/set_title 123456 大佬` |

### 群管理 — 公告与文件

| 指令 | 参数 | 权限 | 说明 | 示例 |
| --- | --- | --- | --- | --- |
| `/send_notice` | `<内容>` | 管理员 | 发布群公告 | `/send_notice 明天放假一天` |
| `/del_notice` | `<公告ID>` | 管理员 | 删除群公告 | `/del_notice abc123` |
| `/list_notices` | 无 | 管理员 | 查看群公告列表 | `/list_notices` |
| `/list_files` | 无 | 管理员 | 查看群文件列表 | `/list_files` |
| `/delete_group_file` | `<file_id>` | 管理员 | 删除群文件 | `/delete_group_file xyz` |
| `/upload_file` | `<本地路径> [文件名]` | 管理员 | 上传文件到群共享 | `/upload_file /tmp/report.pdf` |
| `/create_folder` | `<文件夹名>` | 管理员 | 在群文件根目录创建文件夹 | `/create_folder 学习资料` |
| `/del_folder` | `<文件夹ID>` | 管理员 | 删除群文件夹（含内部文件） | `/del_folder fold123` |

### 群管理 — 设置与查询

| 指令 | 参数 | 权限 | 说明 | 示例 |
| --- | --- | --- | --- | --- |
| `/set_group_name` | `<新名称>` | 管理员 | 修改群名称 | `/set_group_name 摸鱼交流群` |
| `/set_add_option` | `<allow/verify/deny>` | 管理员 | 设置加群验证方式 | `/set_add_option verify` |
| `/group_sign` | 无 | 管理员 | 群打卡/签到 | `/group_sign` |
| `/group_members` | 无 | 管理员 | 获取群成员完整列表 | `/group_members` |
| `/group_honor` | `[talkative/performer/emotion/all]` | 管理员 | 查看群荣誉（龙王、群聊之火等） | `/group_honor talkative` |
| `/shut_list` | 无 | 管理员 | 查看当前被禁言的成员 | `/shut_list` |
| `/at_all_remain` | 无 | 管理员 | 查询 @全体成员 今日剩余次数 | `/at_all_remain` |

### AI 语音

| 指令 | 参数 | 权限 | 说明 | 示例 |
| --- | --- | --- | --- | --- |
| `/ai_characters` | 无 | 管理员 | 获取可用的 AI 语音角色列表 | `/ai_characters` |
| `/ai_voice` | `[角色ID] <文本>` | 管理员 | 发送 AI 语音消息（仅群聊） | `/ai_voice luoli 大家好` |

### 个人资料

| 指令 | 参数 | 权限 | 说明 | 示例 |
| --- | --- | --- | --- | --- |
| `/set_profile` | `nickname=xxx personal_note=xxx` | 管理员 | 修改机器人昵称和个性签名 | `/set_profile nickname=小助手 personal_note=有事私聊` |
| `/set_qq_avatar` | `[图片路径/URL/base64]` | 管理员 | 设置 QQ 头像 | `/set_qq_avatar /tmp/avatar.png` |

### 历史消息

| 指令 | 参数 | 权限 | 说明 | 示例 |
| --- | --- | --- | --- | --- |
| `/get_group_msg_history` | `[群号] [数量]` | 管理员 | 获取群聊历史消息 | `/get_group_msg_history 123456 20` |
| `/get_friend_msg_history` | `<QQ号> [数量]` | 管理员 | 获取私聊历史消息 | `/get_friend_msg_history 123456 20` |

## 函数调用 / 对外接口

> 必填章节。

所有工具通过 `@filter.llm_tool` 装饰器直接注册在 `Main` 类上，LLM 可直接按名称调用，无需额外分发层。

### 领域模块函数

每个领域模块导出纯异步函数，可直接独立调用：

```python
from .qq_tools.group_members import set_group_ban
result = await set_group_ban(client, group_id=123456, user_id='789', duration=600)
# => {'ok': True, 'detail': '已禁言 600 秒 789'}
```

所有函数返回统一格式：`{'ok': bool, 'detail': str, 'result'?: str}`。

## 附加功能

> 必填章节。

- **QQ 状态自动恢复**：设置临时状态（听歌中、睡觉中等）后，到期自动切回"在线"
- **联系人缓存**：好友列表和群聊列表缓存 5 分钟，减少对 NapCat 的 API 调用频率

## 依赖

- `astrbot`（AstrBot 核心框架）

## 常见问题

- **问题**：群管理操作返回"权限不足"错误
  **解决**：确认机器人账号在目标群拥有管理员或群主权限。

- **问题**：AI 语音发送后群内无反应
  **解决**：先通过 `/ai_characters` 测试，若失败则 NapCat 版本可能不支持该功能。

- **问题**：LLM 不主动调用工具
  **解决**：在 AstrBot 人格设定中告知 LLM 可用工具。

- **问题**：斜杠命令无法使用
  **解决**：所有指令需要 AstrBot 管理员权限。

## 更新日志

| 版本 | 日期 | 说明 |
| --- | --- | --- |
| `1.0.0` | `2026-07-04` | 初始版本，35 个 LLM 工具，覆盖消息/群管/联系人/状态/邮件/语音/资料/历史消息 |

## 协议

`MIT`
