"""Small transaction-scoped database helpers for Vercel's Python runtime."""
from __future__ import annotations

import os
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from functools import wraps

import psycopg
from psycopg.rows import dict_row


class DatabaseUnavailable(RuntimeError):
    pass


_active_transaction: ContextVar = ContextVar("talentpulse_transaction", default=None)


def serializable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: serializable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [serializable(item) for item in value]
    return value


@contextmanager
def connection(readonly: bool = True):
    active = _active_transaction.get()
    if active is not None:
        conn, active_readonly = active
        if active_readonly and not readonly:
            raise DatabaseUnavailable("A write operation cannot run inside an analytics read transaction.")
        yield conn
        return
    url = os.getenv("DATABASE_URL")
    if not url:
        raise DatabaseUnavailable("Neon database is not configured. Set DATABASE_URL on the server.")
    try:
        with psycopg.connect(url, row_factory=dict_row, connect_timeout=6) as conn:
            if readonly:
                conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            conn.execute("SET LOCAL statement_timeout = '25000ms'")
            token = _active_transaction.set((conn, readonly))
            try:
                yield conn
            finally:
                _active_transaction.reset(token)
    except psycopg.Error as exc:
        # Connection strings and provider response bodies must never reach the public API.
        logging.getLogger(__name__).warning("Neon request failed: exception_class=%s sqlstate=%s", type(exc).__name__, getattr(exc, "sqlstate", None) or "unavailable")
        raise DatabaseUnavailable("The Neon analytics database could not complete this request. Please retry shortly.") from exc


def read_transaction(operation):
    """Reuse one connection and a consistent snapshot across an analytical request."""
    @wraps(operation)
    def wrapped(*args, **kwargs):
        with connection():
            return operation(*args, **kwargs)
    return wrapped


def rows(query: str, params: tuple | list = ()) -> list[dict]:
    with connection() as conn:
        return serializable(conn.execute(query, params).fetchall())


def row(query: str, params: tuple | list = ()) -> dict:
    with connection() as conn:
        result = conn.execute(query, params).fetchone()
        return serializable(result or {})
