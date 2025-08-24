from dataclasses import dataclass
from tinkoff.invest import (
    AsyncClient,
    InstrumentResponse,        
    PortfolioResponse,
    InstrumentIdType,
    MoneyValue
)
from decimal import Decimal
from typing import List, Optional
import logging


logger = logging.getLogger(__name__)

@dataclass
class Position:
    figi: str
    ticker: str
    lots: int
    direction: str

class TinkoffClient:
    def __init__(self, token: str, account_id: str):
        self.token = token
        self.account_id = account_id
        self.RUB_FIGI = "BBG0013HGFT4"

    async def _get_ticker_by_figi(self, figi: str) -> Optional[str]:
        """Получает тикер инструмента по FIGI"""
        async with AsyncClient(self.token) as client:
            try:
                instrument: InstrumentResponse = await client.instruments.get_instrument_by(
                    id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_FIGI,
                    id=figi
                )
                return instrument.instrument.ticker
            except Exception as e:
                logger.error(f"Ошибка получения тикера для FIGI {figi}: {str(e)}")
                return None

    async def get_margin_attributes(self):
        async with AsyncClient(self.token) as client:
            return await client.operations.get_margin_attributes(account_id=self.account_id)

    async def get_positions_async(self) -> List[Position]:
        async with AsyncClient(self.token) as client:
            response = await client.operations.get_positions(account_id=self.account_id)
            positions = []
            
            for fut in response.futures:
                # ✅ ИСПРАВЛЕНИЕ: Используем общий баланс (balance + blocked)
                # balance = текущий незаблокированный баланс
                # blocked = количество бумаг, заблокированных выставленными заявками  
                # total_position = реальная позиция (открытая + заблокированная)
                
                balance = getattr(fut, 'balance', 0) or 0
                blocked = getattr(fut, 'blocked', 0) or 0
                
                # Суммарная позиция = незаблокированная + заблокированная
                total_position = balance + blocked
                
                logger.debug(f"FIGI {fut.figi}: balance={balance}, blocked={blocked}, total={total_position}")
                
                # Пропускаем нулевые позиции
                if total_position == 0:
                    continue
                    
                # Определяем направление по знаку суммарной позиции
                if total_position > 0:
                    direction = 'long'
                    lots = abs(total_position)
                elif total_position < 0:
                    direction = 'short' 
                    lots = abs(total_position)
                else:
                    continue  # Пропускаем нулевые позиции
                
                ticker = await self._get_ticker_by_figi(fut.figi)
                if not ticker:
                    ticker = fut.figi  # Используем FIGI если тикер не найден
                    
                positions.append(Position(
                    ticker=ticker,
                    figi=fut.figi,
                    lots=lots,
                    direction=direction
                ))
            
            # Логирование для отладки
            logger.debug(f"Найдено позиций: {len(positions)}")
            for pos in positions:
                logger.debug(f"  {pos.ticker}: {pos.lots} лотов ({pos.direction})")
                
            return positions

    async def get_balance_async(self) -> Decimal:
        async with AsyncClient(self.token) as client:
            try:
                # Получаем информацию по валютам
                positions = await client.operations.get_positions(account_id=self.account_id)
                logger.debug(f"Raw positions response: {positions}")
                
                rub_balance = Decimal(0)
                
                for money in positions.money:
                    if money.currency == 'rub':
                        rub_balance += self._money_value_to_decimal(money)
                
                # Обрабатываем ценные бумаги с балансом в RUB
                for security in positions.securities:
                    if security.blocked == 0 and security.balance > 0:
                        instrument = await self._get_instrument_by_figi(security.figi)
                        if instrument and instrument.currency == 'rub':
                            last_price = await self._get_last_price(client, security.figi)
                            rub_balance += last_price * security.balance
                
                logger.info(f"Calculated RUB balance: {rub_balance}")
                return rub_balance
                
            except Exception as e:
                logger.error(f"Balance calculation error: {str(e)}", exc_info=True)
                raise

    async def _get_instrument_by_figi(self, figi: str):
        async with AsyncClient(self.token) as client:
            return await client.instruments.get_instrument_by(
                id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_FIGI,
                id=figi
            )

    async def _get_last_price(self, client: AsyncClient, figi: str) -> Decimal:
        last_price = await client.market_data.get_last_prices(figi=[figi])
        if last_price.last_prices:
            price = last_price.last_prices[0].price
            return Decimal(price.units) + Decimal(price.nano) / Decimal(1e9)
        return Decimal(0)

    def _calculate_available_funds(self, portfolio: PortfolioResponse) -> Decimal:
        cash = next(
            (pos for pos in portfolio.positions 
             if pos.figi == self.RUB_FIGI),
            None
        )
        return self._money_value_to_decimal(cash.current_price) if cash else Decimal(0)

    async def get_figi(self, instrument: str) -> Optional[str]:
        async with AsyncClient(self.token) as client:
            # Убрали некорректный параметр instrument_status
            response = await client.instruments.find_instrument(query=instrument)
            return response.instruments[0].figi if response.instruments else None


    @staticmethod
    def _money_value_to_decimal(money: MoneyValue) -> Decimal:
        """Конвертация MoneyValue в Decimal"""
        return Decimal(money.units) + Decimal(money.nano) / Decimal(1e9)


    async def get_balance_async(self) -> Decimal:
        """Получение доступного RUB баланса"""
        async with AsyncClient(self.token) as client:
            try:
                positions = await client.operations.get_positions(account_id=self.account_id)
                rub_balance = Decimal(0)
                
                # Обрабатываем только рублёвые позиции
                for money in positions.money:
                    if money.currency == 'rub':
                        rub_balance += self._money_value_to_decimal(money)
                
                logger.debug(f"Raw RUB balance: {rub_balance}")
                return rub_balance

            except Exception as e:
                logger.error(f"Balance error: {str(e)}", exc_info=True)
                raise