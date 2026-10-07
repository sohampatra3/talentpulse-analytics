from __future__ import annotations

import csv
import io
import json

from .db import rows
from .experiment_api import experiment
from .filters import Filters
from .metrics import daily
from .quality import tracking


def dataset_rows(dataset: str, filters: Filters) -> list[dict]:
    if dataset == "daily":
        return daily(filters)
    if dataset == "experiments":
        return experiment(filters)["arms"]
    if dataset == "jobs":
        return rows("SELECT * FROM talentpulse.dim_jobs ORDER BY job_id LIMIT 10000")
    if dataset == "tracking":
        return tracking(filters)["events"]
    if dataset == "sessions":
        where, params = filters.sql()
        return rows(f"SELECT session_id,user_id,date,market,device_type,user_type,job_category,traffic_source,experience_level,variant,search_completed,job_viewed,apply_clicked,application_started,cv_uploaded,application_submitted,application_error,load_time_ms,model_cost_usd FROM talentpulse.fact_sessions s WHERE {where} ORDER BY session_id LIMIT 10000", params)
    raise ValueError("Unknown export dataset")


def csv_value(value):
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r", "\n")):
        return "'" + value
    return value


def csv_text(data: list[dict]) -> str:
    output = io.StringIO(newline="")
    if not data:
        return "No rows for selected filters\r\n"
    writer = csv.DictWriter(output, fieldnames=list(data[0]))
    writer.writeheader()
    writer.writerows({key: csv_value(value) for key, value in item.items()} for item in data)
    return output.getvalue()
