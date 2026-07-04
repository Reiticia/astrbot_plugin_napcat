# -*- coding: utf-8 -*-
"""QQ 邮件发送。"""
import smtplib
from email.mime.text import MIMEText
from email.header import Header


async def send_qq_email(config: dict, to: str, subject: str, content: str) -> dict:
    sender = config.get('email_sender', '')
    auth = config.get('email_authorization_code', '')
    if not sender or not auth:
        return {'ok': False, 'detail': '请先配置发件人邮箱和授权码'}
    host = config.get('email_smtp_server', 'smtp.qq.com')
    port = config.get('email_smtp_port', 465)
    msg = MIMEText(content, 'plain', 'utf-8')
    msg['Subject'] = Header(subject, 'utf-8')
    msg['From'] = sender
    msg['To'] = to
    with smtplib.SMTP_SSL(host, port, timeout=10) as smtp:
        smtp.login(sender, auth)
        smtp.sendmail(sender, [to], msg.as_string())
    return {'ok': True, 'detail': '邮件已发送'}
