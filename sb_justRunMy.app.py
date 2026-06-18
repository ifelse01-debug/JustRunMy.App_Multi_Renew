#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
from generate_sign import generate_sign
from tg_utils import send_telegram_notification, send_telegram_photo
from scrapling.fetchers import StealthySession


# ============================================================
#  Webhook 重试链接
# ============================================================
_HOOK_BASE = "https://aa.94sub.qzz.io/hook"
_HOOK_ACCESS_KEY = os.environ.get("HOOK_ACCESS_KEY", "LUenTR6XIqS3AiaA87brxJKkrXFVpQPrHYoWgVv06F78C5Ra").strip()
_HOOK_USER = "dfg727"
_HOOK_REPO = "JustRunMy.App_Multi_Renew"
_HOOK_WORKFLOW = "JustRunMy.yml"


def build_retry_url() -> str:
    """生成带签名的 Webhook 重试链接"""
    ts, sign = generate_sign()
    param = f"{ts}|{sign}|{_HOOK_USER}|{_HOOK_REPO}|{_HOOK_WORKFLOW}"
    return f"{_HOOK_BASE}?access_key={_HOOK_ACCESS_KEY}&param={param}"


LOGIN_URL = "https://justrunmy.app/id/Account/Login"
DOMAIN    = "justrunmy.app"

# ============================================================
#  环境变量与全局变量
# ============================================================
EMAIL        = os.environ.get("JustRunMy_ACC", "coders.lu@gmail.com").strip()
PASSWORD     = os.environ.get("JustRunMy_ACC_PWD", "***").strip()
if not EMAIL or not PASSWORD:
    print("致命错误：未找到 ACC 或 ACC_PWD 环境变量！")
    print("请检查 GitHub Repository Secrets 是否配置正确（EML_1, PWD_1...）。")
    sys.exit(1)


# ============================================================
#  Turnstile / Captcha 助手函数
# ============================================================
def _has_turnstile_or_captcha(page):
    captcha_selectors = (
        "textarea[name='cf-turnstile-response']",
        "input[name='cf-turnstile-response']",
        "textarea[name='g-recaptcha-response']",
        "input[name='g-recaptcha-response']",
        "iframe[src*='turnstile']",
        "iframe[title*='Widget containing a Cloudflare security challenge']",
        ".cf-turnstile",
        "[data-sitekey]",
    )

    for selector in captcha_selectors:
        try:
            if page.locator(selector).count() > 0:
                print(f"检测到验证码相关元素: {selector}")
                return True
        except Exception:
            pass

    print("未检测到验证码相关元素，本次无需等待 token")
    return False


def _wait_for_turnstile_token(page, max_wait_ms, poll_interval_ms=500):
    token_selectors = (
        "textarea[name='cf-turnstile-response']",
        "input[name='cf-turnstile-response']",
        "textarea[name='g-recaptcha-response']",
        "input[name='g-recaptcha-response']",
    )
    start_time = time.time()

    while int((time.time() - start_time) * 1000) < max_wait_ms:
        for selector in token_selectors:
            try:
                locator = page.locator(selector).first
                if locator.count() == 0:
                    continue
                token_value = (locator.input_value(timeout=1000) or "").strip()
                if token_value:
                    print("验证码已就绪")
                    return True
            except Exception:
                continue

        elapsed_ms = int((time.time() - start_time) * 1000)
        remaining_ms = max_wait_ms - elapsed_ms
        sleep_ms = min(poll_interval_ms, max(remaining_ms, 0))
        if sleep_ms <= 0:
            break
        page.wait_for_timeout(sleep_ms)

    print(f"在 {max_wait_ms} ms 内未等到有效的验证码 token")
    return False


class JustRunMyBot:
    def __init__(self):
        self.email = EMAIL
        self.password = PASSWORD
        self.dynamic_app_name = "未知应用"
        self.session = None
        self.page = None

    def send_tg_message(self, status_text):
        text = (
            f"📢 JustRunMy.app 续期通知\n\n"
            f"👤 账号: {self.email}\n"
            f"📱 应用: {self.dynamic_app_name}\n\n"
            f"{status_text}"
        )
        send_telegram_notification(text)

    def perform_login(self, page) -> bool:
        print(f"当前页面 URL: {page.url}")
        
        try:
            page.wait_for_selector('input[name="Email"]', timeout=15000)
        except Exception:
            print("页面未加载出登录表单")
            img_path = "login_load_fail.png"
            page.screenshot(path=img_path)
            send_telegram_photo(img_path, caption="登录表单加载失败")
            return False

        print("关闭可能的 Cookie 弹窗...")
        try:
            accept_btn = page.locator("button:has-text('Accept')").first
            if accept_btn.count() > 0 and accept_btn.is_visible(timeout=2000):
                accept_btn.click()
                page.wait_for_timeout(500)
        except Exception:
            pass

        print("填写邮箱...")
        page.locator('input[name="Email"]').first.fill(self.email)
        page.wait_for_timeout(300)
        
        print("填写密码...")
        page.locator('input[name="Password"]').first.fill(self.password)
        page.wait_for_timeout(1000)

        if _has_turnstile_or_captcha(page):
            if not _wait_for_turnstile_token(page, 15000):
                print("登录界面的 Turnstile 验证失败")
                img_path = "login_turnstile_fail.png"
                page.screenshot(path=img_path)
                send_telegram_photo(img_path, caption="登录 Turnstile 验证失败")
                return False
        else:
            print("未检测到 Turnstile")

        print("敲击回车提交表单...")
        page.locator('input[name="Password"]').first.press('Enter')

        print("等待登录跳转...")
        start_time = time.time()
        login_success = False
        while time.time() - start_time < 15:
            current_url = page.url
            if current_url.split('?')[0].lower() != LOGIN_URL.lower():
                login_success = True
                break
            page.wait_for_timeout(1000)

        if login_success:
            print("登录成功！")
            return True
            
        print("登录失败，页面没有跳转。")
        img_path = "login_failed.png"
        page.screenshot(path=img_path)
        send_telegram_photo(img_path, caption="登录跳转失败")
        return False

    def navigate_to_app(self, page) -> bool:
        print("进入控制面板: https://justrunmy.app/panel")
        page.goto("https://justrunmy.app/panel")
        page.wait_for_timeout(5000)

        print("自动读取应用名称...")
        retry_count = 3
        found = False
        for attempt in range(1, retry_count + 1):
            try:
                page.wait_for_selector('h3.font-semibold', timeout=15000)
                self.dynamic_app_name = page.locator('h3.font-semibold').first.inner_text().strip()
                print(f"成功抓取到应用名称: {self.dynamic_app_name}")
                
                page.locator('h3.font-semibold').first.click()
                page.wait_for_timeout(3000)
                print(f"成功进入应用详情页: {page.url}")
                found = True
                break
            except Exception as e:
                if attempt < retry_count:
                    print(f"第 {attempt} 次尝试获取应用卡片失败，刷新页面重试... 错误: {e}")
                    page.reload()
                    page.wait_for_timeout(5000)
        
        if not found:
            img_path = "renew_app_not_found.png"
            page.screenshot(path=img_path)
            send_telegram_photo(img_path, caption="找不到应用卡片")
            self.send_tg_message(f'❌ 续期失败(找不到应用)\n' + f"\n🔁 重试链接: {build_retry_url()}")
            return False
        return True

    def perform_renewal(self, page) -> bool:
        print("点击 Reset Timer 按钮...")
        try:
            page.locator('button:has-text("Reset Timer")').first.click()
            page.wait_for_timeout(3000)
        except Exception as e:
            print(f"找不到 Reset Timer 按钮: {e}")
            img_path = "renew_reset_btn_not_found.png"
            page.screenshot(path=img_path)
            send_telegram_photo(img_path, caption="找不到 Reset Timer 按钮")
            self.send_tg_message(f'❌ 续期失败(找不到按鈕)\n' + f"\n🔁 重试链接: {build_retry_url()}")
            return False

        print("检查续期弹窗内是否需要 CF 验证...")
        if _has_turnstile_or_captcha(page):
            if not _wait_for_turnstile_token(page, 15000):
                print("弹窗内的 Turnstile 验证失败")
                img_path = "renew_turnstile_fail.png"
                page.screenshot(path=img_path)
                send_telegram_photo(img_path, caption="续期弹窗 Turnstile 验证失败")
                self.send_tg_message(f'❌ 续期失败(人机验证未过)\n' + f"\n🔁 重试链接: {build_retry_url()}")
                return False
        else:
            print("弹窗内未检测到 Turnstile")

        print("点击 Just Reset 确认续期...")
        try:
            page.locator('button:has-text("Just Reset")').first.click()
            print("提交续期请求，等待服务器处理...")
            page.wait_for_timeout(5000) 
            return True
        except Exception as e:
            print(f"找不到 Just Reset 按钮: {e}")
            img_path = "renew_just_reset_not_found.png"
            page.screenshot(path=img_path)
            send_telegram_photo(img_path, caption="找不到 Just Reset 按钮")
            self.send_tg_message(f'❌ 续期失败(无法确认)\n' + f"\n🔁 重试链接: {build_retry_url()}")
            return False

    def verify_timer(self, page) -> bool:
        print("验证最终倒计时状态...")
        try:
            page.reload()
            page.wait_for_timeout(4000)
            timer_text = page.locator('span.font-mono.text-xl').first.inner_text().strip()
            print(f"当前应用剩余时间: {timer_text}")
            
            if "2 days 23" in timer_text or "3 days" in timer_text:
                print("续期任务圆满完成！")
                img_path = "renew_success.png"
                page.screenshot(path=img_path)
                self.send_tg_message(f'🎉 续期完成\n\n⌛ 剩余时间: {timer_text}')
                send_telegram_photo(img_path, caption="续期成功截图")
                return True
            else:
                print("倒计时似乎没有重置到最高值，请人工检查截图。")
                img_path = "renew_warning.png"
                page.screenshot(path=img_path)
                self.send_tg_message(f'⚠️ 续期异常(请检查)\n\n⌛ 剩余时间: {timer_text}')
                send_telegram_photo(img_path, caption="续期异常截图")
                return True 
        except Exception as e:
            print(f"读取倒计时失败，但流程已执行完毕: {e}")
            img_path = "renew_timer_read_fail.png"
            page.screenshot(path=img_path)
            self.send_tg_message(f'⚠️ 读取剩余时间失败\n')
            send_telegram_photo(img_path, caption="读取倒计时失败截图")
            return False

    def run(self):
        print("=" * 50)
        print("   JustRunMy.app 自动登录与续期脚本 (Scrapling 版)")
        print("=" * 50)
        
        proxy_url_env = os.environ.get("PROXY_URL", "").strip()
        session_kwargs = {
            "headless": True,
            "solve_cloudflare": True,
        }
        if proxy_url_env:
            session_kwargs["proxy"] = {"server": "http://127.0.0.1:8080"}
            print("检测到代理配置，挂载本地通道: http://127.0.0.1:8080")
        
        try:
            with StealthySession(**session_kwargs) as session:
                self.session = session
                
                def _workflow(page):
                    self.page = page
                    try:
                        if not self.perform_login(page):
                            print("\n登录环节失败，终止后续续期操作。")
                            self.send_tg_message(f'❌ 登录失败\n' + f"\n🔁 重试链接: {build_retry_url()}")
                            return
                        
                        if not self.navigate_to_app(page):
                            return
                        
                        if not self.perform_renewal(page):
                            return
                        
                        self.verify_timer(page)
                    except Exception as e:
                        print(f"工作流执行异常: {e}")
                        raise e

                response = session.fetch(
                    LOGIN_URL,
                    google_search=False,
                    timeout=120000,
                    load_dom=True,
                    network_idle=True,
                    wait=2000,
                    page_action=_workflow,
                )
                
        except Exception as e:
            print(f"全局异常: {e}")
            img_path = "global_exception.png"
            try:
                if self.page:
                    self.page.screenshot(path=img_path)
                    send_telegram_photo(img_path, caption=f"脚本异常崩溃: {e}")
            except Exception as se:
                print(f"保存崩溃截图失败: {se}")
            self.send_tg_message(f"❌ JustRunMy 脚本崩溃: {e}" + f"\n\n🔁 重试链接: {build_retry_url()}")
        finally:
            self.close()

    def close(self):
        print("浏览器资源已释放")


if __name__ == "__main__":
    bot = JustRunMyBot()
    bot.run()