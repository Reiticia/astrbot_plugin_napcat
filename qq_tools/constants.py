# -*- coding: utf-8 -*-
"""常量定义。"""

# QQ 在线状态预设：(显示名, status_code, ext_status)
STATUS_PRESETS = {
    'online':    ('在线',      10, 0),
    'qme':       ('Q我吧',     60, 0),
    'away':      ('离开',      30, 0),
    'busy':      ('忙碌',      50, 0),
    'dnd':       ('请勿打扰',  70, 0),
    'invisible': ('隐身',      40, 0),
    'listening': ('听歌中',    10, 1028),
    'sleeping':  ('睡觉中',    10, 1016),
    'studying':  ('学习中',    10, 1018),
}
