-- Question: Is the firm paid for trading, or for keeping assets?
-- Grain: segment. Share columns are within the segment, not of the whole firm.

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
)
SELECT
    cu.segment,
    COUNT(*) AS clients,
    ROUND(SUM(COALESCE(cm.commission_eur, 0)), 0) AS commission_eur,
    ROUND(SUM(COALESCE(cs.custody_eur, 0)), 0) AS custody_eur,
    ROUND(
        100.0 * SUM(COALESCE(cm.commission_eur, 0))
        / NULLIF(SUM(COALESCE(cm.commission_eur, 0) + COALESCE(cs.custody_eur, 0)), 0),
        1
    ) AS commission_share_pct,
    ROUND(
        100.0 * SUM(COALESCE(cs.custody_eur, 0))
        / NULLIF(SUM(COALESCE(cm.commission_eur, 0) + COALESCE(cs.custody_eur, 0)), 0),
        1
    ) AS custody_share_pct
FROM customers cu
LEFT JOIN commission cm ON cm.customer_id = cu.customer_id
LEFT JOIN custody cs ON cs.customer_id = cu.customer_id
GROUP BY cu.segment
ORDER BY SUM(COALESCE(cm.commission_eur, 0) + COALESCE(cs.custody_eur, 0)) DESC;
