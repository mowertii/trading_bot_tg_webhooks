# app/trading/db_logger.py
import asyncio
import json
import logging
import os
from datetime import datetime
import asyncpg

logger = logging.getLogger(__name__)

# Получаем URL базы данных из переменных окружения
DATABASE_URL = os.getenv("DB_URL")

async def log_event(event_type: str, symbol: str = None, details: dict = None, message: str = ""):
    """Записывает событие в таблицу event_logs"""
    if not DATABASE_URL:
        logger.warning("DATABASE_URL not configured, skipping event logging")
        return
        
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        
        await conn.execute(
            """
            INSERT INTO event_logs(event_time, event_type, symbol, details, message)
            VALUES($1, $2, $3, $4, $5)
            """,
            datetime.utcnow(), 
            event_type, 
            symbol, 
            json.dumps(details or {}), 
            message
        )
        
        await conn.close()
        logger.info(f"Logged event: {event_type} - {message}")
        
    except Exception as e:
        logger.error(f"Failed to log event to database: {e}")

# Функция для тестирования
async def test_logging():
    """Тестовая функция для проверки логирования"""
    await log_event("test", "TEST_SYMBOL", {"test": True}, "Test log entry")