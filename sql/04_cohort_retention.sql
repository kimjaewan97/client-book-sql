-- Question: Of the clients who opened in a given month, what share were still
-- active 3, 6 and 12 months later?
--
-- Active in a month = at least one trade, or a cash deposit, in that month.
-- The opening month itself is horizon 0 and is not a retention observation.
--
-- Right-censoring: a cohort/horizon cell is dropped unless the horizon month
-- is on or before the last month present in the price calendar. A client who
-- has not had time to reach month 12 is not counted as churned.

WITH bounds AS (
    SELECT substr(MIN(price_date), 1, 7) AS first_month,
           substr(MAX(price_date), 1, 7) AS last_month
    FROM prices
),
cohorts AS (
    SELECT
        c.customer_id,
        a.account_id,
        substr(c.onboarded_on, 1, 7) AS cohort_month
    FROM customers c
    JOIN accounts a ON a.customer_id = c.customer_id
),
activity AS (
    SELECT account_id, substr(trade_date, 1, 7) AS month
    FROM trades
    UNION
    SELECT account_id, substr(flow_date, 1, 7) AS month
    FROM cashflows
    WHERE flow_type = 'deposit'
),
horizons AS (
    SELECT 3 AS horizon
    UNION ALL SELECT 6
    UNION ALL SELECT 12
),
eligible AS (
    SELECT
        co.cohort_month,
        co.customer_id,
        co.account_id,
        h.horizon,
        strftime('%Y-%m', date(co.cohort_month || '-01', '+' || h.horizon || ' months')) AS horizon_month
    FROM cohorts co
    CROSS JOIN horizons h
    JOIN bounds b
      ON strftime('%Y-%m', date(co.cohort_month || '-01', '+' || h.horizon || ' months')) <= b.last_month
),
flags AS (
    SELECT
        e.cohort_month,
        e.horizon,
        e.customer_id,
        MAX(CASE WHEN act.month IS NOT NULL THEN 1 ELSE 0 END) AS active
    FROM eligible e
    LEFT JOIN activity act
      ON act.account_id = e.account_id
     AND act.month = e.horizon_month
    GROUP BY e.cohort_month, e.horizon, e.customer_id
)
SELECT
    cohort_month,
    horizon AS months_after_open,
    COUNT(*) AS clients_observed,
    SUM(active) AS clients_active,
    ROUND(100.0 * SUM(active) / COUNT(*), 1) AS retention_pct
FROM flags
GROUP BY cohort_month, horizon
HAVING COUNT(*) >= 12
ORDER BY cohort_month, horizon;
