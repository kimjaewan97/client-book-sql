-- Northline Brokerage — analytical schema (SQLite)
-- One row per business object. Prices and cash amounts are in EUR.
-- The generator builds one account per customer; the schema still allows more.

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS cashflows;
DROP TABLE IF EXISTS trades;
DROP TABLE IF EXISTS prices;
DROP TABLE IF EXISTS accounts;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS instruments;

CREATE TABLE customers (
    customer_id     INTEGER PRIMARY KEY,
    segment         TEXT NOT NULL CHECK (segment IN ('retail', 'affluent', 'hnw')),
    country         TEXT NOT NULL CHECK (country IN ('DE', 'AT', 'CH', 'NL', 'FR')),
    risk_profile    TEXT NOT NULL CHECK (risk_profile IN ('conservative', 'balanced', 'growth')),
    onboarded_on    TEXT NOT NULL, -- ISO date
    status          TEXT NOT NULL CHECK (status IN ('open', 'closed'))
);

CREATE TABLE accounts (
    account_id   INTEGER PRIMARY KEY,
    customer_id  INTEGER NOT NULL REFERENCES customers(customer_id),
    opened_on    TEXT NOT NULL,
    closed_on    TEXT,
    status       TEXT NOT NULL CHECK (status IN ('open', 'closed'))
);

CREATE TABLE instruments (
    instrument_id  INTEGER PRIMARY KEY,
    ticker         TEXT NOT NULL UNIQUE,
    name           TEXT NOT NULL,
    asset_class    TEXT NOT NULL CHECK (asset_class IN ('equity', 'etf', 'bond')),
    sector         TEXT NOT NULL,
    region         TEXT NOT NULL
);

CREATE TABLE prices (
    instrument_id  INTEGER NOT NULL REFERENCES instruments(instrument_id),
    price_date     TEXT NOT NULL,
    close_price    REAL NOT NULL CHECK (close_price > 0),
    PRIMARY KEY (instrument_id, price_date)
);

CREATE TABLE trades (
    trade_id      INTEGER PRIMARY KEY,
    account_id    INTEGER NOT NULL REFERENCES accounts(account_id),
    instrument_id INTEGER NOT NULL REFERENCES instruments(instrument_id),
    trade_date    TEXT NOT NULL,
    side          TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    quantity      REAL NOT NULL CHECK (quantity > 0),
    price         REAL NOT NULL CHECK (price > 0),
    notional_eur  REAL NOT NULL CHECK (notional_eur > 0),
    commission_eur REAL NOT NULL CHECK (commission_eur >= 0)
);

-- Client cash movements. Sign is from the client's point of view:
-- deposit > 0, withdrawal < 0, custody_fee < 0.
CREATE TABLE cashflows (
    cashflow_id  INTEGER PRIMARY KEY,
    account_id   INTEGER NOT NULL REFERENCES accounts(account_id),
    flow_date    TEXT NOT NULL,
    flow_type    TEXT NOT NULL CHECK (flow_type IN ('deposit', 'withdrawal', 'custody_fee')),
    amount_eur   REAL NOT NULL
);

CREATE INDEX idx_accounts_customer ON accounts(customer_id);
CREATE INDEX idx_trades_account_date ON trades(account_id, trade_date);
CREATE INDEX idx_trades_instrument ON trades(instrument_id, trade_date);
CREATE INDEX idx_prices_date ON prices(price_date);
CREATE INDEX idx_cashflows_account_date ON cashflows(account_id, flow_date);
CREATE INDEX idx_customers_onboarded ON customers(onboarded_on);
