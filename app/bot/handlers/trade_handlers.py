# app/bot/handlers/trade_handlers.py - ИСПРАВЛЕННАЯ ВЕРСИЯ
from telegram import Update
from telegram.ext import ContextTypes
import os
import logging
import asyncio
from decimal import Decimal
from trading.tinkoff_client import TinkoffClient, Position 
from trading.order_executor import OrderExecutor
from trading.settings_manager import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class TradeError(Exception):
    pass

async def _process_trade_command(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str):
    """Обрабатываем команды покупки/продажи с корректными уведомлениями"""
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
            await message.reply_text(f"❌ Инструмент {instrument} не найден")
            return

        # Отправляем уведомление о начале операции
        await message.reply_text(f"🔄 Начинаю выполнение {action.upper()} для {instrument}...")

        positions = await client.get_positions_async()
        
        # Выполняем торговую логику и получаем детальный результат
        if action == 'buy':
            risk_percent = Decimal(settings.risk_long_percent) / Decimal(100)
            result = await _handle_trade_logic(
                client=client,
                executor=executor,
                figi=figi,
                instrument=instrument,
                positions=positions,
                direction='long',
                risk_percent=risk_percent  # 40% от баланса для лонга
            )
        elif action == 'sell':
            result = await _handle_trade_logic(
                client=client,
                executor=executor,
                figi=figi,
                instrument=instrument,
                positions=positions,
                direction='short',
                risk_percent=Decimal('0.3')  # 30% от баланса для шорта
            )
        else:
            await message.reply_text(f"❌ Неподдерживаемое действие: {action}")
            return

        # Отправляем результат операции
        if result['success']:
            await message.reply_text(
                f"✅ Операция {action.upper()} для {instrument} выполнена успешно!\n"
                f"📊 Детали: {result['details']}"
            )
        else:
            await message.reply_text(
                f"❌ Ошибка выполнения {action.upper()} для {instrument}:\n"
                f"🔍 Причина: {result['error']}"
            )

    except TradeError as e:
        await message.reply_text(f"⚠️ {str(e)}")
    except Exception as e:
        logger.error(f"Ошибка в _process_trade_command: {str(e)}", exc_info=True)
        await message.reply_text(f"❌ Критическая ошибка выполнения операции: {str(e)}")

async def _handle_trade_logic(
    client: TinkoffClient,
    executor: OrderExecutor,
    figi: str,
    instrument: str,
    positions: list[Position],
    direction: str,
    risk_percent: Decimal
) -> dict:
    """
    Обновленная логика с возвращением детального результата
    Возвращает: {'success': bool, 'details': str, 'error': str}
    """
    try:
        # Проверяем противоположную позицию
        opposite_direction = 'short' if direction == 'long' else 'long'
        opposite_pos = next(
            (p for p in positions 
             if p.ticker == instrument 
             and p.direction == opposite_direction),
            None
        )
        
        result_details = []
        
        # Закрываем противоположную позицию если есть
        if opposite_pos:
            logger.info(f"Closing {opposite_pos.direction} position: {opposite_pos.lots} lots")
            close_result = await executor.execute_smart_order(
                figi=figi,
                desired_direction=opposite_pos.direction,
                amount=Decimal(opposite_pos.lots),
                close_only=True
            )
            
            if close_result.success:
                result_details.append(f"Закрыта {opposite_pos.direction} позиция: {opposite_pos.lots} лотов")
            else:
                return {
                    'success': False, 
                    'error': f"Не удалось закрыть {opposite_pos.direction} позицию: {close_result.message}",
                    'details': ""
                }
            
            await asyncio.sleep(1)  # Пауза между операциями

        # Получаем обновленный баланс
        balance = await client.get_balance_async()
        if balance <= 0:
            return {
                'success': False,
                'error': "Недостаточно средств на счете",
                'details': f"Текущий баланс: {balance:.2f} RUB"
            }

        # Рассчитываем сумму операции
        operation_amount = balance * risk_percent
        result_details.append(f"Баланс: {balance:.2f} RUB, риск: {risk_percent*100:.1f}%")
        result_details.append(f"Сумма операции: {operation_amount:.2f} RUB")

        # Выполняем основную операцию
        main_result = await executor.execute_smart_order(
            figi=figi,
            desired_direction=direction,
            amount=operation_amount
        )
        
        if main_result.success:
            result_details.append(f"Статус: {main_result.message}")
            return {
                'success': True,
                'details': "\n".join(result_details),
                'error': ""
            }
        else:
            return {
                'success': False,
                'error': main_result.message,
                'details': "\n".join(result_details)
            }

    except Exception as e:
        logger.error(f"Trade error ({direction}): {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': f"Системная ошибка {direction} операции: {str(e)}",
            'details': ""
        }

async def handle_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды покупки"""
    await _process_trade_command(update, context, 'buy')

async def handle_sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды продажи"""
    await _process_trade_command(update, context, 'sell')