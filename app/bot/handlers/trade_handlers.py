# app/bot/handlers/trade_handlers.py
from telegram import Update
from telegram.ext import ContextTypes
import os
import logging
import asyncio
from decimal import Decimal
from trading.tinkoff_client import TinkoffClient, Position 
from trading.order_executor import OrderExecutor

logger = logging.getLogger(__name__)

class TradeError(Exception):
    pass

async def _process_trade_command(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str):
    try:
        message = update.message or update.channel_post
        if not message or not message.text:
            return

        instrument = message.text.split()[1].upper()
        logger.info(f"Processing {action.upper()} command for {instrument}")

        tinkoff_token = os.getenv("TINKOFF_TOKEN")
        account_id = os.getenv("ACCOUNT_ID")
        
        client = TinkoffClient(tinkoff_token, account_id)
        executor = OrderExecutor(tinkoff_token, account_id)

        figi = await client.get_figi(instrument)
        if not figi:
            raise TradeError(f"Инструмент {instrument} не найден")

        positions = await client.get_positions_async()
        
        # Обработка buy/sell через единый метод execute_smart_order
        if action == 'buy':
            await _handle_trade_logic(
                client=client,
                executor=executor,
                figi=figi,
                instrument=instrument,
                positions=positions,
                direction='long',
                risk_percent=Decimal('0.4')  # 40% от баланса для лонга
            )
        elif action == 'sell':
            await _handle_trade_logic(
                client=client,
                executor=executor,
                figi=figi,
                instrument=instrument,
                positions=positions,
                direction='short',
                risk_percent=Decimal('0.3')  # 30% от баланса для шорта
            )

        await message.reply_text(f"✅ Операция {action.upper()} для {instrument} выполнена")

    except TradeError as e:
        await message.reply_text(f"⚠️ {str(e)}")
    except Exception as e:
        logger.error(f"Ошибка: {str(e)}", exc_info=True)
        await message.reply_text("❌ Ошибка выполнения операции")

async def _handle_trade_logic(
    client: TinkoffClient,
    executor: OrderExecutor,
    figi: str,
    instrument: str,
    positions: list[Position],
    direction: str,
    risk_percent: Decimal
):
    """Обновленная логика с учетом изменений в API"""
    try:
        # Проверяем противоположную позицию
        opposite_pos = next(
            (p for p in positions 
             if p.ticker == instrument 
             and p.direction != direction),
            None
        )
        
        # Закрываем противоположную позицию если есть
        if opposite_pos:
            logger.info(f"Closing {opposite_pos.direction} position: {opposite_pos.lots} lots")
            await executor.execute_smart_order(
                figi=figi,
                desired_direction=opposite_pos.direction,
                amount=Decimal(opposite_pos.lots),
                close_only=True
            )
            await asyncio.sleep(1)

        # Получаем обновленный баланс
        balance = await client.get_balance_async()
        if balance <= 0:
            raise TradeError("Недостаточно средств")

        # Выполняем основную операцию
        await executor.execute_smart_order(
            figi=figi,
            desired_direction=direction,
            amount=balance * risk_percent
        )

    except Exception as e:
        logger.error(f"Trade error ({direction}): {str(e)}", exc_info=True)
        raise TradeError(f"Ошибка {direction} операции: {str(e)}")

async def handle_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _process_trade_command(update, context, 'buy')

async def handle_sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _process_trade_command(update, context, 'sell')