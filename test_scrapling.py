import os
import time
import logging

from scrapling.fetchers import StealthyFetcher, StealthySession

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

def login_katabump(username, password, headless=True, timeout=120000, token_wait_timeout=15000):
    """
    使用 StealthySession 登录到 Katabump 仪表板，支持 Cloudflare 绕过。

    此函数执行自动化登录流程：
    1. 打开登录页面 https://dashboard.katabump.com/auth/login
    2. 自动解决 Cloudflare 挑战（如果存在）
    3. 填写方法参数传入的账号密码
    4. 点击提交按钮 (#submit)
    5. 等待登录后页面导航
    6. 通过检查头部用户元素验证登录是否成功

    参数:
        username (str): Katabump 登录邮箱
        password (str): Katabump 登录密码
        headless (bool): 是否以无头模式启动浏览器，默认 True
        timeout (int): 页面操作超时时间，单位毫秒，默认 120000
        token_wait_timeout (int): 提交前等待验证码 token 注入的最长时间，单位毫秒，默认 15000

    返回:
        bool: 如果登录成功并找到用户元素返回 True，否则返回 False

    示例:
        >>> success = login_katabump("user@example.com", "secret")
        >>> if success:
        ...     print("登录成功！")
        ... else:
        ...     print("登录失败")
    """
    if not username or not password:
        logger.error("缺少登录凭据，请传入 username 和 password。")
        return False

    login_url = "https://dashboard.katabump.com/auth/login"
    user_selector = "#header nav ul li a span"
    captcha_error_flag = {"value": False}

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
                    logger.info("[Step 7] 检测到验证码相关元素: %s", selector)
                    return True
            except Exception as exc:
                logger.debug("检测验证码元素失败 %s: %s", selector, exc)

        logger.info("[Step 7] 未检测到验证码相关元素，本次无需等待 token")
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
                        logger.info("[Step 7] 验证码已就绪")
                        return True
                except Exception:
                    continue

            elapsed_ms = int((time.time() - start_time) * 1000)
            remaining_ms = max_wait_ms - elapsed_ms
            sleep_ms = min(poll_interval_ms, max(remaining_ms, 0))
            if sleep_ms <= 0:
                break
            page.wait_for_timeout(sleep_ms)

        logger.error("[Step 7] 在 %s ms 内未等到有效的验证码 token", max_wait_ms)
        return False

    def _first_visible_selector(page, selectors):
        for selector in selectors:
            try:
                locator = page.locator(selector).first
                if locator.is_visible(timeout=3000):
                    logger.info("匹配到可用选择器: %s", selector)
                    return selector
            except Exception:
                continue
        return None

    def _perform_login(page):
        logger.info("[Step 1] 打开登录页并等待 DOM 加载完成")
        page.wait_for_load_state("domcontentloaded")
        logger.info("当前页面 URL: %s", page.url)

        logger.info("[Step 2] 定位邮箱输入框")
        email_selector = _first_visible_selector(
            page,
            (
                "input[name='email']",
                "input[type='email']",
                "input[type='text']",
            ),
        )
        if not email_selector:
            logger.error("未找到邮箱输入框")
            raise RuntimeError("未找到邮箱输入框")

        logger.info("[Step 3] 定位密码输入框")
        password_selector = _first_visible_selector(
            page,
            (
                "input[name='password']",
                "input[type='password']",
            ),
        )
        if not password_selector:
            logger.error("未找到密码输入框")
            raise RuntimeError("未找到密码输入框")

        logger.info("[Step 4] 填写登录邮箱")
        page.locator(email_selector).first.fill(username)
        page.wait_for_timeout(500)
        logger.info("[Step 5] 填写登录密码")
        page.locator(password_selector).first.fill(password)
        page.wait_for_timeout(500)

        logger.info("[Step 6] 定位提交按钮")
        submit_selector = _first_visible_selector(
            page,
            (
                "#submit",
                "button[type='submit']",
                "button:has-text('Login')",
                "button:has-text('Sign in')",
            ),
        )
        if not submit_selector:
            logger.error("未找到登录按钮")
            raise RuntimeError("未找到登录按钮")

        if _has_turnstile_or_captcha(page):
            if not _wait_for_turnstile_token(page, token_wait_timeout):
                logger.error("未获取到验证码 token，终止本次提交")
                raise RuntimeError("未获取到验证码 token")
        else:
            logger.info("[Step 7] 未发现验证码组件，跳过 token 等待")

        logger.info("[Step 8] 点击登录按钮: %s", submit_selector)
        page.locator(submit_selector).first.click()

        logger.info("[Step 9] 等待登录结果")
        start_time = time.time()
        timeout_seconds = max(timeout / 1000, 1)
        while time.time() - start_time < timeout_seconds:
            current_url = page.url
            if "error=captcha" in current_url:
                captcha_error_flag["value"] = True
                logger.error("登录失败，页面返回验证码错误: %s", current_url)
                return

            try:
                if page.locator(user_selector).first.is_visible(timeout=1000):
                    logger.info("检测到登录成功后的用户元素")
                    return
            except Exception:
                pass

            page.wait_for_timeout(1000)

        logger.warning("等待登录结果超时，最后页面 URL: %s", page.url)

    try:
        logger.info("开始 Katabump 登录流程，headless=%s", headless)
        with StealthySession(headless=headless, solve_cloudflare=True) as session:
            logger.info("已创建 StealthySession，准备访问登录页: %s", login_url)
            response = session.fetch(
                login_url,
                google_search=False,
                timeout=timeout,
                load_dom=True,
                network_idle=True,
                wait=2000,
                page_action=_perform_login,
            )

        logger.info("请求完成，最终 URL: %s，状态码: %s", response.url, response.status)
        if captcha_error_flag["value"] or "error=captcha" in response.url:
            logger.error("登录失败：Turnstile/Cloudflare 验证未通过，最终页面: %s", response.url)
            return False

        user_node = response.css(user_selector).first
        current_user = user_node.text.strip() if user_node else ""
        if current_user:
            logger.info("登录成功，当前用户: %s", current_user)
            return True

        logger.error("登录失败：未找到登录后的用户信息，最终页面: %s", response.url)
        return False
    except Exception as exc:
        logger.exception("登录过程异常: %s", exc)
        return False

def nopecha_demo():
    with StealthySession(headless=True, solve_cloudflare=True) as session:  # 保持浏览器打开直到完成
        page = session.fetch('https://nopecha.com/demo/cloudflare', google_search=False)
        # 等待页面完全加载，确保所有资源（HTML、CSS、JS、图片等）加载完成
        try:
            page.wait_for_load_state('networkidle')
        except Exception as e:
            print(f"Warning: Failed to wait for network idle: {e}")
            # 备选方案：短暂等待以确保动态内容渲染完成
            time.sleep(2)
        
        data = page.css('#padded_content a').getall()
        if len(data) > 0:
            print("session fetch: data:", data[0])

    # 或使用一次性请求样式，为此请求打开浏览器，完成后关闭
    page = StealthyFetcher.fetch('https://nopecha.com/demo/cloudflare')
    # 等待页面完全加载
    try:
        page.wait_for_load_state('networkidle')
    except Exception as e:
        print(f"Warning: Failed to wait for network idle: {e}")
        time.sleep(2)

    data = page.css('#padded_content a').getall()
    if len(data) > 0:
        print("one-time fetch: data:", data[0])

def main():
    # nopecha_demo()
    username = os.getenv("KB_USERNAME", "ifelse01@gmail.com")
    password = os.getenv("KB_PASSWORD", "aB@12345")
    login_katabump(username, password)

if __name__ == "__main__":
    main()
