CREATE TABLE IF NOT EXISTS trades (
    id SERIAL PRIMARY KEY,
    figi VARCHAR(20) NOT NULL,
    direction VARCHAR(4) NOT NULL,
    quantity INTEGER NOT NULL,
    price NUMERIC(12,4) NOT NULL,
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS balance_history (
    id SERIAL PRIMARY KEY,
    account_id VARCHAR(20) NOT NULL,
    balance NUMERIC(12,4) NOT NULL,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO bot;

CREATE INDEX idx_trades_figi ON trades(figi);
CREATE INDEX idx_balance_account ON balance_history(account_id);
