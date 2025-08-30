# app/bot/handlers/settings_handler.py
from telegram import Update
from telegram.ext import ContextTypes
import logging
import re

from trading.settings_manager import get_settings, update_settings

logger = logging.getLogger(__name__)

HELP_TEXT = (
    "⚙️ Настройки бота\n\n"
    "Показать: `settings`\n"
    "Установить риск (лонг/шорт): `set risk 40/30`\n"
    "Только лонг: `set risk long 35`\n"
    "Только шорт: `set risk short 25`\n"
    "Стоп-лосс: `set sl 0.7`  (в %)\n"
    "Тейк-профит: `set tp 9`  (в %)\n"
)

def _fmt_settings():
    s = get_settings()
    return (
        "🔧 Текущие настройки:\n"
        f"• Risk LONG: {s.risk_long_percent:.2f}%\n"
        f"• Risk SHORT: {s.risk_short_percent:.2f}%\n"
        f"• Stop-Loss: {s.stop_loss_percent:.2f}%\n"
        f"• Take-Profit: {s.take_profit_percent:.2f}%\n"
    )

async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message or update.channel_post
    if not message:
        return
    await message.reply_text(_fmt_settings())

async def handle_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message or update.channel_post
    if not message or not message.text:
        return
    text = message.text.strip()

    try:
        # set risk 40/30
        m = re.match(r'^set\s+risk\s+(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)$', text, re.IGNORECASE)
        if m:
            long_v = float(m.group(1))
            short_v = float(m.group(2))
            s = update_settings(risk_long_percent=long_v, risk_short_percent=short_v)
            await message.reply_text("✅ Обновлено:\n" + _fmt_settings())
            return

        # set risk long 35
        m = re.match(r'^set\s+risk\s+long\s+(\d+(?:\.\d+)?)$', text, re.IGNORECASE)
        if m:
            long_v = float(m.group(1))
            s = update_settings(risk_long_percent=long_v)
            await message.reply_text("✅ Обновлено:\n" + _fmt_settings())
            return

        # set risk short 25
        m = re.match(r'^set\s+risk\s+short\s+(\d+(?:\.\d+)?)$', text, re.IGNORECASE)
        if m:
            short_v = float(m.group(1))
            s = update_settings(risk_short_percent=short_v)
            await message.reply_text("✅ Обновлено:\n" + _fmt_settings())
            return

        # set sl 0.7
        m = re.match(r'^set\s+sl\s+(\d+(?:\.\d+)?)$', text, re.IGNORECASE)
        if m:
            sl = float(m.group(1))
            s = update_settings(stop_loss_percent=sl)
            await message.reply_text("✅ Обновлено:\n" + _fmt_settings())
            return

        # set tp 9
        m = re.match(r'^set\s+tp\s+(\d+(?:\.\d+)?)$', text, re.IGNORECASE)
        if m:
            tp = float(m.group(1))
            s = update_settings(take_profit_percent=tp)
            await message.reply_text("✅ Обновлено:\n" + _fmt_settings())
            return

        # если ничего не подошло — подсказка
        await message.reply_text("❓ Не понял команду.\n\n" + HELP_TEXT)

    except Exception as e:
        logger.error(f"Ошибка обновления настроек: {e}", exc_info=True)
        await message.reply_text("❌ Ошибка при изменении настроек")
