from pydantic import BaseModel
from datetime import datetime

class TradeSignal(BaseModel):
    figi: str
    direction: str  # buy/sell
    quantity: int
    timestamp: datetime

class AccountBalance(BaseModel):
    total: float
    available: float
    currency: str
    updated_at: datetime

class InstrumentCache(BaseModel):
    ticker: str
    figi: str
    min_lot: int
    updated_at: datetime    
