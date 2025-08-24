# app/webhook_server.py
import asyncio
import logging
from aiohttp import web, ClientSession
from trading.tinkoff_client import TinkoffClient
from trading.order_executor import OrderExecutor
import os
import json
from decimal import Decimal
from typing import Dict, Any
import hashlib
import hmac

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebhookServer:
    def __init__(self):
        self.tinkoff_token = os.getenv("TINKOFF_TOKEN")
        self.account_id = os.getenv("ACCOUNT_ID")
        self.bot_token = os.getenv("BOT_TOKEN")
        self.target_user_id = os.getenv("TARGET_USER_ID")
        self.webhook_secret = os.getenv("WEBHOOK_SECRET", "default_secret_change_me")
        
        # Инициализируем торговые компоненты
        self.client = TinkoffClient(self.tinkoff_token, self.account_id)
        self.executor = OrderExecutor(self.tinkoff_token, self.account_id)
        
        # HTTP клиент для отправки уведомлений в Telegram
        self.session = None
    
    async def start_session(self):
        """Создаем HTTP сессию для Telegram API"""
        self.session = ClientSession()
    
    async def close_session(self):
        """Закрываем HTTP сессию"""
        if self.session:
            await self.session.close()
    
    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """Проверяем подпись вебхука для безопасности"""
        if not signature:
            return False
        
        expected_signature = hmac.new(
            self.webhook_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(f"sha256={expected_signature}", signature)
    
    async def send_telegram_message(self, text: str):
        """Отправляем сообщение в Telegram"""
        if not self.session or not self.target_user_id:
            return
        
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        data = {
            "chat_id": self.target_user_id,
            "text": text
        }
        
        try:
            async with self.session.post(url, json=data) as resp:
                if resp.status != 200:
                    logger.error(f"Failed to send Telegram message: {resp.status}")
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
    
    async def handle_webhook(self, request):
        """Основной обработчик вебхуков"""
        try:
            # Проверяем Content-Type
            if request.content_type != 'application/json':
                return web.Response(status=400, text="Content-Type must be application/json")
            
            # Читаем тело запроса
            payload = await request.read()
            
            # Проверяем подпись (опционально)
            signature = request.headers.get('X-Signature-256')
            if signature and not self.verify_signature(payload, signature):
                logger.warning("Invalid webhook signature")
                return web.Response(status=401, text="Invalid signature")
            
            # Парсим JSON
            try:
                data = json.loads(payload.decode('utf-8'))
            except json.JSONDecodeError:
                return web.Response(status=400, text="Invalid JSON")
            
            # Обрабатываем торговый сигнал
            result = await self.process_trading_signal(data)
            
            return web.json_response({"status": "success", "result": result})
            
        except Exception as e:
            logger.error(f"Webhook error: {str(e)}", exc_info=True)
            await self.send_telegram_message(f"❌ Ошибка обработки вебхука: {str(e)}")
            return web.Response(status=500, text="Internal server error")
    
    async def process_trading_signal(self, data: Dict[str, Any]) -> str:
        """Обрабатываем торговый сигнал из вебхука"""
        
        # Валидируем обязательные поля
        required_fields = ['action', 'symbol']
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
        
        action = data['action'].lower()  # buy, sell, close_all
        symbol = data['symbol'].upper()  # SBER, GAZP и т.д.
        
        logger.info(f"Processing trading signal: {action} {symbol}")
        
        # Обработка разных типов сигналов
        if action == 'close_all':
            return await self.handle_close_all_signal()
        elif action in ['buy', 'sell']:
            return await self.handle_trade_signal(action, symbol, data)
        elif action == 'balance':
            return await self.handle_balance_signal()
        else:
            raise ValueError(f"Unknown action: {action}")
    
    async def handle_trade_signal(self, action: str, symbol: str, data: Dict[str, Any]) -> str:
        """Обрабатываем сигналы BUY/SELL"""
        
        # Получаем FIGI инструмента
        figi = await self.client.get_figi(symbol)
        if not figi:
            raise ValueError(f"Инструмент {symbol} не найден")
        
        # Получаем текущие позиции
        positions = await self.client.get_positions_async()
        
        # Определяем направление и риск
        direction = 'long' if action == 'buy' else 'short'
        risk_percent = Decimal(str(data.get('risk_percent', 0.4 if action == 'buy' else 0.3)))
        
        # Проверяем противоположные позиции
        opposite_pos = next(
            (p for p in positions if p.ticker == symbol and p.direction != direction),
            None
        )
        
        # Закрываем противоположную позицию если есть
        if opposite_pos:
            logger.info(f"Closing opposite {opposite_pos.direction} position: {opposite_pos.lots} lots")
            await self.executor.execute_smart_order(
                figi=figi,
                desired_direction=opposite_pos.direction,
                amount=Decimal(opposite_pos.lots),
                close_only=True
            )
            await asyncio.sleep(1)
        
        # Получаем баланс
        balance = await self.client.get_balance_async()
        if balance <= 0:
            raise ValueError("Недостаточно средств")
        
        # Выполняем операцию
        await self.executor.execute_smart_order(
            figi=figi,
            desired_direction=direction,
            amount=balance * risk_percent
        )
        
        message = f"✅ {action.upper()} {symbol} выполнен (риск: {risk_percent*100}%)"
        await self.send_telegram_message(message)
        
        return message
    
    async def handle_close_all_signal(self) -> str:
        """Обрабатываем сигнал закрытия всех позиций"""
        
        positions = await self.client.get_positions_async()
        closed_count = 0
        
        for pos in positions:
            try:
                await self.executor.execute_smart_order(
                    figi=pos.figi,
                    desired_direction=pos.direction,
                    amount=0,
                    close_only=True
                )
                closed_count += 1
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"Error closing position {pos.ticker}: {e}")
        
        message = f"🔒 Закрыто позиций: {closed_count}"
        await self.send_telegram_message(message)
        
        return message
    
    async def handle_balance_signal(self) -> str:
        """Обрабатываем запрос баланса"""
        balance = await self.client.get_balance_async()
        message = f"💰 Текущий баланс: {balance:.2f} RUB"
        await self.send_telegram_message(message)
        return message
    
    async def handle_health_check(self, request):
        """Health check endpoint"""
        return web.json_response({
            "status": "healthy",
            "service": "trading-webhook-bot"
        })

def create_app():
    """Создаем aiohttp приложение"""
    webhook_server = WebhookServer()
    
    app = web.Application()
    
    # Добавляем middleware для логирования
    async def logging_middleware(request, handler):
        start_time = asyncio.get_event_loop().time()
        response = await handler(request)
        process_time = asyncio.get_event_loop().time() - start_time
        logger.info(f"{request.method} {request.path} - {response.status} - {process_time:.3f}s")
        return response
    
    app.middlewares.append(logging_middleware)
    
    # Маршруты
    app.router.add_post('/webhook', webhook_server.handle_webhook)
    app.router.add_get('/health', webhook_server.handle_health_check)
    
    # Сохраняем ссылку на webhook_server в app для cleanup
    app['webhook_server'] = webhook_server
    
    return app

async def init_app():
    """Инициализируем приложение"""
    app = create_app()
    webhook_server = app['webhook_server']
    await webhook_server.start_session()
    return app

async def cleanup_app(app):
    """Очищаем ресурсы при завершении"""
    webhook_server = app['webhook_server']
    await webhook_server.close_session()

if __name__ == '__main__':
    # Запуск для разработки
    app = create_app()
    web.run_app(app, host='0.0.0.0', port=8080)