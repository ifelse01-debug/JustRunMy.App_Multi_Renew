#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import subprocess
import requests
from seleniumbase import SB

# ============================================================
#  环境变量配置 (严格对接 EML_1, PWD_1, EML_2, PWD_2, TG_TOKEN, TG_ID)
# ============================================================
ACCOUNTS = []
if os.environ.get("EML_1") and os.environ.get("PWD_1"):
    ACCOUNTS.append({"email": os.environ.get("EML_1"), "pwd": os.environ.get("PWD_1"), "tag": "账号 A"})
if os.environ.get("EML_2") and os.environ.get("PWD_2"):
    ACCOUNTS.append({"email": os.environ.get("EML_2"), "pwd": os.environ.get("PWD_2"), "tag": "账号 B"})

TG_TOKEN = os.environ.get("TG_TOKEN")
TG_ID    = os.environ.get("TG_ID")

if not ACCOUNTS:
    print("❌ 致命错误：未检测到有效环境变量（EML_1/PWD_1 或 EML_2/PWD_2）")
    sys.exit(1)

DYNAMIC_APP_NAME = "未知应用"

# ============================================================
#  核心逻辑：JS 注入与坐标计算 (保持原版逻辑)
# ============================================================
_EXPAND_JS = """(function() { var ts = document.querySelector('input[name="cf-turnstile-response"]'); if (!ts) return 'no-turnstile'; var el = ts; for (var i = 0; i < 20; i++) { el = el.parentElement; if (!el) break; var s = window.getComputedStyle(el); if (s.overflow === 'hidden' || s.overflowX === 'hidden' || s.overflowY === 'hidden') el.style.overflow = 'visible'; el.style.minWidth = 'max-content'; } document.querySelectorAll('iframe').forEach(function(f){ if (f.src && f.src.includes('challenges.cloudflare.com')) { f.style.width = '300px'; f.style.height = '65px'; f.style.minWidth = '300px'; f.style.visibility = 'visible'; f.style.opacity = '1'; } }); return 'done'; })()"""
_SOLVED_JS = """(function(){ var i = document.querySelector('input[name="cf-turnstile-response"]'); return !!(i && i.value && i.value.length > 20); })()"""
_EXISTS_JS = """(function(){ return document.querySelector('input[name="cf-turnstile-response"]') !== null; })()"""
_COORDS_JS = """(function(){ var iframes = document.querySelectorAll('iframe'); for (var i = 0; i < iframes.length; i++) { var src = iframes[i].src || ''; if (src.includes('cloudflare') || src.includes('turnstile') || src.includes('challenges')) { var r = iframes[i].getBoundingClientRect(); if (r.width > 0 && r.height > 0) return {cx: Math.round(r.x + 30), cy: Math.round(r.y + r.height / 2)}; } } return null; })()"""
_WININFO_JS = """(function(){ return {sx: window.screenX || 0, sy: window.screenY || 0, oh: window.outerHeight, ih: window.innerHeight}; })()"""

# ============================================================
#  物理级操作：xdotool
# ============================================================
def _activate_window():
    for cls in ["chrome", "chromium", "Chromium", "Chrome"]:
        try:
            r = subprocess.run(["xdotool", "search", "--onlyvisible", "--class", cls], capture_output=True, text=True, timeout=3)
            wids = [w for w in r.stdout.strip().split("\n") if w.strip()]
            if wids:
                subprocess.run(["xdotool", "windowactivate", "--sync", wids[0]], timeout=3)
                return True
        except: pass
    return False

def _xdotool_click(x, y):
    _activate_window()
    try:
        subprocess.run(["xdotool", "mousemove", "--sync", str(x), str(y)], timeout=3)
        time.sleep(0.1)
        subprocess.run(["xdotool", "click", "1"], timeout=2)
    except:
        os.system(f"xdotool mousemove {x} {y} click 1 2>/dev/null")

def handle_turnstile(sb):
    print("🔍 处理 Cloudflare Turnstile 验证...")
    sb.execute_script(_EXPAND_JS)
    for i in range(1, 11):
        if sb.execute_script(_SOLVED_JS):
            print(
