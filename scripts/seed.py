#!/usr/bin/env python3
"""Deterministic synthetic marketplace telemetry, bulk-loaded into Neon.

Run: .venv/bin/python scripts/seed.py
Requires DATABASE_URL_DIRECT (preferred) or DATABASE_URL. Never prints credentials.
Only the dedicated talentpulse schema is modified; --reset explicitly rebuilds it.
Loads commit in bounded batches; the completion manifest is written last. An
interrupted load remains detectable and requires --reset before another load.
"""

from __future__ import annotations

import argparse
import os
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from itertools import islice
from pathlib import Path

import numpy as np
import psycopg


ROOT = Path(__file__).resolve().parents[1]
SEED_VERSION = "talentpulse-v1"
START = date(2026, 8, 10)
END = date(2026, 10, 4)
EXPERIMENT_START = date(2026, 9, 21)
EXPERIMENT_ID = "ai-ranking-v1"
MARKETS = ["Germany", "Austria", "Belgium", "Netherlands", "UK"]
DEVICES = ["desktop", "mobile", "tablet"]
USER_TYPES = ["new", "returning"]
LEVELS = ["junior", "mid", "senior"]
CATEGORIES = ["Data & Analytics", "Engineering", "Product & Design", "Sales & Marketing", "Operations", "Healthcare", "Finance"]
TRAFFIC = ["organic", "paid_search", "email", "direct", "referral"]
VARIANTS = ["control", "gpt4o", "ollama"]
CITIES = {
    "Germany": ["Düsseldorf", "Berlin", "Hamburg", "Munich", "Frankfurt", "Cologne"],
    "Austria": ["Vienna", "Graz", "Linz", "Salzburg"],
    "Belgium": ["Brussels", "Antwerp", "Ghent", "Leuven"],
    "Netherlands": ["Amsterdam", "Rotterdam", "Utrecht", "Eindhoven"],
    "UK": ["London", "Manchester", "Birmingham", "Leeds", "Edinburgh"],
}
TITLES = {
    "Data & Analytics": ["Product Analyst", "Data Analyst", "Analytics Engineer", "BI Analyst", "Data Scientist"],
    "Engineering": ["Software Engineer", "Backend Engineer", "Frontend Engineer", "Platform Engineer", "QA Engineer"],
    "Product & Design": ["Product Manager", "UX Researcher", "Product Designer", "UX Designer"],
    "Sales & Marketing": ["Account Manager", "Growth Analyst", "Marketing Manager", "Sales Executive"],
    "Operations": ["Operations Analyst", "Supply Chain Specialist", "Project Manager", "Customer Success Manager"],
    "Healthcare": ["Registered Nurse", "Clinical Coordinator", "Healthcare Analyst", "Physiotherapist"],
    "Finance": ["Financial Analyst", "Accountant", "Risk Analyst", "Finance Manager"],
}


def load_env() -> None:
    """Read local .env without shell expansion or logging sensitive values."""
    env_path = ROOT / ".env"
    if env_path.exists():
        for raw in env_path.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def copy_rows(conn, table: str, columns: list[str], rows) -> int:
    """Bound COPY statements so PostgreSQL's FK trigger queue fits small compute."""
    count = 0
    iterator = iter(rows)
    while batch := list(islice(iterator, 10000)):
        with conn.cursor().copy(f"COPY talentpulse.{table} ({','.join(columns)}) FROM STDIN") as copy:
            for row in batch:
                copy.write_row(row)
                count += 1
        conn.commit()
    return count


def make_data(seed: int, users_count: int, jobs_count: int, sessions_count: int) -> dict:
    rng = np.random.default_rng(seed)
    market_ids = rng.choice(5, users_count, p=[.52, .10, .09, .12, .17])
    device_ids = rng.choice(3, users_count, p=[.43, .52, .05])
    user_type_ids = rng.choice(2, users_count, p=[.33, .67])
    level_ids = rng.choice(3, users_count, p=[.30, .48, .22])
    role_ids = rng.choice(7, users_count, p=[.17, .25, .11, .14, .13, .10, .10])
    assignment = rng.choice(3, users_count, p=[1 / 3] * 3)
    users = []
    for i in range(users_count):
        market = MARKETS[market_ids[i]]
        registered = START - timedelta(days=int(rng.integers(1, 31) if user_type_ids[i] == 0 else rng.integers(40, 720)))
        users.append((i + 1, market, DEVICES[device_ids[i]], USER_TYPES[user_type_ids[i]], LEVELS[level_ids[i]],
                      CATEGORIES[role_ids[i]], str(rng.choice(CITIES[market])), registered))

    jobs = []
    pools: dict[tuple[int, int], list[int]] = defaultdict(list)
    job_market_ids = rng.choice(5, jobs_count, p=[.52, .10, .09, .12, .17])
    job_category_ids = rng.choice(7, jobs_count, p=[.17, .25, .11, .14, .13, .10, .10])
    salary_base = [65000, 72000, 68000, 52000, 48000, 44000, 62000]
    for i in range(jobs_count):
        market_idx, category_idx = int(job_market_ids[i]), int(job_category_ids[i])
        market, category = MARKETS[market_idx], CATEGORIES[category_idx]
        level = int(rng.choice(3, p=[.28, .48, .24]))
        low = int(max(28000, salary_base[category_idx] * [.69, 1., 1.42][level] * rng.uniform(.84, 1.12)) / 1000) * 1000
        high = low + int(rng.integers(8, 22)) * 1000
        jobs.append((i + 1, category, str(rng.choice(TITLES[category])), market, str(rng.choice(CITIES[market])),
                     low, high, str(rng.choice(["on_site", "hybrid", "remote"], p=[.34, .49, .17])),
                     LEVELS[level], START - timedelta(days=int(rng.integers(0, 14)))))
        pools[(market_idx, category_idx)].append(i + 1)

    dates = [START + timedelta(days=i) for i in range((END - START).days + 1)]
    day_weights = np.array([(0.67 if d.weekday() >= 5 else 1.0) * (0.94 + i * .003)
                            for i, d in enumerate(dates)])
    days = rng.choice(len(dates), sessions_count, p=day_weights / day_weights.sum())
    seconds = np.clip(rng.normal(14 * 3600, 4.3 * 3600, sessions_count), 300, 85800).astype(np.int32)
    order = np.lexsort((seconds, days))
    days, seconds = days[order], seconds[order]
    user_indices = rng.integers(0, users_count, sessions_count)
    session_markets = market_ids[user_indices]
    session_devices = device_ids[user_indices].copy()
    alternate_device = rng.random(sessions_count) < .11
    session_devices[alternate_device] = rng.choice(3, alternate_device.sum(), p=[.43, .52, .05])
    session_types = user_type_ids[user_indices]
    session_levels = level_ids[user_indices]
    session_categories = role_ids[user_indices].copy()
    cross_category = rng.random(sessions_count) < .18
    session_categories[cross_category] = rng.integers(0, 7, cross_category.sum())
    traffic_ids = rng.choice(5, sessions_count, p=[.38, .21, .13, .19, .09])
    experiment_day = (EXPERIMENT_START - START).days
    in_experiment = days >= experiment_day
    variants = np.where(in_experiment, assignment[user_indices], 0)
    job_ids = np.empty(sessions_count, dtype=np.int32)
    for market_idx in range(5):
        for category_idx in range(7):
            mask = (session_markets == market_idx) & (session_categories == category_idx)
            job_ids[mask] = rng.choice(pools[(market_idx, category_idx)], mask.sum())

    release_affected = ((days >= (date(2026, 9, 18) - START).days)
                        & (days <= (date(2026, 9, 22) - START).days)
                        & (session_devices == 1))
    search_success_p = .964 - .014 * (session_devices == 1) - .012 * (session_markets == 4)
    search = rng.random(sessions_count) < search_success_p
    engagement_p = .72 + .055 * (variants == 1) + .039 * (variants == 2)
    engagement_p -= .044 * (session_markets == 4) + .032 * (session_types == 0)
    job_view = search & (rng.random(sessions_count) < engagement_p)
    apply_p = .15 + .013 * (variants != 0) - .02 * (session_markets == 4)
    apply_clicked = job_view & (rng.random(sessions_count) < apply_p)
    app_started = apply_clicked & (rng.random(sessions_count) < .91)
    error_p = (.026 + .085 * (session_devices == 1) + .015 * (session_types == 0)
               + .22 * release_affected)
    app_error = app_started & (rng.random(sessions_count) < error_p)
    cv_p = .91 - .20 * (session_devices == 1) - .11 * (session_types == 0)
    cv_uploaded = app_started & ~app_error & (rng.random(sessions_count) < cv_p)
    complete_p = .88 - .16 * (session_types == 0) - .07 * (session_markets == 4)
    app_submitted = cv_uploaded & (rng.random(sessions_count) < complete_p)

    # Predeclare one user-level Bernoulli outcome. Choose one exposed session for
    # each converter, so repeated visits never inflate the inferential sample.
    weights = (np.choose(device_ids, [1.18, .77, .88])
               * np.choose(user_type_ids, [.70, 1.14])
               * np.choose(market_ids, [1.07, 1.01, .97, 1.02, .69]))
    target = np.array([.081, .103, .097])
    mean_weights = np.array([weights[assignment == variant].mean() for variant in range(3)])
    user_convert = rng.random(users_count) < target[assignment] * weights / mean_weights[assignment]
    final_exposure = np.full(users_count, -1, dtype=np.int64)
    experiment_indices = np.flatnonzero(in_experiment)
    np.maximum.at(final_exposure, user_indices[experiment_indices], experiment_indices)
    forced = final_exposure[user_convert & (final_exposure >= 0)]
    app_submitted[in_experiment] = False
    app_submitted[forced] = True
    search[forced] = job_view[forced] = apply_clicked[forced] = app_started[forced] = cv_uploaded[forced] = True
    app_error[forced] = False

    latencies = rng.lognormal(np.log(480), .24, sessions_count).astype(np.int32)
    latencies += (session_devices == 1) * 190 + (session_devices == 2) * 110
    latencies += (variants == 1) * rng.integers(450, 850, sessions_count)
    latencies += (variants == 2) * rng.integers(800, 1400, sessions_count)
    latencies += release_affected * rng.integers(150, 450, sessions_count)
    costs = np.where(variants == 1, .0018, np.where(variants == 2, .0007, 0.0))
    result_count = np.where(search, rng.integers(18, 86, sessions_count), 0)
    ai = variants != 0
    event_count = int(sessions_count + 5 * search.sum() + job_view.sum() + apply_clicked.sum()
                      + app_started.sum() + 2 * cv_uploaded.sum() + app_submitted.sum()
                      + app_error.sum() + (ai & search).sum() + (ai & job_view).sum())
    return locals()


def session_rows(data):
    for i in range(data["sessions_count"]):
        day = data["dates"][int(data["days"][i])]
        occurred = datetime.combine(day, time(), timezone.utc) + timedelta(seconds=int(data["seconds"][i]))
        user_index = int(data["user_indices"][i])
        yield (i + 1, user_index + 1, int(data["job_ids"][i]), occurred, day,
               MARKETS[data["session_markets"][i]], DEVICES[data["session_devices"][i]],
               USER_TYPES[data["session_types"][i]], CATEGORIES[data["session_categories"][i]],
               TRAFFIC[data["traffic_ids"][i]], LEVELS[data["session_levels"][i]], VARIANTS[data["variants"][i]],
               bool(data["search"][i]), bool(data["job_view"][i]), bool(data["apply_clicked"][i]),
               bool(data["app_started"][i]), bool(data["cv_uploaded"][i]), bool(data["app_submitted"][i]),
               bool(data["app_error"][i]), int(data["latencies"][i]), float(data["costs"][i]), int(data["result_count"][i]))


def load_events(conn, data) -> int:
    """Write a distinct ordered event sequence, including four result impressions."""
    columns = "session_id,user_id,job_id,occurred_at,date,event_name,market,device_type,traffic_source,experiment_id,experiment_variant,page,error_code,load_time_ms,event_seq,result_position"
    count = 0
    batch: list[str] = []
    # Each COPY can queue multiple FK checks per row until its statement ends.
    # A millions-row COPY exhausts RAM on the minimum Neon compute; ~70k-event
    # statements and commits release that queue and bound WAL/transaction state.
    for chunk_start in range(0, data["sessions_count"], 10000):
      with conn.cursor().copy(f"COPY talentpulse.fact_events ({columns}) FROM STDIN") as copy:
        for i in range(chunk_start, min(chunk_start + 10000, data["sessions_count"])):
            day = data["dates"][int(data["days"][i])]
            occurred = datetime.combine(day, time(), timezone.utc) + timedelta(seconds=int(data["seconds"][i]))
            events = [(0, "search_started", "search", None, None)]
            if data["search"][i]:
                events.append((2, "search_completed", "search", None, None))
                events.extend((3 + rank, "search_result_viewed", "search", None, rank) for rank in range(1, 5))
                if data["ai"][i]:
                    events.append((8, "recommendation_viewed", "search", None, None))
            if data["job_view"][i]:
                if data["ai"][i]:
                    events.append((18, "recommendation_clicked", "search", None, None))
                events.append((20, "job_viewed", "job_detail", None, None))
            if data["apply_clicked"][i]:
                events.append((90, "apply_clicked", "job_detail", None, None))
            if data["app_started"][i]:
                events.append((95, "application_started", "application", None, None))
            if data["app_error"][i]:
                error = "CV_UPLOAD_TIMEOUT" if data["session_devices"][i] == 1 else "APPLICATION_VALIDATION_ERROR"
                events.append((178, "application_error", "application", error, None))
            if data["cv_uploaded"][i]:
                events.extend([(180, "cv_uploaded", "application", None, None),
                               (200, "application_step_completed", "application", None, None)])
            if data["app_submitted"][i]:
                events.append((250, "application_submitted", "application_confirmation", None, None))
            experiment = EXPERIMENT_ID if data["in_experiment"][i] else "\\N"
            prefix = f'{i + 1}\t{int(data["user_indices"][i]) + 1}\t{int(data["job_ids"][i])}\t'
            common = (f'\t{MARKETS[data["session_markets"][i]]}\t{DEVICES[data["session_devices"][i]]}'
                      f'\t{TRAFFIC[data["traffic_ids"][i]]}\t{experiment}\t{VARIANTS[data["variants"][i]]}\t')
            for sequence, (offset, name, page, error, position) in enumerate(events, start=1):
                timestamp = (occurred + timedelta(seconds=offset)).isoformat()
                error_value = error or "\\N"
                position_value = str(position) if position is not None else "\\N"
                batch.append(f'{prefix}{timestamp}\t{day.isoformat()}\t{name}{common}{page}\t{error_value}\t{int(data["latencies"][i])}\t{sequence}\t{position_value}\n')
                count += 1
            if len(batch) >= 10000:
                copy.write("".join(batch))
                batch.clear()
            if (i + 1) % 50000 == 0:
                print(f"  Ordered telemetry: {i + 1:,} sessions / {count:,} events", flush=True)
        if batch:
            copy.write("".join(batch))
            batch.clear()
      conn.commit()
    return count


def application_rows(data):
    for i in np.flatnonzero(data["app_started"]):
        day = data["dates"][int(data["days"][i])]
        occurred = datetime.combine(day, time(), timezone.utc) + timedelta(seconds=int(data["seconds"][i]))
        status = "submitted" if data["app_submitted"][i] else "error" if data["app_error"][i] else "abandoned"
        error = ("CV_UPLOAD_TIMEOUT" if data["session_devices"][i] == 1 else "APPLICATION_VALIDATION_ERROR") if status == "error" else None
        yield (int(data["user_indices"][i]) + 1, int(i) + 1, int(data["job_ids"][i]), occurred + timedelta(seconds=95),
               occurred + timedelta(seconds=250) if status == "submitted" else None,
               status, MARKETS[data["session_markets"][i]], DEVICES[data["session_devices"][i]], error)


def outcome_rows(data):
    indices = np.flatnonzero(data["in_experiment"])
    users = data["user_indices"][indices]
    size = data["users_count"]
    sessions = np.bincount(users, minlength=size)
    conversions = np.bincount(users, weights=data["app_submitted"][indices], minlength=size) > 0
    engagement = np.bincount(users, weights=data["job_view"][indices], minlength=size) > 0
    errors = np.bincount(users, weights=data["app_error"][indices], minlength=size)
    latency_sum = np.bincount(users, weights=data["latencies"][indices], minlength=size)
    costs = np.bincount(users, weights=data["costs"][indices], minlength=size)
    for i in range(size):
        yield (EXPERIMENT_ID, i + 1, VARIANTS[data["assignment"][i]], EXPERIMENT_START, END,
               bool(sessions[i]), bool(conversions[i]), bool(engagement[i]), int(sessions[i]),
               int(errors[i]), float(latency_sum[i] / sessions[i]) if sessions[i] else 0.0, float(costs[i]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="Explicitly rebuild only the talentpulse schema")
    parser.add_argument("--seed", type=int, default=20261004)
    parser.add_argument("--users", type=int, default=50000)
    parser.add_argument("--jobs", type=int, default=100000)
    parser.add_argument("--sessions", type=int, default=350000)
    parser.add_argument("--dry-run", action="store_true", help="Generate and summarize without connecting")
    args = parser.parse_args()
    if min(args.users, args.jobs, args.sessions) <= 0:
        parser.error("All data counts must be positive")
    load_env()
    print(f"Generating reproducible synthetic telemetry (seed {args.seed})…", flush=True)
    data = make_data(args.seed, args.users, args.jobs, args.sessions)
    print(f"Prepared {args.users:,} users, {args.jobs:,} jobs, {args.sessions:,} sessions, {data['event_count']:,} ordered events.", flush=True)
    for variant_id, variant in enumerate(VARIANTS):
        rows = [row for row in outcome_rows(data) if row[2] == variant]
        exposed = sum(row[5] for row in rows)
        converted = sum(row[6] for row in rows)
        print(f"  {variant}: {len(rows):,} assigned, {exposed:,} exposed users; {converted / exposed:.2%} user conversion" if exposed else f"  {variant}: no exposed users", flush=True)
    if args.dry_run:
        return
    connection = os.getenv("DATABASE_URL_DIRECT") or os.getenv("DATABASE_URL")
    if not connection:
        parser.error("Set DATABASE_URL_DIRECT or DATABASE_URL")
    if args.users >= 50000 and args.sessions >= 350000 and data["event_count"] <= 2000000:
        raise RuntimeError("Required million-event scale was not met")
    with psycopg.connect(connection, connect_timeout=30) as conn:
        if args.reset:
            conn.execute("DROP SCHEMA IF EXISTS talentpulse CASCADE")
        conn.execute((ROOT / "database/schema.sql").read_text())
        existing = conn.execute("SELECT users,jobs,sessions,events FROM talentpulse.seed_manifest WHERE seed_version=%s", (SEED_VERSION,)).fetchone()
        if existing:
            print(f"Seed already loaded: {existing[0]:,} users, {existing[1]:,} jobs, {existing[2]:,} sessions, {existing[3]:,} events. Use --reset to rebuild.", flush=True)
            return
        if conn.execute("SELECT EXISTS(SELECT 1 FROM talentpulse.dim_users)").fetchone()[0]:
            raise RuntimeError("The talentpulse schema contains partial or unrecognized data without a completed manifest; use --reset only if rebuilding this lab is intended")
        conn.commit()
        print("Loading dimensions…", flush=True)
        copy_rows(conn, "dim_users", ["user_id", "market", "device_type", "user_type", "experience_level", "preferred_role", "preferred_location", "registration_date"], data["users"])
        copy_rows(conn, "dim_jobs", ["job_id", "job_category", "job_title", "market", "location", "salary_min", "salary_max", "remote_type", "experience_level", "posted_date"], data["jobs"])
        # Events can pass midnight, but their analytics date belongs to the session.
        copy_rows(conn, "dim_date", ["date", "day_of_week", "day_name", "week_start", "month", "is_weekend"],
                  ((d, d.weekday(), d.strftime("%A"), d - timedelta(days=d.weekday()), d.month, d.weekday() >= 5) for d in data["dates"]))
        copy_rows(conn, "dim_releases", ["release_id", "release_name", "feature", "release_date", "market", "platform", "description"], [
            ("rel-20260824", "Search relevance refresh", "Search ranking", date(2026, 8, 24), "All", "All", "Weekly ranking refresh with expanded title synonyms."),
            ("rel-20260918", "Mobile CV upload v2", "CV upload", date(2026, 9, 18), "All", "mobile", "Mobile upload client and validation changes; monitor error and completion guardrails."),
            ("rel-20260921", "AI ranking experiment launch", "AI recommendations", date(2026, 9, 21), "All", "All", "Fixed user-randomized three-arm ranking experiment begins."),
            ("rel-20260923", "Mobile CV upload hotfix", "CV upload", date(2026, 9, 23), "All", "mobile", "Retry and timeout handling recovery release."),
        ])
        conn.execute("INSERT INTO talentpulse.dim_experiments VALUES (%s,%s,%s,%s,%s,%s,%s)",
                     (EXPERIMENT_ID, "AI-assisted job ranking", EXPERIMENT_START, END,
                      "Application conversion per exposed user", "user",
                      "Synthetic controlled comparison: database ranking, GPT-4o via OpenRouter, GPT-OSS 120B via Ollama Cloud. Historical outcomes are simulated, not provider evaluations."))
        copy_rows(conn, "fact_experiment_assignments", ["experiment_id", "user_id", "variant", "assigned_at"],
                  ((EXPERIMENT_ID, i + 1, VARIANTS[data["assignment"][i]], datetime.combine(EXPERIMENT_START, time(), timezone.utc)) for i in range(args.users)))
        print("Loading sessions and applications…", flush=True)
        copy_rows(conn, "fact_sessions", ["session_id", "user_id", "job_id", "occurred_at", "date", "market", "device_type", "user_type", "job_category", "traffic_source", "experience_level", "variant", "search_completed", "job_viewed", "apply_clicked", "application_started", "cv_uploaded", "application_submitted", "application_error", "load_time_ms", "model_cost_usd", "search_result_count"], session_rows(data))
        copy_rows(conn, "fact_applications", ["user_id", "session_id", "job_id", "started_at", "submitted_at", "status", "market", "device_type", "error_code"], application_rows(data))
        copy_rows(conn, "fact_experiment_outcomes", ["experiment_id", "user_id", "variant", "window_start", "window_end", "exposed", "converted", "job_engaged", "sessions", "errors", "avg_load_time_ms", "model_cost_usd"], outcome_rows(data))
        print("Loading ordered product events…", flush=True)
        events = load_events(conn, data)
        if events != data["event_count"]:
            raise RuntimeError("Event-count reconciliation failed")
        conn.execute("""INSERT INTO talentpulse.fact_kpis
          SELECT date,market,count(*),count(DISTINCT user_id),count(*),
          count(*) FILTER (WHERE job_viewed),count(*) FILTER (WHERE application_started),
          count(*) FILTER (WHERE application_submitted),count(*) FILTER (WHERE application_error)
          FROM talentpulse.fact_sessions GROUP BY date,market""")
        conn.execute("INSERT INTO talentpulse.seed_manifest(seed_version,seed,users,jobs,sessions,events) VALUES(%s,%s,%s,%s,%s,%s)",
                     (SEED_VERSION, args.seed, args.users, args.jobs, args.sessions, events))
        conn.execute("ANALYZE talentpulse.fact_sessions")
        conn.execute("ANALYZE talentpulse.fact_events")
        conn.execute("ANALYZE talentpulse.fact_experiment_outcomes")
    print("Completed batched synthetic load to Neon. Historical experiment outcomes and live model calls are separate.", flush=True)


if __name__ == "__main__":
    main()
