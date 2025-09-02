# app/webhook_server.py - ИСПРАВЛЕННАЯ ВЕРСИЯ с поддержкой quantity
import os
import json
import hmac
import hashlib
import logging
from aiohttp import web, web_request
from decimal import Decimal, ROUND_DOWN
import asyncio
from typing import Optional

from trading.tinkoff_client import TinkoffClient
from trading.order_executor import OrderExecutor
from trading.settings_manager import get_settings
from utils.telegram_notifications import send_telegram_message

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

tinkoff_token = os.getenv("TINKOFF_TOKEN")
account_id = os.getenv("ACCOUNT_ID")
bot_token = os.getenv("BOT_TOKEN")
chat_id = os.getenv("TG_CHAT_ID")
webhook_secret = os.getenv("WEBHOOK_SECRET", "")

try:
    leverage = Decimal(os.getenv("LEVERAGE", "1"))
    if leverage <= 0:
        leverage = Decimal("1")
except Exception:
    leverage = Decimal("1")


class WebhookError(Exception):
    pass


def verify_signature(payload: bytes, signature: str) -> bool:
    if not webhook_secret or not signature:
        return True
    if signature.startswith("sha256="):
        signature = signature[7:]
    expected_signature = hmac.new(webhook_secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected_signature, signature)


async def send_notification(message: str):
    if not bot_token or not chat_id:
        logger.warning("Telegram credentials not configured")
        return
    try:
        await send_telegram_message(bot_token, chat_id, message)
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления: {e}")


def _fmt_pct(x: Decimal) -> str:
    return f"{x.quantize(Decimal('0.1'))}%"


def _fmt_money(x: Decimal) -> str:
    return f"{x.quantize(Decimal('0.01'), rounding=ROUND_DOWN)} RUB"


async def process_trade_webhook(action: str, symbol: str, risk_percent: float | None = None, quantity: int | None = None):
    try:
        client = TinkoffClient(tinkoff_token, account_id)
        executor = OrderExecutor(tinkoff_token, account_id)
        
        # Настройки риска
        settings = get_settings()
        if risk_percent is None:
            if action == "buy":
                risk_percent = settings.risk_long_percent / 100.0
            else:
                risk_percent = settings.risk_short_percent / 100.0

        risk_d = Decimal(str(risk_percent or 0))
        
        # Формируем сообщение в зависимости от режима торговли
        if quantity is not None:
            await send_notification(
                f"✅ {action.upper()} {symbol}: {quantity} лот(ов), плечо {leverage}"
            )
        else:
            await send_notification(
                f"✅ {action.upper()} {symbol}: риск {_fmt_pct(risk_d * 100)}, плечо {leverage}"
            )

        figi = await client.get_figi(symbol)
        if not figi:
            raise WebhookError(f"Инструмент {symbol} не найден")

        positions = await client.get_positions_async()

        if action == "buy":
            result = await _execute_buy_operation(client, executor, figi, symbol, positions, risk_d, quantity)
        elif action == "sell":
            result = await _execute_sell_operation(client, executor, figi, symbol, positions, risk_d, quantity)
        else:
            raise WebhookError(f"Неподдерживаемое действие: {action}")

        if result.get("success"):
            await send_notification(f"✅ {action.upper()} {symbol} выполнен\n📊 {result.get('details')}")
        else:
            await send_notification(f"❌ Ошибка {action.upper()} {symbol}: {result.get('error')}")
        return result

    except Exception as e:
        msg = f"❌ Критическая ошибка {action.upper()} {symbol}: {str(e)}"
        await send_notification(msg)
        logger.error(f"Trade processing error: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def _amount_with_leverage(client: TinkoffClient, figi: str, risk_d: Decimal) -> tuple[Decimal, Decimal]:
    balance = await client.get_balance_async()
    bal_d = Decimal(str(balance))
    amount = (bal_d * risk_d * leverage).quantize(Decimal("0.01"), rounding=ROUND_DOWN)

    # Оценка цены лота (фоллбэк на last_price)
    from tinkoff.invest import AsyncClient
    price_per_lot = Decimal("0")
    try:
        async with AsyncClient(client.token) as api:
            ob = await api.market_data.get_order_book(figi=figi, depth=1)
            current_price: Optional[Decimal] = None
            try:
                if ob.bids and ob.asks:
                    bid0 = ob.bids[0]
                    ask0 = ob.asks[0]
                    if getattr(bid0, "price", None) and getattr(ask0, "price", None):
                        best_bid = Decimal(str(bid0.price.units)) + Decimal(str(bid0.price.nano)) / Decimal("1e9")
                        best_ask = Decimal(str(ask0.price.units)) + Decimal(str(ask0.price.nano)) / Decimal("1e9")
                        current_price = (best_bid + best_ask) / 2
            except Exception:
                current_price = None
            if current_price is None and getattr(ob, "last_price", None):
                lp = ob.last_price
                current_price = Decimal(str(lp.units)) + Decimal(str(lp.nano)) / Decimal("1e9")
            if current_price and current_price > 0:
                lot = 1
                # Попробуем взять lot из инструмента для точности
                try:
                    instr = await api.instruments.get_instrument_by(id_type=1, id=figi)
                    lot = int(instr.instrument.lot or 1)
                except Exception:
                    lot = 1
                price_per_lot = (current_price * Decimal(lot)).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    except Exception:
        price_per_lot = Decimal("0")

    return amount, price_per_lot


async def _execute_buy_operation(client, executor, figi, symbol, positions, risk_d: Decimal, quantity: int | None = None):
    try:
        short_position = next((p for p in positions if p.ticker == symbol and p.direction == "short"), None)
        if short_position:
            logger.info(f"Closing short position for {symbol}: {short_position.lots} lots")
            close_result = await executor.execute_smart_order(figi=figi, desired_direction="short", amount=Decimal(0), close_only=True)
            if not close_result.success:
                return {"success": False, "error": f"Не удалось закрыть короткую позицию: {close_result.message}"}
            await asyncio.sleep(1)

        # Если quantity указан, используем его; иначе вычисляем по риску
        if quantity is not None:
            # При фиксированном количестве лотов расчитываем приблизительную сумму для логирования
            _, price_per_lot = await _amount_with_leverage(client, figi, risk_d)
            amount = Decimal(quantity) * price_per_lot
            buy_result = await executor.execute_smart_order(figi=figi, desired_direction="long", amount=amount, lots_override=quantity)
        else:
            amount, price_per_lot = await _amount_with_leverage(client, figi, risk_d)
            if amount <= 0:
                return {"success": False, "error": "Недостаточно средств"}
            if price_per_lot > 0 and amount < price_per_lot:
                return {
                    "success": False,
                    "error": f"Сумма позиции {_fmt_money(amount)} меньше цены 1 лота ≈ {_fmt_money(price_per_lot)}"
                }
            buy_result = await executor.execute_smart_order(figi=figi, desired_direction="long", amount=amount)

        if buy_result.success:
            return {"success": True, "details": f"Сумма: {_fmt_money(amount)}; {buy_result.message}"}
        return {"success": False, "error": buy_result.message}
    except Exception as e:
        logger.error(f"Buy operation error: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def _execute_sell_operation(client, executor, figi, symbol, positions, risk_d: Decimal, quantity: int | None = None):
    try:
        long_position = next((p for p in positions if p.ticker == symbol and p.direction == "long"), None)
        if long_position:
            logger.info(f"Closing long position for {symbol}: {long_position.lots} lots")
            close_result = await executor.execute_smart_order(figi=figi, desired_direction="long", amount=Decimal(0), close_only=True)
            if not close_result.success:
                return {"success": False, "error": f"Не удалось закрыть длинную позицию: {close_result.message}"}
            await asyncio.sleep(1)

        # Поддержка явного количества
        if quantity is not None:
            # При фиксированном количестве лотов расчитываем приблизительную сумму для логирования
            _, price_per_lot = await _amount_with_leverage(client, figi, risk_d)
            amount = Decimal(quantity) * price_per_lot
            sell_result = await executor.execute_smart_order(figi=figi, desired_direction="short", amount=amount, lots_override=quantity)
        else:
            amount, price_per_lot = await _amount_with_leverage(client, figi, risk_d)
            if amount <= 0:
                return {"success": False, "error": "Недостаточно средств"}
            if price_per_lot > 0 and amount < price_per_lot:
                return {
                    "success": False,
                    "error": f"Сумма позиции {_fmt_money(amount)} меньше цены 1 лота ≈ {_fmt_money(price_per_lot)}"
                }
            sell_result = await executor.execute_smart_order(figi=figi, desired_direction="short", amount=amount)

        if sell_result.success:
            return {"success": True, "details": f"Сумма: {_fmt_money(amount)}; {sell_result.message}"}
        return {"success": False, "error": sell_result.message}
    except Exception as e:
        logger.error(f"Sell operation error: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def handle_webhook(request: web_request.Request):
    try:
        body = await request.read()
        signature = request.headers.get("X-Signature-256", "")
        if not verify_signature(body, signature):
            logger.warning("Invalid webhook signature")
            return web.json_response({"status": "error", "message": "Invalid signature"}, status=401)

        try:
            data = json.loads(body.decode())
        except json.JSONDecodeError:
            return web.json_response({"status": "error", "message": "Invalid JSON"}, status=400)

        action = (data.get("action") or "").lower()
        if not action:
            return web.json_response({"status": "error", "message": "Missing action field"}, status=400)

        if action in ["buy", "sell"]:
            symbol = (data.get("symbol") or "").upper()
            if not symbol:
                return web.json_response({"status": "error", "message": "Missing symbol field"}, status=400)
            
            risk_percent = data.get("risk_percent")
            quantity = data.get("quantity")  # Новый параметр
            
            result = await process_trade_webhook(action, symbol, risk_percent, quantity)
            if result.get("success"):
                return web.json_response({"status": "success", "result": f"✅ {action.upper()} {symbol} выполнен успешно"})
            return web.json_response({"status": "error", "message": result.get("error")}, status=500)

        if action == "balance":
            result = await handle_balance_request()
            return web.json_response({"status": "success", "balance": result})

        if action == "close_all":
            result = await handle_close_all_request()
            if result.get("success"):
                return web.json_response({"status": "success", "result": result.get("message")})
            return web.json_response({"status": "error", "message": result.get("error")}, status=500)

        return web.json_response({"status": "error", "message": f"Unknown action: {action}"}, status=400)

    except Exception as e:
        logger.error(f"Webhook handler error: {e}", exc_info=True)
        return web.json_response({"status": "error", "message": "Internal server error"}, status=500)


async def handle_balance_request():
    try:
        client = TinkoffClient(tinkoff_token, account_id)
        balance = await client.get_balance_async()
        await send_notification(f"💰 Баланс: {Decimal(str(balance)).quantize(Decimal('0.01'))} RUB")
        return balance
    except Exception as e:
        logger.error(f"Balance request error: {e}", exc_info=True)
        await send_notification(f"❌ Ошибка получения баланса: {str(e)}")
        return 0


async def handle_close_all_request():
    try:
        client = TinkoffClient(tinkoff_token, account_id)
        executor = OrderExecutor(tinkoff_token, account_id)

        await send_notification("🔄 Начинаю закрытие всех позиций...")

        positions = await client.get_positions_async()

        closed_count = 0
        for position in positions:
            try:
                result = await executor.execute_smart_order(
                    figi=position.figi, desired_direction=position.direction, amount=Decimal(0), close_only=True
                )
                if result.success:
                    closed_count += 1
                    logger.info(f"Closed position: {position.ticker}")
                else:
                    logger.error(f"Failed to close {position.ticker}: {result.message}")
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"Error closing position {position.ticker}: {e}")

        cancelled = await executor.cancel_all_orders()

        message = (f"✅ Закрытие позиций завершено!\n"
                   f"📊 Закрыто позиций: {closed_count}\n"
                   f"🚫 Отменено лимитных ордеров: {cancelled['limit_orders']}\n"
                   f"🛑 Отменено стоп-ордеров: {cancelled['stop_orders']}")
        await send_notification(message)
        return {"success": True, "message": message}

    except Exception as e:
        error_msg = f"❌ Ошибка закрытия позиций: {str(e)}"
        await send_notification(error_msg)
        logger.error(f"Close all error: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def handle_health(request):
    return web.json_response({"status": "healthy", "service": "trading-webhook-bot"})


def create_app():
    app = web.Application()
    app.router.add_post("/webhook", handle_webhook)
    app.router.add_get("/health", handle_health)
    return app


if __name__ == "__main__":
    required_vars = ["TINKOFF_TOKEN", "ACCOUNT_ID", "BOT_TOKEN", "TG_CHAT_ID"]
    missing = [v for v in required_vars if not os.getenv(v)]
    if missing:
        logger.error(f"Missing required environment variables: {missing}")
        exit(1)
    app = create_app()
    host = os.getenv("WEBHOOK_HOST", "0.0.0.0")
    port = int(os.getenv("WEBHOOK_PORT", 8080))
    logger.info(f"Starting webhook server on {host}:{port}")
    web.run_app(app, host=host, port=port)

app = create_app()