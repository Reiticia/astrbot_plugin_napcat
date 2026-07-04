# -*- coding: utf-8 -*-
"""公共工具函数。"""
import re
import os
import base64


def safe_error(e: Exception) -> str:
    """脱敏错误信息：隐藏文件路径和 IP 地址。"""
    msg = str(e)
    msg = re.sub(r'[/\\][\w./\\-]+\.py', '[internal]', msg)
    msg = re.sub(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', '[redacted]', msg)
    return msg[:200] + '...' if len(msg) > 200 else (msg or '操作失败')


def truncate(text: str, limit: int = 2000) -> str:
    """截断文本，附带原始长度提示。"""
    if limit > 0 and len(text) > limit:
        return text[:limit] + f'\n…（共 {len(text)} 字符，已截断）'
    return text


def resolve_image(file_ref: str) -> str:
    """将图片路径/URL/base64 统一为 base64:// 格式。"""
    if not file_ref:
        return ''
    if file_ref.startswith('base64://') or file_ref.startswith('http'):
        return file_ref
    if os.path.isfile(file_ref):
        with open(file_ref, 'rb') as f:
            return 'base64://' + base64.b64encode(f.read()).decode()
    return file_ref
