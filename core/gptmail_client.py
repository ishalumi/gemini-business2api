import random
import string
import time
from datetime import datetime
from typing import Optional

import requests

from core.mail_utils import extract_verification_code


class GPTMailClient:
    """GPTMail 客户端"""

    def __init__(
        self,
        base_url: str = "https://mail.chatgpt.org.uk",
        api_key: str = "",
        proxy: str = "",
        verify_ssl: bool = True,
        log_callback=None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key.strip()
        self.proxies = {"http": proxy, "https": proxy} if proxy else None
        self.verify_ssl = verify_ssl
        self.log_callback = log_callback
        self.email: Optional[str] = None

    def set_credentials(self, email: str) -> None:
        self.email = email

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        headers = kwargs.pop("headers", None) or {}
        if self.api_key and "X-API-Key" not in headers:
            headers["X-API-Key"] = self.api_key
        kwargs["headers"] = headers
        self._log("info", f"📤 发送 {method} 请求: {url}")
        if "json" in kwargs:
            self._log("info", f"📦 请求体: {kwargs['json']}")
        try:
            res = requests.request(
                method,
                url,
                proxies=self.proxies,
                verify=self.verify_ssl,
                timeout=kwargs.pop("timeout", 15),
                **kwargs,
            )
            self._log("info", f"📥 收到响应: HTTP {res.status_code}")
            if res.content and res.status_code >= 400:
                try:
                    self._log("info", f"📄 响应内容: {res.text[:500]}")
                except Exception:
                    pass
            return res
        except Exception as exc:
            self._log("error", f"❌ 网络请求失败: {exc}")
            raise

    def generate_email(self, prefix: str = "", domain: str = "") -> Optional[str]:
        """生成邮箱地址"""
        payload = {}
        if prefix:
            payload["prefix"] = prefix
        if domain:
            payload["domain"] = domain

        try:
            if payload:
                res = self._request("POST", f"{self.base_url}/api/generate-email", json=payload)
            else:
                res = self._request("GET", f"{self.base_url}/api/generate-email")
        except Exception as exc:
            self._log("error", f"❌ GPTMail 请求异常: {exc}")
            return None

        if res.status_code != 200:
            self._log("error", f"❌ GPTMail 生成邮箱失败: HTTP {res.status_code}")
            return None

        try:
            data = res.json() if res.content else {}
        except Exception:
            data = {}
        if not data.get("success"):
            self._log("error", f"❌ GPTMail 生成邮箱失败: {data.get('error')}")
            return None

        email = (data.get("data") or {}).get("email")
        if not email:
            self._log("error", "❌ GPTMail 响应中缺少邮箱地址")
            return None

        self.email = email
        self._log("info", f"✅ GPTMail 生成邮箱成功: {email}")
        return email

    def fetch_verification_code(self, since_time: Optional[datetime] = None) -> Optional[str]:
        """获取验证码"""
        if not self.email:
            self._log("error", "❌ 邮箱未设置")
            return None

        try:
            self._log("info", "📬 正在拉取邮件列表...")
            res = self._request(
                "GET",
                f"{self.base_url}/api/emails",
                params={"email": self.email},
            )
            if res.status_code != 200:
                self._log("error", f"❌ 获取邮件列表失败: HTTP {res.status_code}")
                return None

            payload = res.json() if res.content else {}
            if not payload.get("success"):
                self._log("error", f"❌ 获取邮件列表失败: {payload.get('error')}")
                return None

            emails = (payload.get("data") or {}).get("emails") or []
            if not emails:
                self._log("info", "📭 邮箱为空，暂无邮件")
                return None

            # 时间过滤阈值
            since_ts = None
            if since_time:
                since_ts = int(since_time.timestamp())

            # 只检查最新的 10 封
            for idx, msg in enumerate(emails[:10], 1):
                msg_id = msg.get("id")
                if not msg_id:
                    continue
                msg_ts = msg.get("timestamp")
                if since_ts and isinstance(msg_ts, int) and msg_ts < since_ts:
                    continue

                self._log("info", f"🔍 正在读取邮件 {idx}/{len(emails)} (ID: {msg_id})")
                detail = self._request("GET", f"{self.base_url}/api/email/{msg_id}")
                if detail.status_code != 200:
                    self._log("warning", f"⚠️ 读取邮件详情失败: HTTP {detail.status_code}")
                    continue
                detail_payload = detail.json() if detail.content else {}
                if not detail_payload.get("success"):
                    self._log("warning", f"⚠️ 读取邮件详情失败: {detail_payload.get('error')}")
                    continue

                data = detail_payload.get("data") or {}
                content = (data.get("content") or "") + (data.get("html_content") or "")
                code = extract_verification_code(content)
                if code:
                    self._log("info", f"✅ 找到验证码: {code}")
                    return code

            self._log("warning", "⚠️ 未找到验证码")
            return None
        except Exception as exc:
            self._log("error", f"❌ 获取验证码异常: {exc}")
            return None

    def poll_for_code(
        self,
        timeout: int = 120,
        interval: int = 4,
        since_time: Optional[datetime] = None,
    ) -> Optional[str]:
        max_retries = max(1, timeout // interval)
        self._log("info", f"⏱️ 开始轮询验证码 (超时 {timeout}秒, 间隔 {interval}秒, 最多 {max_retries} 次)")
        for i in range(1, max_retries + 1):
            self._log("info", f"🔄 第 {i}/{max_retries} 次轮询...")
            code = self.fetch_verification_code(since_time=since_time)
            if code:
                self._log("info", f"🎉 验证码获取成功: {code}")
                return code
            if i < max_retries:
                time.sleep(interval)
        self._log("error", f"⏰ 验证码获取超时 ({timeout}秒)")
        return None

    @staticmethod
    def _build_prefix(prefix: str = "") -> str:
        if prefix:
            return prefix
        rand = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
        return f"t{rand}"

    def generate_email_with_fallback(self, domain: str = "", prefix: str = "") -> Optional[str]:
        """带前缀回退的邮箱生成"""
        prefix_value = self._build_prefix(prefix)
        email = self.generate_email(prefix=prefix_value, domain=domain)
        if email:
            return email
        # 如果失败，尝试不带域名
        return self.generate_email(prefix=prefix_value)

    def _log(self, level: str, message: str) -> None:
        if self.log_callback:
            try:
                self.log_callback(level, message)
            except Exception:
                pass
