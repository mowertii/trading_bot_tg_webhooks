# app/bot/main.py - ИСПРАВЛЕННАЯ И РАСШИРЕННАЯ ВЕРСИЯ
import os
import re
import asyncio
import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters,
)

# Импорты обработчиков
from bot.handlers import (
    handle_balance,
    handle_figi_message,
    handle_buy,
    handle_sell,
    handle_positions,
    handle_close_all,
)

# Импорты настроек
from bot.handlers.settings_handler import handle_settings_command, handle_set

# НОВЫЙ ИМПОРТ: обработчик справки
from bot.handlers.help_handler import handle_help_command, handle_help_message

# Торговые компоненты
from trading.order_executor import OrderExecutor
from trading.order_watcher import OrderWatcher

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
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
    """Настройка всех обработчиков команд"""
    
    # ========== КОМАНДЫ (/command) ==========
    application.add_handler(CommandHandler("help", handle_help_command))
    application.add_handler(CommandHandler("start", handle_help_command))  # start тоже показывает справку
    
    # ========== СПРАВКА ==========
    application.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(re.compile(r"^help$", re.IGNORECASE)),
        handle_help_message,
    ))
    
    # ========== БАЛАНС ==========
    application.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(re.compile(r"^(баланс|balance)$", re.IGNORECASE)),
        handle_balance,
    ))

    # ========== FIGI ==========
    application.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(re.compile(r"^figi\s+\w+", re.IGNORECASE)),
        handle_figi_message,
    ))

    # ========== ПОЗИЦИИ ==========
    application.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(re.compile(r"^(состояние|positions|status)$", re.IGNORECASE)),
        handle_positions,
    ))

    # ========== ЗАКРЫТЬ ВСЁ ==========
    application.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(re.compile(
            r"^(закрыть всё|закрыть все|завершить|уйти в кэш|сэйв|save|close all|exit all|liquidate|"
            r"стоп всё|стоп все|выход|экстренный выход|паника|panic|emergency exit|"
            r"закрыть позиции|снять все|отменить все|cancel all)$",
            re.IGNORECASE,
        )),
        handle_close_all,
    ))

    # ========== ТОРГОВЫЕ ОПЕРАЦИИ ==========
    # Покупка
    application.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(re.compile(r"^buy\s+\w+", re.IGNORECASE)),
        handle_buy,
    ))

    # Продажа
    application.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(re.compile(r"^sell\s+\w+", re.IGNORECASE)),
        handle_sell,
    ))

    # ========== НАСТРОЙКИ ==========
    # Показать настройки
    application.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(re.compile(r"^(settings|настройки)$", re.IGNORECASE)),
        handle_settings_command,
    ))

    # Изменить настройки (расширенная регулярка для всех set команд)
    application.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(re.compile(
            r"^set\s+(risk|sl|tp|multi|auto)", re.IGNORECASE
        )),
        handle_set,
    ))

def main():
    """Главная функция запуска бота"""
    # Переменные окружения
    token = os.getenv("BOT_TOKEN")
    tinkoff_token = os.getenv("TINKOFF_TOKEN")
    account_id = os.getenv("ACCOUNT_ID")
    chat_id = os.getenv("TG_CHAT_ID")

    # Проверка обязательных переменных
    if not token:
        raise ValueError("Не задан BOT_TOKEN")
    if not tinkoff_token or not account_id:
        raise ValueError("Не заданы TINKOFF_TOKEN или ACCOUNT_ID")

    # Создание приложения
    application = ApplicationBuilder().token(token).build()

    # Настройка обработчиков
    setup_handlers(application)
    
    # Обработчик ошибок
    application.add_error_handler(error_handler)

    # Инициализация торговых компонентов
    executor = OrderExecutor(tinkoff_token, account_id)
    watcher = OrderWatcher(
        tinkoff_token,
        account_id,
        executor,
        tg_bot=application.bot,
        chat_id=chat_id,
    )

    # Запуск OrderWatcher в фоне
    loop = asyncio.get_event_loop()
    loop.create_task(watcher.watch_trades())

    logger.info("🤖 Telegram бот запущен с поддержкой:")
    logger.info("  📊 Просмотр баланса и позиций")
    logger.info("  💹 Торговые операции (buy/sell)")
    logger.info("  ⚙️ Настройки (риски, SL, TP)")
    logger.info("  🎯 Мульти-TP система")
    logger.info("  ⏰ Авто-ликвидация")
    logger.info("  ❓ Справка (/help)")
    
    # Запуск polling
    application.run_polling()

if __name__ == "__main__":
    main()