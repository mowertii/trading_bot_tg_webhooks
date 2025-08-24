from telegram import Update, Message
from telegram.ext import ContextTypes
from telegram.helpers import escape_markdown
from tinkoff.invest import AsyncClient, InstrumentShort
import os
import logging

logger = logging.getLogger(__name__)

async def handle_figi_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        message = update.message or update.channel_post
        if not message or not message.text:
            return

        # Извлекаем название инструмента после команды figi
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.reply_text("❌ Укажите название инструмента")
            return

        instrument_name = parts[1].strip()
        await process_figi_request(message, instrument_name)

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        await message.reply_text("⚠️ Ошибка обработки запроса")

async def process_figi_request(message: Message, instrument_name: str):
    try:
        token = os.getenv("TINKOFF_TOKEN")
        if not token:
            logger.error("TINKOFF_TOKEN not configured!")
            await message.reply_text("❌ Ошибка конфигурации")
            return

        async with AsyncClient(token) as client:
            # Ищем инструмент
            response = await client.instruments.find_instrument(query=instrument_name)
            
            if not response.instruments:
                await message.reply_text(f"❌ Инструмент '{escape_markdown(instrument_name, version=2)}' не найден")
                return

            # Берем первый результат и экранируем все поля
            instrument = response.instruments[0]
            safe_data = {
                'name': escape_markdown(instrument.name, version=2),
                'figi': escape_markdown(instrument.figi, version=2),
                'ticker': escape_markdown(instrument.ticker, version=2)
            }

            response_text = (
                f"🔍 *{safe_data['name']}*\n"
                f"FIGI: \`{safe_data['figi']}\`\n"
                f"Тикер: {safe_data['ticker']}"
            )
            
            await message.reply_text(response_text, parse_mode='MarkdownV2')

    except Exception as e:
        logger.error(f"API Error: {str(e)}", exc_info=True)
        await message.reply_text("⚠️ Ошибка подключения к брокеру")
