# config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    TINKOFF_TOKEN = os.getenv("TINKOFF_TOKEN")
    ACCOUNT_ID = os.getenv("ACCOUNT_ID")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG")    
    DATABASE_URL = os.getenv("DB_URL")