import logging
import asyncio
from tinkoff.invest import AsyncClient
from .order_executor import OrderExecutor

logger = logging.getLogger(__name__)


class OrderWatcher:
    def __init__(self, token: str, account_id: str, executor: OrderExecutor, tg_bot=None, chat_id=None):
        self.token = token
        self.account_id = account_id
        self.executor = executor
        self.tg_bot = tg_bot
        self.chat_id = chat_id

    async def watch_trades(self):
        """
        Отслеживает исполненные сделки через периодические проверки.
        Fallback-версия если stream API недоступен.
        """
        logger.info("OrderWatcher запущен в режиме polling...")
        
        # Словарь для хранения последних известных позиций
        last_positions = {}
        
        while True:
            try:
                async with AsyncClient(self.token) as client:
                    # Получаем текущие позиции
                    positions = await client.operations.get_positions(account_id=self.account_id)
                    
                    current_positions = {}
                    for fut in positions.futures:
                        figi = fut.figi
                        # Определяем текущий размер позиции
                        if hasattr(fut, 'balance'):
                            signed_qty = int(getattr(fut, 'balance', 0) or 0)
                        else:
                            signed_qty = int(getattr(fut, 'quantity', 0) or 0)
                        
                        current_positions[figi] = signed_qty
                    
                    # Сравниваем с предыдущим состоянием
                    for figi, prev_qty in last_positions.items():
                        current_qty = current_positions.get(figi, 0)
                        
                        # Если позиция была открыта и теперь закрыта
                        if prev_qty != 0 and current_qty == 0:
                            # Отменяем все ордера по этому инструменту
                            await self.executor._cancel_all_stop_orders(client, figi)
                            await self.executor._cancel_all_limit_orders(client, figi)
                            
                            msg = f"ℹ️ Позиция по {figi} закрыта. Все стопы и лимиты сняты."
                            logger.info(msg)
                            
                            if self.tg_bot and self.chat_id:
                                try:
                                    await self.tg_bot.send_message(chat_id=self.chat_id, text=msg)
                                except Exception as e:
                                    logger.error(f"Ошибка при отправке уведомления: {e}")
                    
                    # Обновляем состояние
                    last_positions = current_positions
                    
            except Exception as e:
                logger.error(f"Ошибка в OrderWatcher polling: {e}", exc_info=True)
            
            # Ждем 5 секунд до следующей проверки
            await asyncio.sleep(5)
