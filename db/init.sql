-- db/init.sql
-- Схема БД для сигналов, сделок и ошибок

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Входящие сигналы (webhooks)
CREATE TABLE IF NOT EXISTS signals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    action VARCHAR(50) NOT NULL,        -- buy/sell/close_all/balance
    symbol VARCHAR(50),                  -- тикер/символ
    risk_percent NUMERIC(6,3),
    raw_payload JSONB,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

-- Исполненные сделки
CREATE TABLE IF NOT EXISTS trades (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    figi VARCHAR(64) NOT NULL,
    ticker VARCHAR(50),
    direction VARCHAR(10) NOT NULL,     -- long/short
    lots INT NOT NULL,
    amount NUMERIC(18,2),
    price NUMERIC(18,6),
    status VARCHAR(32),                  -- success / failed
    details TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

-- Ошибки
CREATE TABLE IF NOT EXISTS errors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source VARCHAR(100),
    message TEXT NOT NULL,
    traceback TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

-- События
CREATE TABLE IF NOT EXISTS event_logs (
  id SERIAL PRIMARY KEY,
  event_time TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  event_type TEXT NOT NULL,       -- e.g. 'signal', 'trade', 'error'
  symbol TEXT,                    -- тикер инструмента
  details JSONB,                  -- произвольные данные
  message TEXT                    -- человекочитаемое описание
);


-- Полезные индексы
CREATE INDEX IF NOT EXISTS idx_signals_created_at ON signals (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_trades_created_at ON trades (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_trades_ticker ON trades (ticker);
