# app/utils/telegram_notifications.py - НОВЫЙ ФАЙЛ
import asyncio
import logging
from telegram import Bot

logger = logging.getLogger(__name__)

async def send_telegram_message(bot_token: str, chat_id: str, message: str):
    """
    Асинхронная отправка сообщения в Telegram
    """
    try:
        bot = Bot(token=bot_token)
        await bot.send_message(chat_id=chat_id, text=message, parse_mode='HTML')
        logger.info(f"Telegram message sent to {chat_id}")
    except Exception as e:
        logger.error(f"Failed to send telegram message: {e}", exc_info=True)
        raise

async def send_trade_notification(bot_token: str, chat_id: str, 
                                 action: str, symbol: str, 
                                 status: str, details: str = ""):
    """
    Отправляем уведомление о торговой операции
    
    Args:
        action: 'buy' или 'sell'
        symbol: тикер инструмента  
        status: 'started', 'success', 'error'
        details: дополнительная информация
    """
    
    emoji_map = {
        'buy': {'started': '🔄', 'success': '✅', 'error': '❌'},
        'sell': {'started': '🔄', 'success': '✅', 'error': '❌'}
    }
    
    emoji = emoji_map.get(action, {}).get(status, '📊')
    action_text = action.upper()
    
    if status == 'started':
        message = f"{emoji} Получен сигнал {action_text} {symbol}"
        if details:
            message += f"\n{details}"
    elif status == 'processing':
        message = f"{emoji} Обрабатываю {action_text} {symbol}..."
        if details:
            message += f"\n{details}"
    elif status == 'success':
        message = f"{emoji} <b>Операция {action_text} для {symbol} выполнена успешно!</b>"
        if details:
            message += f"\n📊 Детали:\n{details}"
    elif status == 'error':
        message = f"{emoji} <b>Ошибка {action_text} {symbol}</b>"
        if details:
            message += f"\n🔍 Причина: {details}"
    else:
        message = f"{emoji} {action_text} {symbol}: {status}"
        if details:
            message += f"\n{details}"
    
    await send_telegram_message(bot_token, chat_id, message)

async def send_balance_notification(bot_token: str, chat_id: str, balance: float):
    """Отправляем уведомление о балансе"""
    message = f"💰 <b>Текущий баланс:</b> {balance:.2f} RUB"
    await send_telegram_message(bot_token, chat_id, message)

async def send_positions_notification(bot_token: str, chat_id: str, positions: list):
    """Отправляем уведомление о позициях"""
    if not positions:
        message = "📊 <b>Открытых позиций нет</b>"
    else:
        message = "📊 <b>Открытые позиции:</b>\n\n"
        for pos in positions:
            direction_emoji = "📈" if pos.direction == 'long' else "📉"
            message += f"{direction_emoji} <b>{pos.ticker}</b>: {pos.lots} лот(ов) ({pos.direction.upper()})\n"
    
    await send_telegram_message(bot_token, chat_id, message)

async def send_close_all_notification(bot_token: str, chat_id: str, 
                                    closed_positions: int, 
                                    cancelled_orders: dict):
    """Отправляем уведомление о закрытии всех позиций"""
    message = (
        f"✅ <b>Операция завершена!</b>\n\n"
        f"📊 Закрыто позиций: <b>{closed_positions}</b>\n"
        f"🚫 Отменено лимитных ордеров: <b>{cancelled_orders.get('limit_orders', 0)}</b>\n"
        f"🛑 Отменено стоп-ордеров: <b>{cancelled_orders.get('stop_orders', 0)}</b>"
    )
    await send_telegram_message(bot_token, chat_id, message)