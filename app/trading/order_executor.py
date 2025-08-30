# app/trading/order_executor.py
import asyncio
import logging
from decimal import Decimal
from typing import Optional, List
from dataclasses import dataclass

from tinkoff.invest import (
    AsyncClient, 
    OrderDirection, 
    OrderType, 
    MoneyValue,
    Quotation,
    StopOrderDirection,
    StopOrderExpirationType,
    StopOrderType
)

from trading.tinkoff_client import TinkoffClient, Position
from trading.settings_manager import get_settings

logger = logging.getLogger(__name__)

@dataclass
class OrderResult:
    """Результат выставления ордера"""
    order_id: str
    success: bool
    message: str
    price: Optional[Decimal] = None
    quantity: Optional[int] = None

class OrderExecutor:
    def __init__(self, token: str, account_id: str):
        self.token = token
        self.account_id = account_id
        self.client = TinkoffClient(token, account_id)

    def _money_value_to_decimal(self, money: MoneyValue) -> Decimal:
        """Конвертация MoneyValue в Decimal"""
        return Decimal(str(money.units)) + Decimal(str(money.nano)) / Decimal("1000000000")

    def _quotation_to_decimal(self, quotation: Quotation) -> Decimal:
        """Конвертация Quotation в Decimal"""
        return Decimal(str(quotation.units)) + Decimal(str(quotation.nano)) / Decimal("1000000000")

    def _decimal_to_quotation(self, value: Decimal) -> Quotation:
        """Конвертация Decimal в Quotation"""
        units = int(value)
        nano = int((value - units) * Decimal("1000000000"))
        return Quotation(units=units, nano=nano)

    async def get_current_price(self, figi: str) -> Decimal:
        """Получение текущей цены инструмента"""
        async with AsyncClient(self.token) as api_client:
            # Получаем стакан котировок
            orderbook = await api_client.market_data.get_order_book(
                figi=figi,
                depth=1
            )
            
            if orderbook.bids and orderbook.asks:
                bid = self._quotation_to_decimal(orderbook.bids[0].price)
                ask = self._quotation_to_decimal(orderbook.asks[0].price)
                return (bid + ask) / 2
            
            # Если стакан пустой, получаем последнюю цену
            candles = await api_client.market_data.get_candles(
                figi=figi,
                from_=None,
                to=None,
                interval=1  # 1 минута
            )
            
            if candles.candles:
                return self._quotation_to_decimal(candles.candles[-1].close)
            
            raise ValueError(f"Не удалось получить цену для {figi}")

    async def place_market_order(
        self, 
        figi: str, 
        direction: OrderDirection, 
        quantity: int
    ) -> OrderResult:
        """Выставление рыночного ордера"""
        try:
            async with AsyncClient(self.token) as api_client:
                response = await api_client.orders.post_order(
                    figi=figi,
                    quantity=quantity,
                    direction=direction,
                    account_id=self.account_id,
                    order_type=OrderType.ORDER_TYPE_MARKET,
                    order_id=f"market_{figi}_{direction.name}_{quantity}"
                )
                
                executed_price = self._money_value_to_decimal(response.executed_order_price)
                
                logger.info(f"Market order executed: {response.order_id}, price: {executed_price}")
                
                return OrderResult(
                    order_id=response.order_id,
                    success=True,
                    message=f"Market order executed at {executed_price}",
                    price=executed_price,
                    quantity=quantity
                )
                
        except Exception as e:
            logger.error(f"Market order error: {e}")
            return OrderResult(
                order_id="",
                success=False,
                message=str(e)
            )

    async def place_stop_order(
        self,
        figi: str,
        direction: StopOrderDirection,
        quantity: int,
        stop_price: Decimal,
        order_type: StopOrderType = StopOrderType.STOP_ORDER_TYPE_STOP_LOSS
    ) -> OrderResult:
        """Выставление стоп-ордера (НЕ лимитного!)"""
        try:
            async with AsyncClient(self.token) as api_client:
                # Получаем информацию об инструменте для правильного форматирования цены
                instrument = await api_client.instruments.get_instrument_by(
                    id_type=1,  # FIGI
                    id=figi
                )
                
                # Конвертируем цену в правильный формат
                stop_price_quotation = self._decimal_to_quotation(stop_price)
                
                response = await api_client.stop_orders.post_stop_order(
                    figi=figi,
                    quantity=quantity,
                    direction=direction,
                    account_id=self.account_id,
                    expiration_type=StopOrderExpirationType.STOP_ORDER_EXPIRATION_TYPE_GOOD_TILL_CANCEL,
                    stop_order_type=order_type,
                    expire_date=None,
                    stop_price=stop_price_quotation
                )
                
                logger.info(f"Stop order placed: {response.stop_order_id}, stop price: {stop_price}")
                
                return OrderResult(
                    order_id=response.stop_order_id,
                    success=True,
                    message=f"Stop order placed at {stop_price}",
                    price=stop_price,
                    quantity=quantity
                )
                
        except Exception as e:
            logger.error(f"Stop order error: {e}")
            return OrderResult(
                order_id="",
                success=False,
                message=str(e)
            )

    async def place_take_profit_order(
        self,
        figi: str,
        direction: StopOrderDirection,
        quantity: int,
        take_profit_price: Decimal
    ) -> OrderResult:
        """Выставление Take-Profit ордера как стоп-ордера"""
        return await self.place_stop_order(
            figi=figi,
            direction=direction,
            quantity=quantity,
            stop_price=take_profit_price,
            order_type=StopOrderType.STOP_ORDER_TYPE_TAKE_PROFIT
        )

    async def execute_smart_order(
        self,
        figi: str,
        desired_direction: str,
        amount: Decimal,
        close_only: bool = False
    ):
        """Умное выставление ордера с автоматическим TP/SL"""
        try:
            # Получаем настройки
            settings = get_settings()
            
            # Получаем информацию об инструменте
            async with AsyncClient(self.token) as api_client:
                instrument = await api_client.instruments.get_instrument_by(
                    id_type=1,  # FIGI
                    id=figi
                )
                
                lot_size = instrument.instrument.lot
                current_price = await self.get_current_price(figi)
                
                # Если это закрытие позиции
                if close_only:
                    positions = await self.client.get_positions_async()
                    target_pos = next((p for p in positions if p.figi == figi), None)
                    
                    if target_pos:
                        # Определяем направление закрытия
                        close_direction = (
                            OrderDirection.ORDER_DIRECTION_SELL 
                            if target_pos.direction == "long" 
                            else OrderDirection.ORDER_DIRECTION_BUY
                        )
                        
                        # Закрываем рыночным ордером
                        result = await self.place_market_order(
                            figi=figi,
                            direction=close_direction,
                            quantity=target_pos.lots
                        )
                        
                        if result.success:
                            logger.info(f"Position closed: {target_pos.ticker}")
                        
                        return result
                    
                    return OrderResult("", True, "No position to close")
                
                # Рассчитываем количество лотов
                position_value = amount
                lots_to_buy = max(1, int(position_value / (current_price * lot_size)))
                
                # Определяем направление ордера
                order_direction = (
                    OrderDirection.ORDER_DIRECTION_BUY 
                    if desired_direction == "long" 
                    else OrderDirection.ORDER_DIRECTION_SELL
                )
                
                # Выставляем основной рыночный ордер
                main_result = await self.place_market_order(
                    figi=figi,
                    direction=order_direction,
                    quantity=lots_to_buy
                )
                
                if not main_result.success:
                    return main_result
                
                # Получаем цену исполнения основного ордера
                execution_price = main_result.price
                
                # Рассчитываем уровни TP и SL
                if desired_direction == "long":
                    # Для лонга: SL ниже, TP выше
                    sl_price = execution_price * (1 - settings.stop_loss_percent / 100)
                    tp_price = execution_price * (1 + settings.take_profit_percent / 100)
                    
                    sl_direction = StopOrderDirection.STOP_ORDER_DIRECTION_SELL
                    tp_direction = StopOrderDirection.STOP_ORDER_DIRECTION_SELL
                else:
                    # Для шорта: SL выше, TP ниже  
                    sl_price = execution_price * (1 + settings.stop_loss_percent / 100)
                    tp_price = execution_price * (1 - settings.take_profit_percent / 100)
                    
                    sl_direction = StopOrderDirection.STOP_ORDER_DIRECTION_BUY
                    tp_direction = StopOrderDirection.STOP_ORDER_DIRECTION_BUY
                
                # Выставляем стоп-лосс как стоп-ордер
                sl_result = await self.place_stop_order(
                    figi=figi,
                    direction=sl_direction,
                    quantity=lots_to_buy,
                    stop_price=sl_price,
                    order_type=StopOrderType.STOP_ORDER_TYPE_STOP_LOSS
                )
                
                # Выставляем тейк-профит как стоп-ордер
                tp_result = await self.place_take_profit_order(
                    figi=figi,
                    direction=tp_direction,
                    quantity=lots_to_buy,
                    take_profit_price=tp_price
                )
                
                # Логируем результаты
                success_msg = [f"Main order: {main_result.message}"]
                if sl_result.success:
                    success_msg.append(f"SL: {sl_price:.4f}")
                if tp_result.success:
                    success_msg.append(f"TP: {tp_price:.4f}")
                
                logger.info(f"Smart order completed: {'; '.join(success_msg)}")
                
                return OrderResult(
                    order_id=main_result.order_id,
                    success=True,
                    message=f"Order executed with SL/TP: {execution_price:.4f}",
                    price=execution_price,
                    quantity=lots_to_buy
                )
                
        except Exception as e:
            logger.error(f"Smart order error: {e}", exc_info=True)
            return OrderResult(
                order_id="",
                success=False,
                message=str(e)
            )

    async def cancel_all_orders(self) -> dict:
        """Отмена всех активных ордеров"""
        try:
            cancelled = {"limit_orders": 0, "stop_orders": 0}
            
            async with AsyncClient(self.token) as api_client:
                # Отменяем лимитные ордера
                limit_orders = await api_client.orders.get_orders(account_id=self.account_id)
                for order in limit_orders.orders:
                    try:
                        await api_client.orders.cancel_order(
                            account_id=self.account_id,
                            order_id=order.order_id
                        )
                        cancelled["limit_orders"] += 1
                    except Exception as e:
                        logger.error(f"Failed to cancel limit order {order.order_id}: {e}")
                
                # Отменяем стоп-ордера
                stop_orders = await api_client.stop_orders.get_stop_orders(account_id=self.account_id)
                for stop_order in stop_orders.stop_orders:
                    try:
                        await api_client.stop_orders.cancel_stop_order(
                            account_id=self.account_id,
                            stop_order_id=stop_order.stop_order_id
                        )
                        cancelled["stop_orders"] += 1
                    except Exception as e:
                        logger.error(f"Failed to cancel stop order {stop_order.stop_order_id}: {e}")
            
            return cancelled
            
        except Exception as e:
            logger.error(f"Cancel all orders error: {e}")
            raise