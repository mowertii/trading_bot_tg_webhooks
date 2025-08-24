from telegram import Update
from telegram.ext import ContextTypes
from trading.tinkoff_client import TinkoffClient
import os
import logging

logger = logging.getLogger(__name__)

async def handle_positions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message or update.channel_post  # Исправление ошибки NoneType
    if not message:
        return

    try:
        client = TinkoffClient(os.getenv("TINKOFF_TOKEN"), os.getenv("ACCOUNT_ID"))
        positions = await client.get_positions_async()

        if not positions:
            await message.reply_text("🔍 Нет открытых позиций")
            return

        response = "📊 Открытые позиции:\n\n"
        for pos in positions:
            response += f"• {pos.ticker}: {pos.lots} лотов ({pos.direction.upper()})\n"

        await message.reply_text(response)

    except Exception as e:
        logger.error(f"Ошибка: {str(e)}", exc_info=True)
        await message.reply_text("❌ Ошибка при получении позиций")
