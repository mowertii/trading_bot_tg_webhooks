# trading_bot_tg_webhooks
# 📡 Trading Bot с интеграцией Telegram и Tinkoff Invest API

Этот проект — торговый бот, который принимает **сигналы через вебхуки**, управляется **через Telegram**, и автоматически торгует через **Tinkoff Invest API**.

---
# Основные файлы проекта

* app/webhook_server.py — основной сервер вебхуков.
* app/trading/tinkoff_client.py — работа с API Тинькофф.
* app/trading/order_executor.py — исполнение ордеров.
* app/trading/settings_manager.py — хранение и изменение risk/SL/TP.
* app/bot/ (handlers, utils) — логика бота и команды в Telegram.
* db/bot_settings.json — хранение текущих настроек.
* docker-compose.yml + Dockerfile — для запуска контейнеров.
* README.md и API_DOCUMENTATION.md — документация

## 🚀 Возможности

- Приём сигналов через Webhook API (`buy`, `sell`, `close_all`, `balance`).
- Автоматическая торговля по сигналам с учётом риска.
- Управление ботом через **Telegram**:
  - 💰 Просмотр баланса
  - 📊 Список позиций
  - 🔍 Поиск FIGI по тикеру
  - ✅ Покупка / продажа
  - 🛑 Закрытие всех позиций
  - ⚙️ Настройка risk/stop-loss/take-profit прямо в чате
- 📢 Уведомления в Telegram об операциях и ошибках.
- 🔄 Автоматический stop-loss и take-profit.

---

## 📂 Структура проекта

```
📁 app
 ├── 📁 bot            # Telegram-бот
 │    ├── handlers     # Обработчики команд
 │    └── main.py      # Точка запуска Telegram-бота
 ├── 📁 trading        # Логика работы с брокером
 │    ├── tinkoff_client.py   # Работа с API Tinkoff
 │    ├── order_executor.py   # Выставление ордеров
 │    ├── order_watcher.py    # Мониторинг исполнения
 │    ├── settings_manager.py # Настройки risk/sl/tp
 │    └── risk_manager.py
 ├── 📄 webhook_server.py     # Webhook API
 ├── 📄 notifications.py      # Отправка сообщений в Telegram
 ├── 📄 config.py             # Конфигурация (env)
 ├── 📄 requirements.txt      # Зависимости
 ├── 📄 Dockerfile            # Docker сборка
 └── 📄 docker-compose.yml    # Многоконтейнерный запуск
📁 db
 └── init.sql                 # SQL-инициализация
.env                          # Настройки окружения
```

---

## ⚙️ Установка и запуск

### 1. Клонируем проект
```bash
git clone git@github.com:mowertii/trading_bot_tg_webhooks.git
cd trading_bot_tg_webhooks
```

### 2. Заполняем `.env`
Пример:
```ini
BOT_TOKEN=ваш_telegram_token
TG_CHAT_ID=ваш_telegram_chat_id
TINKOFF_TOKEN=ваш_tinkoff_api_token
ACCOUNT_ID=ваш_account_id
REDIS_URL=redis://redis:6379/0
POSTGRES_DB=trading_data
POSTGRES_USER=bot
POSTGRES_PASSWORD=11111111
DB_URL=postgresql://bot:11111111@db:5432/trading_data
WEBHOOK_SECRET=секретный_ключ
WEBHOOK_PORT=8080
WEBHOOK_HOST=0.0.0.0
```

### 3. Запуск через Docker
```bash
docker-compose up --build -d
```

### 4. Проверка
- Health check:
  ```bash
  curl http://localhost:8080/health
  ```
- Логи:
  ```bash
  docker-compose logs -f webhook-bot
  ```

---

## 💬 Telegram команды

- `баланс` / `balance` — показать баланс
- `состояние` / `positions` — показать открытые позиции
- `figi SBER` — найти FIGI
- `buy SBER` — купить
- `sell GAZP` — продать
- `close all` — закрыть все позиции
- `settings` — показать текущие настройки
- `set risk 40/30` — обновить риск (лонг/шорт)
- `set risk long 35` — риск только для лонга
- `set risk short 25` — риск только для шорта
- `set sl 0.7` — стоп-лосс (%)
- `set tp 9` — тейк-профит (%)
- `/help` → показать доступные функции 

---

## 🔌 API Webhook

Документация вынесена в [API_DOCUMENTATION.md](./API_DOCUMENTATION.md).

Примеры запросов:
# открытие сделки по риску в % от доступных средств, с учётом плеча ЛОКАЛЬНО
```bash
curl -X POST http://localhost:8080/webhook \
  -H "Content-Type: application/json" \
  -d '{"action": "buy", "symbol": "SBER", "risk_percent": 0.4}'
```
# открытие сделок строго по количеству, игнорируя настройки риска УДАЛЁННО
curl -X POST https://webhook.example.ru/webhook?token=<WEBHOOK_SECRET> \
  -H 'Content-Type: application/json' \
  -d '{"action":"sell","symbol":"GZU5","quantity":1}'  
---

## 🛠️ Технологии

- Python 3.11
- [python-telegram-bot](https://docs.python-telegram-bot.org/)
- [tinkoff-investments](https://tinkoff.github.io/investAPI/)
- Docker + docker-compose
- Redis, PostgreSQL
- Gunicorn + aiohttp

---

## 📈 Дальнейшие планы

- ✅ Автоматический stop-loss / take-profit (реализовано)
- 📊 Отчёты по сделкам
- 🔔 Поддержка сигналов от нескольких источников
- 🤖 Подключение ML для прогнозов
- 🌐 Веб-панель управления

---

## 📝 Лицензия

MIT License. Используйте и дорабатывайте под свои нужды.
