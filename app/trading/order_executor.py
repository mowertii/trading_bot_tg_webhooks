# app/trading/order_executor.py - ИСПРАВЛЕННАЯ ВЕРСИЯ

import logging
import asyncio
from decimal import Decimal, ROUND_DOWN
from dataclasses import dataclass
from typing import Optional, Dict, Any
from tinkoff.invest import (
    AsyncClient,
    OrderDirection,
    OrderType,
    RequestError,
    StopOrderDirection,
    StopOrderExpirationType,
    StopOrderType
)
from .tinkoff_client import TinkoffClient
from trading.settings_manager import get_settings

logger = logging.getLogger(__name__)

@dataclass
class OrderResult:
    success: bool
    message: str
    order_id: Optional[str] = None
    executed_price: Optional[Decimal] = None
    executed_lots: Optional[int] = None
    details: Optional[Dict[str, Any]] = None


class OrderExecutor:
    def __init__(self, token: str, account_id: str):
        self.token = token
        self.account_id = account_id
        self.client = TinkoffClient(token, account_id)
        self._last_price_per_lot: Optional[Decimal] = None

    async def execute_smart_order(
        self,
        figi: str,
        desired_direction: str,
        amount: Decimal,
        close_only: bool = False,
        lots_override: int | None = None,  # НОВЫЙ ПАРАМЕТР
        tp_percent: float | None = None,   # НОВЫЙ - для кастомного TP
        sl_percent: float | None = None    # НОВЫЙ - для кастомного SL
    ) -> OrderResult:
        try:
            logger.info(f"Executing smart order: {desired_direction} {figi}, amount={amount}, close_only={close_only}, lots_override={lots_override}")

            instrument_info = await self._get_instrument_info(figi)
            if not instrument_info:
                return OrderResult(False, f"Не удалось получить информацию об инструменте {figi}")

            ticker = instrument_info.get("ticker", figi)
            positions = await self.client.get_positions_async()
            current_position = next((p for p in positions if p.figi == figi), None)

            if close_only:
                return await self._close_position(current_position, figi, ticker)

            # ИЗМЕНЕНИЕ: используем lots_override если указан
            if lots_override is not None:
                lots_to_trade = lots_override
                logger.info(f"Using lots override: {lots_to_trade}")
            else:
                lots_to_trade = await self._calculate_lots(figi, amount, instrument_info)
                if lots_to_trade <= 0:
                    ppl = self._last_price_per_lot
                    if ppl:
                        return OrderResult(
                            success=False,
                            message=(
                                f"Сумма позиции недостаточна для 1 лота {ticker}. "
                                f"Рассчитано: {self._fmt_money(amount)}, 1 лот ≈ {self._fmt_money(ppl)}"
                            ),
                        )
                    return OrderResult(
                        success=False,
                        message=f"Сумма позиции недостаточна для торговли {ticker}: {self._fmt_money(amount)}"
                    )

            if desired_direction == "long":
                result = await self._execute_buy_order(figi, lots_to_trade, ticker)
            elif desired_direction == "short":
                result = await self._execute_sell_order(figi, lots_to_trade, ticker)
            else:
                return OrderResult(False, f"Неподдерживаемое направление: {desired_direction}")

            if result.success:
                result.details = {
                    "ticker": ticker,
                    "direction": desired_direction,
                    "lots_traded": lots_to_trade,
                    "amount_used": str(self._fmt_money(amount))
                }
                result.message = f"{result.message} Торговано: {lots_to_trade} лот(ов)"

                # Выставляем SL и TP после успешного открытия позиции
                if not close_only:
                    await self._place_tp_sl_orders(figi, desired_direction, lots_to_trade, result, tp_percent, sl_percent)

            return result

        except Exception as e:
            logger.error(f"Error in execute_smart_order: {e}", exc_info=True)
            return OrderResult(False, f"Системная ошибка при выполнении ордера: {str(e)}")

    async def _place_tp_sl_orders(self, figi: str, direction: str, lots: int, result: OrderResult, tp_percent: float = None, sl_percent: float = None):
        """Размещаем TP и SL ордера после открытия позиции"""
        try:
            settings = get_settings()
            
            # ИСПРАВЛЕНИЕ: используем переданные значения или из настроек
            if tp_percent is not None:
                tp_pct = Decimal(tp_percent) / Decimal(100)
            else:
                tp_pct = Decimal(settings.take_profit_percent) / Decimal(100)
                
            if sl_percent is not None:
                sl_pct = Decimal(sl_percent) / Decimal(100)
            else:
                sl_pct = Decimal(settings.stop_loss_percent) / Decimal(100)

            async with AsyncClient(self.token) as api:
                # Получаем информацию об инструменте для min_price_increment
                instrument_resp = await api.instruments.get_instrument_by(id_type=1, id=figi)
                if not instrument_resp or not instrument_resp.instrument:
                    logger.error("Не удалось получить информацию об инструменте для TP/SL")
                    return

                min_price_increment = self._quotation_to_decimal(instrument_resp.instrument.min_price_increment)
                logger.info(f"Min price increment for {figi}: {min_price_increment}")

                # Получаем текущую цену
                last_prices = await api.market_data.get_last_prices(figi=[figi])
                if not last_prices.last_prices:
                    logger.error("Не удалось получить текущую цену для TP/SL")
                    return

                price_q = last_prices.last_prices[0].price
                current_price = self._quotation_to_decimal(price_q)

                # Рассчитываем цены SL/TP
                if direction == "long":
                    sl_price_raw = current_price * (Decimal(1) - sl_pct)
                    tp_price_raw = current_price * (Decimal(1) + tp_pct)
                    stop_direction = StopOrderDirection.STOP_ORDER_DIRECTION_SELL
                else:  # short
                    sl_price_raw = current_price * (Decimal(1) + sl_pct)
                    tp_price_raw = current_price * (Decimal(1) - tp_pct)
                    stop_direction = StopOrderDirection.STOP_ORDER_DIRECTION_BUY

                # КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: округляем цены до min_price_increment
                def round_to_increment(price: Decimal, increment: Decimal) -> Decimal:
                    if increment <= 0:
                        return price.quantize(Decimal("0.01"), rounding=ROUND_DOWN)
                    # Округляем до ближайшего кратного increment
                    rounded = (price / increment).quantize(Decimal("1"), rounding=ROUND_DOWN) * increment
                    return rounded.quantize(increment, rounding=ROUND_DOWN)

                sl_price = round_to_increment(sl_price_raw, min_price_increment)
                tp_price = round_to_increment(tp_price_raw, min_price_increment)

                logger.info(f"Calculated prices - SL: {sl_price}, TP: {tp_price} (increment: {min_price_increment})")

                # Конвертируем цены в Quotation
                def decimal_to_quotation(price: Decimal):
                    units = int(price)
                    nano = int((price - units) * Decimal("1000000000"))
                    from tinkoff.invest import Quotation
                    return Quotation(units=units, nano=nano)

                sl_quotation = decimal_to_quotation(sl_price)
                tp_quotation = decimal_to_quotation(tp_price)

                # Размещаем стоп-лосс
                try:
                    sl_resp = await api.stop_orders.post_stop_order(
                        figi=figi,
                        quantity=lots,
                        price=sl_quotation,
                        stop_price=sl_quotation,
                        direction=stop_direction,
                        account_id=self.account_id,
                        expiration_type=StopOrderExpirationType.STOP_ORDER_EXPIRATION_TYPE_GOOD_TILL_CANCEL,
                        stop_order_type=StopOrderType.STOP_ORDER_TYPE_STOP_LOSS
                    )
                    logger.info(f"SL order placed: {sl_resp.stop_order_id}")
                    
                    result.details["stop_loss_order_id"] = sl_resp.stop_order_id
                    result.details["stop_loss_price"] = str(sl_price)
                except Exception as e:
                    logger.error(f"Failed to place SL order: {e}")

                # Размещаем тейк-профит
                try:
                    tp_resp = await api.stop_orders.post_stop_order(
                        figi=figi,
                        quantity=lots,
                        price=tp_quotation,
                        stop_price=tp_quotation,
                        direction=stop_direction,
                        account_id=self.account_id,
                        expiration_type=StopOrderExpirationType.STOP_ORDER_EXPIRATION_TYPE_GOOD_TILL_CANCEL,
                        stop_order_type=StopOrderType.STOP_ORDER_TYPE_TAKE_PROFIT
                    )
                    logger.info(f"TP order placed: {tp_resp.stop_order_id}")
                    
                    result.details["take_profit_order_id"] = tp_resp.stop_order_id
                    result.details["take_profit_price"] = str(tp_price)
                except Exception as e:
                    logger.error(f"Failed to place TP order: {e}")

        except Exception as e:
            logger.error(f"Error placing TP/SL orders: {e}", exc_info=True)

    async def _get_instrument_info(self, figi: str) -> Optional[Dict[str, Any]]:
        try:
            async with AsyncClient(self.token) as client:
                response = await client.instruments.get_instrument_by(id_type=1, id=figi)
                if response and response.instrument:
                    return {
                        "ticker": response.instrument.ticker,
                        "lot": response.instrument.lot,
                        "currency": response.instrument.currency,
                        "min_price_increment": response.instrument.min_price_increment
                    }
                return None
        except Exception as e:
            logger.error(f"Error getting instrument info for {figi}: {e}")
            return None

    async def _calculate_lots(self, figi: str, amount: Decimal, instrument_info: Dict) -> int:
        """Рассчитываем количество лотов; безопасный парсинг стакана с фоллбэком на last_price."""
        try:
            async with AsyncClient(self.token) as client:
                ob = await client.market_data.get_order_book(figi=figi, depth=1)

                current_price: Optional[Decimal] = None

                # bids/asks могут быть списками записей, у каждой есть поле price (Quotation)
                # Берем среднюю между лучшим бидом и аском, если есть
                try:
                    has_bid = bool(ob.bids)
                    has_ask = bool(ob.asks)
                    if has_bid and has_ask:
                        bid0 = ob.bids[0]
                        ask0 = ob.asks[0]
                        bid_price_q = getattr(bid0, "price", None)
                        ask_price_q = getattr(ask0, "price", None)
                        if bid_price_q and ask_price_q:
                            best_bid = self._quotation_to_decimal(bid_price_q)
                            best_ask = self._quotation_to_decimal(ask_price_q)
                            current_price = (best_bid + best_ask) / 2
                except Exception as e:
                    logger.warning(f"OrderBook top levels parse issue for {figi}: {e}")

                if current_price is None:
                    lp = getattr(ob, "last_price", None)
                    if lp:
                        current_price = self._quotation_to_decimal(lp)

                if current_price is None or current_price <= 0:
                    logger.error(f"No valid price in orderbook for {figi}")
                    return 0

                lot_size = int(instrument_info.get("lot", 1) or 1)
                price_per_lot = (current_price * Decimal(lot_size)).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
                self._last_price_per_lot = price_per_lot

                lots = int((amount / price_per_lot).to_integral_value(rounding=ROUND_DOWN))
                logger.info(f"Calculated lots: {lots} (price_per_lot: {price_per_lot}, amount: {amount})")
                return lots

        except Exception as e:
            logger.error(f"Error calculating lots: {e}")
            return 0

    async def _close_position(self, position, figi: str, ticker: str) -> OrderResult:
        if not position:
            return OrderResult(True, f"Позиция по {ticker} отсутствует, закрытие не требуется")

        try:
            # Сначала отменяем все стоп-ордера по этому инструменту
            await self._cancel_orders_for_figi(figi)

            if position.direction == "long":
                result = await self._execute_sell_order(figi, position.lots, ticker, closing=True)
            else:
                result = await self._execute_buy_order(figi, position.lots, ticker, closing=True)

            if result.success:
                result.message = f"Закрыта {position.direction} позиция по {ticker}: {position.lots} лот(ов)"
            return result

        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return OrderResult(False, f"Ошибка закрытия позиции {ticker}: {str(e)}")

    async def _cancel_orders_for_figi(self, figi: str):
        """Отменяем все ордера по конкретному FIGI"""
        try:
            async with AsyncClient(self.token) as client:
                # Отменяем стоп-ордера
                stop_orders = await client.stop_orders.get_stop_orders(account_id=self.account_id)
                for stop_order in stop_orders.stop_orders:
                    if stop_order.figi == figi:
                        try:
                            await client.stop_orders.cancel_stop_order(
                                account_id=self.account_id,
                                stop_order_id=stop_order.stop_order_id
                            )
                            logger.info(f"Cancelled stop order for {figi}: {stop_order.stop_order_id}")
                        except Exception as e:
                            logger.error(f"Error cancelling stop order {stop_order.stop_order_id}: {e}")

                # Отменяем лимитные ордера
                orders = await client.orders.get_orders(account_id=self.account_id)
                for order in orders.orders:
                    if order.figi == figi:
                        try:
                            await client.orders.cancel_order(
                                account_id=self.account_id,
                                order_id=order.order_id
                            )
                            logger.info(f"Cancelled limit order for {figi}: {order.order_id}")
                        except Exception as e:
                            logger.error(f"Error cancelling limit order {order.order_id}: {e}")

        except Exception as e:
            logger.error(f"Error cancelling orders for {figi}: {e}")

    async def _execute_buy_order(self, figi: str, lots: int, ticker: str, closing: bool = False) -> OrderResult:
        try:
            async with AsyncClient(self.token) as client:
                order_response = await client.orders.post_order(
                    order_id="",
                    figi=figi,
                    quantity=lots,
                    direction=OrderDirection.ORDER_DIRECTION_BUY,
                    account_id=self.account_id,
                    order_type=OrderType.ORDER_TYPE_MARKET
                )
                if order_response:
                    action_text = "закрытия позиции" if closing else "покупки"
                    return OrderResult(True, f"Ордер {action_text} {ticker} успешно размещен",
                                       order_id=order_response.order_id,
                                       executed_lots=lots)
                return OrderResult(False, f"Не удалось разместить ордер покупки {ticker}")

        except RequestError as e:
            logger.error(f"Tinkoff API error in buy order: {e}")
            return OrderResult(False, f"Ошибка API при покупке {ticker}: {e.details}")
        except Exception as e:
            logger.error(f"Error in buy order: {e}")
            return OrderResult(False, f"Системная ошибка при покупке {ticker}: {str(e)}")

    async def _check_margin_requirements(self, figi: str, direction: str, lots: int) -> tuple[bool, str]:
        """
        Проверяет маржинальные требования перед размещением ордера
        """
        try:
            async with AsyncClient(self.token) as client:
                # Проверяем торговый статус инструмента
                trading_status = await client.market_data.get_trading_status(figi=figi)

                if not trading_status.api_trade_available_flag:
                    return False, "Торговля через API недоступна для данного инструмента"

                # Для шорт-позиций проверяем доступность маржинальной торговли
                if direction == "short":
                    try:
                        # Получаем маржинальные атрибуты счета
                        margin_attrs = await client.users.get_margin_attributes(account_id=self.account_id)

                        # Проверяем что маржинальная торговля включена
                        if not margin_attrs:
                            return False, "Маржинальная торговля отключена для данного счета"

                        # Получаем информацию об инструменте
                        instrument_resp = await client.instruments.get_instrument_by(id_type=1, id=figi)
                        if not instrument_resp or not instrument_resp.instrument:
                            return False, "Не удалось получить информацию об инструменте"

                        ticker = instrument_resp.instrument.ticker

                        # Проверяем что инструмент доступен для шорта
                        if not getattr(instrument_resp.instrument, 'short_enabled_flag', False):
                            return False, f"Инструмент {ticker} недоступен для продажи в шорт"

                        logger.info(f"Margin check passed for short {ticker}")

                    except Exception as margin_error:
                        logger.warning(f"Margin check failed: {margin_error}")
                        return False, f"Недостаточно средств для маржинальной торговли: {str(margin_error)}"

                return True, "OK"

        except Exception as e:
            logger.error(f"Error checking margin requirements: {e}")
            return False, f"Ошибка проверки маржинальных требований: {str(e)}"

    async def _execute_sell_order(self, figi: str, lots: int, ticker: str, closing: bool = False) -> OrderResult:
        try:
            # НОВОЕ: проверяем маржинальные требования для шорт-позиций
            if not closing:
                margin_ok, margin_msg = await self._check_margin_requirements(figi, "short", lots)
                if not margin_ok:
                    return OrderResult(False, f"Маржинальные требования: {margin_msg}")

            async with AsyncClient(self.token) as client:
                order_response = await client.orders.post_order(
                    order_id="",
                    figi=figi,
                    quantity=lots,
                    direction=OrderDirection.ORDER_DIRECTION_SELL,
                    account_id=self.account_id,
                    order_type=OrderType.ORDER_TYPE_MARKET
                )
                if order_response:
                    action_text = "закрытия позиции" if closing else "продажи"
                    return OrderResult(True, f"Ордер {action_text} {ticker} успешно размещен",
                                       order_id=order_response.order_id,
                                       executed_lots=lots)
                return OrderResult(False, f"Не удалось разместить ордер продажи {ticker}")

        except RequestError as e:
            logger.error(f"Tinkoff API error in sell order: {e}")
            error_msg = str(e.details) if hasattr(e, 'details') else str(e)
            if "30042" in error_msg or "margin" in error_msg.lower():
                return OrderResult(False, f"Недостаточно средств для маржинальной торговли {ticker}")
            return OrderResult(False, f"Ошибка API при продаже {ticker}: {error_msg}")
        except Exception as e:
            logger.error(f"Error in sell order: {e}")
            return OrderResult(False, f"Системная ошибка при продаже {ticker}: {str(e)}")

    async def cancel_all_orders(self) -> Dict[str, int]:
        try:
            cancelled = {"limit_orders": 0, "stop_orders": 0}
            async with AsyncClient(self.token) as client:
                orders_response = await client.orders.get_orders(account_id=self.account_id)
                for order in orders_response.orders:
                    try:
                        await client.orders.cancel_order(account_id=self.account_id, order_id=order.order_id)
                        cancelled["limit_orders"] += 1
                        logger.info(f"Cancelled limit order: {order.order_id}")
                    except Exception as e:
                        logger.error(f"Error cancelling limit order {order.order_id}: {e}")

                stop_orders_response = await client.stop_orders.get_stop_orders(account_id=self.account_id)
                for stop_order in stop_orders_response.stop_orders:
                    try:
                        await client.stop_orders.cancel_stop_order(
                            account_id=self.account_id,
                            stop_order_id=stop_order.stop_order_id
                        )
                        cancelled["stop_orders"] += 1
                        logger.info(f"Cancelled stop order: {stop_order.stop_order_id}")
                    except Exception as e:
                        logger.error(f"Error cancelling stop order {stop_order.stop_order_id}: {e}")
            return cancelled
        except Exception as e:
            logger.error(f"Error cancelling orders: {e}")
            return {"limit_orders": 0, "stop_orders": 0}

    def _quotation_to_decimal(self, quotation) -> Decimal:
        """Конвертируем Quotation в Decimal"""
        return Decimal(str(quotation.units)) + Decimal(str(quotation.nano)) / Decimal("1000000000")

    def _fmt_money(self, x: Decimal) -> Decimal:
        """Форматируем деньги с округлением до 2 знаков"""
        return x.quantize(Decimal("0.01"), rounding=ROUND_DOWN)