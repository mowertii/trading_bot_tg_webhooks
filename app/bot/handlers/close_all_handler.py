# app/bot/handlers/close_all_handler.py
from telegram import Update
from telegram.ext import ContextTypes
from trading.tinkoff_client import TinkoffClient
from trading.order_executor import OrderExecutor
import os
import logging
import asyncio
from tinkoff.invest import AsyncClient, OrderType, StopOrderType

logger = logging.getLogger(__name__)

class CloseAllError(Exception):
    pass

async def handle_close_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды закрытия всех позиций и снятия всех ордеров"""
    message = update.message or update.channel_post
    if not message:
        return

    try:
        await message.reply_text("🔄 Начинаю закрытие всех позиций и снятие ордеров...")
        
        tinkoff_token = os.getenv("TINKOFF_TOKEN")
        account_id = os.getenv("ACCOUNT_ID")
        
        client = TinkoffClient(tinkoff_token, account_id)
        executor = OrderExecutor(tinkoff_token, account_id)
        
        # Получаем все открытые позиции
        positions = await client.get_positions_async()
        logger.info(f"Найдено позиций для закрытия: {len(positions)}")
        
        # Закрываем все позиции
        closed_count = 0
        for pos in positions:
            try:
                logger.info(f"Закрываем позицию: {pos.ticker} ({pos.direction}) - {pos.lots} лотов")
                await executor.execute_smart_order(
                    figi=pos.figi,
                    desired_direction=pos.direction,
                    amount=0,  # Не используется при close_only=True
                    close_only=True
                )
                closed_count += 1
                await asyncio.sleep(0.5)  # Небольшая пауза между закрытиями
                
            except Exception as e:
                logger.error(f"Ошибка закрытия позиции {pos.ticker}: {str(e)}")
                await message.reply_text(f"⚠️ Ошибка закрытия позиции {pos.ticker}: {str(e)}")
        
        # Снимаем все активные ордера
        async with AsyncClient(tinkoff_token) as api_client:
            # Отменяем все лимитные ордера
            limit_orders = await api_client.orders.get_orders(account_id=account_id)
            limit_cancelled = 0
            
            for order in limit_orders.orders:
                try:
                    await api_client.orders.cancel_order(
                        account_id=account_id, 
                        order_id=order.order_id
                    )
                    limit_cancelled += 1
                    logger.info(f"Отменен лимитный ордер: {order.order_id}")
                    
                except Exception as e:
                    logger.error(f"Ошибка отмены лимитного ордера {order.order_id}: {str(e)}")
            
            # Отменяем все стоп-ордера
            stop_orders = await api_client.stop_orders.get_stop_orders(account_id=account_id)
            stop_cancelled = 0
            
            for stop_order in stop_orders.stop_orders:
                try:
                    await api_client.stop_orders.cancel_stop_order(
                        account_id=account_id, 
                        stop_order_id=stop_order.stop_order_id
                    )
                    stop_cancelled += 1
                    logger.info(f"Отменен стоп-ордер: {stop_order.stop_order_id}")
                    
                except Exception as e:
                    logger.error(f"Ошибка отмены стоп-ордера {stop_order.stop_order_id}: {str(e)}")
        
        # Формируем итоговый отчет
        summary_lines = [
            "✅ Операция завершена!",
            "",
            f"📊 Закрыто позиций: {closed_count}",
            f"🚫 Отменено лимитных ордеров: {limit_cancelled}",
            f"🛑 Отменено стоп-ордеров: {stop_cancelled}"
        ]
        
        # Получаем обновленный баланс
        try:
            final_balance = await client.get_balance_async()
            summary_lines.append(f"💰 Итоговый баланс: {final_balance:.2f} RUB")
        except Exception as e:
            logger.error(f"Ошибка получения итогового баланса: {str(e)}")
            summary_lines.append("💰 Баланс: ошибка получения")
        
        await message.reply_text("\n".join(summary_lines))
        logger.info(f"Close all completed: positions={closed_count}, limits={limit_cancelled}, stops={stop_cancelled}")
        
    except Exception as e:
        logger.error(f"Общая ошибка в handle_close_all: {str(e)}", exc_info=True)
        await message.reply_text(f"❌ Критическая ошибка: {str(e)}")