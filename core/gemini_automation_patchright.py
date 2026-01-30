"""
Gemini自动化登录模块（使用 Patchright）
"""
import os
import random
import string
import tempfile
import time
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import quote

from patchright.sync_api import sync_playwright

from core.base_task_service import TaskCancelledError

# 常量
AUTH_HOME_URL = "https://auth.business.gemini.google/"
DEFAULT_XSRF_TOKEN = "KdLRzKwwBTD5wo8nUollAbY6cW0"

WARMUP_URLS = [
    "https://www.google.com/",
    "https://accounts.google.com/",
    "https://myaccount.google.com/",
]


class GeminiAutomationPatchright:
    """Gemini自动化登录（使用 Patchright）"""

    def __init__(
        self,
        user_agent: str = "",
        proxy: str = "",
        headless: bool = True,
        stealth_enabled: bool = True,
        webrtc_protect: bool = True,
        timezone: str = "",
        geo_latitude: Optional[float] = None,
        geo_longitude: Optional[float] = None,
        geo_accuracy: int = 50,
        random_delay_min_ms: int = 120,
        random_delay_max_ms: int = 380,
        verification_poll_attempts: int = 3,
        verification_poll_interval_seconds: int = 4,
        verification_resend_clicks: int = 4,
        warmup_enabled: bool = True,
        warmup_duration_seconds: int = 5,
        timeout: int = 60,
        log_callback=None,
    ) -> None:
        self.user_agent = user_agent or ""
        self.proxy = str(proxy or "").strip()
        self.headless = headless
        self.stealth_enabled = stealth_enabled
        self.webrtc_protect = webrtc_protect
        self.timezone = timezone
        self.geo_latitude = geo_latitude
        self.geo_longitude = geo_longitude
        self.geo_accuracy = geo_accuracy
        self.random_delay_min_ms = max(0, int(random_delay_min_ms))
        self.random_delay_max_ms = max(self.random_delay_min_ms, int(random_delay_max_ms))
        self.verification_poll_attempts = max(1, int(verification_poll_attempts))
        self.verification_poll_interval_seconds = max(1, int(verification_poll_interval_seconds))
        self.verification_resend_clicks = max(0, int(verification_resend_clicks))
        self.warmup_enabled = bool(warmup_enabled)
        self.warmup_duration_seconds = max(0, int(warmup_duration_seconds))
        self.timeout = timeout
        self.log_callback = log_callback

        self._playwright = None
        self._context = None
        self._page = None
        self._user_data_dir = None

    def stop(self) -> None:
        """外部请求停止：尽力关闭浏览器实例。"""
        try:
            self._cleanup()
        except Exception:
            pass

    def login_and_extract(self, email: str, mail_client) -> dict:
        """执行登录并提取配置"""
        try:
            self._create_context()
            if self.warmup_enabled:
                self._run_warmup()
            return self._run_flow(self._page, email, mail_client)
        except TaskCancelledError:
            raise
        except Exception as exc:
            self._log("error", f"automation error: {exc}")
            return {"success": False, "error": str(exc)}
        finally:
            self._cleanup()

    def _create_context(self) -> None:
        """创建 Patchright 浏览器上下文"""
        self._playwright = sync_playwright().start()
        self._user_data_dir = tempfile.mkdtemp(prefix="patchright_")

        args = [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-setuid-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--window-size=1280,800",
            "--disable-quic",
            "--disable-http2",
        ]
        if self.webrtc_protect:
            args.extend([
                "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
                "--webrtc-ip-handling-policy=disable_non_proxied_udp",
            ])
        if self.proxy:
            args.append(f"--proxy-server={self.proxy}")

        context_options = {
            "headless": self.headless,
            "no_viewport": True,
            "locale": "zh-CN",
            "args": args,
        }

        if self.proxy:
            context_options["proxy"] = {"server": self.proxy}
            self._log("info", f"🌐 使用代理: {self.proxy}")
        if self.user_agent:
            context_options["user_agent"] = self.user_agent
        if self.timezone:
            context_options["timezone_id"] = self.timezone
        if self.geo_latitude is not None and self.geo_longitude is not None:
            context_options["geolocation"] = {
                "latitude": float(self.geo_latitude),
                "longitude": float(self.geo_longitude),
                "accuracy": float(self.geo_accuracy or 50),
            }
            context_options["permissions"] = ["geolocation"]

        self._context = self._playwright.chromium.launch_persistent_context(
            user_data_dir=self._user_data_dir,
            **context_options,
        )

        # 默认超时配置（毫秒）
        self._context.set_default_timeout(self.timeout * 1000)
        self._context.set_default_navigation_timeout(self.timeout * 1000)

        if self.stealth_enabled:
            try:
                self._context.add_init_script(
                    """
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                    Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en']});
                    window.chrome = {runtime: {}};
                    Object.defineProperty(navigator, 'maxTouchPoints', {get: () => 1});
                    Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
                    Object.defineProperty(navigator, 'vendor', {get: () => 'Google Inc.'});
                    Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
                    Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});
                    """
                )
            except Exception:
                pass

        self._page = self._context.pages[0] if self._context.pages else self._context.new_page()

    def _run_warmup(self) -> None:
        """预热流程：访问 Google 系网站建立信任"""
        for url in WARMUP_URLS:
            try:
                self._log("info", f"🔥 预热访问: {url}")
                self._page.goto(url, wait_until="domcontentloaded")
                self._simulate_human_behavior(self._page)
                self._sleep(self.warmup_duration_seconds)
            except Exception as exc:
                self._log("warning", f"⚠️ 预热异常: {exc}")

    def _simulate_human_behavior(self, page) -> None:
        """模拟人类行为（鼠标移动、滚动）"""
        try:
            for _ in range(random.randint(2, 5)):
                x = random.randint(100, 900)
                y = random.randint(100, 700)
                page.mouse.move(x, y)
                time.sleep(random.uniform(0.1, 0.3))
            page.mouse.wheel(0, random.randint(120, 480))
        except Exception:
            pass

    def _sleep(self, base_seconds: float) -> None:
        """随机化等待时间"""
        extra = 0.0
        if self.random_delay_max_ms > 0:
            extra = random.uniform(self.random_delay_min_ms, self.random_delay_max_ms) / 1000.0
        time.sleep(max(0, base_seconds) + extra)

    @staticmethod
    def _normalize_selector(selector: str) -> str:
        if selector.startswith("css:"):
            return selector[4:]
        if selector.startswith("tag:"):
            return selector[4:]
        return selector

    def _query(self, page, selector: str, timeout_ms: int = 0):
        selector = self._normalize_selector(selector)
        try:
            if timeout_ms and timeout_ms > 0:
                return page.wait_for_selector(selector, timeout=timeout_ms)
            return page.query_selector(selector)
        except Exception:
            return None

    def _query_all(self, page, selector: str):
        selector = self._normalize_selector(selector)
        try:
            return page.query_selector_all(selector) or []
        except Exception:
            return []

    def _run_flow(self, page, email: str, mail_client) -> dict:
        """执行登录流程"""
        send_time = datetime.now()

        # Step 1: 导航到首页并设置 Cookie
        self._log("info", f"🌐 正在打开登录页面: {email}")
        page.goto(AUTH_HOME_URL, wait_until="domcontentloaded")
        self._sleep(2)

        # 设置两个关键 Cookie
        try:
            self._log("info", "🍪 正在设置认证 Cookies...")
            self._context.add_cookies([
                {
                    "name": "__Host-AP_SignInXsrf",
                    "value": DEFAULT_XSRF_TOKEN,
                    "url": AUTH_HOME_URL,
                    "path": "/",
                    "secure": True,
                },
                {
                    "name": "_GRECAPTCHA",
                    "value": "09ABCL...",
                    "url": "https://google.com",
                    "path": "/",
                    "secure": True,
                },
            ])
            self._log("info", "✅ Cookies 设置成功")
        except Exception as e:
            self._log("warning", f"⚠️ 设置 Cookies 失败: {e}")

        login_hint = quote(email, safe="")
        login_url = (
            "https://auth.business.gemini.google/login/email?"
            f"continueUrl=https%3A%2F%2Fbusiness.gemini.google%2F&loginHint={login_hint}"
            f"&xsrfToken={DEFAULT_XSRF_TOKEN}"
        )
        self._log("info", "🔗 正在访问登录链接...")
        page.goto(login_url, wait_until="domcontentloaded")
        self._sleep(5)

        # Step 2: 检查当前页面状态
        current_url = page.url
        self._log("info", f"📍 当前 URL: {current_url}")
        has_business_params = "business.gemini.google" in current_url and (
            "csesidx=" in current_url or "/cid/" in current_url
        )
        if has_business_params:
            self._log("info", "✅ 检测到已登录，直接提取配置")
            return self._extract_config(page, email)

        # Step 3: 点击发送验证码按钮
        self._log("info", "🔘 正在查找并点击发送验证码按钮...")
        if not self._click_send_code_button(page):
            self._log("error", "❌ 未找到发送验证码按钮")
            self._save_screenshot(page, "send_code_button_missing")
            return {"success": False, "error": "send code button not found"}

        # Step 4: 等待验证码输入框出现
        self._log("info", "⏳ 等待验证码输入框出现...")
        code_input = self._wait_for_code_input(page)
        if not code_input:
            self._log("error", "❌ 验证码输入框未出现")
            self._save_screenshot(page, "code_input_missing")
            return {"success": False, "error": "code input not found"}

        # Step 5: 轮询邮件获取验证码
        self._log("info", "📬 开始轮询邮箱获取验证码...")
        code = self._poll_for_verification_code(mail_client, send_time)
        if not code:
            if self.verification_resend_clicks <= 0:
                self._log("error", "❌ 验证码获取超时")
                self._save_screenshot(page, "code_timeout")
                return {"success": False, "error": "verification code timeout"}
            self._log("warning", f"⚠️ 验证码获取超时，准备重发 {self.verification_resend_clicks} 次...")
            for attempt in range(self.verification_resend_clicks):
                send_time = datetime.now()
                if not self._click_resend_code_button(page):
                    self._log("error", "❌ 未找到重新发送按钮")
                    self._save_screenshot(page, "resend_button_missing")
                    return {"success": False, "error": "resend code button not found"}
                self._log("info", f"🔄 已点击重新发送按钮 ({attempt + 1}/{self.verification_resend_clicks})，等待新验证码...")
                code = self._poll_for_verification_code(mail_client, send_time)
                if code:
                    break
            if not code:
                self._log("error", "❌ 多次重发后仍未收到验证码")
                self._save_screenshot(page, "code_timeout_after_resend")
                return {"success": False, "error": "verification code timeout after resend"}

        self._log("info", f"✅ 收到验证码: {code}")

        # Step 6: 输入验证码并提交
        code_input = self._query(page, "css:input[jsname='ovqh0b']", timeout_ms=3000) or \
                     self._query(page, "css:input[type='tel']", timeout_ms=2000)

        if not code_input:
            self._log("error", "❌ 验证码输入框已失效")
            return {"success": False, "error": "code input expired"}

        self._log("info", "⌨️ 正在输入验证码 (模拟人类输入)...")
        if not self._simulate_human_input(code_input, code):
            self._log("warning", "⚠️ 模拟输入失败，降级为直接输入")
            try:
                code_input.fill(code)
            except Exception:
                pass
            self._sleep(0.5)

        self._log("info", "⏎ 按下回车键提交验证码")
        try:
            code_input.press("Enter")
        except Exception:
            try:
                page.keyboard.press("Enter")
            except Exception:
                pass

        # Step 7: 等待页面自动重定向
        self._log("info", "⏳ 等待验证后自动跳转...")
        current_url = page.url
        max_submit_attempts = 3
        wait_rounds = 5
        wait_interval = 2

        for attempt in range(max_submit_attempts):
            for _ in range(wait_rounds):
                self._sleep(wait_interval)
                current_url = page.url
                if "verify-oob-code" not in current_url:
                    break

            if "verify-oob-code" not in current_url:
                break

            if attempt < max_submit_attempts - 1:
                self._log("warning", f"⚠️ 未跳转，重试提交验证码 ({attempt + 1}/{max_submit_attempts - 1})")
                try:
                    code_input.press("Enter")
                except Exception:
                    pass
                submit_btn = self._query(page, "css:button[type='submit']", timeout_ms=2000)
                if not submit_btn:
                    keywords = ["Verify", "Continue", "提交", "继续", "确认", "下一步", "验证"]
                    for btn in self._query_all(page, "tag:button"):
                        text = (btn.inner_text() or "").strip()
                        if text and any(kw in text for kw in keywords):
                            submit_btn = btn
                            break
                if submit_btn:
                    try:
                        submit_btn.click()
                    except Exception:
                        pass

        self._log("info", f"📍 验证后 URL: {current_url}")
        if "verify-oob-code" in current_url:
            self._log("error", "❌ 验证码提交失败，仍停留在验证页面")
            self._save_screenshot(page, "verification_submit_failed")
            return {"success": False, "error": "verification code submission failed"}

        # Step 8: 处理协议页面
        self._handle_agreement_page(page)

        # Step 9: 检查是否已经在正确的页面
        current_url = page.url
        has_business_params = "business.gemini.google" in current_url and "csesidx=" in current_url and "/cid/" in current_url
        if has_business_params:
            self._log("info", "already on business page with parameters")
            return self._extract_config(page, email)

        # Step 10: 如果不在正确的页面，尝试导航
        if "business.gemini.google" not in current_url:
            self._log("info", "navigating to business page")
            page.goto("https://business.gemini.google/", wait_until="domcontentloaded")
            self._sleep(5)
            current_url = page.url
            self._log("info", f"URL after navigation: {current_url}")

        # Step 11: 检查是否需要设置用户名
        if "cid" not in page.url:
            if self._handle_username_setup(page):
                self._sleep(5)

        # Step 12: 等待 URL 参数生成
        self._log("info", "waiting for URL parameters")
        if not self._wait_for_business_params(page):
            self._log("warning", "URL parameters not generated, trying refresh")
            try:
                page.reload(wait_until="domcontentloaded")
            except Exception:
                pass
            self._sleep(5)
            if not self._wait_for_business_params(page):
                self._log("error", "URL parameters generation failed")
                current_url = page.url
                self._log("error", f"final URL: {current_url}")
                self._save_screenshot(page, "params_missing")
                return {"success": False, "error": "URL parameters not found"}

        # Step 13: 提取配置
        self._log("info", "🎊 登录流程完成，正在提取配置...")
        return self._extract_config(page, email)

    def _click_send_code_button(self, page) -> bool:
        """点击发送验证码按钮（如果需要）"""
        self._sleep(2)

        direct_btn = self._query(page, "#sign-in-with-email", timeout_ms=5000)
        if direct_btn:
            try:
                direct_btn.click()
                self._log("info", "✅ 找到并点击了发送验证码按钮 (ID: #sign-in-with-email)")
                self._sleep(3)
                return True
            except Exception as e:
                self._log("warning", f"⚠️ 点击按钮失败: {e}")

        keywords = ["通过电子邮件发送验证码", "通过电子邮件发送", "email", "Email", "Send code", "Send verification", "Verification code"]
        try:
            self._log("info", f"🔍 通过关键词搜索按钮: {keywords}")
            for btn in self._query_all(page, "tag:button"):
                try:
                    text = (btn.inner_text() or "").strip()
                except Exception:
                    text = ""
                if text and any(kw in text for kw in keywords):
                    try:
                        self._log("info", f"✅ 找到匹配按钮: '{text}'")
                        btn.click()
                        self._log("info", "✅ 成功点击发送验证码按钮")
                        self._sleep(3)
                        return True
                    except Exception as e:
                        self._log("warning", f"⚠️ 点击按钮失败: {e}")
        except Exception as e:
            self._log("warning", f"⚠️ 搜索按钮异常: {e}")

        code_input = self._query(page, "css:input[jsname='ovqh0b']", timeout_ms=2000) or \
                     self._query(page, "css:input[name='pinInput']", timeout_ms=1000)
        if code_input:
            self._log("info", "✅ 已在验证码输入页面，无需点击按钮")
            return True

        self._log("error", "❌ 未找到发送验证码按钮")
        return False

    def _wait_for_code_input(self, page, timeout: int = 30):
        """等待验证码输入框出现"""
        selectors = [
            "css:input[jsname='ovqh0b']",
            "css:input[type='tel']",
            "css:input[name='pinInput']",
            "css:input[autocomplete='one-time-code']",
        ]
        for _ in range(max(1, timeout // 2)):
            for selector in selectors:
                el = self._query(page, selector, timeout_ms=1000)
                if el:
                    return el
            self._sleep(2)
        return None

    def _poll_for_verification_code(self, mail_client, since_time) -> Optional[str]:
        """按配置轮询验证码"""
        poll_attempts = max(1, int(self.verification_poll_attempts))
        poll_interval = max(1, int(self.verification_poll_interval_seconds))
        poll_timeout = poll_attempts * poll_interval
        return mail_client.poll_for_code(timeout=poll_timeout, interval=poll_interval, since_time=since_time)

    def _simulate_human_input(self, element, text: str) -> bool:
        """模拟人类输入（逐字符输入，带随机延迟）"""
        try:
            element.click()
            time.sleep(random.uniform(0.1, 0.3))
            for char in text:
                element.type(char, delay=random.randint(50, 150))
            time.sleep(random.uniform(0.2, 0.5))
            self._log("info", "simulated human input successfully")
            return True
        except Exception as e:
            self._log("warning", f"simulated input failed: {e}")
            return False

    def _click_resend_code_button(self, page) -> bool:
        """点击重新发送验证码按钮"""
        self._sleep(2)
        try:
            for btn in self._query_all(page, "tag:button"):
                try:
                    text = (btn.inner_text() or "").strip().lower()
                except Exception:
                    text = ""
                if text and ("重新" in text or "resend" in text):
                    try:
                        self._log("info", f"found resend button: {text}")
                        btn.click()
                        self._sleep(2)
                        return True
                    except Exception:
                        pass
        except Exception:
            pass
        return False

    def _handle_agreement_page(self, page) -> None:
        """处理协议页面"""
        if "/admin/create" in page.url:
            agree_btn = self._query(page, "css:button.agree-button", timeout_ms=5000)
            if agree_btn:
                agree_btn.click()
                self._sleep(2)

    def _wait_for_business_params(self, page, timeout: int = 30) -> bool:
        """等待业务页面参数生成（csesidx 或 cid 任一即可）"""
        for _ in range(timeout):
            url = page.url
            if "csesidx=" in url or "/cid/" in url:
                self._log("info", f"business params ready: {url}")
                return True
            self._sleep(1)
        return False

    def _handle_username_setup(self, page) -> bool:
        """处理用户名设置页面"""
        current_url = page.url
        if "auth.business.gemini.google/login" in current_url:
            return False

        selectors = [
            "css:input[type='text']",
            "css:input[name='displayName']",
            "css:input[aria-label*='用户名' i]",
            "css:input[aria-label*='display name' i]",
        ]

        username_input = None
        for selector in selectors:
            username_input = self._query(page, selector, timeout_ms=2000)
            if username_input:
                break

        if not username_input:
            return False

        suffix = "".join(random.choices(string.ascii_letters + string.digits, k=3))
        username = f"Test{suffix}"

        try:
            username_input.click()
            self._sleep(0.2)
            try:
                username_input.fill("")
            except Exception:
                pass
            self._sleep(0.1)

            if not self._simulate_human_input(username_input, username):
                self._log("warning", "simulated username input failed, fallback to direct input")
                try:
                    username_input.type(username, delay=80)
                except Exception:
                    pass
                self._sleep(0.3)

            submit_btn = None
            for btn in self._query_all(page, "tag:button"):
                try:
                    text = (btn.inner_text() or "").strip().lower()
                except Exception:
                    text = ""
                if any(kw in text for kw in ["确认", "提交", "继续", "submit", "continue", "confirm", "save", "保存", "下一步", "next"]):
                    submit_btn = btn
                    break

            if submit_btn:
                submit_btn.click()
            else:
                try:
                    username_input.press("Enter")
                except Exception:
                    pass

            self._sleep(5)
            return True
        except Exception:
            return False

    def _extract_config(self, page, email: str) -> dict:
        """提取配置"""
        try:
            if "cid/" not in page.url:
                page.goto("https://business.gemini.google/", wait_until="domcontentloaded")
                self._sleep(3)

            url = page.url
            if "cid/" not in url:
                return {"success": False, "error": "cid not found"}

            config_id = url.split("cid/")[1].split("?")[0].split("/")[0]
            csesidx = url.split("csesidx=")[1].split("&")[0] if "csesidx=" in url else ""

            cookies = self._context.cookies()
            ses = next((c["value"] for c in cookies if c["name"] == "__Secure-C_SES"), None)
            host = next((c["value"] for c in cookies if c["name"] == "__Host-C_OSES"), None)

            ses_obj = next((c for c in cookies if c["name"] == "__Secure-C_SES"), None)
            beijing_tz = timezone(timedelta(hours=8))
            if ses_obj and "expires" in ses_obj:
                cookie_expire_beijing = datetime.fromtimestamp(ses_obj["expires"], tz=beijing_tz)
                expires_at = (cookie_expire_beijing - timedelta(hours=12)).strftime("%Y-%m-%d %H:%M:%S")
            else:
                expires_at = (datetime.now(beijing_tz) + timedelta(hours=12)).strftime("%Y-%m-%d %H:%M:%S")

            config = {
                "id": email,
                "csesidx": csesidx,
                "config_id": config_id,
                "secure_c_ses": ses,
                "host_c_oses": host,
                "expires_at": expires_at,
            }
            return {"success": True, "config": config}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _save_screenshot(self, page, name: str) -> None:
        """保存截图"""
        try:
            screenshot_dir = os.path.join("data", "automation")
            os.makedirs(screenshot_dir, exist_ok=True)
            path = os.path.join(screenshot_dir, f"{name}_{int(time.time())}.png")
            page.screenshot(path=path, full_page=True)
        except Exception:
            pass

    def _log(self, level: str, message: str) -> None:
        """记录日志"""
        if self.log_callback:
            try:
                self.log_callback(level, message)
            except TaskCancelledError:
                raise
            except Exception:
                pass

    def _cleanup(self) -> None:
        """清理资源"""
        if self._context:
            try:
                self._context.close()
            except Exception:
                pass
        self._context = None

        if self._playwright:
            try:
                self._playwright.stop()
            except Exception:
                pass
        self._playwright = None

        self._page = None
        self._cleanup_user_data(self._user_data_dir)
        self._user_data_dir = None

    def _cleanup_user_data(self, user_data_dir: Optional[str]) -> None:
        """清理浏览器用户数据目录"""
        if not user_data_dir:
            return
        try:
            import shutil
            if os.path.exists(user_data_dir):
                shutil.rmtree(user_data_dir, ignore_errors=True)
        except Exception:
            pass
