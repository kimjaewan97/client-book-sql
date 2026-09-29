-- Question: Who trades the book, relative to the assets they hold?
-- Turnover for calendar year 2025 =
--   segment traded notional (buys + sells)
--   / average month-end invested AUM of that segment.
-- The denominator is the average of the segment's total invested wealth,
-- not the average account size. A figure of 1.0 means the segment traded
-- a year's worth of its average invested wealth. Costs are not deducted.
-- Month-end positions are rebuilt from the trade ledger (no stored holdings).

WITH month_ends AS (
    SELECT substr(price_date, 1, 7) AS month, MAX(price_date) AS as_of
    FROM prices
    WHERE substr(price_date, 1, 4) = '2025'
    GROUP BY 1
),
positions AS (
    SELECT
        m.month,
        t.account_id,
        t.instrument_id,
        SUM(CASE WHEN t.side = 'buy' THEN t.quantity ELSE -t.quantity END) AS qty
    FROM month_ends m
    JOIN trades t ON t.trade_date <= m.as_of
    GROUP BY m.month, t.account_id, t.instrument_id
    HAVING qty > 0.0001
),
month_aum AS (
    SELECT
        p.month,
        a.customer_id,
        SUM(p.qty * px.close_price) AS aum_eur
    FROM positions p
    JOIN month_ends m ON m.month = p.month
    JOIN prices px
      ON px.instrument_id = p.instrument_id
     AND px.price_date = m.as_of
    JOIN accounts a ON a.account_id = p.account_id
    GROUP BY p.month, a.customer_id
),
avg_aum AS (
    SELECT
        cu.segment,
        SUM(m.aum_eur) / COUNT(DISTINCT m.month) AS avg_monthly_invested_aum
    FROM month_aum m
    JOIN customers cu ON cu.customer_id = m.customer_id
    GROUP BY cu.segment
),
traded AS (
    SELECT
        cu.segment,
        SUM(t.notional_eur) AS traded_notional_eur,
        COUNT(*) AS trades
    FROM trades t
    JOIN accounts a ON a.account_id = t.account_id
    JOIN customers cu ON cu.customer_id = a.customer_id
    WHERE substr(t.trade_date, 1, 4) = '2025'
    GROUP BY cu.segment
)
SELECT
    s.segment,
    ROUND(a.avg_monthly_invested_aum, 0) AS avg_month_end_invested_aum_eur,
    ROUND(s.traded_notional_eur, 0) AS traded_notional_2025_eur,
    s.trades AS trades_2025,
    ROUND(s.traded_notional_eur / NULLIF(a.avg_monthly_invested_aum, 0), 2) AS turnover_x
FROM traded s
JOIN avg_aum a ON a.segment = s.segment
ORDER BY turnover_x DESC;
