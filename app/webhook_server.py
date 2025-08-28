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
        self.chat_id = os.getenv("TG_CHAT_ID")
        self.webhook_secret = os.getenv("WEBHOOK_SECRET", "default_secret_change_me")
        
        self.client = TinkoffClient(self.tinkoff_token, self.account_id)
        self.executor = OrderExecutor(self.tinkoff_token, self.account_id)
        self.session: ClientSession | None = None
    
    async def start_session(self):
        self.session = ClientSession()
    
    async def close_session(self):
        if self.session:
            await self.session.close()
    
    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """Проверка HMAC подписи в заголовке"""
        if not signature:
            return False
        expected_signature = hmac.new(
            self.webhook_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(f"sha256={expected_signature}", signature)
    
    async def send_telegram_message(self, text: str):
        if not self.session or not self.chat_id:
            return
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        data = {"chat_id": self.chat_id, "text": text}
        try:
            async with self.session.post(url, json=data) as resp:
                if resp.status != 200:
                    logger.error(f"Failed to send Telegram message: {resp.status}")
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
    
    async def handle_webhook(self, request):
        try:
            if request.content_type != 'application/json':
                return web.Response(status=400, text="Content-Type must be application/json")
            
            payload = await request.read()

            # --- Проверка безопасности ---
            signature = request.headers.get("X-Signature-256")
            token = request.query.get("token")

            if signature:
                if not self.verify_signature(payload, signature):
                    logger.warning("Invalid HMAC signature")
                    return web.Response(status=401, text="Invalid signature")
            elif token:
                if token != self.webhook_secret:
                    logger.warning("Invalid query token")
                    return web.Response(status=401, text="Invalid token")
            else:
                logger.warning("No authentication provided")
                return web.Response(status=401, text="Missing authentication")
            # ------------------------------

            try:
                data = json.loads(payload.decode("utf-8"))
            except json.JSONDecodeError:
                return web.Response(status=400, text="Invalid JSON")
            
            result = await self.process_trading_signal(data)
            return web.json_response({"status": "success", "result": result})
            
        except Exception as e:
            logger.error(f"Webhook error: {str(e)}", exc_info=True)
            await self.send_telegram_message(f"❌ Ошибка обработки вебхука: {str(e)}")
            return web.Response(status=500, text="Internal server error")
    
    async def process_trading_signal(self, data: Dict[str, Any]) -> str:
        if "action" not in data:
            raise ValueError("Missing required field: action")
        action = data["action"].lower()

        if action in ("buy", "sell"):
            if "symbol" not in data:
                raise ValueError("Missing required field: symbol")
            symbol = data["symbol"].upper()
        else:
            symbol = data.get("symbol")

        logger.info(f"Processing trading signal: {action} {symbol or ''}".strip())
        
        if action == "close_all":
            return await self.handle_close_all_signal()
        elif action in ("buy", "sell"):
            return await self.handle_trade_signal(action, symbol, data)
        elif action == "balance":
            return await self.handle_balance_signal()
        else:
            raise ValueError(f"Unknown action: {action}")
    
    async def handle_trade_signal(self, action: str, symbol: str, data: Dict[str, Any]) -> str:
        figi = await self.client.get_figi(symbol)
        if not figi:
            raise ValueError(f"Инструмент {symbol} не найден")
        
        positions = await self.client.get_positions_async()
        direction = "long" if action == "buy" else "short"
        risk_percent = Decimal(str(data.get("risk_percent", 0.4 if action == "buy" else 0.3)))
        
        opposite_pos = next((p for p in positions if p.ticker == symbol and p.direction != direction), None)
        if opposite_pos:
            logger.info(f"Closing opposite {opposite_pos.direction} position: {opposite_pos.lots} lots")
            await self.executor.execute_smart_order(
                figi=figi,
                desired_direction=opposite_pos.direction,
                amount=Decimal(opposite_pos.lots),
                close_only=True
            )
            await asyncio.sleep(1)
        
        balance = await self.client.get_balance_async()
        if balance <= 0:
            raise ValueError("Недостаточно средств")
        
        await self.executor.execute_smart_order(
            figi=figi,
            desired_direction=direction,
            amount=balance * risk_percent
        )
        
        message = f"✅ {action.upper()} {symbol} выполнен (риск: {risk_percent*100}%)"
        await self.send_telegram_message(message)
        return message
    
    async def handle_close_all_signal(self) -> str:
        positions = await self.client.get_positions_async()
        closed_count = 0
        for pos in positions:
            try:
                opposite_direction = "short" if pos.direction == "long" else "long"
                await self.executor.execute_smart_order(
                    figi=pos.figi,
                    desired_direction=opposite_direction,
                    amount=Decimal(pos.lots),
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
        balance = await self.client.get_balance_async()
        message = f"💰 Текущий баланс: {balance:.2f} RUB"
        await self.send_telegram_message(message)
        return message
    
    async def handle_health_check(self, request):
        return web.json_response({
            "status": "healthy",
            "service": "trading-webhook-bot"
        })

def create_app():
    webhook_server = WebhookServer()
    app = web.Application()

    @web.middleware
    async def logging_middleware(request, handler):
        start_time = asyncio.get_event_loop().time()
        response = None
        try:
            response = await handler(request)
            return response
        finally:
            process_time = asyncio.get_event_loop().time() - start_time
            status = getattr(response, "status", 500)
            logger.info(f"{request.method} {request.path} - {status} - {process_time:.3f}s")

    app.middlewares.append(logging_middleware)

    app.router.add_post("/webhook", webhook_server.handle_webhook)
    app.router.add_get("/health", webhook_server.handle_health_check)

    app["webhook_server"] = webhook_server
    return app

async def init_app():
    app = create_app()
    webhook_server = app["webhook_server"]
    await webhook_server.start_session()
    return app

async def cleanup_app(app):
    webhook_server = app["webhook_server"]
    await webhook_server.close_session()

if __name__ == "__main__":
    app = create_app()
    web.run_app(app, host="0.0.0.0", port=8080)
