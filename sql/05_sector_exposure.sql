-- Question: Where is client wealth actually sitting on the last price date?
-- Position = cumulative signed quantity (buys positive, sells negative).
-- Accounts are long-only in this book; a tiny residual is filtered out.
-- Market value uses that date's close. Cash is not an instrument, so this is
-- invested AUM, not total client equity.

WITH last_day AS (
    SELECT MAX(price_date) AS as_of FROM prices
),
positions AS (
    SELECT
        t.account_id,
        t.instrument_id,
        SUM(CASE WHEN t.side = 'buy' THEN t.quantity ELSE -t.quantity END) AS qty
    FROM trades t
    JOIN last_day d ON t.trade_date <= d.as_of
    GROUP BY t.account_id, t.instrument_id
    HAVING qty > 0.0001
),
valued AS (
    SELECT
        i.asset_class,
        i.sector,
        i.region,
        p.qty * px.close_price AS market_value_eur
    FROM positions p
    JOIN last_day d
    JOIN prices px
      ON px.instrument_id = p.instrument_id
     AND px.price_date = d.as_of
    JOIN instruments i ON i.instrument_id = p.instrument_id
),
totals AS (
    SELECT SUM(market_value_eur) AS invested_aum FROM valued
)
SELECT
    v.asset_class,
    v.sector,
    ROUND(SUM(v.market_value_eur), 0) AS market_value_eur,
    ROUND(100.0 * SUM(v.market_value_eur) / t.invested_aum, 1) AS share_of_invested_aum_pct
FROM valued v
CROSS JOIN totals t
GROUP BY v.asset_class, v.sector
ORDER BY market_value_eur DESC;
