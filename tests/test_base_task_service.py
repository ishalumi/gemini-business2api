import asyncio
import time
import unittest
import uuid

from core.base_task_service import BaseTask, BaseTaskService, TaskStatus


class DummyTask(BaseTask):
    def __init__(self, steps: int = 50):
        super().__init__(id=str(uuid.uuid4()))
        self.steps = steps


class DummyTaskService(BaseTaskService[DummyTask]):
    def __init__(self):
        super().__init__(
            multi_account_mgr=None,
            http_client=None,
            user_agent="test",
            account_failure_threshold=1,
            rate_limit_cooldown_seconds=0,
            session_cache_ttl_seconds=0,
            global_stats_provider=lambda: {},
            set_multi_account_mgr=None,
            log_prefix="TEST",
        )

    async def start(self, steps: int = 50) -> DummyTask:
        task = DummyTask(steps=steps)
        self._tasks[task.id] = task
        await self._enqueue_task(task)
        return task

    def _execute_task(self, task: DummyTask):
        return self._run(task)

    async def _run(self, task: DummyTask) -> None:
        for _ in range(task.steps):
            self._append_log(task, "info", "tick")
            await asyncio.sleep(0.01)
            task.progress += 1
        task.status = TaskStatus.SUCCESS
        task.finished_at = time.time()


class BaseTaskServiceCancelTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancel_running_task_transitions_to_cancelled(self):
        service = DummyTaskService()
        task = await service.start(steps=200)

        # 等待进入 running 状态
        for _ in range(200):
            if task.status == TaskStatus.RUNNING:
                break
            await asyncio.sleep(0.01)
        self.assertEqual(task.status, TaskStatus.RUNNING)

        await service.cancel_task(task.id, reason="cancelled_by_test")

        # 取消应在较短时间内生效
        for _ in range(200):
            if task.status == TaskStatus.CANCELLED:
                break
            await asyncio.sleep(0.01)
        self.assertEqual(task.status, TaskStatus.CANCELLED)
        self.assertIsNotNone(task.finished_at)

        # 任务结束后不应继续占用 current_task
        for _ in range(200):
            if service.get_current_task() is None:
                break
            await asyncio.sleep(0.01)
        self.assertIsNone(service.get_current_task())

    async def test_cancel_pending_task_is_never_executed(self):
        service = DummyTaskService()
        first = await service.start(steps=200)

        # 确保第一个任务已开始运行，第二个任务会进入 pending 队列
        for _ in range(200):
            if first.status == TaskStatus.RUNNING:
                break
            await asyncio.sleep(0.01)
        self.assertEqual(first.status, TaskStatus.RUNNING)

        second = await service.start(steps=5)
        self.assertEqual(second.status, TaskStatus.PENDING)

        await service.cancel_task(second.id, reason="cancelled_pending")
        self.assertEqual(second.status, TaskStatus.CANCELLED)
        self.assertEqual(second.progress, 0)

        # 等待第一个任务结束
        for _ in range(400):
            if first.status in (TaskStatus.SUCCESS, TaskStatus.FAILED, TaskStatus.CANCELLED):
                break
            await asyncio.sleep(0.01)
        self.assertEqual(first.status, TaskStatus.SUCCESS)

