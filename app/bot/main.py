from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters
)
from bot.handlers import (
    handle_balance,
    handle_figi_message,
    handle_buy,
    handle_sell,
    handle_positions,
    handle_close_all  # ← Новый импорт
)
import os
import logging
import re
import asyncio

# Импортируем новый функционал
from trading.order_executor import OrderExecutor
from trading.order_watcher import OrderWatcher

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Ошибка: {context.error}", exc_info=True)
    try:
        message = update.message or update.channel_post
        if message:
            await message.reply_text("⚠️ Произошла внутренняя ошибка")
    except Exception as e:
        logger.error(f"Ошибка в error_handler: {str(e)}")

def setup_handlers(application):
    # Balance handler
    application.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(re.compile(r'^(баланс|balance)$', re.IGNORECASE)),
        handle_balance
    ))
    
    # FIGI info handler
    application.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(re.compile(r'^figi\s+\w+', re.IGNORECASE)),
        handle_figi_message
    ))
    
    # Positions handler
    application.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(re.compile(r'^(состояние|positions)$', re.IGNORECASE)),
        handle_positions
    ))
    
    # ✅ Close All handler - добавляем обработчик для закрытия всех позиций
    application.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(re.compile(
            r'^(закрыть всё|закрыть все|завершить|уйти в кэш|сэйв|save|close all|exit all|liquidate|'
            r'стоп всё|стоп все|выход|экстренный выход|паника|panic|emergency exit|'
            r'закрыть позиции|снять все|отменить все|cancel all)$', 
            re.IGNORECASE
        )),
        handle_close_all
    ))
    
    # Buy/Sell handlers
    application.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(re.compile(r'^buy\s+\w+', re.IGNORECASE)),
        handle_buy
    ))
    
    application.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(re.compile(r'^sell\s+\w+', re.IGNORECASE)),
        handle_sell
    ))

def main():
    token = os.getenv("BOT_TOKEN")
    tinkoff_token = os.getenv("TINKOFF_TOKEN")
    account_id = os.getenv("ACCOUNT_ID")
    chat_id = os.getenv("TG_CHAT_ID")  # Новый параметр (можно задать в .env)

    if not token:
        raise ValueError("Не задан BOT_TOKEN")
    if not tinkoff_token or not account_id:
        raise ValueError("Не заданы TINKOFF_TOKEN или ACCOUNT_ID")

    # Создаём Telegram-бот
    application = ApplicationBuilder().token(token).build()
    setup_handlers(application)
    application.add_error_handler(error_handler)

    # Создаём исполнителя и вотчера
    executor = OrderExecutor(tinkoff_token, account_id)
    watcher = OrderWatcher(
        tinkoff_token,
        account_id,
        executor,
        tg_bot=application.bot,
        chat_id=chat_id
    )

    # Запускаем вотчер в отдельной задаче
    loop = asyncio.get_event_loop()
    loop.create_task(watcher.watch_trades())

    logger.info("Бот запущен")
    application.run_polling()

if __name__ == '__main__':
    main()