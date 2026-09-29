-- Question: Does the risk profile on the application match how the client trades?
-- Compares stated profile with two observed facts over the full sample:
--   * average number of trades
--   * share of that profile's invested AUM that is technology equity
-- A growth profile that does not own technology, or a conservative profile
-- that trades like a day-trader, is a suitability question — not just a chart.

WITH last_day AS (
    SELECT MAX(price_date) AS as_of FROM prices
),
trade_counts AS (
    SELECT a.customer_id, COUNT(*) AS trades
    FROM trades t
    JOIN accounts a ON a.account_id = t.account_id
    GROUP BY a.customer_id
),
positions AS (
    SELECT
        a.customer_id,
        i.sector,
        i.asset_class,
        SUM(CASE WHEN t.side = 'buy' THEN t.quantity ELSE -t.quantity END) AS qty,
        px.close_price
    FROM trades t
    JOIN accounts a ON a.account_id = t.account_id
    JOIN instruments i ON i.instrument_id = t.instrument_id
    JOIN last_day d ON t.trade_date <= d.as_of
    JOIN prices px
      ON px.instrument_id = t.instrument_id
     AND px.price_date = d.as_of
    GROUP BY a.customer_id, t.instrument_id
    HAVING qty > 0.0001
),
exposure AS (
    SELECT
        customer_id,
        SUM(qty * close_price) AS aum_eur,
        SUM(CASE WHEN sector = 'Technology' AND asset_class = 'equity' THEN qty * close_price ELSE 0 END) AS tech_aum_eur
    FROM positions
    GROUP BY customer_id
)
SELECT
    cu.risk_profile,
    COUNT(*) AS clients,
    ROUND(AVG(COALESCE(tc.trades, 0)), 1) AS avg_trades,
    ROUND(SUM(COALESCE(ex.aum_eur, 0)), 0) AS invested_aum_eur,
    ROUND(100.0 * SUM(COALESCE(ex.tech_aum_eur, 0)) / NULLIF(SUM(COALESCE(ex.aum_eur, 0)), 0), 1) AS technology_share_pct
FROM customers cu
LEFT JOIN trade_counts tc ON tc.customer_id = cu.customer_id
LEFT JOIN exposure ex ON ex.customer_id = cu.customer_id
GROUP BY cu.risk_profile
ORDER BY technology_share_pct DESC;
