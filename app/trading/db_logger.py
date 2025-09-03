# app/trading/db_logger.py
import os
import json
import logging
import asyncpg
from typing import Optional

logger = logging.getLogger(__name__)

# Ожидаем переменную окружения DB_URL вида: postgresql://user:pass@db:5432/trading_data
DB_URL = os.getenv("DB_URL")

_pool: Optional[asyncpg.pool.Pool] = None

async def get_pool():
    global _pool
    if _pool is None:
        if not DB_URL:
            raise RuntimeError("DB_URL is not set in environment")
        _pool = await asyncpg.create_pool(dsn=DB_URL, min_size=1, max_size=5)
    return _pool

async def log_signal(action: str, symbol: Optional[str], risk_percent: Optional[float], raw_payload: Optional[dict]):
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO signals (action, symbol, risk_percent, raw_payload)
                VALUES ($1, $2, $3, $4)
                """,
                action, symbol, risk_percent, json.dumps(raw_payload) if raw_payload is not None else None
            )
    except Exception as e:
        logger.exception("Failed to log signal: %s", e)

async def log_trade(figi: str, ticker: Optional[str], direction: str, lots: int,
                    amount: Optional[float], price: Optional[float], status: str, details: Optional[str] = None):
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO trades (figi, ticker, direction, lots, amount, price, status, details)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                figi, ticker, direction, lots, amount, price, status, details
            )
    except Exception as e:
        logger.exception("Failed to log trade: %s", e)

async def log_error(source: str, message: str, traceback_text: Optional[str] = None):
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO errors (source, message, traceback)
                VALUES ($1, $2, $3)
                """,
                source, message, traceback_text
            )
    except Exception as e:
        logger.exception("Failed to log error: %s", e)
