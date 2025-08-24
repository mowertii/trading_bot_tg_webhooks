from telegram import Update
from telegram.ext import ContextTypes
from trading.tinkoff_client import TinkoffClient
import os
import logging
import asyncio  

logger = logging.getLogger(__name__)

async def handle_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        message = update.message or update.channel_post
        client = TinkoffClient(os.getenv("TINKOFF_TOKEN"), os.getenv("ACCOUNT_ID"))
        
        balance = await client.get_balance_async()
        logger.debug(f"Raw balance data: {balance}")
        
        await message.reply_text(f"💰 Баланс: {balance:.2f} RUB")
    except Exception as e:
        logger.error(f"Balance error: {str(e)}", exc_info=True)
        await message.reply_text("❌ Ошибка получения баланса")
