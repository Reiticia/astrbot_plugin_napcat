# -*- coding: utf-8 -*-
"""QQ AI 语音（TTS）。"""
import json


async def get_ai_characters(client) -> dict:
    result = await client.call_action('get_ai_characters', chat_type=1)
    chars = result.get('data', result)
    return {'ok': True, 'result': json.dumps(chars, ensure_ascii=False)}


async def send_ai_voice(client, config: dict, group_id: int,
                        text: str, character_id: str = '') -> dict:
    if not character_id:
        character_id = config.get('ai_voice_default_character', '')
    limit = config.get('ai_voice_max_text_length', 500)
    await client.call_action('send_group_ai_record',
        group_id=group_id, character_id=character_id,
        text=text[:limit], chat_type=1)
    return {'ok': True, 'detail': '语音已发送'}
