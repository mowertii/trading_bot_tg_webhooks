# 📘 Webhook Trader Bot — Полное руководство для новичка

Этот проект позволяет подключать **сигналы из TradingView** к **Тинькофф Инвестициям** через вебхуки и управлять ботом прямо из **Telegram**.

---

## 🖥 Требования

- **Операционная система**: Linux (Ubuntu 20.04+), macOS или Windows 10/11 с установленным [Docker Desktop](https://www.docker.com/products/docker-desktop).  
- **Интернет**: постоянное соединение для связи с API Тинькофф и Telegram.  
- **Docker + docker-compose**: для запуска сервисов в контейнерах.  

---

## 🔑 Получение токенов и ID

### 1. Telegram Bot Token (BOT_TOKEN)
1. В Telegram найдите бота `@BotFather`.
2. Отправьте команду `/newbot` и создайте нового бота.
3. Сохраните полученный **BOT_TOKEN**.

### 2. Telegram Chat ID (TG_CHAT_ID)
- Добавьте созданного бота в свой **личный чат** или **группу**.  
- Напишите в этот чат любое сообщение.  
- В браузере откройте:  
  ```
  https://api.telegram.org/bot<BOT_TOKEN>/getUpdates
  ```
- В ответе найдите поле `"chat":{"id": ... }` → это ваш **TG_CHAT_ID**.  
  ⚠️ Подходит как для **личных чатов**, так и для **групп**.

### 3. Тинькофф Инвестиции
- Авторизуйтесь в [личном кабинете Тинькофф Инвестиции](https://www.tinkoff.ru/invest/).  
- Перейдите в раздел **«API Тинькофф Инвестиции»** → сгенерируйте **TINKOFF_TOKEN**.  
- Найдите свой **ACCOUNT_ID** (идентификатор брокерского счёта).  

### 4. Webhook Secret
- Придумайте случайный набор символов (например, сгенерируйте на [random.org](https://www.random.org/passwords/)) — это будет ваш **WEBHOOK_SECRET**.  

---

## ⚙️ Подготовка проекта

1. Клонируем репозиторий:
   ```bash
   git clone git@github.com:mowertii/trading_bot_tg_webhooks.git
   cd trading_bot_tg_webhooks
   ```

2. Создаём файл `.env` и прописываем переменные окружения:
   ```ini
   TINKOFF_TOKEN=ваш_токен
   ACCOUNT_ID=ваш_счёт
   BOT_TOKEN=ваш_тг_бот_токен
   TG_CHAT_ID=ваш_chat_id
   WEBHOOK_SECRET=ваш_секрет
   ```

3. Проверяем структуру проекта:
   ```
   app/
     ├── bot/
     ├── trading/
     ├── webhook_server.py
   db/
     └── bot_settings.json
   docker-compose.yml
   Dockerfile
   ```

---

## ▶️ Запуск приложения

1. Поднимаем контейнеры:
   ```bash
   docker-compose up --build -d
   ```

2. Проверяем, что сервис работает:
   ```bash
   curl http://localhost:8080/health
   ```
   ответ должен быть:
   ```json
   {"status":"healthy","service":"trading-webhook-bot"}
   ```

3. Проверяем Telegram-бота:  
   В чат пишем:
   ```
   /show_settings
   ```
   бот вернёт текущие настройки (риск, стоп, тейк-профит).

---

## 📡 Подключение TradingView

1. В TradingView создаём новый алерт.  
2. В поле **Webhook URL** указываем:
   ```
   https://ваш_домен/webhook
   ```
3. В **Headers** добавляем:
   ```
   X-Signature-256: sha256=<сигнатура, сгенерированная вашим скриптом>
   ```
4. В **Message** пишем JSON.  
   Пример для покупки:
   ```json
   {
     "action": "buy",
     "symbol": "SBER"
   }
   ```
   Пример для продажи:
   ```json
   {
     "action": "sell",
     "symbol": "SBER"
   }
   ```

---

## ⚙️ Управление ботом через Telegram

Доступные команды:
```
/set_risk 0.5     → установить риск на сделку (50%)
/set_stop 1%      → установить стоп-лосс (1%)
/set_tp 9%        → установить тейк-профит (9%)
/show_settings    → показать текущие настройки
/help             → показать доступные функции
```

---

## ❓ Частые вопросы

- **Можно ли использовать в группах Telegram?**  
  ✅ Да, бот работает как в личных чатах, так и в группах.

- **Что если контейнер упадёт?**  
  Docker автоматически перезапустит сервис. Настройки сохраняются в `db/bot_settings.json`.

- **Где хранятся риски и стопы?**  
  В JSON-файле `db/bot_settings.json`. Их можно менять прямо из Telegram.

---
