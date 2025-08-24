from tinkoff.invest import (
    AsyncClient,
    OrderDirection,
    OrderType,
    InstrumentIdType,
    MoneyValue,
    StopOrderType,
    StopOrderExpirationType
)
from decimal import Decimal
import logging
import asyncio
from typing import Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class TradeError(Exception):
    message: str

class OrderExecutor:
    def __init__(
        self,
        token: str,
        account_id: str,
        risk_percentage: Decimal = Decimal('0.4'),
        stop_loss_percent: Decimal = Decimal('0.51'),
        take_profit_percent: Decimal = Decimal('1.9'),
    ):
        self.token = token
        self.account_id = account_id
        self.risk_percentage = risk_percentage
        self.stop_loss_percent = stop_loss_percent / 100
        self.take_profit_percent = take_profit_percent / 100

        # ✅ Здесь храним соответствие order_id → причина
        self.order_reasons: dict[str, str] = {}

    # ---------------------------
    # Вспомогательные методы
    # ---------------------------
    def _money_value_to_decimal(self, money: MoneyValue) -> Decimal:
        if money is None:
            return Decimal(0)
        return Decimal(money.units) + Decimal(money.nano) / Decimal(1e9)

    async def _get_current_price(self, client: AsyncClient, figi: str) -> Decimal:
        last_prices = await client.market_data.get_last_prices(figi=[figi])
        price = last_prices.last_prices[0].price
        return Decimal(price.units) + Decimal(price.nano) / Decimal(1e9)

    async def _get_current_position(self, client: AsyncClient, figi: str) -> Tuple[Optional[str], int]:
        """
        ✅ ИСПРАВЛЕНИЕ: Получает реальную позицию (открытая + заблокированная)
        """
        positions = await client.operations.get_positions(account_id=self.account_id)
        for future in positions.futures:
            if future.figi == figi:
                # Получаем balance и blocked
                balance = getattr(future, 'balance', 0) or 0
                blocked = getattr(future, 'blocked', 0) or 0
                
                # Суммарная позиция = незаблокированная + заблокированная
                total_quantity = balance + blocked
                
                logger.debug(f"Position check for {figi}: balance={balance}, blocked={blocked}, total={total_quantity}")
                
                if total_quantity > 0:
                    return 'long', abs(total_quantity)
                elif total_quantity < 0:
                    return 'short', abs(total_quantity)
        return None, 0

    async def _get_available_funds(self, client: AsyncClient) -> Decimal:
        portfolio = await client.operations.get_portfolio(account_id=self.account_id)
        return self._money_value_to_decimal(portfolio.total_amount_currencies)

    # ---------------------------
    # Отмена ордеров
    # ---------------------------
    async def _cancel_all_limit_orders(self, client: AsyncClient, figi: str):
        orders = await client.orders.get_orders(account_id=self.account_id)
        for order in orders.orders:
            if order.figi == figi and order.order_type == OrderType.ORDER_TYPE_LIMIT:
                await client.orders.cancel_order(account_id=self.account_id, order_id=order.order_id)

    async def _cancel_all_stop_orders(self, client: AsyncClient, figi: str):
        stops = await client.stop_orders.get_stop_orders(account_id=self.account_id)
        for so in stops.stop_orders:
            if so.figi == figi:
                await client.stop_orders.cancel_stop_order(account_id=self.account_id, stop_order_id=so.stop_order_id)

    # ---------------------------
    # Закрытие позиции
    # ---------------------------
    async def _close_position(self, client: AsyncClient, figi: str, position_type: str, quantity: int):
        await self._cancel_all_stop_orders(client, figi)
        await self._cancel_all_limit_orders(client, figi)

        direction = (
            OrderDirection.ORDER_DIRECTION_SELL if position_type == 'long'
            else OrderDirection.ORDER_DIRECTION_BUY
        )
        order = await self._execute_order(
            client=client,
            figi=figi,
            quantity=quantity,
            direction=direction,
            order_type=OrderType.ORDER_TYPE_MARKET
        )
        # ✅ Запоминаем причину
        self.order_reasons[order.order_id] = "MARKET"
        return order

    # ---------------------------
    # Выставление защитных ордеров
    # ---------------------------
    async def _place_protection_orders(self, client: AsyncClient, figi: str, direction: str, entry_price: Decimal, quantity: int):
        instrument = (await client.instruments.get_instrument_by(
            id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_FIGI,
            id=figi
        )).instrument
        min_price_increment = self._money_value_to_decimal(instrument.min_price_increment)

        if direction == 'long':
            stop_price = entry_price * (Decimal(1) - self.stop_loss_percent)
            take_profit_price = entry_price * (Decimal(1) + self.take_profit_percent)
            stop_direction = OrderDirection.ORDER_DIRECTION_SELL
        else:
            stop_price = entry_price * (Decimal(1) + self.stop_loss_percent)
            take_profit_price = entry_price * (Decimal(1) - self.take_profit_percent)
            stop_direction = OrderDirection.ORDER_DIRECTION_BUY

        stop_price = (stop_price // min_price_increment) * min_price_increment
        take_profit_price = (take_profit_price // min_price_increment) * min_price_increment

        def decimal_to_money(value: Decimal) -> MoneyValue:
            units = int(value)
            nano = int((value - units) * Decimal('1e9'))
            return MoneyValue(units=units, nano=nano)

        stop_price_money = decimal_to_money(stop_price)
        tp_price_money = decimal_to_money(take_profit_price)

        # Стоп-лосс
        stop_order = await client.stop_orders.post_stop_order(
            figi=figi,
            quantity=quantity,
            direction=stop_direction,
            account_id=self.account_id,
            stop_price=stop_price_money,
            price=stop_price_money,
            stop_order_type=StopOrderType.STOP_ORDER_TYPE_STOP_LOSS,
            expiration_type=StopOrderExpirationType.STOP_ORDER_EXPIRATION_TYPE_GOOD_TILL_CANCEL
        )
        self.order_reasons[stop_order.stop_order_id] = "STOP_LOSS"

        # Тейк-профит лимитом
        tp_order = await client.orders.post_order(
            figi=figi,
            quantity=quantity,
            direction=stop_direction,
            account_id=self.account_id,
            order_type=OrderType.ORDER_TYPE_LIMIT,
            price=tp_price_money
        )
        self.order_reasons[tp_order.order_id] = "TAKE_PROFIT"

    # ---------------------------
    # Исполнение ордеров
    # ---------------------------
    async def _execute_order(self, client: AsyncClient, figi: str, quantity: int, direction: OrderDirection, order_type: OrderType):
        return await client.orders.post_order(
            figi=figi,
            quantity=quantity,
            direction=direction,
            account_id=self.account_id,
            order_type=order_type
        )

    async def execute_smart_order(self, figi: str, desired_direction: str, amount: Decimal, close_only: bool = False):
        async with AsyncClient(self.token) as client:
            current_pos_type, current_pos_qty = await self._get_current_position(client, figi)

            if close_only:
                if current_pos_type:
                    await self._close_position(client, figi, current_pos_type, current_pos_qty)
                    return
                raise TradeError("Нет позиции для закрытия")

            direction_enum = (
                OrderDirection.ORDER_DIRECTION_BUY if desired_direction == 'long'
                else OrderDirection.ORDER_DIRECTION_SELL
            )

            if current_pos_type and current_pos_type != desired_direction:
                await self._close_position(client, figi, current_pos_type, current_pos_qty)

            futures_margin = await client.instruments.get_futures_margin(figi=figi)
            margin_field = 'initial_margin_on_buy' if desired_direction == 'long' else 'initial_margin_on_sell'
            go_per_lot = self._money_value_to_decimal(getattr(futures_margin, margin_field))
            available_funds = await self._get_available_funds(client)
            quantity = int((available_funds * self.risk_percentage) // go_per_lot)
            if quantity < 1:
                raise TradeError("Недостаточно средств")

            order = await self._execute_order(client, figi, quantity, direction_enum, OrderType.ORDER_TYPE_MARKET)
            self.order_reasons[order.order_id] = "MARKET"

            entry_price = await self._get_current_price(client, figi)
            await self._place_protection_orders(client, figi, desired_direction, entry_price, quantity)