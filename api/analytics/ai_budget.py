"""Atomic per-provider-call accounting, shared across all request-driven AI features."""
from contextvars import ContextVar
from datetime import datetime, timezone
import hashlib
import os
from fastapi import HTTPException
from .db import connection

client_context=ContextVar('ai_client_address',default=None)
run_context=ContextVar('ai_evaluation_id',default=None)

def reserve(cost=0.0):
    address=client_context.get()
    if address is None:return None
    digest=hashlib.sha256((os.getenv('LAB_HASH_SALT','talentpulse-demo')+address).encode()).hexdigest()
    today=datetime.now(timezone.utc).date();run_id=run_context.get()
    with connection(readonly=False) as conn:
        conn.execute('SELECT pg_advisory_xact_lock(7408312026)')
        counts={r['client_hash']:r for r in conn.execute("SELECT client_hash,requests,reserved_usd FROM talentpulse.api_usage_daily WHERE day=%s AND client_hash IN (%s,'_global')",(today,digest)).fetchall()}
        if counts.get(digest,{}).get('requests',0)>=int(os.getenv('AI_PER_IP_DAILY_LIMIT','20')) or counts.get('_global',{}).get('requests',0)>=int(os.getenv('AI_GLOBAL_DAILY_LIMIT','150')):
            raise HTTPException(429,'Daily AI request allowance reached. Saved analytics remain available. Retry after the next UTC day.')
        if float(counts.get('_global',{}).get('reserved_usd',0))+cost>float(os.getenv('AI_DAILY_USD_LIMIT','2')):
            raise HTTPException(429,'Shared OpenRouter daily budget reached. Saved results remain available.')
        if run_id:
            current=conn.execute('SELECT reserved_usd FROM talentpulse.search_evaluations WHERE run_id=%s FOR UPDATE',(run_id,)).fetchone()
            if not current or float(current['reserved_usd'])+cost>.10:
                raise HTTPException(429,'This comparison reached its $0.10 OpenRouter reservation limit. Select a less expensive model or smaller candidate pool.')
            conn.execute('UPDATE talentpulse.search_evaluations SET reserved_usd=reserved_usd+%s WHERE run_id=%s',(cost,run_id))
        conn.execute("INSERT INTO talentpulse.api_usage_daily(day,client_hash,requests,reserved_usd) VALUES(%s,%s,1,%s),(%s,'_global',1,%s) ON CONFLICT(day,client_hash) DO UPDATE SET requests=talentpulse.api_usage_daily.requests+1,reserved_usd=talentpulse.api_usage_daily.reserved_usd+EXCLUDED.reserved_usd",(today,digest,cost,today,cost))
    return {'day':today,'digest':digest,'cost':cost,'run_id':run_id}

def settle(receipt,actual):
    if not receipt or actual is None:return
    delta=max(0,float(actual))-receipt['cost']
    with connection(readonly=False) as conn:
        conn.execute('SELECT pg_advisory_xact_lock(7408312026)')
        conn.execute("UPDATE talentpulse.api_usage_daily SET reserved_usd=greatest(0,reserved_usd+%s) WHERE day=%s AND client_hash IN (%s,'_global')",(delta,receipt['day'],receipt['digest']))
        if receipt['run_id']:conn.execute('UPDATE talentpulse.search_evaluations SET reserved_usd=greatest(0,reserved_usd+%s) WHERE run_id=%s',(delta,receipt['run_id']))
