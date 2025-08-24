import redis
from pydantic import BaseModel
import json
from config import Settings

settings = Settings()

class RedisQueue:
    def __init__(self):
        self.redis = redis.Redis.from_url(settings.REDIS_URL)
        self.channel = 'trading_signals'

    async def publish_signal(self, signal: dict):
        self.redis.publish(self.channel, json.dumps(signal))

    async def listen_signals(self, callback):
        pubsub = self.redis.pubsub()
        pubsub.subscribe(self.channel)
        for message in pubsub.listen():
            if message['type'] == 'message':
                callback(json.loads(message['data']))

class TradeSignal(BaseModel):
    action: str  # buy/sell/balance
    figi: str = "NG_FIGI"  # Замените на реальный FIGI
    quantity: int = 1
    user_id: int
    chat_id: int
