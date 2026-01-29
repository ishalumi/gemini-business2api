"""
Storage abstraction supporting PostgreSQL backend.

Requires DATABASE_URL for all persistence.
"""

import asyncio
import json
import logging
import os
import threading
import time
from typing import Optional, Tuple, List

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_db_pool = None
_db_pool_lock = None
_db_loop = None
_db_thread = None
_db_loop_lock = threading.Lock()


def _get_database_url() -> str:
    return os.environ.get("DATABASE_URL", "").strip()


def is_database_enabled() -> bool:
    """Return True when DATABASE_URL is configured."""
    return bool(_get_database_url())


def _ensure_db_loop() -> asyncio.AbstractEventLoop:
    global _db_loop, _db_thread
    if _db_loop and _db_thread and _db_thread.is_alive():
        return _db_loop
    with _db_loop_lock:
        if _db_loop and _db_thread and _db_thread.is_alive():
            return _db_loop
        loop = asyncio.new_event_loop()

        def _runner() -> None:
            asyncio.set_event_loop(loop)
            loop.run_forever()

        thread = threading.Thread(target=_runner, name="storage-db-loop", daemon=True)
        thread.start()
        _db_loop = loop
        _db_thread = thread
        return _db_loop


def _run_in_db_loop(coro):
    loop = _ensure_db_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()


def _parse_json(value):
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return None
    return value


def _ensure_account_id(data: dict, account_id: str) -> dict:
    if not isinstance(data, dict):
        return {"id": account_id}
    if not data.get("id"):
        data = dict(data)
        data["id"] = account_id
    return data


async def _get_postgres_pool():
    """Get (or create) the asyncpg connection pool."""
    global _db_pool, _db_pool_lock
    if _db_pool is not None:
        return _db_pool
    if _db_pool_lock is None:
        _db_pool_lock = asyncio.Lock()
    async with _db_pool_lock:
        if _db_pool is not None:
            return _db_pool
        db_url = _get_database_url()
        if not db_url:
            raise ValueError("DATABASE_URL is not set")
        try:
            import asyncpg
            _db_pool = await asyncpg.create_pool(
                db_url,
                min_size=1,
                max_size=10,
                command_timeout=30,
            )
            await _init_tables_postgres(_db_pool)
            logger.info("[STORAGE] PostgreSQL pool initialized")
        except ImportError:
            logger.error("[STORAGE] asyncpg is required for PostgreSQL storage")
            raise
        except Exception as e:
            logger.error(f"[STORAGE] Database connection failed: {e}")
            raise
    return _db_pool


async def _init_tables_postgres(pool) -> None:
    """Initialize PostgreSQL tables."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                account_id TEXT PRIMARY KEY,
                position INTEGER NOT NULL,
                data JSONB NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS accounts_position_idx
            ON accounts(position)
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS kv_settings (
                key TEXT PRIMARY KEY,
                value JSONB NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS kv_stats (
                key TEXT PRIMARY KEY,
                value JSONB NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS task_history (
                id TEXT PRIMARY KEY,
                data JSONB NOT NULL,
                created_at DOUBLE PRECISION NOT NULL
            )
            """
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS task_history_created_at_idx
            ON task_history(created_at DESC)
            """
        )
        logger.info("[STORAGE] PostgreSQL tables initialized")


async def _kv_get(table: str, key: str) -> Optional[dict]:
    pool = await _get_postgres_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"SELECT value FROM {table} WHERE key = $1", key
        )
        if not row:
            return None
        return _parse_json(row["value"])


async def _kv_set(table: str, key: str, value: dict) -> None:
    payload = json.dumps(value, ensure_ascii=False)
    pool = await _get_postgres_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            f"""
            INSERT INTO {table} (key, value, updated_at)
            VALUES ($1, $2, CURRENT_TIMESTAMP)
            ON CONFLICT (key) DO UPDATE SET
                value = EXCLUDED.value,
                updated_at = CURRENT_TIMESTAMP
            """,
            key,
            payload,
        )


async def _kv_has(table: str, key: str) -> bool:
    pool = await _get_postgres_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"SELECT 1 FROM {table} WHERE key = $1", key
        )
        return row is not None


# ==================== Accounts storage ====================

async def load_accounts() -> list:
    """Load account configuration from database."""
    accounts: List[dict] = []
    pool = await _get_postgres_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT account_id, data FROM accounts ORDER BY position"
        )
    for row in rows:
        account_id = row["account_id"]
        data = _parse_json(row["data"]) or {}
        accounts.append(_ensure_account_id(data, account_id))
    return accounts


async def save_accounts(accounts: list) -> bool:
    """Save account configuration to database (replace all)."""
    accounts = accounts or []
    normalized: List[tuple[str, int, dict]] = []
    for position, acc in enumerate(accounts, 1):
        if not isinstance(acc, dict):
            continue
        account_id = str(acc.get("id") or f"account_{position}")
        payload = dict(acc)
        payload["id"] = account_id
        normalized.append((account_id, position, payload))
    account_ids = [item[0] for item in normalized]
    pool = await _get_postgres_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            if account_ids:
                await conn.execute(
                    "DELETE FROM accounts WHERE NOT (account_id = ANY($1::text[]))",
                    account_ids,
                )
            else:
                await conn.execute("DELETE FROM accounts")
            for account_id, position, payload in normalized:
                await conn.execute(
                    """
                    INSERT INTO accounts (account_id, position, data, updated_at)
                    VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
                    ON CONFLICT (account_id) DO UPDATE SET
                        position = EXCLUDED.position,
                        data = EXCLUDED.data,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    account_id,
                    position,
                    json.dumps(payload, ensure_ascii=False),
                )
    logger.info(f"[STORAGE] Saved {len(accounts)} accounts to database")
    return True


async def get_accounts_updated_at() -> Optional[float]:
    """Get the accounts updated_at timestamp (epoch seconds)."""
    pool = await _get_postgres_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT EXTRACT(EPOCH FROM MAX(updated_at)) AS ts FROM accounts"
        )
    if not row or row["ts"] is None:
        return None
    return float(row["ts"])


async def has_accounts() -> bool:
    """Check if there is any account data."""
    pool = await _get_postgres_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT 1 FROM accounts LIMIT 1")
        return row is not None


async def update_account_disabled(account_id: str, disabled: bool) -> bool:
    """Update disabled status for a single account."""
    pool = await _get_postgres_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE accounts
            SET data = COALESCE(data, '{}'::jsonb) || jsonb_build_object('disabled', $2),
                updated_at = CURRENT_TIMESTAMP
            WHERE account_id = $1
            RETURNING account_id
            """,
            account_id,
            disabled,
        )
        return row is not None


async def bulk_update_accounts_disabled(account_ids: list[str], disabled: bool) -> Tuple[int, list[str]]:
    """Bulk update disabled status."""
    if not account_ids:
        return 0, []
    pool = await _get_postgres_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT account_id FROM accounts WHERE account_id = ANY($1::text[])",
            account_ids,
        )
        found = {row["account_id"] for row in rows}
        if found:
            await conn.execute(
                """
                UPDATE accounts
                SET data = COALESCE(data, '{}'::jsonb) || jsonb_build_object('disabled', $2),
                    updated_at = CURRENT_TIMESTAMP
                WHERE account_id = ANY($1::text[])
                """,
                list(found),
                disabled,
            )
        missing = [acc_id for acc_id in account_ids if acc_id not in found]
        return len(found), missing


async def delete_accounts(account_ids: list[str]) -> int:
    """Delete accounts in batch and return deleted count."""
    if not account_ids:
        return 0
    pool = await _get_postgres_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "DELETE FROM accounts WHERE account_id = ANY($1::text[]) RETURNING account_id",
            account_ids,
        )
        return len(rows)


def load_accounts_sync() -> list:
    """Sync wrapper for load_accounts."""
    return _run_in_db_loop(load_accounts())


def save_accounts_sync(accounts: list) -> bool:
    """Sync wrapper for save_accounts."""
    return _run_in_db_loop(save_accounts(accounts))


def get_accounts_updated_at_sync() -> Optional[float]:
    """Sync wrapper for get_accounts_updated_at."""
    return _run_in_db_loop(get_accounts_updated_at())


def has_accounts_sync() -> bool:
    return _run_in_db_loop(has_accounts())


def update_account_disabled_sync(account_id: str, disabled: bool) -> bool:
    return _run_in_db_loop(update_account_disabled(account_id, disabled))


def bulk_update_accounts_disabled_sync(account_ids: list[str], disabled: bool) -> Tuple[int, list[str]]:
    return _run_in_db_loop(bulk_update_accounts_disabled(account_ids, disabled))


def delete_accounts_sync(account_ids: list[str]) -> int:
    return _run_in_db_loop(delete_accounts(account_ids))


# ==================== Settings storage ====================

async def load_settings() -> Optional[dict]:
    return await _kv_get("kv_settings", "settings")


async def save_settings(settings: dict) -> bool:
    await _kv_set("kv_settings", "settings", settings)
    logger.info("[STORAGE] Settings saved to database")
    return True


async def has_settings() -> bool:
    return await _kv_has("kv_settings", "settings")


def load_settings_sync() -> Optional[dict]:
    return _run_in_db_loop(load_settings())


def save_settings_sync(settings: dict) -> bool:
    return _run_in_db_loop(save_settings(settings))


def has_settings_sync() -> bool:
    return _run_in_db_loop(has_settings())


# ==================== Stats storage ====================

async def load_stats() -> Optional[dict]:
    return await _kv_get("kv_stats", "stats")


async def save_stats(stats: dict) -> bool:
    await _kv_set("kv_stats", "stats", stats)
    return True


async def has_stats() -> bool:
    return await _kv_has("kv_stats", "stats")


def load_stats_sync() -> Optional[dict]:
    return _run_in_db_loop(load_stats())


def save_stats_sync(stats: dict) -> bool:
    return _run_in_db_loop(save_stats(stats))


def has_stats_sync() -> bool:
    return _run_in_db_loop(has_stats())


# ==================== Task history storage ====================

async def save_task_history_entry(entry_id: str, data: dict, created_at: Optional[float] = None) -> bool:
    """Save a task history entry (keep latest 100)."""
    created_at = float(created_at or time.time())
    payload = json.dumps(data, ensure_ascii=False)
    pool = await _get_postgres_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                INSERT INTO task_history (id, data, created_at)
                VALUES ($1, $2, $3)
                ON CONFLICT (id) DO UPDATE SET
                    data = EXCLUDED.data,
                    created_at = EXCLUDED.created_at
                """,
                entry_id,
                payload,
                created_at,
            )
            await conn.execute(
                """
                DELETE FROM task_history
                WHERE id IN (
                    SELECT id FROM task_history
                    ORDER BY created_at DESC
                    OFFSET 100
                )
                """
            )
    return True


async def load_task_history(limit: int = 100) -> list:
    """Load task history entries."""
    items: List[dict] = []
    pool = await _get_postgres_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, data, created_at FROM task_history ORDER BY created_at DESC LIMIT $1",
            limit,
        )
    for row in rows:
        data = _parse_json(row["data"]) or {}
        data.setdefault("id", row["id"])
        data.setdefault("created_at", row["created_at"])
        items.append(data)
    return items


async def clear_task_history() -> int:
    """Clear all task history entries."""
    pool = await _get_postgres_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("DELETE FROM task_history RETURNING id")
        return len(rows)


def save_task_history_entry_sync(entry_id: str, data: dict, created_at: Optional[float] = None) -> bool:
    return _run_in_db_loop(save_task_history_entry(entry_id, data, created_at))


def load_task_history_sync(limit: int = 100) -> list:
    return _run_in_db_loop(load_task_history(limit))


def clear_task_history_sync() -> int:
    return _run_in_db_loop(clear_task_history())
