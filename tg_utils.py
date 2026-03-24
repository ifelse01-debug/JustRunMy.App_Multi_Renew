#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import requests

def send_telegram_notification(text):
    """
    发送 Telegram 消息通知
    
    :param text: 消息内容
    """
    token = os.environ.get("TG_TOKEN")
    chat_id = os.environ.get("TG_ID")
    
    if not token or not chat_id:
        print("未配置 TG_TOKEN 或 TG_ID，跳过 Telegram 推送。")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            print("  Telegram 通知发送成功！")
        else:
            print(f"  Telegram 通知发送失败: {r.text}")
    except Exception as e:
        print(f"  Telegram 通知发送异常: {e}")
