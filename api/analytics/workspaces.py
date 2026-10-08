"""Token-isolated connector configuration with authenticated encryption."""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
from datetime import datetime, timezone

from cryptography.fernet import Fernet, InvalidToken
from fastapi import Header, HTTPException
from psycopg.types.json import Jsonb

from .db import connection, read_transaction, row, rows

CONNECTOR_IDS = ("adobe", "powerbi", "mcp", "ollama", "openrouter")


def workspace_identity(token: str | None) -> str:
    if not token or not re.fullmatch(r"[0-9a-f]{64}", token):
        raise HTTPException(401, "Create or select your private workspace before accessing workspace data.")
    identity = hashlib.sha256(token.encode()).hexdigest()
    exists = row("SELECT workspace_hash FROM talentpulse.lab_workspaces WHERE workspace_hash=%s", (identity,))
    if not exists:
        raise HTTPException(401, "This workspace token is invalid or expired.")
    return identity


def require_workspace_token(x_workspace_token: str | None = Header(default=None)) -> str:
    workspace_identity(x_workspace_token)
    return x_workspace_token


def create_workspace() -> dict:
    token = secrets.token_hex(32)
    identity = hashlib.sha256(token.encode()).hexdigest()
    with connection(readonly=False) as conn:
        created = conn.execute("INSERT INTO talentpulse.lab_workspaces(workspace_hash) VALUES(%s) RETURNING created_at", (identity,)).fetchone()
    return {"workspace_token": token, "workspace_id": identity[:12], "created_at": created["created_at"].isoformat()}


def cipher() -> Fernet:
    key = os.getenv("APP_ENCRYPTION_KEY")
    if not key:
        raise HTTPException(503, "Workspace credential encryption is not configured on the server.")
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as exc:
        raise HTTPException(503, "Workspace credential encryption is misconfigured on the server.") from exc


def decrypt_secrets(encrypted: str | None) -> dict:
    if not encrypted:
        return {}
    try:
        result = json.loads(cipher().decrypt(encrypted.encode()).decode())
        return result if isinstance(result, dict) else {}
    except (InvalidToken, ValueError, TypeError) as exc:
        raise HTTPException(503, "Saved connector credentials could not be decrypted. Reconfigure this workspace connection.") from exc


def connector_config(identity: str, connector_id: str) -> dict:
    if connector_id not in CONNECTOR_IDS:
        raise HTTPException(404, "Unknown workspace connector")
    result = row("SELECT * FROM talentpulse.connector_configs WHERE workspace_hash=%s AND connector_id=%s", (identity, connector_id))
    if not result:
        return {"connector_id": connector_id, "settings": {}, "secrets": {}, "last_status": "not_configured"}
    result["secrets"] = decrypt_secrets(result.pop("encrypted_secrets", None))
    return result


def safe_config(config: dict) -> dict:
    name = config["connector_id"]
    return {"id": name, "name": {"adobe": "Adobe Analytics", "powerbi": "Microsoft Power BI", "mcp": "External MCP", "ollama": "Ollama Cloud", "openrouter": "OpenRouter"}[name], "configured": bool(config.get("settings") or config.get("secrets")), "status": config.get("last_status", "not_configured"), "settings": config.get("settings", {}), "secrets_present": sorted(config.get("secrets", {})), "updated_at": config.get("updated_at"), "last_tested_at": config.get("last_tested_at"), "last_result": config.get("last_result")}


@read_transaction
def workspace_connectors(token: str) -> dict:
    identity = workspace_identity(token)
    return {"workspace_id": identity[:12], "connectors": [safe_config(connector_config(identity, name)) for name in CONNECTOR_IDS]}


def save_connector(identity: str, connector_id: str, settings: dict, new_secrets: dict, clear_secrets: bool = False) -> dict:
    existing = connector_config(identity, connector_id)
    saved_secrets = {} if clear_secrets else dict(existing["secrets"])
    saved_secrets.update({key: value.strip() for key, value in new_secrets.items() if value and value.strip()})
    encrypted = cipher().encrypt(json.dumps(saved_secrets).encode()).decode() if saved_secrets else None
    merged_settings = {**existing["settings"], **settings}
    with connection(readonly=False) as conn:
        conn.execute("INSERT INTO talentpulse.connector_configs(workspace_hash,connector_id,settings,encrypted_secrets,last_status) VALUES(%s,%s,%s,%s,'configured') ON CONFLICT(workspace_hash,connector_id) DO UPDATE SET settings=EXCLUDED.settings,encrypted_secrets=EXCLUDED.encrypted_secrets,updated_at=now(),last_status='configured',last_tested_at=NULL,last_result=NULL", (identity, connector_id, Jsonb(merged_settings), encrypted))
    return safe_config(connector_config(identity, connector_id))


def save_check(identity: str, connector_id: str, result: dict):
    with connection(readonly=False) as conn:
        conn.execute("UPDATE talentpulse.connector_configs SET last_status=%s,last_tested_at=now(),last_result=%s WHERE workspace_hash=%s AND connector_id=%s", (result["status"], Jsonb(result), identity, connector_id))


def remove_connector(identity: str, connector_id: str):
    if connector_id not in CONNECTOR_IDS:
        raise HTTPException(404, "Unknown workspace connector")
    with connection(readonly=False) as conn:
        conn.execute("DELETE FROM talentpulse.connector_configs WHERE workspace_hash=%s AND connector_id=%s", (identity, connector_id))
