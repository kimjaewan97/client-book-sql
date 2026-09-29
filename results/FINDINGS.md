# What the queries show

The book is fictional (see `generate_book.py`) and the figures below are produced by the SQL in `sql/`, not typed in by hand.

* **450 clients**, **9,693 trades**, **8,224 cash movements**.
* Invested AUM on **2026-06-30** is **€18,267,860**. The largest 10 clients hold **25.3%**. Client-level HHI is **0.0125** (0–1 scale).
* Largest sector sleeve: **Diversified** at **32.5%** of invested AUM.
* Six-month activity retention averages **49.4%** for cohorts opened in the first half of 2024, versus **29.4%** for the July–September 2025 cohorts. Horizons that run past the sample end are excluded, so this is not a censoring artifact.

Revenue by segment:

* **affluent** — commission €16,789, custody €8,521
* **hnw** — commission €9,457, custody €10,162
* **retail** — commission €34,197, custody €3,908

Read `results/` for the full grids. Each file matches one query.
