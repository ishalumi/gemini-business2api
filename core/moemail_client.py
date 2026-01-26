import random
import string
import time
from datetime import datetime
from typing import Optional, Tuple

import requests

from core.mail_utils import extract_verification_code


class MoeMailClient:
    """MoeMail 客户端"""

    def __init__(
        self,
        base_url: str = "",
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
        self.email_id: Optional[str] = None

    def set_credentials(self, email: str, email_id: Optional[str] = None) -> None:
        self.email = email
        if email_id:
            self.email_id = email_id

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

    @staticmethod
    def _build_name(prefix: str = "") -> str:
        if prefix:
            return prefix
        rand = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        return f"user{rand}"

    def generate_email(self, domain: str = "", prefix: str = "", expiry_ms: int = 3600000) -> Optional[Tuple[str, str]]:
        """生成邮箱，返回 (email_id, email_address)"""
        name_value = self._build_name(prefix)
        payload = {
            "name": name_value,
            "expiryTime": int(expiry_ms),
        }
        if domain:
            payload["domain"] = domain

        try:
            res = self._request(
                "POST",
                f"{self.base_url}/api/emails/generate",
                headers={"Content-Type": "application/json"},
                json=payload,
            )
        except Exception as exc:
            self._log("error", f"❌ MoeMail 请求异常: {exc}")
            return None

        if res.status_code != 200:
            self._log("error", f"❌ MoeMail 生成邮箱失败: HTTP {res.status_code}")
            return None

        try:
            data = res.json() if res.content else {}
        except Exception:
            data = {}

        email_id = data.get("id")
        email_addr = data.get("email") or data.get("address")
        if not email_id or not email_addr:
            self._log("error", "❌ MoeMail 响应缺少邮箱信息")
            return None

        self.email_id = email_id
        self.email = email_addr
        self._log("info", f"✅ MoeMail 生成邮箱成功: {email_addr}")
        return email_id, email_addr

    def fetch_verification_code(self, since_time: Optional[datetime] = None) -> Optional[str]:
        """获取验证码"""
        if not self.email_id:
            self._log("error", "❌ 邮箱 ID 未设置")
            return None

        try:
            self._log("info", "📬 正在拉取邮件列表...")
            res = self._request(
                "GET",
                f"{self.base_url}/api/emails/{self.email_id}",
            )
            if res.status_code != 200:
                self._log("error", f"❌ 获取邮件列表失败: HTTP {res.status_code}")
                return None

            payload = res.json() if res.content else {}
            messages = payload.get("messages") or []
            if not messages:
                self._log("info", "📭 邮箱为空，暂无邮件")
                return None

            since_ms = None
            if since_time:
                since_ms = int(since_time.timestamp() * 1000)

            for idx, msg in enumerate(messages[:10], 1):
                msg_id = msg.get("id") or msg.get("messageId")
                if not msg_id:
                    continue

                sent_at = msg.get("received_at") or msg.get("receivedAt") or msg.get("sent_at")
                if since_ms and isinstance(sent_at, (int, float)) and sent_at < since_ms:
                    continue

                self._log("info", f"🔍 正在读取邮件 {idx}/{len(messages)} (ID: {msg_id})")
                detail = self._request("GET", f"{self.base_url}/api/emails/{self.email_id}/{msg_id}")
                if detail.status_code != 200:
                    self._log("warning", f"⚠️ 读取邮件详情失败: HTTP {detail.status_code}")
                    continue
                detail_payload = detail.json() if detail.content else {}
                message = detail_payload.get("message") or detail_payload.get("data") or {}

                html = message.get("html") or ""
                text = message.get("content") or ""
                content = html or text
                if not content:
                    continue
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
        timeout: int = 60,
        interval: int = 3,
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

    def _log(self, level: str, message: str) -> None:
        if self.log_callback:
            try:
                self.log_callback(level, message)
            except Exception:
                pass
