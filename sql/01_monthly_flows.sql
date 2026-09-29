-- Question: How did client money and trading activity move through the book,
-- month by month?
-- Grain: calendar month.
-- Net new money = deposits + withdrawals (withdrawals are already negative).
-- Custody fees are excluded from net new money; they are revenue, not a funding flow.

WITH flows AS (
    SELECT
        substr(flow_date, 1, 7) AS month,
        SUM(CASE WHEN flow_type = 'deposit' THEN amount_eur ELSE 0 END) AS deposits_eur,
        SUM(CASE WHEN flow_type = 'withdrawal' THEN amount_eur ELSE 0 END) AS withdrawals_eur,
        SUM(CASE WHEN flow_type = 'custody_fee' THEN -amount_eur ELSE 0 END) AS custody_revenue_eur
    FROM cashflows
    GROUP BY 1
),
trading AS (
    SELECT
        substr(trade_date, 1, 7) AS month,
        COUNT(*) AS trades,
        SUM(notional_eur) AS traded_notional_eur,
        SUM(commission_eur) AS commission_eur,
        COUNT(DISTINCT account_id) AS active_accounts
    FROM trades
    GROUP BY 1
)
SELECT
    f.month,
    ROUND(f.deposits_eur, 0) AS deposits_eur,
    ROUND(f.withdrawals_eur, 0) AS withdrawals_eur,
    ROUND(f.deposits_eur + f.withdrawals_eur, 0) AS net_new_money_eur,
    COALESCE(t.trades, 0) AS trades,
    COALESCE(t.active_accounts, 0) AS accounts_that_traded,
    ROUND(COALESCE(t.traded_notional_eur, 0), 0) AS traded_notional_eur,
    ROUND(COALESCE(t.commission_eur, 0), 0) AS commission_eur,
    ROUND(f.custody_revenue_eur, 0) AS custody_revenue_eur
FROM flows f
LEFT JOIN trading t ON t.month = f.month
ORDER BY f.month;
