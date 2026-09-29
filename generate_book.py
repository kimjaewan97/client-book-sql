#!/usr/bin/env python3
"""Create a reproducible fictional EUR brokerage book.

Python is only the data factory. The analysis lives in sql/.
Uses the standard library so a reviewer can regenerate the CSVs with:

    python generate_book.py

Seed, calendar and fee schedule are fixed. Do not hand-edit data/*.csv —
change this file and regenerate.
"""

from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SEED = 7
N_CUSTOMERS = 450
FIRST_DAY = date(2024, 1, 2)
LAST_DAY = date(2026, 6, 30)

# Annual custody fee charged monthly on invested market value.
CUSTODY_ANNUAL = {"retail": 0.0018, "affluent": 0.0012, "hnw": 0.0007}

INSTRUMENTS = [
    # ticker, name, asset_class, sector, region, start_price, ann_drift, ann_vol, beta
    ("NXLF", "Nexalift", "equity", "Technology", "Europe", 86.0, 0.11, 0.30, 1.25),
    ("VELD", "Veld Semiconductor", "equity", "Technology", "Europe", 210.0, 0.16, 0.36, 1.40),
    ("ORBN", "Orbin Software", "equity", "Technology", "United States", 140.0, 0.09, 0.28, 1.15),
    ("KITE", "Kite Cloud", "equity", "Technology", "United States", 54.0, 0.18, 0.42, 1.50),
    ("HALD", "Hald Industrial", "equity", "Industrials", "Europe", 118.0, 0.07, 0.20, 1.00),
    ("BRUK", "Bruk Engineering", "equity", "Industrials", "Europe", 73.0, 0.06, 0.18, 0.90),
    ("MERO", "Mero Logistics", "equity", "Industrials", "United States", 47.0, 0.08, 0.22, 1.05),
    ("FENN", "Fenn Bank", "equity", "Financials", "Europe", 36.0, 0.09, 0.24, 1.15),
    ("ALBA", "Alba Insurance", "equity", "Financials", "Europe", 91.0, 0.05, 0.16, 0.85),
    ("CORT", "Cort Capital", "equity", "Financials", "United States", 64.0, 0.10, 0.26, 1.20),
    ("LIRA", "Lira Health", "equity", "Health Care", "Europe", 152.0, 0.06, 0.18, 0.70),
    ("NUVA", "Nuva Pharma", "equity", "Health Care", "United States", 77.0, 0.07, 0.22, 0.80),
    ("SELA", "Sela Medtech", "equity", "Health Care", "Europe", 41.0, 0.08, 0.27, 0.90),
    ("PINE", "Pine Energy", "equity", "Energy", "Europe", 33.0, 0.05, 0.28, 0.80),
    ("DUNE", "Dune Resources", "equity", "Energy", "United States", 58.0, 0.04, 0.26, 0.75),
    ("WEUR", "World Equity ETF", "etf", "Diversified", "Global", 100.0, 0.07, 0.14, 1.00),
    ("EEUR", "Europe Equity ETF", "etf", "Diversified", "Europe", 80.0, 0.06, 0.15, 1.05),
    ("EMKT", "Emerging Markets ETF", "etf", "Diversified", "Emerging", 45.0, 0.08, 0.19, 1.10),
    ("BAGG", "Euro Aggregate Bond ETF", "etf", "Fixed Income", "Europe", 102.0, 0.025, 0.045, 0.10),
    ("BUND", "Euro Government Bond", "bond", "Fixed Income", "Europe", 99.0, 0.020, 0.040, 0.05),
    ("CORP", "Euro Corporate Bond", "bond", "Fixed Income", "Europe", 101.0, 0.028, 0.055, 0.15),
]


def business_days(start: date, end: date) -> list[date]:
    days = []
    cursor = start
    while cursor <= end:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor += timedelta(days=1)
    return days


def month_ends(days: list[date]) -> list[date]:
    last: dict[tuple[int, int], date] = {}
    for day in days:
        last[(day.year, day.month)] = day
    return [last[key] for key in sorted(last)]


def add_months(day: date, months: int) -> date:
    month_index = day.month - 1 + months
    year = day.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def pick(rng: random.Random, options: list[tuple[str, float]]) -> str:
    roll = rng.random()
    upto = 0.0
    for label, weight in options:
        upto += weight
        if roll <= upto:
            return label
    return options[-1][0]


def money(value: float) -> float:
    return round(value, 2)


def commission(segment: str, notional: float) -> float:
    if segment == "retail":
        return money(max(4.90, 0.0012 * notional))
    if segment == "affluent":
        return money(max(8.00, 0.0008 * notional))
    return money(max(15.00, 0.00035 * notional))


def initial_deposit(segment: str, rng: random.Random) -> float:
    if segment == "retail":
        return money(min(28000.0, max(900.0, rng.lognormvariate(8.55, 0.38))))
    if segment == "affluent":
        return money(min(200000.0, max(18000.0, rng.lognormvariate(10.65, 0.30))))
    return money(min(2_400_000.0, max(90_000.0, rng.lognormvariate(12.35, 0.45))))


def build_prices(days: list[date], rng: random.Random) -> dict[tuple[int, date], float]:
    prices: dict[tuple[int, date], float] = {}
    levels = {i: spec[5] for i, spec in enumerate(INSTRUMENTS, start=1)}
    for day in days:
        market = rng.normalvariate(0.00022, 0.0085)
        sector_shock = {}
        for spec in INSTRUMENTS:
            sector_shock.setdefault(spec[3], rng.normalvariate(0.0, 0.0045))
        for instrument_id, spec in enumerate(INSTRUMENTS, start=1):
            _ticker, _name, _asset, sector, _region, _start, drift, vol, beta = spec
            idiosyncratic = rng.normalvariate(0.0, vol / (252 ** 0.5) * 0.85)
            move = drift / 252 + beta * market * 0.65 + sector_shock[sector] + idiosyncratic * 0.55
            move = max(-0.12, min(0.12, move))
            levels[instrument_id] *= 2.718281828 ** move
            prices[(instrument_id, day)] = round(levels[instrument_id], 4)
    return prices


def weight_plan(profile: str, rng: random.Random) -> dict[int, float]:
    """Instrument id -> target weight of the amount being invested."""
    groups = {
        "tech": [],
        "other_equity": [],
        "etf": [],
        "bond": [],
    }
    for instrument_id, spec in enumerate(INSTRUMENTS, start=1):
        asset, sector = spec[2], spec[3]
        if asset == "bond" or sector == "Fixed Income":
            groups["bond"].append(instrument_id)
        elif asset == "etf":
            groups["etf"].append(instrument_id)
        elif sector == "Technology":
            groups["tech"].append(instrument_id)
        else:
            groups["other_equity"].append(instrument_id)

    if profile == "conservative":
        buckets = [("bond", 0.55), ("etf", 0.30), ("other_equity", 0.12), ("tech", 0.03)]
    elif profile == "balanced":
        buckets = [("bond", 0.18), ("etf", 0.42), ("other_equity", 0.28), ("tech", 0.12)]
    else:
        buckets = [("bond", 0.04), ("etf", 0.16), ("other_equity", 0.25), ("tech", 0.55)]

    raw: dict[int, float] = {}
    for name, bucket_weight in buckets:
        members = groups[name]
        noise = [rng.uniform(0.7, 1.3) for _ in members]
        scale = sum(noise)
        for instrument_id, tilt in zip(members, noise):
            raw[instrument_id] = bucket_weight * tilt / scale
    total = sum(raw.values())
    return {instrument_id: weight / total for instrument_id, weight in raw.items()}


def on_or_after(days: list[date], day: date) -> date:
    for candidate in days:
        if candidate >= day:
            return candidate
    return days[-1]


def main() -> None:
    rng = random.Random(SEED)
    days = business_days(FIRST_DAY, LAST_DAY)
    ends = month_ends(days)
    day_index = {day: i for i, day in enumerate(days)}
    prices = build_prices(days, rng)

    customers = []
    accounts = []
    trades = []
    cashflows = []
    trade_id = 1
    cashflow_id = 1

    def add_cash(account_id: int, flow_date: date, flow_type: str, amount: float) -> None:
        nonlocal cashflow_id
        cashflows.append(
            {
                "cashflow_id": cashflow_id,
                "account_id": account_id,
                "flow_date": flow_date.isoformat(),
                "flow_type": flow_type,
                "amount_eur": money(amount),
            }
        )
        cashflow_id += 1

    def add_trade(account_id: int, instrument_id: int, trade_date: date, side: str, quantity: float, price: float, segment: str) -> float:
        nonlocal trade_id
        notional = quantity * price
        fee = commission(segment, notional)
        trades.append(
            {
                "trade_id": trade_id,
                "account_id": account_id,
                "instrument_id": instrument_id,
                "trade_date": trade_date.isoformat(),
                "side": side,
                "quantity": round(quantity, 4),
                "price": round(price, 4),
                "notional_eur": money(notional),
                "commission_eur": fee,
            }
        )
        trade_id += 1
        return fee

    promo_months = {date(2025, 7, 1), date(2025, 8, 1), date(2025, 9, 1)}

    for customer_id in range(1, N_CUSTOMERS + 1):
        segment = pick(rng, [("retail", 0.68), ("affluent", 0.24), ("hnw", 0.08)])
        country = pick(rng, [("DE", 0.52), ("AT", 0.10), ("CH", 0.13), ("NL", 0.14), ("FR", 0.11)])
        if country == "CH" and segment == "retail" and rng.random() < 0.30:
            segment = "affluent"
        if segment == "hnw":
            profile = pick(rng, [("conservative", 0.34), ("balanced", 0.46), ("growth", 0.20)])
        elif segment == "affluent":
            profile = pick(rng, [("conservative", 0.24), ("balanced", 0.52), ("growth", 0.24)])
        else:
            profile = pick(rng, [("conservative", 0.18), ("balanced", 0.36), ("growth", 0.46)])

        promo = segment == "retail" and rng.random() < 0.22
        if promo:
            month_start = rng.choice(list(promo_months))
            onboard = on_or_after(days, month_start + timedelta(days=rng.randint(0, 20)))
        else:
            latest = date(2025, 12, 15)
            window = [day for day in days if day <= latest]
            onboard = rng.choice(window)

        deposit = initial_deposit(segment, rng)
        customers.append(
            {
                "customer_id": customer_id,
                "segment": segment,
                "country": country,
                "risk_profile": profile,
                "onboarded_on": onboard.isoformat(),
                "status": "open",
            }
        )
        accounts.append(
            {
                "account_id": customer_id,
                "customer_id": customer_id,
                "opened_on": onboard.isoformat(),
                "closed_on": "",
                "status": "open",
            }
        )

        cash = deposit
        positions = {instrument_id: 0.0 for instrument_id in range(1, len(INSTRUMENTS) + 1)}
        add_cash(customer_id, onboard, "deposit", deposit)

        plan = weight_plan(profile, rng)
        investable = cash * 0.93
        for instrument_id, weight in plan.items():
            if weight < 0.02:
                continue
            price = prices[(instrument_id, onboard)]
            notional = investable * weight
            quantity = notional / price
            if notional < 25 or cash < notional + commission(segment, notional):
                continue
            fee = add_trade(customer_id, instrument_id, onboard, "buy", quantity, price, segment)
            cash -= notional + fee
            positions[instrument_id] += quantity

        # Retail promo cohorts go quiet early. The flag is behavior, not a column.
        goes_quiet = promo and rng.random() < 0.70
        quiet_on = add_months(onboard, 2) if goes_quiet else None
        quiet_done = False
        trade_chance = {"retail": 0.42, "affluent": 0.26, "hnw": 0.15}[segment]
        if profile == "growth":
            trade_chance += 0.16
        if profile == "conservative":
            trade_chance -= 0.08

        for as_of in ends:
            if as_of <= onboard:
                continue
            invested = 0.0
            for instrument_id, quantity in positions.items():
                if quantity > 0:
                    invested += quantity * prices[(instrument_id, as_of)]

            if quiet_on is not None and as_of >= quiet_on and not quiet_done:
                quiet_done = True
                if rng.random() < 0.60:
                    for instrument_id, quantity in list(positions.items()):
                        if quantity <= 0 or rng.random() > 0.5:
                            continue
                        sell_qty = quantity * rng.uniform(0.25, 0.55)
                        price = prices[(instrument_id, as_of)]
                        fee = add_trade(customer_id, instrument_id, as_of, "sell", sell_qty, price, segment)
                        cash += sell_qty * price - fee
                        positions[instrument_id] -= sell_qty
                    withdrawal = cash * rng.uniform(0.35, 0.75)
                    if withdrawal > 20:
                        add_cash(customer_id, as_of, "withdrawal", -withdrawal)
                        cash -= withdrawal

            quiet = quiet_done
            if not quiet and rng.random() < trade_chance:
                side = "buy" if rng.random() < 0.62 or invested < 50 else "sell"
                if side == "sell":
                    held = [i for i, q in positions.items() if q * prices[(i, as_of)] > 40]
                    if not held:
                        side = "buy"
                    else:
                        instrument_id = rng.choice(held)
                        price = prices[(instrument_id, as_of)]
                        sell_qty = positions[instrument_id] * rng.uniform(0.08, 0.25)
                        fee = add_trade(customer_id, instrument_id, as_of, "sell", sell_qty, price, segment)
                        cash += sell_qty * price - fee
                        positions[instrument_id] -= sell_qty
                if side == "buy" and cash > 80:
                    if profile == "growth" and rng.random() < 0.65:
                        choices = [i for i, spec in enumerate(INSTRUMENTS, start=1) if spec[3] == "Technology"]
                    elif profile == "conservative":
                        choices = [i for i, spec in enumerate(INSTRUMENTS, start=1) if spec[3] == "Fixed Income" or spec[2] == "etf"]
                    else:
                        choices = list(range(1, len(INSTRUMENTS) + 1))
                    instrument_id = rng.choice(choices)
                    price = prices[(instrument_id, as_of)]
                    notional = min(cash * rng.uniform(0.06, 0.18), cash - 10)
                    fee_estimate = commission(segment, notional)
                    if notional > 30 and cash >= notional + fee_estimate:
                        quantity = notional / price
                        fee = add_trade(customer_id, instrument_id, as_of, "buy", quantity, price, segment)
                        cash -= notional + fee
                        positions[instrument_id] += quantity

            if not quiet and rng.random() < {"retail": 0.08, "affluent": 0.12, "hnw": 0.16}[segment]:
                topup = initial_deposit(segment, rng) * rng.uniform(0.08, 0.30)
                add_cash(customer_id, as_of, "deposit", topup)
                cash += topup

            invested = sum(
                quantity * prices[(instrument_id, as_of)]
                for instrument_id, quantity in positions.items()
                if quantity > 0
            )
            fee_due = invested * CUSTODY_ANNUAL[segment] / 12
            if fee_due >= 0.5:
                add_cash(customer_id, as_of, "custody_fee", -money(fee_due))
                cash = max(0.0, cash - fee_due)

            still_invested = any(quantity > 0.01 for quantity in positions.values())
            if quiet and cash < 30 and not still_invested:
                customers[-1]["status"] = "closed"
                accounts[-1]["status"] = "closed"
                accounts[-1]["closed_on"] = as_of.isoformat()
                break

        _ = day_index  # calendar is complete; index reserved if a future path needs it

    DATA.mkdir(parents=True, exist_ok=True)
    write_csv(
        DATA / "instruments.csv",
        ["instrument_id", "ticker", "name", "asset_class", "sector", "region"],
        [
            {
                "instrument_id": i,
                "ticker": spec[0],
                "name": spec[1],
                "asset_class": spec[2],
                "sector": spec[3],
                "region": spec[4],
            }
            for i, spec in enumerate(INSTRUMENTS, start=1)
        ],
    )
    write_csv(DATA / "customers.csv", ["customer_id", "segment", "country", "risk_profile", "onboarded_on", "status"], customers)
    write_csv(DATA / "accounts.csv", ["account_id", "customer_id", "opened_on", "closed_on", "status"], accounts)
    write_csv(
        DATA / "prices.csv",
        ["instrument_id", "price_date", "close_price"],
        [
            {"instrument_id": instrument_id, "price_date": day.isoformat(), "close_price": price}
            for (instrument_id, day), price in prices.items()
        ],
    )
    write_csv(
        DATA / "trades.csv",
        ["trade_id", "account_id", "instrument_id", "trade_date", "side", "quantity", "price", "notional_eur", "commission_eur"],
        trades,
    )
    write_csv(
        DATA / "cashflows.csv",
        ["cashflow_id", "account_id", "flow_date", "flow_type", "amount_eur"],
        cashflows,
    )
    print(f"customers {len(customers)} trades {len(trades)} cashflows {len(cashflows)} price rows {len(prices)}")


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
