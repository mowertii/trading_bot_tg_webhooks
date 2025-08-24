# test_tinkoff.py
from trading.tinkoff_client import TinkoffClient
import asyncio

async def main():
    client = TinkoffClient(os.getenv("TINKOFF_TOKEN"), os.getenv("ACCOUNT_ID"))
    
    # Тест поиска FIGI
    figi = await client.get_figi_by_ticker_async("AAPL")
    print(f"FIGI для AAPL: {figi}")
    
    # Тест ордера
    result = await client.place_market_order_async(figi, 1, "buy")
    print(f"Результат ордера: {result}")

asyncio.run(main())
