#!/usr/bin/env python3
"""Load the CSVs into SQLite and run every analytical query.

    python generate_book.py
    python run_analysis.py

Writes data/northline.db (gitignored), results/<query>.md, and results/FINDINGS.md.
The CSVs are the source of truth. The database is rebuilt on every run.
"""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SQL = ROOT / "sql"
RESULTS = ROOT / "results"
DB = ROOT / "data" / "northline.db"

TABLES = {
    "instruments": ["instrument_id", "ticker", "name", "asset_class", "sector", "region"],
    "customers": ["customer_id", "segment", "country", "risk_profile", "onboarded_on", "status"],
    "accounts": ["account_id", "customer_id", "opened_on", "closed_on", "status"],
    "prices": ["instrument_id", "price_date", "close_price"],
    "trades": ["trade_id", "account_id", "instrument_id", "trade_date", "side", "quantity", "price", "notional_eur", "commission_eur"],
    "cashflows": ["cashflow_id", "account_id", "flow_date", "flow_type", "amount_eur"],
}


def load(connection: sqlite3.Connection) -> None:
    connection.executescript((SQL / "00_schema.sql").read_text(encoding="utf-8"))
    for table, columns in TABLES.items():
        path = DATA / f"{table}.csv"
        with path.open(newline="", encoding="utf-8") as handle:
            rows = []
            for record in csv.DictReader(handle):
                values = []
                for column in columns:
                    raw = record[column]
                    if raw == "" and column == "closed_on":
                        values.append(None)
                    else:
                        values.append(raw)
                rows.append(values)
        placeholders = ", ".join("?" for _ in columns)
        connection.executemany(
            f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
            rows,
        )
    connection.commit()


def markdown_table(headers: list[str], rows: list[tuple]) -> str:
    def cell(value: object) -> str:
        if value is None:
            return ""
        return str(value)

    head = "| " + " | ".join(headers) + " |"
    rule = "| " + " | ".join("---" for _ in headers) + " |"
    body = ["| " + " | ".join(cell(value) for value in row) + " |" for row in rows]
    return "\n".join([head, rule, *body])


def run_queries(connection: sqlite3.Connection) -> dict[str, list[tuple]]:
    RESULTS.mkdir(parents=True, exist_ok=True)
    captured = {}
    for path in sorted(SQL.glob("*.sql")):
        if path.name.startswith("00_"):
            continue
        sql = path.read_text(encoding="utf-8")
        cursor = connection.execute(sql)
        headers = [item[0] for item in cursor.description]
        rows = cursor.fetchall()
        captured[path.name] = rows
        title = path.stem.replace("_", " ")
        text = f"# {title}\n\n{markdown_table(headers, rows)}\n"
        (RESULTS / f"{path.stem}.md").write_text(text, encoding="utf-8")
        print(f"{path.name}: {len(rows)} rows")
    return captured


def write_findings(connection: sqlite3.Connection) -> None:
    def one(sql: str) -> tuple:
        return connection.execute(sql).fetchone()

    clients, trades, flows = one(
        "SELECT (SELECT COUNT(*) FROM customers), (SELECT COUNT(*) FROM trades), (SELECT COUNT(*) FROM cashflows)"
    )
    as_of, aum, top10, hhi = one(
        """
        WITH last_day AS (SELECT MAX(price_date) AS as_of FROM prices),
        positions AS (
            SELECT account_id, instrument_id,
                   SUM(CASE WHEN side = 'buy' THEN quantity ELSE -quantity END) AS qty
            FROM trades GROUP BY 1, 2 HAVING qty > 0.0001
        ),
        client_aum AS (
            SELECT a.customer_id, SUM(p.qty * px.close_price) AS aum
            FROM positions p
            JOIN last_day d JOIN prices px
              ON px.instrument_id = p.instrument_id AND px.price_date = d.as_of
            JOIN accounts a ON a.account_id = p.account_id
            GROUP BY a.customer_id
        ),
        ranked AS (
            SELECT aum, ROW_NUMBER() OVER (ORDER BY aum DESC) AS rk, SUM(aum) OVER () AS total
            FROM client_aum
        )
        SELECT
            (SELECT as_of FROM last_day),
            ROUND(MAX(total), 0),
            ROUND(100.0 * SUM(CASE WHEN rk <= 10 THEN aum ELSE 0 END) / MAX(total), 1),
            ROUND(SUM((aum / total) * (aum / total)), 4)
        FROM ranked
        """
    )
    mix = connection.execute(
        """
        WITH commission AS (
            SELECT a.customer_id, cu.segment, SUM(t.commission_eur) AS commission_eur
            FROM trades t
            JOIN accounts a ON a.account_id = t.account_id
            JOIN customers cu ON cu.customer_id = a.customer_id
            GROUP BY a.customer_id
        ),
        custody AS (
            SELECT a.customer_id, cu.segment, SUM(-c.amount_eur) AS custody_eur
            FROM cashflows c
            JOIN accounts a ON a.account_id = c.account_id
            JOIN customers cu ON cu.customer_id = a.customer_id
            WHERE c.flow_type = 'custody_fee'
            GROUP BY a.customer_id
        ),
        segments AS (SELECT DISTINCT segment FROM customers)
        SELECT s.segment,
               ROUND(COALESCE(SUM(cm.commission_eur), 0), 0),
               ROUND(COALESCE(SUM(cs.custody_eur), 0), 0)
        FROM segments s
        LEFT JOIN customers cu ON cu.segment = s.segment
        LEFT JOIN commission cm ON cm.customer_id = cu.customer_id
        LEFT JOIN custody cs ON cs.customer_id = cu.customer_id
        GROUP BY s.segment
        ORDER BY s.segment
        """
    ).fetchall()
    cohort_sql = (SQL / "04_cohort_retention.sql").read_text(encoding="utf-8")
    cohort_rows = connection.execute(cohort_sql).fetchall()
    early = [row for row in cohort_rows if row[0] <= "2024-06" and row[1] == 6]
    promo = [row for row in cohort_rows if row[0] in {"2025-07", "2025-08", "2025-09"} and row[1] == 6]

    def avg(rows: list[tuple]) -> float | None:
        if not rows:
            return None
        observed = sum(row[2] for row in rows)
        active = sum(row[3] for row in rows)
        return 100.0 * active / observed

    early_avg = avg(early)
    promo_avg = avg(promo)
    tech = connection.execute(
        """
        WITH last_day AS (SELECT MAX(price_date) AS as_of FROM prices),
        positions AS (
            SELECT instrument_id,
                   SUM(CASE WHEN side = 'buy' THEN quantity ELSE -quantity END) AS qty
            FROM trades GROUP BY 1 HAVING qty > 0.0001
        ),
        valued AS (
            SELECT i.sector, SUM(p.qty * px.close_price) AS mv
            FROM positions p
            JOIN instruments i ON i.instrument_id = p.instrument_id
            JOIN last_day d JOIN prices px
              ON px.instrument_id = p.instrument_id AND px.price_date = d.as_of
            GROUP BY i.sector
        )
        SELECT sector, ROUND(100.0 * mv / (SELECT SUM(mv) FROM valued), 1)
        FROM valued
        ORDER BY mv DESC
        LIMIT 1
        """
    ).fetchone()

    mix_lines = "\n".join(
        f"* **{segment}** — commission €{commission:,.0f}, custody €{custody:,.0f}"
        for segment, commission, custody in mix
    )
    early_txt = "n/a" if early_avg is None else f"{early_avg:.1f}%"
    promo_txt = "n/a" if promo_avg is None else f"{promo_avg:.1f}%"
    text = f"""# What the queries show

The book is fictional (see `generate_book.py`) and the figures below are produced by the SQL in `sql/`, not typed in by hand.

* **{clients} clients**, **{trades:,} trades**, **{flows:,} cash movements**.
* Invested AUM on **{as_of}** is **€{aum:,.0f}**. The largest 10 clients hold **{top10}%**. Client-level HHI is **{hhi}** (0–1 scale).
* Largest sector sleeve: **{tech[0]}** at **{tech[1]}%** of invested AUM.
* Six-month activity retention averages **{early_txt}** for cohorts opened in the first half of 2024, versus **{promo_txt}** for the July–September 2025 cohorts. Horizons that run past the sample end are excluded, so this is not a censoring artifact.

Revenue by segment:

{mix_lines}

Read `results/` for the full grids. Each file matches one query.
"""
    (RESULTS / "FINDINGS.md").write_text(text, encoding="utf-8")
    print(text)


def main() -> None:
    if DB.exists():
        DB.unlink()
    connection = sqlite3.connect(DB)
    connection.row_factory = sqlite3.Row
    load(connection)
    # Row factory makes markdown harder; use plain tuples for query output.
    connection.row_factory = None
    run_queries(connection)
    write_findings(connection)


if __name__ == "__main__":
    main()
