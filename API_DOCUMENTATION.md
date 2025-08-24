# 📡 Trading Webhook Bot API

## Базовая информация

- **URL**: `https://webhook.mowertii.ru`
- **Метод**: `POST`
- **Content-Type**: `application/json`
- **Аутентификация**: Подпись HMAC SHA-256 (опционально)

## Endpoints

### 1. 📈 Торговые сигналы
**POST** `/webhook`

#### Покупка (BUY)
```json
{
  "action": "buy",
  "symbol": "SBER",
  "risk_percent": 0.4
}
```

#### Продажа (SELL)
```json
{
  "action": "sell", 
  "symbol": "GAZP",
  "risk_percent": 0.3
}
```

#### Закрыть все позиции
```json
{
  "action": "close_all"
}
```

#### Получить баланс
```json
{
  "action": "balance"
}
```

### 2. 🏥 Health Check
**GET** `/health`

Ответ:
```json
{
  "status": "healthy",
  "service": "trading-webhook-bot"
}
```

## Параметры запроса

| Поле | Тип | Обязательно | Описание |
|------|-----|-------------|----------|
| `action` | string | ✅ | Действие: `buy`, `sell`, `close_all`, `balance` |
| `symbol` | string | ✅* | Тикер инструмента (SBER, GAZP, и т.д.) |
| `risk_percent` | float | ❌ | Процент риска от баланса (по умолчанию: 0.4 для buy, 0.3 для sell) |

*Обязательно для `buy` и `sell`

## Безопасность

### HMAC подпись (рекомендуется)

Добавьте заголовок с подписью:
```
X-Signature-256: sha256=<hmac_signature>
```

Генерация подписи (Python):
```python
import hmac
import hashlib

secret = "your_webhook_secret"
payload = '{"action": "buy", "symbol": "SBER"}'
signature = hmac.new(
    secret.encode(),
    payload.encode(),
    hashlib.sha256
).hexdigest()

headers = {
    'Content-Type': 'application/json',
    'X-Signature-256': f'sha256={signature}'
}
```

## Примеры запросов

### cURL
```bash
# Покупка SBER с риском 40%
curl -X POST https://webhook.mowertii.ru/webhook \
  -H 'Content-Type: application/json' \
  -d '{"action": "buy", "symbol": "SBER", "risk_percent": 0.4}'

# Продажа GAZP с риском 30%  
curl -X POST https://webhook.mowertii.ru/webhook \
  -H 'Content-Type: application/json' \
  -d '{"action": "sell", "symbol": "GAZP", "risk_percent": 0.3}'

# Закрыть все позиции
curl -X POST https://webhook.mowertii.ru/webhook \
  -H 'Content-Type: application/json' \
  -d '{"action": "close_all"}'

# Получить баланс
curl -X POST https://webhook.mowertii.ru/webhook \
  -H 'Content-Type: application/json' \
  -d '{"action": "balance"}'
```

### Python
```python
import requests
import json

url = "https://webhook.mowertii.ru/webhook"
headers = {"Content-Type": "application/json"}

# Покупка
payload = {
    "action": "buy",
    "symbol": "SBER", 
    "risk_percent": 0.4
}

response = requests.post(url, headers=headers, json=payload)
print(response.json())
```

### JavaScript
```javascript
const webhook_url = "https://webhook.mowertii.ru/webhook";

const buySignal = {
    action: "buy",
    symbol: "SBER",
    risk_percent: 0.4
};

fetch(webhook_url, {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
    },
    body: JSON.stringify(buySignal)
})
.then(response => response.json())
.then(data => console.log(data));
```

## Ответы сервера

### Успешный ответ
```json
{
  "status": "success",
  "result": "✅ BUY SBER выполнен (риск: 40.0%)"
}
```

### Ошибка
```json
{
  "status": "error", 
  "message": "Инструмент XYZ не найден"
}
```

## Коды состояния HTTP

- `200` - Успешно
- `400` - Неверный запрос (невалидный JSON, отсутствуют поля)
- `401` - Неверная подпись
- `500` - Внутренняя ошибка сервера

## Уведомления в Telegram

Бот автоматически отправляет уведомления в Telegram:
- ✅ Подтверждение выполнения операций
- ❌ Ошибки и предупреждения  
- 📊 Результаты операций

## Мониторинг

### Логи
```bash
# Смотреть логи в реальном времени
docker-compose logs -f webhook-bot

# Последние 100 строк логов
docker-compose logs --tail 100 webhook-bot
```

### Метрики
- Health check: `GET /health`
- Проверка доступности: `curl https://webhook.mowertii.ru/health`