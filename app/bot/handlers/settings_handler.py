# app/bot/handlers/settings_handler.py - ИСПРАВЛЕННАЯ ВЕРСИЯ
from telegram import Update
from telegram.ext import ContextTypes
import logging
import re

from trading.settings_manager import get_settings, update_settings

logger = logging.getLogger(__name__)

HELP_TEXT = (
    "⚙️ *Настройки бота*\n\n"
    "*Торговля:*\n"
    "• Показать: `settings`\n"
    "• Риск (лонг/шорт): `set risk 40/30`\n"
    "• Только лонг: `set risk long 35`\n"
    "• Только шорт: `set risk short 25`\n"
    "• Стоп-лосс: `set sl 0.7` (в %)\n"
    "• Тейк-профит: `set tp 9` (в %)\n\n"
    "*Авто-ликвидация:*\n"
    "• Включить/выключить: `set auto on/off`\n"
    "• Время: `set auto time 21:30`\n"
    "• Окно блокировки: `set auto block 45` (мин)\n"
    "• Дни недели: `set auto days 0,1,2,3,4` (0=Пн)"
)

def _fmt_settings():
    """Форматирует настройки для красивого вывода в Telegram"""
    s = get_settings()
    days_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    active_days = ", ".join([days_names[d] for d in s.auto_liquidation_days])
    
    return (
        f"🔧 *Текущие настройки:*\n\n"
        f"*Торговля:*\n"
        f"• Risk LONG: `{s.risk_long_percent:.1f}%`\n"
        f"• Risk SHORT: `{s.risk_short_percent:.1f}%`\n"
        f"• Stop-Loss: `{s.stop_loss_percent:.2f}%`\n"
        f"• Take-Profit: `{s.take_profit_percent:.1f}%`\n\n"
        f"*Авто-ликвидация:*\n"
        f"• Статус: {'✅ Включена' if s.auto_liquidation_enabled else '❌ Выключена'}\n"
        f"• Время: `{s.auto_liquidation_time}` МСК\n"
        f"• Блокировка: `{s.auto_liquidation_block_minutes}` мин\n"
        f"• Дни: `{active_days}`"
    )

async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает текущие настройки"""
    message = update.message or update.channel_post
    if not message:
        return
    await message.reply_text(_fmt_settings(), parse_mode='Markdown')

async def handle_settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды 'settings'"""
    await show_settings(update, context)

async def handle_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команд 'set ...'"""
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
            update_settings(risk_long_percent=long_v, risk_short_percent=short_v)
            await message.reply_text("✅ Обновлено:\n" + _fmt_settings(), parse_mode='Markdown')
            return

        # set risk long 35
        m = re.match(r'^set\s+risk\s+long\s+(\d+(?:\.\d+)?)$', text, re.IGNORECASE)
        if m:
            long_v = float(m.group(1))
            update_settings(risk_long_percent=long_v)
            await message.reply_text("✅ Обновлено:\n" + _fmt_settings(), parse_mode='Markdown')
            return

        # set risk short 25
        m = re.match(r'^set\s+risk\s+short\s+(\d+(?:\.\d+)?)$', text, re.IGNORECASE)
        if m:
            short_v = float(m.group(1))
            update_settings(risk_short_percent=short_v)
            await message.reply_text("✅ Обновлено:\n" + _fmt_settings(), parse_mode='Markdown')
            return

        # set sl 0.7
        m = re.match(r'^set\s+sl\s+(\d+(?:\.\d+)?)$', text, re.IGNORECASE)
        if m:
            sl = float(m.group(1))
            update_settings(stop_loss_percent=sl)
            await message.reply_text("✅ Обновлено:\n" + _fmt_settings(), parse_mode='Markdown')
            return

        # set tp 9
        m = re.match(r'^set\s+tp\s+(\d+(?:\.\d+)?)$', text, re.IGNORECASE)
        if m:
            tp = float(m.group(1))
            update_settings(take_profit_percent=tp)
            await message.reply_text("✅ Обновлено:\n" + _fmt_settings(), parse_mode='Markdown')
            return

        # set auto on/off
        m = re.match(r'^set\s+auto\s+(on|off|true|false|1|0)$', text, re.IGNORECASE)
        if m:
            enabled = m.group(1).lower() in ['on', 'true', '1']
            update_settings(auto_liquidation_enabled=enabled)
            status = "включена" if enabled else "выключена"
            await message.reply_text(f"✅ Авто-ликвидация {status}\n\n" + _fmt_settings(), parse_mode='Markdown')
            return

        # set auto time 21:30
        m = re.match(r'^set\s+auto\s+time\s+(\d{1,2}):(\d{2})$', text, re.IGNORECASE)
        if m:
            hour = int(m.group(1))
            minute = int(m.group(2))
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                time_str = f"{hour:02d}:{minute:02d}"
                update_settings(auto_liquidation_time=time_str)
                await message.reply_text(f"✅ Время авто-ликвидации изменено на {time_str} МСК\n\n" + _fmt_settings(), parse_mode='Markdown')
                return
            else:
                await message.reply_text("❌ Неверный формат времени. Используйте HH:MM (00:00 - 23:59)")
                return

        # set auto block 45
        m = re.match(r'^set\s+auto\s+block\s+(\d+)$', text, re.IGNORECASE)
        if m:
            minutes = int(m.group(1))
            if 1 <= minutes <= 180:  # От 1 до 3 часов
                update_settings(auto_liquidation_block_minutes=minutes)
                await message.reply_text(f"✅ Окно блокировки изменено на {minutes} минут\n\n" + _fmt_settings(), parse_mode='Markdown')
                return
            else:
                await message.reply_text("❌ Окно блокировки должно быть от 1 до 180 минут")
                return

        # set auto days 0,1,2,3,4
        m = re.match(r'^set\s+auto\s+days\s+([0-6,\s]+)$', text, re.IGNORECASE)
        if m:
            try:
                days_str = m.group(1).replace(" ", "")
                days = [int(d) for d in days_str.split(",") if d.strip()]
                days = [d for d in days if 0 <= d <= 6]  # Фильтруем только валидные дни
                if days:
                    days = sorted(list(set(days)))  # Убираем дубли и сортируем
                    update_settings(auto_liquidation_days=days)
                    days_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
                    active_days = ", ".join([days_names[d] for d in days])
                    await message.reply_text(f"✅ Дни авто-ликвидации: {active_days}\n\n" + _fmt_settings(), parse_mode='Markdown')
                    return
                else:
                    await message.reply_text("❌ Укажите валидные дни недели (0=Пн, 1=Вт, ..., 6=Вс)")
                    return
            except ValueError:
                await message.reply_text("❌ Неверный формат. Используйте: `set auto days 0,1,2,3,4`")
                return

        # если ничего не подошло — подсказка
        await message.reply_text("❓ Не понял команду.\n\n" + HELP_TEXT, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Ошибка обновления настроек: {e}", exc_info=True)
        await message.reply_text("❌ Ошибка при изменении настроек")
