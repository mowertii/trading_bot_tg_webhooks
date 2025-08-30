# app/webhook_server_lazy.py
import os
import json
import hmac
import hashlib
import logging
from decimal import Decimal
from aiohttp import web, ClientSession
from aiohttp.web_request import Request
from aiohttp.web_response import Response
import asyncio

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class WebhookServer:
    def __init__(self):
        self.tinkoff_token = os.getenv("TINKOFF_TOKEN")
        self.account_id = os.getenv("ACCOUNT_ID") 
        self.webhook_secret = os.getenv("WEBHOOK_SECRET")
        self.bot_token = os.getenv("BOT_TOKEN")
        self.chat_id = os.getenv("TG_CHAT_ID")
        
        if not all([self.tinkoff_token, self.account_id]):
            raise ValueError("Missing required environment variables")
        
        # Ленивая инициализация - создаем клиенты только при первом использовании
        self._client = None
        self._executor = None

    async def get_client(self):
        """Ленивое получение Tinkoff клиента"""
        if self._client is None:
            from trading.tinkoff_client import TinkoffClient
            self._client = TinkoffClient(self.tinkoff_token, self.account_id)
            logger.info("TinkoffClient initialized")
        return self._client

    async def get_executor(self):
        """Ленивое получение Order executor"""
        if self._executor is None:
            from trading.order_executor import OrderExecutor
            self._executor = OrderExecutor(self.tinkoff_token, self.account_id)
            logger.info("OrderExecutor initialized")
        return self._executor

    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """Проверка HMAC подписи"""
        if not self.webhook_secret or not signature:
            return True  # Если секрет не установлен, пропускаем проверку
            
        expected_signature = hmac.new(
            self.webhook_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        # Убираем префикс sha256= если есть
        if signature.startswith('sha256='):
            signature = signature[7:]
            
        return hmac.compare_digest(expected_signature, signature)

    async def send_telegram_message(self, message: str):
        """Отправка сообщения в Telegram"""
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram credentials not configured")
            return
            
        try:
            async with ClientSession() as session:
                url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
                data = {
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": "HTML"
                }
                async with session.post(url, json=data) as response:
                    if response.status != 200:
                        logger.error(f"Failed to send Telegram message: {response.status}")
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")

    async def process_balance_action(self) -> dict:
        """Обработка запроса баланса"""
        try:
            client = await self.get_client()
            balance = await client.get_balance_async()
            result = f"💰 Баланс: {balance:.2f} RUB"
            await self.send_telegram_message(result)
            return {"status": "success", "result": result}
        except Exception as e:
            error_msg = f"❌ Ошибка получения баланса: {str(e)}"
            logger.error(error_msg)
            await self.send_telegram_message(error_msg)
            return {"status": "error", "message": str(e)}

    async def process_close_all_action(self) -> dict:
        """Обработка закрытия всех позиций"""
        try:
            await self.send_telegram_message("🔄 Начинаю закрытие всех позиций...")
            
            client = await self.get_client()
            executor = await self.get_executor()
            
            positions = await client.get_positions_async()
            closed_count = 0
            
            for pos in positions:
                try:
                    await executor.execute_smart_order(
                        figi=pos.figi,
                        desired_direction=pos.direction,
                        amount=0,
                        close_only=True
                    )
                    closed_count += 1
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"Error closing position {pos.ticker}: {e}")
            
            result = f"✅ Закрыто позиций: {closed_count}"
            await self.send_telegram_message(result)
            return {"status": "success", "result": result}
            
        except Exception as e:
            error_msg = f"❌ Ошибка закрытия позиций: {str(e)}"
            logger.error(error_msg)
            await self.send_telegram_message(error_msg)
            return {"status": "error", "message": str(e)}

    async def process_trade_action(self, action: str, symbol: str, risk_percent: float = None) -> dict:
        """Обработка торговых действий"""
        try:
            # Получаем настройки риска
            from trading.settings_manager import get_settings
            settings = get_settings()
            
            if action == "buy":
                default_risk = settings.risk_long_percent / 100
                direction = "long"
            else:  # sell
                default_risk = settings.risk_short_percent / 100
                direction = "short"
                
            if risk_percent is None:
                risk_percent = default_risk
            else:
                risk_percent = risk_percent / 100 if risk_percent > 1 else risk_percent

            client = await self.get_client()
            executor = await self.get_executor()

            # Получаем FIGI инструмента
            figi = await client.get_figi(symbol.upper())
            if not figi:
                raise ValueError(f"Инструмент {symbol} не найден")

            # Получаем текущие позиции
            positions = await client.get_positions_async()
            
            # Закрываем противоположную позицию если есть
            opposite_pos = next(
                (p for p in positions if p.ticker == symbol.upper() and p.direction != direction),
                None
            )
            
            if opposite_pos:
                await executor.execute_smart_order(
                    figi=figi,
                    desired_direction=opposite_pos.direction,
                    amount=Decimal(opposite_pos.lots),
                    close_only=True
                )
                await asyncio.sleep(1)

            # Получаем баланс для расчета размера позиции
            balance = await client.get_balance_async()
            if balance <= 0:
                raise ValueError("Недостаточно средств")

            # Выполняем основную операцию
            await executor.execute_smart_order(
                figi=figi,
                desired_direction=direction,
                amount=balance * Decimal(str(risk_percent))
            )

            result = f"✅ {action.upper()} {symbol.upper()} выполнен (риск: {risk_percent*100:.1f}%)"
            await self.send_telegram_message(result)
            return {"status": "success", "result": result}

        except Exception as e:
            error_msg = f"❌ Ошибка {action} {symbol}: {str(e)}"
            logger.error(error_msg)
            await self.send_telegram_message(error_msg)
            return {"status": "error", "message": str(e)}

    async def handle_webhook(self, request: Request) -> Response:
        """Основной обработчик webhook"""
        try:
            # Читаем тело запроса
            body = await request.read()
            
            # Проверяем подпись если настроена
            signature = request.headers.get('X-Signature-256', '')
            if not self.verify_signature(body, signature):
                logger.warning("Invalid webhook signature")
                return web.json_response(
                    {"status": "error", "message": "Invalid signature"}, 
                    status=401
                )

            # Парсим JSON
            try:
                data = json.loads(body.decode('utf-8'))
            except json.JSONDecodeError:
                return web.json_response(
                    {"status": "error", "message": "Invalid JSON"}, 
                    status=400
                )

            # Проверяем обязательные поля
            action = data.get("action", "").lower()
            if not action:
                return web.json_response(
                    {"status": "error", "message": "Missing 'action' field"}, 
                    status=400
                )

            logger.info(f"Processing webhook action: {action}")

            # Обрабатываем действие
            if action == "balance":
                result = await self.process_balance_action()
            elif action == "close_all":
                result = await self.process_close_all_action()
            elif action in ["buy", "sell"]:
                symbol = data.get("symbol", "").upper()
                if not symbol:
                    return web.json_response(
                        {"status": "error", "message": "Missing 'symbol' field"}, 
                        status=400
                    )
                risk_percent = data.get("risk_percent")
                result = await self.process_trade_action(action, symbol, risk_percent)
            else:
                return web.json_response(
                    {"status": "error", "message": f"Unknown action: {action}"}, 
                    status=400
                )

            return web.json_response(result)

        except Exception as e:
            logger.error(f"Webhook handler error: {e}", exc_info=True)
            return web.json_response(
                {"status": "error", "message": "Internal server error"}, 
                status=500
            )

    async def handle_health(self, request: Request) -> Response:
        """Health check endpoint"""
        return web.json_response({
            "status": "healthy",
            "service": "trading-webhook-bot"
        })

def create_app() -> web.Application:
    """Создание aiohttp приложения"""
    try:
        server = WebhookServer()
        app = web.Application()
        
        # Добавляем маршруты
        app.router.add_post('/webhook', server.handle_webhook)
        app.router.add_get('/health', server.handle_health)
        
        logger.info("Webhook server initialized successfully")
        return app
    except Exception as e:
        logger.error(f"Failed to initialize webhook server: {e}")
        raise

# Для gunicorn - сразу создаем объект Application
app = create_app()

if __name__ == "__main__":
    # Запуск в development режиме
    port = int(os.getenv("WEBHOOK_PORT", 8080))
    host = os.getenv("WEBHOOK_HOST", "0.0.0.0")
    
    logger.info(f"Starting webhook server on {host}:{port}")
    web.run_app(app, host=host, port=port)