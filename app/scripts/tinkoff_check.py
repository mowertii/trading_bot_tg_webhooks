import os
import asyncio
from tinkoff.invest import AsyncClient, InstrumentIdType
from trading.tinkoff_client import TinkoffClient

async def main():
    token = os.getenv("TINKOFF_TOKEN")
    account_id = os.getenv("ACCOUNT_ID")
    
    client = TinkoffClient(token, account_id)
    
    # Тест поиска FIGI
    figi = await client.get_figi_by_ticker("SBER")
    print(f"FIGI для SBER: {figi}")
    
    # Проверка инструмента
    async with AsyncClient(token) as api_client:
        instrument = await api_client.instruments.get_instrument_by(
            id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_FIGI,
            id=figi
        )
        print(f"Информация об инструменте: {instrument}")

if __name__ == "__main__":
    asyncio.run(main())