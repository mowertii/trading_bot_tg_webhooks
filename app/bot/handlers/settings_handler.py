# app/bot/handlers/settings_handler.py - ВЕРСИЯ с мульти-TP настройками
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
    "*Мульти-TP:*\n"
    "• Включить/выключить: `set multi on/off`\n"
    "• Уровни TP: `set tp levels 0.5,1.0,1.6`\n"
    "• Доли позиций: `set tp portions 33,33,34`\n\n"
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
    
    # Форматируем мульти-TP информацию
    multi_tp_status = "✅ Включен" if s.use_multi_tp else "❌ Выключен"
    tp_levels_str = ", ".join([f"{tp:.1f}%" for tp in s.tp_levels])
    tp_portions_str = ", ".join([f"{int(p*100)}%" for p in s.tp_portions])
    
    return (
        f"🔧 *Текущие настройки:*\n\n"
        f"*Торговля:*\n"
        f"• Risk LONG: `{s.risk_long_percent:.1f}%`\n"
        f"• Risk SHORT: `{s.risk_short_percent:.1f}%`\n"
        f"• Stop-Loss: `{s.stop_loss_percent:.2f}%`\n"
        f"• Take-Profit: `{s.take_profit_percent:.1f}%` (базовый)\n\n"
        f"*Мульти-TP:*\n"
        f"• Статус: {multi_tp_status}\n"
        f"• Уровни: `{tp_levels_str}`\n"
        f"• Доли: `{tp_portions_str}`\n\n"
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

        # НОВЫЕ КОМАНДЫ для мульти-TP
        
        # set multi on/off
        m = re.match(r'^set\s+multi\s+(on|off|true|false|1|0)$', text, re.IGNORECASE)
        if m:
            enabled = m.group(1).lower() in ['on', 'true', '1']
            update_settings(use_multi_tp=enabled)
            status = "включен" if enabled else "выключен"
            await message.reply_text(f"✅ Мульти-TP {status}\n\n" + _fmt_settings(), parse_mode='Markdown')
            return

        # set tp levels 0.5,1.0,1.6
        m = re.match(r'^set\s+tp\s+levels\s+([\d\.,\s]+)$', text, re.IGNORECASE)
        if m:
            try:
                levels_str = m.group(1).replace(" ", "")
                levels = [float(l) for l in levels_str.split(",") if l.strip()]
                if len(levels) > 0 and all(0 <= l <= 100 for l in levels):
                    # Автоматически подстраиваем доли под количество уровней
                    count = len(levels)
                    base_portion = 1.0 / count
                    portions = [base_portion] * (count - 1) + [1.0 - base_portion * (count - 1)]
                    
                    update_settings(tp_levels=levels, tp_portions=portions)
                    await message.reply_text(f"✅ Уровни TP обновлены: {levels}\nДоли автоматически распределены\n\n" + _fmt_settings(), parse_mode='Markdown')
                    return
                else:
                    await message.reply_text("❌ Уровни TP должны быть в диапазоне 0-100%")
                    return
            except ValueError:
                await message.reply_text("❌ Неверный формат. Используйте: `set tp levels 0.5,1.0,1.6`")
                return

        # set tp portions 33,33,34
        m = re.match(r'^set\s+tp\s+portions\s+([\d,\s]+)$', text, re.IGNORECASE)
        if m:
            try:
                portions_str = m.group(1).replace(" ", "")
                portions_pct = [int(p) for p in portions_str.split(",") if p.strip()]
                
                if len(portions_pct) > 0 and sum(portions_pct) == 100:
                    portions = [p / 100.0 for p in portions_pct]
                    # Подстраиваем количество уровней под количество долей
                    s = get_settings()
                    if len(portions) != len(s.tp_levels):
                        # Создаем равномерные уровни
                        levels = [0.5 + i * 0.5 for i in range(len(portions))]
                        update_settings(tp_levels=levels, tp_portions=portions)
                        await message.reply_text(f"✅ Доли TP обновлены: {portions_pct}%\nУровни автоматически подстроены\n\n" + _fmt_settings(), parse_mode='Markdown')
                    else:
                        update_settings(tp_portions=portions)
                        await message.reply_text(f"✅ Доли TP обновлены: {portions_pct}%\n\n" + _fmt_settings(), parse_mode='Markdown')
                    return
                else:
                    await message.reply_text("❌ Доли должны быть положительными и в сумме равны 100%")
                    return
            except ValueError:
                await message.reply_text("❌ Неверный формат. Используйте: `set tp portions 33,33,34`")
                return

        # КОМАНДЫ для авто-ликвидации (без изменений)
        
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
            if 1 <= minutes <= 180:
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
                days = [d for d in days if 0 <= d <= 6]
                if days:
                    days = sorted(list(set(days)))
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