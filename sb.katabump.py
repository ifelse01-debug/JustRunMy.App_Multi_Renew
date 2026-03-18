#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Katabump 自动续期脚本 - SeleniumBase 重制版 (无惧Cloudflare)
功能：
1. 自动登录 (支持 SB 本地用户缓存)
2. 检查服务器过期时间
3. 自动续期 (点击续期按钮)
4. TG 消息推送
"""
import os, platform
import time
from datetime import datetime, timedelta
from loguru import logger
from seleniumbase import SB
from sb.turnstile_solver import handle_turnstile, exists_turnstile

from notify import send
from env_utils import load_security_env
load_security_env()

def send_tg_message(content):
    send("Katabump 续期通知", content)

class KatabumpBot:
    def __init__(self):
        self.username = os.environ.get("KB_USERNAME", "").strip()
        self.password = os.environ.get("KB_PASSWORD", "").strip()
        self.user_data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kb_sb_profile")
        
        self.sb_context = None
        self.sb = None

    def init_browser(self):
        logger.info("初始化浏览器 (SeleniumBase UC Mode)...")
        # 实例化 SB 的 context manager
        self.sb_context = SB(
            uc=True,
            test=True,
            headless=False,
            user_data_dir=self.user_data_dir
        )
        self.sb = self.sb_context.__enter__()
        time.sleep(2)

    def check_login_status(self) -> bool:
        logger.info("[Step 1] 检查登录状态...")
        dashboard_url = "https://dashboard.katabump.com/dashboard"
        try:
            self.sb.open(dashboard_url)
            time.sleep(4)
        except Exception as e:
            logger.warning(f"访问 Dashboard 失败: {e}")
            return False

        user_selector = '//*[@id="header"]/nav/ul/li/a/span'
        try:
            if self.sb.is_element_visible(user_selector):
                current_user = self.sb.get_text(user_selector)
                logger.success(f"✅ 已登录，当前用户: {current_user}")
                return True
        except Exception:
            pass

        logger.info("未检测到登录状态")
        return False

    def perform_login(self) -> bool:
        if not self.username or not self.password:
            logger.error("❌ 未配置 KB_USERNAME 或 KB_PASSWORD")
            return False

        logger.info("[Step 1.5] 执行登录流程...")
        login_url = "https://dashboard.katabump.com/auth/login"
        self.sb.uc_open_with_reconnect(login_url, reconnect_time=5)
        time.sleep(3)
        
        user_selector = '//*[@id="header"]/nav/ul/li/a/span'
        try:
            logger.info("开始输入账号...")            
            if self.sb.is_element_visible("input[name='email']"):
                self.sb.type("input[name='email']", self.username)
            else:
                self.sb.type("input[type='text']", self.username)
            
            time.sleep(0.5)
            logger.info("开始输入密码...")  
            self.sb.type("input[type='password']", self.password)
            time.sleep(1)
            
            # 处理 Turnstile 验证
            if exists_turnstile(self.sb):
                logger.info("检测到登录页面 Turnstile，正在处理...")
                if not handle_turnstile(self.sb):
                    logger.error("❌ 登录页面 Turnstile 验证失败")
                    self.sb.save_screenshot("login_turnstile_fail.png")
                    return False
            
            self.sb.click("button[type='submit']")
            logger.info("点击登录按钮")
            
            time.sleep(5)
            
            if self.sb.is_element_visible(user_selector):
                current_user = self.sb.get_text(user_selector)
                logger.success(f"✅ 登录成功，当前用户: {current_user}")
                return True
            else:
                msg = "❌ 登录失败：未找到用户信息"
                logger.error(msg)
                send_tg_message(msg)
                self.sb.save_screenshot("login_fail.png")
                return False
                
        except Exception as e:
            logger.error(f"登录过程异常: {e}")
            self.sb.save_screenshot("login_error.png")
            return False

    def check_server_expiry(self) -> tuple[str, bool]:
        logger.info("[Step 2] 检查服务器续期状态...")
        edit_url = "https://dashboard.katabump.com/servers/edit?id=206673"
        self.sb.open(edit_url)
        time.sleep(4)
        
        expiry_selector = '//*[@id="profile-overview"]/div[9]/div[2]'
        
        try:
            if not self.sb.is_element_visible(expiry_selector):
                logger.error("❌ 未找到过期日期元素")
                self.sb.save_screenshot("expiry_not_found.png")
                return "", False

            expiry_text = self.sb.get_text(expiry_selector).strip()
            logger.info(f"📅 当前过期日期: {expiry_text}")
            
            should_renew = False
            today_str = datetime.now().strftime("%Y-%m-%d")
            
            for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%m/%d/%Y"]:
                try:
                    expiry_date = datetime.strptime(expiry_text, fmt)
                    today_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                    if expiry_date == today_date:
                        should_renew = True
                        logger.info("日期匹配：今天是过期日")
                    break
                except:
                    continue
            
            if not should_renew and today_str in expiry_text:
                should_renew = True
                logger.info("文本匹配：包含今日日期")
                
            return expiry_text, should_renew
            
        except Exception as e:
            logger.warning(f"检查过期状态异常: {e}")
            return "", False

    def perform_renewal(self, old_expiry_text: str):
        logger.info("⚠️ 需要续期，开始执行续期操作...")
        expiry_selector = '//*[@id="profile-overview"]/div[9]/div[2]'
        renew_btn_selector = '//*[@id="profile-overview"]/button[@data-bs-target="#renew-modal"]'
        
        try:
            self.sb.click(renew_btn_selector)
            logger.info("已点击打开续期弹窗")
            time.sleep(2)
            
            # 处理弹窗确认
            modal_selector = "#renew-modal"
            if self.sb.is_element_visible(modal_selector):
                logger.info("弹窗已显示，尝试点击确认...")
                if exists_turnstile(self.sb):
                    logger.info("检测到弹窗内 Turnstile，正在处理...")
                    if not handle_turnstile(self.sb):
                        logger.error("❌ 续期弹窗 Turnstile 验证失败")
                        self.sb.save_screenshot("renew_turnstile_fail.png")
                        return
                
                time.sleep(1)
                submit_btn1 = f"{modal_selector} button[type='submit']"
                submit_btn2 = f"{modal_selector} button.btn-primary"
                
                if self.sb.is_element_visible(submit_btn1):
                    self.sb.click(submit_btn1)
                    logger.info("已点击弹窗确认按钮")
                elif self.sb.is_element_visible(submit_btn2):
                    self.sb.click(submit_btn2)
                    logger.info("已点击弹窗确认按钮")
                else:
                    logger.warning("未找到弹窗内的确认按钮")

            logger.info("等待 5 秒服务器处理...")
            time.sleep(5)
            
            logger.info("刷新页面...")
            self.sb.refresh()
            time.sleep(4)
            
            new_expiry_text = self.sb.get_text(expiry_selector).strip()
            logger.info(f"📅 刷新后过期日期: {new_expiry_text}")
            
            success = False
            try:
                target_date = datetime.now() + timedelta(days=4)
                target_str = target_date.strftime("%Y-%m-%d")
                
                if target_str in new_expiry_text:
                    success = True
                else:
                    for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%m/%d/%Y"]:
                        try:
                            new_date = datetime.strptime(new_expiry_text, fmt)
                            diff = (new_date - datetime.now()).days
                            if 3 <= diff <= 5:
                                success = True
                                break
                        except:
                            continue
            except:
                pass
            
            if success:
                msg = (
                    "🎉 Katabump 续期成功\n\n"
                    f"👤 账号: {self.username}\n"
                    f"📅 旧日期: {old_expiry_text}\n"
                    f"📅 新日期: {new_expiry_text}"
                )
                logger.success(msg)
                send_tg_message(msg)
            else:
                msg = (
                    "⚠️ Katabump 续期结果存疑\n\n"
                    f"👤 账号: {self.username}\n"
                    f"📅 旧日期: {old_expiry_text}\n"
                    f"📅 新日期: {new_expiry_text}\n"
                    "未检测到预期的日期变化(4天后)"
                )
                logger.warning(msg)
                send_tg_message(msg)
                self.sb.save_screenshot("renew_uncertain.png")
                
        except Exception as e:
            msg = f"❌ 续期操作异常: {e}"
            logger.error(msg)
            send_tg_message(msg)
            self.sb.save_screenshot("renew_error.png")

    def run(self):
        logger.info("=" * 60)
        logger.info("🚀 Katabump 自动续期脚本开始")
        logger.info(f"👤 账号: {self.username}")
        logger.info("=" * 60)

        try:
            self.init_browser()
            
            if not self.check_login_status():
                if not self.perform_login():
                    return

            expiry_text, should_renew = self.check_server_expiry()
            if should_renew:
                self.perform_renewal(expiry_text)
            else:
                logger.info("✅ 无需续期 (日期未到)")
                msg = f"Katabump 无需续期\n👤 {self.username}\n📅 到期日: {expiry_text}"
                logger.info(msg)

        except Exception as e:
            logger.error(f"全局异常: {e}")
            send_tg_message(f"Katabump 脚本崩溃: {e}")
        finally:
            self.close()

    def close(self):
        if self.sb_context:
            try:
                self.sb_context.__exit__(None, None, None)
            except Exception:
                pass
        logger.info("浏览器资源已释放")

if __name__ == "__main__":
    bot = KatabumpBot()
    bot.run()
