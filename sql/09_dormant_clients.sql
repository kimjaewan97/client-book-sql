-- Question: How much invested wealth sits with clients who have stopped trading?
-- A client is dormant when their account is still open and their last trade
-- was more than 180 days before the last price date (or they never traded).
--
-- Caution: high-net-worth clients are scheduled to trade rarely, so this rule
-- flags a lot of them even when the relationship is healthy. The retail block
-- opened in 2025-H2 is the group that looks like a failed acquisition cohort:
-- many open accounts, little remaining wealth, and no recent orders.
-- Grain: segment x onboarding half-year, limited to dormant clients.

WITH last_day AS (
    SELECT MAX(price_date) AS as_of FROM prices
),
last_trade AS (
    SELECT account_id, MAX(trade_date) AS last_trade_on
    FROM trades
    GROUP BY account_id
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
aum AS (
    SELECT p.account_id, SUM(p.qty * px.close_price) AS aum_eur
    FROM positions p
    JOIN last_day d
    JOIN prices px
      ON px.instrument_id = p.instrument_id
     AND px.price_date = d.as_of
    GROUP BY p.account_id
),
dormant AS (
    SELECT
        cu.segment,
        CASE
            WHEN CAST(substr(cu.onboarded_on, 6, 2) AS INTEGER) <= 6
            THEN substr(cu.onboarded_on, 1, 4) || '-H1'
            ELSE substr(cu.onboarded_on, 1, 4) || '-H2'
        END AS onboard_half,
        cu.customer_id,
        COALESCE(au.aum_eur, 0) AS aum_eur
    FROM customers cu
    JOIN accounts a ON a.customer_id = cu.customer_id
    JOIN last_day d
    LEFT JOIN last_trade lt ON lt.account_id = a.account_id
    LEFT JOIN aum au ON au.account_id = a.account_id
    WHERE a.status = 'open'
      AND (
            lt.last_trade_on IS NULL
            OR julianday(d.as_of) - julianday(lt.last_trade_on) > 180
          )
)
SELECT
    segment,
    onboard_half,
    COUNT(*) AS dormant_clients,
    ROUND(SUM(aum_eur), 0) AS invested_aum_eur,
    ROUND(AVG(aum_eur), 0) AS avg_invested_aum_eur
FROM dormant
GROUP BY segment, onboard_half
ORDER BY invested_aum_eur DESC;
