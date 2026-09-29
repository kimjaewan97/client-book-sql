-- Question: How concentrated is invested wealth across clients?
-- Latest invested AUM per customer, then:
--   * share held by the largest 10 clients
--   * Herfindahl-Hirschman index (sum of squared client weights)
-- HHI is on a 0–1 scale here (1 = a single client owns the book).
-- Multiply by 10,000 if you want the regulator-style index.

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
client_aum AS (
    SELECT
        a.customer_id,
        SUM(p.qty * px.close_price) AS aum_eur
    FROM positions p
    JOIN last_day d
    JOIN prices px
      ON px.instrument_id = p.instrument_id
     AND px.price_date = d.as_of
    JOIN accounts a ON a.account_id = p.account_id
    GROUP BY a.customer_id
),
ranked AS (
    SELECT
        customer_id,
        aum_eur,
        ROW_NUMBER() OVER (ORDER BY aum_eur DESC) AS aum_rank,
        SUM(aum_eur) OVER () AS total_aum
    FROM client_aum
),
weights AS (
    SELECT
        aum_rank,
        aum_eur / total_aum AS weight,
        total_aum
    FROM ranked
)
SELECT
    (SELECT as_of FROM last_day) AS as_of,
    COUNT(*) AS clients_with_a_position,
    ROUND(MAX(total_aum), 0) AS invested_aum_eur,
    ROUND(100.0 * SUM(CASE WHEN aum_rank <= 10 THEN weight ELSE 0 END), 1) AS top_10_share_pct,
    ROUND(100.0 * SUM(CASE WHEN aum_rank <= 20 THEN weight ELSE 0 END), 1) AS top_20_share_pct,
    ROUND(SUM(weight * weight), 4) AS hhi
FROM weights;
