# app/bot/handlers/help_handler.py - Новый файл с командой /help
from telegram import Update
from telegram.ext import ContextTypes
import logging

logger = logging.getLogger(__name__)

HELP_TEXT = """
🤖 **Торговый бот - Справка по командам**

📊 **ПРОСМОТР ИНФОРМАЦИИ:**
• `balance` — показать баланс счета
• `positions` — открытые позиции
• `status` — общий статус счета
• `settings` — текущие настройки бота

💹 **ТОРГОВЫЕ ОПЕРАЦИИ:**
• `buy SBER` — купить SBER по настройкам риска
• `sell GAZP` — продать GAZP по настройкам риска
• `close all` — закрыть все позиции и отменить ордера

⚙️ **НАСТРОЙКИ ТОРГОВЛИ:**
• `set risk 40/30` — риск лонг/шорт (в %)
• `set risk long 35` — только риск лонга
• `set risk short 25` — только риск шорта
• `set sl 0.7` — стоп-лосс (в %)
• `set tp 5.0` — базовый тейк-профит (в %)

🎯 **МУЛЬТИ-TP НАСТРОЙКИ:**
• `set multi on` — включить мульти-TP
• `set multi off` — выключить мульти-TP  
• `set tp levels 0.5,1.0,1.6` — уровни TP (в %)
• `set tp portions 33,33,34` — доли позиции (в %)

⏰ **АВТО-ЛИКВИДАЦИЯ:**
• `set auto on/off` — включить/выключить
• `set auto time 21:44` — время закрытия (МСК)
• `set auto block 30` — окно блокировки (мин)
• `set auto days 0,1,2,3,4` — дни (0=Пн, 6=Вс)

🌐 **WEBHOOK API:**
```
POST /webhook
{
  "action": "buy",
  "symbol": "SBER", 
  "quantity": 5,
  "tp_percent": 1.5,
  "sl_percent": 0.8
}
```

**Параметры webhook:**
• `action` — "buy" или "sell"
• `symbol` — тикер инструмента
• `quantity` — количество лотов (опционально)
• `risk_percent` — риск в % (опционально)
• `tp_percent` — кастомный TP в % (отключает мульти-TP)
• `sl_percent` — кастомный SL в %

📝 **ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ:**

*Торговля:*
```
buy SBER
sell GAZP  
close all
```

*Настройка рисков:*
```
set risk 50/40
set sl 1.2
set tp 8.0
```

*Мульти-TP:*
```
set multi on
set tp levels 0.3,0.8,1.5
set tp portions 30,40,30
```

*Авто-ликвидация:*
```
set auto on
set auto time 21:30
set auto days 0,1,2,3,4
```

ℹ️ **ДОПОЛНИТЕЛЬНО:**
• Все проценты указываются в человеческом формате (1.5 = 1.5%)
• Мульти-TP автоматически делит позицию на части
• Авто-ликвидация закрывает все в заданное время
• Webhook блокируется за 30 мин до авто-ликвидации
"""

async def handle_help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    message = update.message or update.channel_post
    if not message:
        return
    
    try:
        await message.reply_text(HELP_TEXT, parse_mode='Markdown')
        logger.info("Help command executed successfully")
    except Exception as e:
        logger.error(f"Error in help command: {e}")
        # Если Markdown не работает, отправляем как обычный текст
        await message.reply_text(HELP_TEXT.replace('*', '').replace('`', ''))

async def handle_help_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик сообщения 'help' (без /)"""
    await handle_help_command(update, context)