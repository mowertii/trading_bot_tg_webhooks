from telegram import Bot
import logging

logger = logging.getLogger(__name__)

class Notifier:
    def __init__(self, token: str, chat_id: int):
        self.bot = Bot(token=token)
        self.chat_id = chat_id

    def send_order_confirmation(self, order_details: dict):
        message = (
            f"🔄 Ордер исполнен:\\n"
            f"FIGI: {order_details.figi}\\n"
            f"Направление: {order_details.direction}\\n"
            f"Количество: {order_details.quantity}\\n"
            f"Цена: {order_details.executed_price}"
        )
        self.bot.send_message(chat_id=self.chat_id, text=message)
