from decimal import Decimal
from tinkoff.invest import AsyncClient, Quotation, InstrumentShort
from redis import Redis
import logging
from config import Settings

logger = logging.getLogger(__name__)

class RiskManager:
    def __init__(self, token: str, account_id: str):
        self.token = token
        self.account_id = account_id
        self.settings = Settings()
        self.redis = Redis.from_url(self.settings.REDIS_URL)
        self.cache_ttl = 86400  # 24 часа

    async def get_figi(self, instrument_name: str) -> str:
        """Поиск FIGI с кэшированием"""
        cache_key = f"figi:{instrument_name}"
        cached = self.redis.get(cache_key)
        
        if cached:
            return cached.decode()

        async with AsyncClient(self.token) as client:
            try:
                response = await client.instruments.find_instrument(query=instrument_name)
                for instrument in response.instruments:
                    if instrument.ticker.upper() == instrument_name.upper():
                        figi = instrument.figi
                        self.redis.setex(cache_key, self.cache_ttl, figi)
                        return figi
                raise ValueError(f"Инструмент {instrument_name} не найден")
            except Exception as e:
                logger.error(f"FIGI search error: {str(e)}")
                raise

    def _validate_min_lot(self, instrument: InstrumentShort, quantity: int):
        """Проверка минимального лота"""
        if not hasattr(instrument, 'min_quantity_increment') or instrument.min_quantity_increment is None:
            raise ValueError("Инструмент не имеет минимального лота")

        min_lot = instrument.min_quantity_increment
        if quantity < min_lot:
            raise ValueError(f"Количество {quantity} меньше минимального лота {min_lot}")

    async def validate_order(self, figi: str, quantity: int) -> dict:
        """Основная проверка перед исполнением ордера"""
        try:
            async with AsyncClient(self.token) as client:
                instrument = await client.instruments.get_instrument_by_figi(figi=figi)
                
                # Валидация минимального лота
                self._validate_min_lot(instrument, quantity)

                # Получение цены и расчет стоимости
                last_price = await self._get_last_price(client, figi)
                position_cost = last_price * quantity * instrument.lot

                # Получение доступного баланса
                portfolio = await client.operations.get_portfolio(account_id=self.account_id)
                total = portfolio.total_amount_portfolio
                available = self._quotation_to_decimal(total)

                # Проверки
                checks = {
                    'min_lot': quantity >= instrument.min_quantity_increment,
                    'balance': position_cost <= available * Decimal('0.5'),
                    'daily_limit': position_cost <= Decimal('100000'),
                    'instrument_active': instrument.api_trade_available_flag
                }

                return {
                    'status': 'approved' if all(checks.values()) else 'rejected',
                    'checks': checks
                }

        except Exception as e:
            logger.error(f"Risk validation error: {str(e)}")
            return {
                'status': 'error',
                'message': str(e),
                'checks': {}
            }

    async def _get_last_price(self, client: AsyncClient, figi: str) -> Decimal:
        """Получение последней цены"""
        order_book = await client.market_data.get_order_book(figi=figi, depth=1)
        return self._quotation_to_decimal(order_book.last_price)

    def _quotation_to_decimal(self, q: Quotation) -> Decimal:
        """Конвертация Quotation в Decimal"""
        return Decimal(q.units) + Decimal(q.nano) / 1e9
