"""
数据迁移脚本：将旧数据迁移到新数据库结构。

支持来源：
- PostgreSQL 旧表 kv_store（accounts/settings/stats）

用法：
python scripts/migrate_to_database.py
"""

import json
import os
import sys

from core import storage


def _print(msg: str) -> None:
    print(f"[migrate] {msg}")


def _normalize_accounts(accounts: list) -> list:
    normalized = []
    for i, acc in enumerate(accounts or [], 1):
        if not isinstance(acc, dict):
            _print(f"跳过第 {i} 项：不是对象")
            continue
        acc = dict(acc)
        if not acc.get("id"):
            acc["id"] = f"account_{i}"
        normalized.append(acc)
    return normalized


async def _fetch_kv_store_value(key: str):
    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        return None
    import asyncpg
    conn = await asyncpg.connect(db_url)
    try:
        exists = await conn.fetchrow(
            "SELECT 1 FROM information_schema.tables WHERE table_name = $1",
            "kv_store",
        )
        if not exists:
            return None
        row = await conn.fetchrow(
            "SELECT value FROM kv_store WHERE key = $1",
            key,
        )
        if not row:
            return None
        value = row["value"]
        if isinstance(value, str):
            return json.loads(value)
        return value
    finally:
        await conn.close()


def _migrate_from_postgres():
    import asyncio

    _print("检测到 PostgreSQL，尝试从 kv_store 迁移...")

    if not storage.has_accounts_sync():
        accounts = asyncio.run(_fetch_kv_store_value("accounts"))
        if isinstance(accounts, list) and accounts:
            normalized = _normalize_accounts(accounts)
            storage.save_accounts_sync(normalized)
            _print(f"已迁移账户 {len(normalized)} 条")
        else:
            _print("kv_store.accounts 不存在或为空")
    else:
        _print("accounts 表已有数据，跳过迁移")

    if not storage.has_settings_sync():
        settings = asyncio.run(_fetch_kv_store_value("settings"))
        if isinstance(settings, dict) and settings:
            storage.save_settings_sync(settings)
            _print("已迁移 settings")
        else:
            _print("kv_store.settings 不存在或为空")
    else:
        _print("kv_settings 表已有数据，跳过迁移")

    if not storage.has_stats_sync():
        stats = asyncio.run(_fetch_kv_store_value("stats"))
        if isinstance(stats, dict) and stats:
            storage.save_stats_sync(stats)
            _print("已迁移 stats")
        else:
            _print("kv_store.stats 不存在或为空")
    else:
        _print("kv_stats 表已有数据，跳过迁移")


def main() -> int:
    try:
        if not storage.is_database_enabled():
            _print("DATABASE_URL 未配置，无法迁移")
            return 1
        _migrate_from_postgres()
        _print("迁移完成")
        return 0
    except Exception as exc:
        _print(f"迁移失败: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
