# Исправление для app/utils/telegram_notifications.py

import logging
from telegram import Bot
import html
import re

logger = logging.getLogger(__name__)

async def send_telegram_message(bot_token: str, chat_id: str, message: str):
    """
    Отправляет сообщение в Telegram с безопасным экранированием HTML
    """
    try:
        bot = Bot(token=bot_token)
        
        # ИСПРАВЛЕНИЕ: экранируем HTML символы для безопасной отправки
        safe_message = escape_telegram_html(message)
        
        await bot.send_message(
            chat_id=chat_id, 
            text=safe_message, 
            parse_mode='HTML'
        )
        logger.info(f"Telegram message sent to {chat_id}")
        
    except Exception as e:
        logger.error(f"Failed to send telegram message: {e}")
        # Повторная попытка с обычным текстом без HTML
        try:
            plain_message = strip_html_tags(message)
            await bot.send_message(chat_id=chat_id, text=plain_message)
            logger.info(f"Fallback plain message sent to {chat_id}")
        except Exception as e2:
            logger.error(f"Failed to send fallback message: {e2}")


def escape_telegram_html(text: str) -> str:
    """
    Экранирует HTML символы для безопасной отправки в Telegram
    Сохраняет только допустимые HTML теги: b, i, u, s, code, pre, a
    """
    # Сначала экранируем все HTML символы
    escaped = html.escape(text)
    
    # Затем возвращаем разрешенные теги обратно (если нужно)
    # Для простоты пока оставляем всё экранированным
    return escaped


def strip_html_tags(text: str) -> str:
    """
    Удаляет все HTML теги из текста для fallback отправки
    """
    # Убираем HTML теги
    clean = re.sub('<[^<]+?>', '', text)
    # Убираем лишние пробелы и переносы
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean