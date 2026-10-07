from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DIMENSIONS = ("market", "device_type", "user_type", "job_category", "traffic_source", "experience_level", "variant")


class Filters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_date: date = date(2026, 9, 7)
    end_date: date = date(2026, 10, 4)
    market: str | None = Field(default=None, max_length=80)
    device_type: str | None = Field(default=None, max_length=80)
    user_type: str | None = Field(default=None, max_length=80)
    job_category: str | None = Field(default=None, max_length=80)
    traffic_source: str | None = Field(default=None, max_length=80)
    experience_level: str | None = Field(default=None, max_length=80)
    variant: str | None = Field(default=None, max_length=80)

    @field_validator(*DIMENSIONS, mode="before")
    @classmethod
    def normalize_dimension(cls, value: Any):
        if value is None or str(value).strip().lower() in ("", "all"):
            return None
        return str(value).strip()

    @model_validator(mode="after")
    def valid_window(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if (self.end_date - self.start_date).days > 366:
            raise ValueError("Choose a date range no longer than 367 days")
        return self

    def sql(self, alias: str = "s", include_dates: bool = True) -> tuple[str, tuple]:
        # Names are static/allowlisted; all incoming values are bound parameters.
        if alias not in ("s", "o", ""):
            raise ValueError("Unsupported SQL alias")
        prefix = f"{alias}." if alias else ""
        clauses: list[str] = []
        params: list[Any] = []
        if include_dates:
            clauses.append(f"{prefix}date BETWEEN %s AND %s")
            params.extend([self.start_date, self.end_date])
        for name in DIMENSIONS:
            value = getattr(self, name)
            if value is not None:
                clauses.append(f"{prefix}{name} = %s")
                params.append(value)
        return " AND ".join(clauses) or "TRUE", tuple(params)

    def previous(self) -> "Filters":
        length = (self.end_date - self.start_date).days + 1
        return self.model_copy(update={"end_date": self.start_date - timedelta(days=1), "start_date": self.start_date - timedelta(days=length)})

    def window(self):
        return {"start_date": str(self.start_date), "end_date": str(self.end_date)}
