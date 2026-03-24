#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
from seleniumbase import SB
from sb_turnstile_solver import handle_turnstile, exists_turnstile
from tg_utils import send_telegram_notification


LOGIN_URL = "https://justrunmy.app/id/Account/Login"
DOMAIN    = "justrunmy.app"

# ============================================================
#  环境变量与全局变量
# ============================================================
EMAIL        = os.environ.get("JustRunMy_ACC")
PASSWORD     = os.environ.get("JustRunMy_ACC_PWD")

if not EMAIL or not PASSWORD:
    print("致命错误：未找到 ACC 或 ACC_PWD 环境变量！")
    print("请检查 GitHub Repository Secrets 是否配置正确（EML_1, PWD_1...）。")
    sys.exit(1)

class JustRunMyBot:
    def __init__(self):
        self.email = EMAIL
        self.password = PASSWORD
        self.dynamic_app_name = "未知应用"
        self.user_data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jrm_sb_profile")
        
        self.sb_context = None
        self.sb = None

    def init_browser(self):
        print("初始化浏览器 (SeleniumBase UC Mode)...")
        proxy_url_env = os.environ.get("PROXY_URL", "").strip()
        sb_kwargs = {
            "uc": True,
            "test": True,
            "headless": False,
            "user_data_dir": self.user_data_dir
        }
        
        if proxy_url_env:
            local_proxy = "http://127.0.0.1:8080"
            print(f"检测到代理配置，挂载本地通道: {local_proxy}")
            sb_kwargs["proxy"] = local_proxy
            
        self.sb_context = SB(**sb_kwargs)
        self.sb = self.sb_context.__enter__()
        time.sleep(2)
        
        try:
            self.sb.open("https://api.ipify.org/?format=json")
            print(f"当前出口 IP: {self.sb.get_text('body')}")
        except Exception:
            pass

    def send_tg_message(self, status_text):
        text = (
            f"📢 JustRunMy.app 续期通知 | {self.dynamic_app_name}\n"
            f"👤 账号: {self.email}\n\n"
            f"{status_text}"
        )
        send_telegram_notification(text)

    def js_fill_input(self, selector: str, text: str):
        safe_text = text.replace('\\', '\\\\').replace('"', '\\"')
        self.sb.execute_script(f"""
        (function(){{
            var el = document.querySelector('{selector}');
            if (!el) return;
            var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
            if (nativeInputValueSetter) {{
                nativeInputValueSetter.call(el, "{safe_text}");
            }} else {{
                el.value = "{safe_text}";
            }}
            el.dispatchEvent(new Event('input', {{ bubbles: true }}));
            el.dispatchEvent(new Event('change', {{ bubbles: true }}));
        }})()
        """)

    def perform_login(self) -> bool:
        print(f"打开登录页面: {LOGIN_URL}")
        self.sb.uc_open_with_reconnect(LOGIN_URL, reconnect_time=5)
        time.sleep(4)

        try:
            self.sb.wait_for_element('input[name="Email"]', timeout=15)
        except Exception:
            print("页面未加载出登录表单")
            self.sb.save_screenshot("login_load_fail.png")
            return False

        print("关闭可能的 Cookie 弹窗...")
        try:
            for btn in self.sb.find_elements("button"):
                if "Accept" in (btn.text or ""):
                    btn.click()
                    time.sleep(0.5)
                    break
        except Exception:
            pass

        print(f"填写邮箱...")
        self.js_fill_input('input[name="Email"]', self.email)
        time.sleep(0.3)
        
        print("填写密码...")
        self.js_fill_input('input[name="Password"]', self.password)
        time.sleep(1)

        if exists_turnstile(self.sb):
            if not handle_turnstile(self.sb):
                print("登录界面的 Turnstile 验证失败")
                self.sb.save_screenshot("login_turnstile_fail.png")
                return False
        else:
            print("未检测到 Turnstile")

        print("敲击回车提交表单...")
        self.sb.press_keys('input[name="Password"]', '\n')

        print("等待登录跳转...")
        for _ in range(12):
            time.sleep(1)
            if self.sb.get_current_url().split('?')[0].lower() != LOGIN_URL.lower():
                break

        if self.sb.get_current_url().split('?')[0].lower() != LOGIN_URL.lower():
            print("登录成功！")
            return True
            
        print("登录失败，页面没有跳转。")
        self.sb.save_screenshot("login_failed.png")
        return False

    def navigate_to_app(self) -> bool:
        print("进入控制面板: https://justrunmy.app/panel")
        self.sb.open("https://justrunmy.app/panel")
        time.sleep(5)

        print("自动读取应用名称...")
        retry_count = 3
        found = False
        for attempt in range(1, retry_count + 1):
            try:
                self.sb.wait_for_element('h3.font-semibold', timeout=15)
                self.dynamic_app_name = self.sb.get_text('h3.font-semibold')
                print(f"成功抓取到应用名称: {self.dynamic_app_name}")
                
                self.sb.click('h3.font-semibold')
                time.sleep(3)
                print(f"成功进入应用详情页: {self.sb.get_current_url()}")
                found = True
                break
            except Exception as e:
                if attempt < retry_count:
                    print(f"第 {attempt} 次尝试获取应用卡片失败，刷新页面重试...")
                    self.sb.refresh()
                    time.sleep(5)
        
        if not found:
            self.sb.save_screenshot("renew_app_not_found.png")
            self.send_tg_message(f'❌ 续期失败(找不到应用)\n')
            return False
        return True

    def perform_renewal(self) -> bool:
        print("点击 Reset Timer 按钮...")
        try:
            self.sb.click('button:contains("Reset Timer")')
            time.sleep(3)
        except Exception as e:
            print(f"找不到 Reset Timer 按钮: {e}")
            self.sb.save_screenshot("renew_reset_btn_not_found.png")
            self.send_tg_message(f'❌ 续期失败(找不到按钮)\n')
            return False

        print("检查续期弹窗内是否需要 CF 验证...")
        if exists_turnstile(self.sb):
            if not handle_turnstile(self.sb):
                print("弹窗内的 Turnstile 验证失败")
                self.sb.save_screenshot("renew_turnstile_fail.png")
                self.send_tg_message(f'❌ 续期失败(人机验证未过)\n')
                return False

        print("点击 Just Reset 确认续期...")
        try:
            self.sb.click('button:contains("Just Reset")')
            print("提交续期请求，等待服务器处理...")
            time.sleep(5) 
            return True
        except Exception as e:
            print(f"找不到 Just Reset 按钮: {e}")
            self.sb.save_screenshot("renew_just_reset_not_found.png")
            self.send_tg_message(f'❌ 续期失败(无法确认)\n')
            return False

    def verify_timer(self) -> bool:
        print("验证最终倒计时状态...")
        try:
            self.sb.refresh()
            time.sleep(4)
            timer_text = self.sb.get_text('span.font-mono.text-xl')
            print(f"当前应用剩余时间: {timer_text}")
            
            if "2 days 23" in timer_text or "3 days" in timer_text:
                print("续期任务圆满完成！")
                self.sb.save_screenshot("renew_success.png")
                self.send_tg_message(f'🎉 续期完成\n\n⌛ 剩余时间: {timer_text}')
                return True
            else:
                print("倒计时似乎没有重置到最高值，请人工检查截图。")
                self.sb.save_screenshot("renew_warning.png")
                self.send_tg_message(f'⚠️ 续期异常(请检查)\n\n⌛ 剩余时间: {timer_text}')
                return True 
        except Exception as e:
            print(f"读取倒计时失败，但流程已执行完毕: {e}")
            self.sb.save_screenshot("renew_timer_read_fail.png")
            self.send_tg_message(f'⚠️ 读取剩余时间失败\n')
            return False

    def run(self):
        print("=" * 50)
        print("   JustRunMy.app 自动登录与续期脚本")
        print("=" * 50)
        
        try:
            self.init_browser()
            
            if self.perform_login():
                if self.navigate_to_app():
                    if self.perform_renewal():
                        self.verify_timer()
            else:
                print("\n登录环节失败，终止后续续期操作。")
                self.send_tg_message(f'❌ 登录失败\n')

        except Exception as e:
            print(f"全局异常: {e}")
            self.send_tg_message(f"❌ JustRunMy 脚本崩溃: {e}")
        finally:
            self.close()

    def close(self):
        if self.sb_context:
            try:
                self.sb_context.__exit__(None, None, None)
            except Exception:
                pass
        print("浏览器资源已释放")

if __name__ == "__main__":
    bot = JustRunMyBot()
    bot.run()