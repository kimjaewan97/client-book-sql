-- Question: Which names are clients sitting on, and what is the unrealized
-- result versus the average price they paid?
--
-- Cost method (read this before quoting the number):
-- average buy price = total buy notional / total buy quantity.
-- Unrealized P&L = remaining shares * (last close - average buy price).
-- Under a strict moving-average cost method, selling does not change the
-- average, but buying again after a sale does. Using every historical buy
-- ignores that later buys should blend only with the shares still held.
-- Treat the ranking as a screening tool, not as a ledger balance.

WITH last_day AS (
    SELECT MAX(price_date) AS as_of FROM prices
),
buys AS (
    SELECT instrument_id,
           SUM(quantity) AS buy_qty,
           SUM(notional_eur) AS buy_notional
    FROM trades
    WHERE side = 'buy'
    GROUP BY instrument_id
),
remaining AS (
    SELECT
        instrument_id,
        SUM(CASE WHEN side = 'buy' THEN quantity ELSE -quantity END) AS qty
    FROM trades
    GROUP BY instrument_id
    HAVING qty > 0.0001
)
SELECT
    i.ticker,
    i.name,
    i.sector,
    ROUND(r.qty, 2) AS shares_held,
    ROUND(b.buy_notional / b.buy_qty, 2) AS avg_buy_price,
    ROUND(px.close_price, 2) AS last_price,
    ROUND(r.qty * px.close_price, 0) AS market_value_eur,
    ROUND(r.qty * (px.close_price - b.buy_notional / b.buy_qty), 0) AS unrealized_pnl_eur,
    ROUND(100.0 * (px.close_price / (b.buy_notional / b.buy_qty) - 1), 1) AS unrealized_return_pct
FROM remaining r
JOIN buys b ON b.instrument_id = r.instrument_id
JOIN instruments i ON i.instrument_id = r.instrument_id
JOIN last_day d
JOIN prices px
  ON px.instrument_id = r.instrument_id
 AND px.price_date = d.as_of
ORDER BY unrealized_pnl_eur ASC;
