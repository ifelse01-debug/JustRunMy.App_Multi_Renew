#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, sys
import requests

token = os.environ.get("TG_TOKEN", "8200328409:***")
chat_id = os.environ.get("TG_ID", "***")

if not token or not chat_id:
    print("未配置 TG_TOKEN 或 TG_ID，跳过 Telegram 推送。")
    sys.exit(1)
    
def send_telegram_notification(text):
    """
    发送 Telegram 消息通知
    
    :param text: 消息内容
    """
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

def send_telegram_photo(path, caption=""):
    """
    发送 Telegram 图片
    
    :param path: 图片路径
    :param caption: 图片描述
    """
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    
    try:
        with open(path, 'rb') as f:
            r = requests.post(
                url,
                data={"chat_id": chat_id, "caption": caption[:1024]},
                files={"photo": f},
                timeout=60
            )
            if r.status_code == 200:
                print("  Telegram 图片发送成功！")
            else:
                print(f"  Telegram 通知图片发送失败: {r.text}")
    except Exception as e:
        print(f"  Telegram 通知图片发送异常: {e}")
