import asyncio
import logging
import os
import time
import random
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from core.account import load_accounts_from_source
from core.base_task_service import BaseTask, BaseTaskService, TaskCancelledError, TaskStatus
from core.config import config
from core.duckmail_client import DuckMailClient
from core.gptmail_client import GPTMailClient
from core.moemail_client import MoeMailClient
from core.gemini_automation import GeminiAutomation
from core.gemini_automation_uc import GeminiAutomationUC

logger = logging.getLogger("gemini.register")


@dataclass
class RegisterTask(BaseTask):
    """注册任务数据类"""
    count: int = 0
    domain: Optional[str] = None

    def to_dict(self) -> dict:
        """转换为字典"""
        base_dict = super().to_dict()
        base_dict["count"] = self.count
        base_dict["domain"] = self.domain
        return base_dict


class RegisterService(BaseTaskService[RegisterTask]):
    """注册服务类"""

    def __init__(
        self,
        multi_account_mgr,
        http_client,
        user_agent: str,
        account_failure_threshold: int,
        rate_limit_cooldown_seconds: int,
        session_cache_ttl_seconds: int,
        global_stats_provider: Callable[[], dict],
        set_multi_account_mgr: Optional[Callable[[Any], None]] = None,
    ) -> None:
        super().__init__(
            multi_account_mgr,
            http_client,
            user_agent,
            account_failure_threshold,
            rate_limit_cooldown_seconds,
            session_cache_ttl_seconds,
            global_stats_provider,
            set_multi_account_mgr,
            log_prefix="REGISTER",
        )

    async def start_register(self, count: Optional[int] = None, domain: Optional[str] = None) -> RegisterTask:
        """启动注册任务（支持排队）。"""
        async with self._lock:
            if os.environ.get("ACCOUNTS_CONFIG"):
                raise ValueError("已设置 ACCOUNTS_CONFIG 环境变量，注册功能已禁用")

            current = self.get_current_task()
            if current and current.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
                raise ValueError("已有注册任务正在运行中")

            domain_value = (domain or "").strip()
            if not domain_value:
                domain_value = (config.basic.register_domain or "").strip() or None

            register_count = count or config.basic.register_default_count
            register_count = max(1, int(register_count))
            task = RegisterTask(id=str(uuid.uuid4()), count=register_count, domain=domain_value)
            self._tasks[task.id] = task
            # 将 domain 记录在日志里，便于排查
            self._append_log(task, "info", f"register task queued (count={register_count}, domain={domain_value or 'default'})")
            await self._enqueue_task(task)
            self._append_log(task, "info", f"📝 创建注册任务 (数量={register_count})")
            return task

    def _execute_task(self, task: RegisterTask):
        return self._run_register_async(task, task.domain)

    async def _run_register_async(self, task: RegisterTask, domain: Optional[str]) -> None:
        """异步执行注册任务（支持取消）。"""
        loop = asyncio.get_running_loop()
        self._append_log(task, "info", f"🚀 注册任务已启动 (共 {task.count} 个账号)")

        for idx in range(task.count):
            if task.cancel_requested:
                self._append_log(task, "warning", f"register task cancelled: {task.cancel_reason or 'cancelled'}")
                task.status = TaskStatus.CANCELLED
                task.finished_at = time.time()
                return

            try:
                self._append_log(task, "info", f"📊 进度: {idx + 1}/{task.count}")
                result = await loop.run_in_executor(self._executor, self._register_one, domain, task)
            except TaskCancelledError:
                task.status = TaskStatus.CANCELLED
                task.finished_at = time.time()
                return
            except Exception as exc:
                result = {"success": False, "error": str(exc)}
            task.progress += 1
            task.results.append(result)

            if result.get("success"):
                task.success_count += 1
                email = result.get('email', '未知')
                self._append_log(task, "info", f"✅ 注册成功: {email}")
            else:
                task.fail_count += 1
                error = result.get('error', '未知错误')
                self._append_log(task, "error", f"❌ 注册失败: {error}")

            # 账号注册间隔（降低频率/随机化节奏）
            if idx < task.count - 1:
                delay_min = config.automation.between_account_min_seconds
                delay_max = config.automation.between_account_max_seconds
                if delay_max > 0:
                    delay_min = max(0, int(delay_min))
                    delay_max = max(delay_min, int(delay_max))
                    sleep_seconds = random.uniform(delay_min, delay_max)
                    if sleep_seconds > 0:
                        self._append_log(task, "info", f"⏳ 休眠 {sleep_seconds:.1f} 秒后继续注册")
                        await asyncio.sleep(sleep_seconds)

        if task.cancel_requested:
            task.status = TaskStatus.CANCELLED
        else:
            task.status = TaskStatus.SUCCESS if task.fail_count == 0 else TaskStatus.FAILED
        task.finished_at = time.time()
        self._append_log(task, "info", f"🏁 注册任务完成 (成功: {task.success_count}, 失败: {task.fail_count}, 总计: {task.count})")

    def _register_one(self, domain: Optional[str], task: RegisterTask) -> dict:
        """注册单个账户"""
        log_cb = lambda level, message: self._append_log(task, level, message)

        log_cb("info", "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        log_cb("info", "🆕 开始注册新账户")
        log_cb("info", "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        provider = (config.basic.register_mail_provider or "duckmail").lower()
        if provider == "gptmail":
            client = GPTMailClient(
                base_url=config.basic.gptmail_base_url,
                api_key=config.basic.gptmail_api_key,
                proxy=config.basic.proxy_for_auth,
                verify_ssl=config.basic.gptmail_verify_ssl,
                log_callback=log_cb,
            )
            if not config.basic.gptmail_api_key:
                log_cb("error", "❌ GPTMail API Key 未配置")
                return {"success": False, "error": "GPTMail API Key 未配置"}

            log_cb("info", "📧 步骤 1/3: 生成 GPTMail 邮箱...")
            email = client.generate_email_with_fallback(
                domain=domain or "",
                prefix=config.basic.register_mail_prefix or "",
            )
            if not email:
                log_cb("error", "❌ GPTMail 邮箱生成失败")
                return {"success": False, "error": "GPTMail 生成失败"}

            log_cb("info", f"✅ GPTMail 邮箱生成成功: {client.email}")
        elif provider == "moemail":
            client = MoeMailClient(
                base_url=config.basic.moemail_base_url,
                api_key=config.basic.moemail_api_key,
                proxy=config.basic.proxy_for_auth,
                verify_ssl=config.basic.moemail_verify_ssl,
                log_callback=log_cb,
            )
            if not config.basic.moemail_api_key:
                log_cb("error", "❌ MoeMail API Key 未配置")
                return {"success": False, "error": "MoeMail API Key 未配置"}

            # 支持多域名随机选取（逗号分隔）
            moemail_domains = [d.strip() for d in (config.basic.moemail_domain or "").split(",") if d.strip()]
            selected_domain = random.choice(moemail_domains) if moemail_domains else ""

            log_cb("info", "📧 步骤 1/3: 生成 MoeMail 邮箱...")
            if selected_domain:
                log_cb("info", f"📧 使用域名: {selected_domain}")
            result = client.generate_email(
                domain=selected_domain,
                prefix=config.basic.register_mail_prefix or "",
            )
            if not result:
                log_cb("error", "❌ MoeMail 邮箱生成失败")
                return {"success": False, "error": "MoeMail 生成失败"}
            email_id, email_addr = result
            client.set_credentials(email_addr, email_id)
            log_cb("info", f"✅ MoeMail 邮箱生成成功: {client.email}")
        else:
            client = DuckMailClient(
                base_url=config.basic.duckmail_base_url,
                proxy=config.basic.proxy_for_auth,
                verify_ssl=config.basic.duckmail_verify_ssl,
                api_key=config.basic.duckmail_api_key,
                log_callback=log_cb,
            )

            log_cb("info", "📧 步骤 1/3: 注册 DuckMail 邮箱...")
            if not client.register_account(domain=domain):
                log_cb("error", "❌ DuckMail 邮箱注册失败")
                return {"success": False, "error": "DuckMail 注册失败"}

            log_cb("info", f"✅ DuckMail 邮箱注册成功: {client.email}")

        # 根据配置选择浏览器引擎
        browser_engine = (config.basic.browser_engine or "dp").lower()
        headless = config.basic.browser_headless

        log_cb("info", f"🌐 步骤 2/3: 启动浏览器 (引擎={browser_engine}, 无头模式={headless})...")

        if browser_engine == "dp":
            # DrissionPage 引擎：支持有头和无头模式
            automation = GeminiAutomation(
                user_agent=self.user_agent,
                proxy=config.basic.proxy_for_auth,
                headless=headless,
                stealth_enabled=config.automation.stealth_enabled,
                webrtc_protect=config.automation.webrtc_protect,
                timezone=config.automation.timezone,
                geo_latitude=config.automation.geo_latitude,
                geo_longitude=config.automation.geo_longitude,
                geo_accuracy=config.automation.geo_accuracy,
                random_delay_min_ms=config.automation.random_delay_min_ms,
                random_delay_max_ms=config.automation.random_delay_max_ms,
                log_callback=log_cb,
            )
        else:
            # undetected-chromedriver 引擎：无头模式反检测能力弱，强制使用有头模式
            if headless:
                log_cb("warning", "⚠️ UC 引擎无头模式反检测能力弱，强制使用有头模式")
                headless = False
            automation = GeminiAutomationUC(
                user_agent=self.user_agent,
                proxy=config.basic.proxy_for_auth,
                headless=headless,
                stealth_enabled=config.automation.stealth_enabled,
                webrtc_protect=config.automation.webrtc_protect,
                timezone=config.automation.timezone,
                geo_latitude=config.automation.geo_latitude,
                geo_longitude=config.automation.geo_longitude,
                geo_accuracy=config.automation.geo_accuracy,
                random_delay_min_ms=config.automation.random_delay_min_ms,
                random_delay_max_ms=config.automation.random_delay_max_ms,
                log_callback=log_cb,
            )
        # 允许外部取消时立刻关闭浏览器
        self._add_cancel_hook(task.id, lambda: getattr(automation, "stop", lambda: None)())

        try:
            log_cb("info", "🔐 步骤 3/3: 执行 Gemini 自动登录...")
            result = automation.login_and_extract(client.email, client)
        except Exception as exc:
            log_cb("error", f"❌ 自动登录异常: {exc}")
            return {"success": False, "error": str(exc)}

        if not result.get("success"):
            error = result.get("error", "自动化流程失败")
            log_cb("error", f"❌ 自动登录失败: {error}")
            return {"success": False, "error": error}

        log_cb("info", "✅ Gemini 登录成功，正在保存配置...")

        config_data = result["config"]
        if provider == "gptmail":
            config_data["mail_provider"] = "gptmail"
            config_data["mail_address"] = client.email
            config_data["mail_password"] = ""
        elif provider == "moemail":
            config_data["mail_provider"] = "moemail"
            config_data["mail_address"] = client.email
            config_data["mail_password"] = ""
            config_data["mail_box_id"] = client.email_id
        else:
            config_data["mail_provider"] = "duckmail"
            config_data["mail_address"] = client.email
            config_data["mail_password"] = client.password

        accounts_data = load_accounts_from_source()
        updated = False
        for acc in accounts_data:
            if acc.get("id") == config_data["id"]:
                acc.update(config_data)
                updated = True
                break
        if not updated:
            accounts_data.append(config_data)

        self._apply_accounts_update(accounts_data)

        log_cb("info", "✅ 配置已保存到数据库")
        log_cb("info", "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        log_cb("info", f"🎉 账户注册完成: {client.email}")
        log_cb("info", "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        return {"success": True, "email": client.email, "config": config_data}
