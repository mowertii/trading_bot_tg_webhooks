# trading_bot_tg_webhooks
📡 Trading Bot с интеграцией Telegram и Tinkoff Invest API, поддержкой Webhook-сигналов, мульти-TP, авто-ликвидации и логированием в PostgreSQL.
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
-  Приём сигналов через Webhook API (buy, sell, close_all, balance)
-  Автоматическая торговля по сигналам с учётом риска (лонг/шорт)
-  Разбиение позиции на несколько TP-уровней (мульти-TP)
-  Авто-ликвидация по расписанию с блокировкой входящих сигналов
-  Логирование всех событий (signal, trade, sl_order, tp_order, error, close_all, balance_request, auto_liquidation_*, startup) в таблицу event_logs
-  Управление ботом через Telegram:
    💰 balance / баланс — показать баланс
    📊 positions / состояние — открыть позиции
    🔍 figi SBER — найти FIGI
    ✅ buy SBER / sell GAZP — торговые операции
    🛑 close all — снять все позиции и ордера
    ⚙️ settings — текущие настройки;
    set ... — менять риск, SL, TP, мульти-TP, авто-ликвидацию
    /help — справка по всем командам
---

## 📂 Структура проекта (основные файлы проекта)

```
📁 app
 ├── 📁 bot            # Telegram-бот
 │    ├──📁 handlers     # Обработчики команд
 │    │   ├── 📄 balance_handler.py
 │    │   ├── 📄 close_all_handler.py
 │    │   ├── 📄 figi_handler.py
 │    │   ├── 📄 help_handler.py
 │    │   ├── 📄 init.py
 │    │   ├── 📄 position_handler.py
 │    │   ├── 📄 settings_handler.py
 │    │   └── 📄 trade_handlers.py 
 │    ├── 📄 init.py
 │    └── 📄 main.py             # Точка запуска Telegram-бота
 ├── 📁 trading                  # Логика работы с брокером
 │    ├── 📄 tinkoff_client.py   # Работа с API Tinkoff
 │    ├── 📄 order_executor.py   # Торговая логика + логирование ордеров
 │    ├── 📄 order_watcher.py    # Мониторинг исполнения
 │    ├── 📄 settings_manager.py # risk/sl/tp, мульти-TP, авто-ликвидация
 │    ├── 📄 risk_manager.py     # Дополнительная проверка риск-менеджмента (опционально)
 ├── 📁 utils
 │    └── 📄 telegram_notifications.py 
 ├── 📄 webhook_server.py     # Webhook API + планировщик
 ├── 📄 notifications.py      # Отправка сообщений в Telegram
 ├── 📄 config.py             # Конфигурация (env)
 ├── 📄 requirements.txt      # Зависимости
 ├── 📄 Dockerfile            # Docker сборка
 └── 📄 docker-compose.yml    # Многоконтейнерный запуск
📁 db
 ├── 📄 bot_settings.json     # Хранимые параметры
 └── 📄 init.sql              # SQL-инициализация, создание таблиц
📄.env                        # Настройки окружения
```
# Веб-интерфейсы и управление
  - PgAdmin — https://dealstatics.mowertii.ru/pgadmin/
  - (При первом входе используйте настройки из .env)
  - Webhook API — POST-запросы с торговыми сигналами на /webhook
  - Telegram бот — для настройки и мониторинга
---
# Мониторинг и логирование в PostgreSQL
 - В таблице event_logs логируются все события:
 - Webhook сигналы (signal)
 - Торговые операции (trade)
 - Установка SL / TP (sl_order, tp_order)
 - Обработка ошибок (error)
 - Запрос баланса и закрытие всех позиций
 - Для просмотра используйте pgAdmin или команду:
```bash
docker-compose exec db psql -U bot -d trading_data -c "SELECT * FROM event_logs ORDER BY event_time DESC LIMIT 10;"
```
---
# Настройка nginx для доступа к pgAdmin
Должна быть корректная прокси-настройка с WebSocket поддержкой:
```text
map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      close;
}

server {
    listen 80;
    server_name dealstatics.mowertii.ru;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name dealstatics.mowertii.ru;

    ssl_certificate     /etc/nginx/ssl.d/certs/mowertii.ru/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl.d/certs/mowertii.ru/privkey.pem;

    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;
    ssl_session_cache   shared:SSL:10m;
    ssl_session_timeout 10m;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    location / {
        proxy_pass http://127.0.0.1:5050;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
    }
}

```
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
POSTGRES_USER=bot #For example
POSTGRES_PASSWORD=your_password #Very strong pass for example: 11111111
PGADMIN_EMAIL=admin@mowertii.ru
PGADMIN_PASSWORD=other_your_password
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
