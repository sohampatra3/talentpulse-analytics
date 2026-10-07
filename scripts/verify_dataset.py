"""Read-only reconciliation of the actual seeded dataset, never prints credentials."""
from __future__ import annotations

import json
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]


def main():
    load_dotenv(ROOT / ".env")
    with psycopg.connect(os.environ.get("DATABASE_URL_DIRECT") or os.environ["DATABASE_URL"], row_factory=dict_row) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        conn.execute("SET LOCAL statement_timeout = '120s'")
        conn.execute("SET LOCAL TIME ZONE 'UTC'")
        manifest = conn.execute("SELECT seed_version,seed,users,jobs,sessions,events FROM talentpulse.seed_manifest WHERE seed_version='talentpulse-v1'").fetchone()
        assert manifest, "Synthetic load has not completed; completion manifest is absent"
        counts = conn.execute("""SELECT
          (SELECT count(*) FROM talentpulse.dim_users) AS users,
          (SELECT count(*) FROM talentpulse.dim_jobs) AS jobs,
          (SELECT count(*) FROM talentpulse.fact_sessions) AS sessions,
          (SELECT count(*) FROM talentpulse.fact_events) AS events,
          (SELECT count(*) FROM talentpulse.fact_applications) AS applications,
          (SELECT count(*) FROM talentpulse.fact_experiment_assignments WHERE experiment_id='ai-ranking-v1') AS assignments,
          (SELECT count(*) FROM talentpulse.fact_experiment_outcomes WHERE experiment_id='ai-ranking-v1') AS experiment_outcomes
        """).fetchone()
        assert counts["users"] >= 50_000 and counts["jobs"] >= 100_000 and counts["events"] >= 2_000_000, counts
        assert all(counts[key] == manifest[key] for key in ("users", "jobs", "sessions", "events")), "Actual counts differ from the completed seed manifest"
        assert counts["assignments"] == counts["users"], "Assignment coverage mismatch"
        assert counts["experiment_outcomes"] == counts["assignments"], "Outcome coverage mismatch"
        checks = conn.execute("""SELECT
          count(*) FILTER(WHERE job_viewed AND NOT search_completed
            OR apply_clicked AND NOT job_viewed OR application_started AND NOT apply_clicked
            OR cv_uploaded AND NOT application_started OR application_submitted AND NOT cv_uploaded) AS funnel_violations,
          count(*) FILTER(WHERE s.market <> j.market OR s.job_category <> j.job_category) AS catalog_mismatches,
          count(*) FILTER(WHERE s.date BETWEEN '2026-09-21' AND '2026-10-04' AND s.variant <> a.variant) AS assignment_mismatches,
          count(*) FILTER(WHERE s.date < '2026-09-21' AND s.variant <> 'control') AS pre_experiment_noncontrol,
          count(*) FILTER(WHERE s.date <> s.occurred_at::date) AS session_date_mismatches
          FROM talentpulse.fact_sessions s
          JOIN talentpulse.dim_jobs j USING(job_id)
          JOIN talentpulse.fact_experiment_assignments a ON a.user_id=s.user_id AND a.experiment_id='ai-ranking-v1'
        """).fetchone()
        assert all(value == 0 for value in checks.values()), checks
        event_check = conn.execute("""SELECT
          count(*) FILTER(WHERE e.occurred_at < s.occurred_at) AS events_before_session,
          count(*) FILTER(WHERE e.date <> e.occurred_at::date) AS event_date_mismatches,
          count(*) FILTER(WHERE e.user_id <> s.user_id OR e.job_id <> s.job_id OR e.experiment_variant <> s.variant) AS attribution_mismatches,
          count(*) FILTER(WHERE e.event_name='application_submitted') AS submitted_events
          FROM talentpulse.fact_events e JOIN talentpulse.fact_sessions s USING(session_id)
        """).fetchone()
        assert all(event_check[k] == 0 for k in ("events_before_session", "event_date_mismatches", "attribution_mismatches")), event_check
        submitted = conn.execute("SELECT count(*) AS n FROM talentpulse.fact_sessions WHERE application_submitted").fetchone()["n"]
        assert event_check["submitted_events"] == submitted, "Submission events do not reconcile to outcomes"
        experiment_check = conn.execute("""WITH actual AS (
          SELECT user_id, bool_or(application_submitted) AS converted, bool_or(job_viewed) AS engaged, count(*) AS sessions
          FROM talentpulse.fact_sessions WHERE date BETWEEN '2026-09-21' AND '2026-10-04' GROUP BY user_id
        ) SELECT count(*) FILTER(WHERE o.converted <> coalesce(a.converted,false)
          OR o.job_engaged <> coalesce(a.engaged,false) OR o.exposed <> (a.user_id IS NOT NULL)
          OR o.sessions <> coalesce(a.sessions,0)) AS outcome_mismatches
          FROM talentpulse.fact_experiment_outcomes o LEFT JOIN actual a USING(user_id)
          WHERE o.experiment_id='ai-ranking-v1'
        """).fetchone()
        assert experiment_check["outcome_mismatches"] == 0, experiment_check
        size = conn.execute("SELECT pg_size_pretty(pg_database_size(current_database())) AS database_size").fetchone()
        report = {"status": "passed", "synthetic": True, "seed_manifest": manifest, "counts": counts, "session_checks": checks, "event_checks": event_check, "experiment_checks": experiment_check, **size}
    (ROOT / "artifacts").mkdir(exist_ok=True)
    (ROOT / "artifacts" / "dataset-verification.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
