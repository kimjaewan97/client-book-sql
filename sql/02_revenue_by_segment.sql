-- Question: Which client segment actually pays for the platform?
-- Revenue = trade commission + custody fees (custody cashflows are negative
-- for the client, so firm revenue is the sign-flipped amount).
-- Grain: segment x country.

WITH commission AS (
    SELECT a.customer_id, SUM(t.commission_eur) AS commission_eur
    FROM trades t
    JOIN accounts a ON a.account_id = t.account_id
    GROUP BY a.customer_id
),
custody AS (
    SELECT a.customer_id, SUM(-c.amount_eur) AS custody_eur
    FROM cashflows c
    JOIN accounts a ON a.account_id = c.account_id
    WHERE c.flow_type = 'custody_fee'
    GROUP BY a.customer_id
),
client AS (
    SELECT
        cu.segment,
        cu.country,
        cu.customer_id,
        COALESCE(cm.commission_eur, 0) AS commission_eur,
        COALESCE(cs.custody_eur, 0) AS custody_eur
    FROM customers cu
    LEFT JOIN commission cm ON cm.customer_id = cu.customer_id
    LEFT JOIN custody cs ON cs.customer_id = cu.customer_id
)
SELECT
    segment,
    country,
    COUNT(*) AS clients,
    ROUND(SUM(commission_eur), 0) AS commission_eur,
    ROUND(SUM(custody_eur), 0) AS custody_eur,
    ROUND(SUM(commission_eur + custody_eur), 0) AS total_revenue_eur,
    ROUND(SUM(commission_eur + custody_eur) / COUNT(*), 0) AS revenue_per_client_eur
FROM client
GROUP BY segment, country
ORDER BY total_revenue_eur DESC;
