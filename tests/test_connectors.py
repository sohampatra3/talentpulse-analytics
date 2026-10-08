"""Workspace isolation, encryption, actual-report parsing and outbound boundaries."""
import asyncio
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import date

import httpcore
import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from fastapi.testclient import TestClient

from api.analytics import connectors, providers, workspaces
from api.index import app, cached, dataset_cache_name, invalidate_dataset_cache


@pytest.fixture(autouse=True)
def local_catalog(monkeypatch):
    values = [{"provider":"ollama","id":"gpt-oss:120b"},{"provider":"ollama","id":"gemma4:31b"},{"provider":"openrouter","id":"openai/gpt-4o"}]
    monkeypatch.setattr(providers,"cloud_catalog",lambda:(values,"verified_test_catalog"))


def test_fast_health_does_not_query_database(monkeypatch):
    import api.index as index
    monkeypatch.setenv("DATABASE_URL","configured-private-dsn")
    monkeypatch.setattr(index,"row",lambda *args:pytest.fail("Liveness must not query Neon"))
    response=TestClient(app).get('/api/health')
    assert response.status_code==200
    assert response.json()['database']=='configured'
    assert response.json()['database_verified'] is False
    assert 'configured-private-dsn' not in response.text


def test_missing_workspace_token_blocks_private_connectors():
    response=TestClient(app).get('/api/workspace/connectors')
    assert response.status_code==401
    with pytest.raises(HTTPException) as exc:workspaces.workspace_identity('not-a-secret-token')
    assert exc.value.status_code==401


def test_workspace_token_is_hashed_and_must_exist(monkeypatch):
    captured=[]
    monkeypatch.setattr(workspaces,'row',lambda sql,params:(captured.append(params) or {}))
    token='a'*64
    with pytest.raises(HTTPException):workspaces.workspace_identity(token)
    assert captured[0][0]!=token
    assert len(captured[0][0])==64


def test_secrets_encrypt_roundtrip_and_never_appear_in_metadata(monkeypatch):
    monkeypatch.setenv('APP_ENCRYPTION_KEY',Fernet.generate_key().decode())
    raw={'api_key':'private-workspace-provider-value'}
    encrypted=workspaces.cipher().encrypt(json.dumps(raw).encode()).decode()
    assert raw['api_key'] not in encrypted
    assert workspaces.decrypt_secrets(encrypted)==raw
    safe=workspaces.safe_config({'connector_id':'ollama','settings':{'model':'gemma4:31b'},'secrets':raw,'last_status':'configured'})
    assert safe['secrets_present']==['api_key']
    assert raw['api_key'] not in json.dumps(safe)


def test_save_keeps_existing_empty_secrets_and_resets_verification(monkeypatch):
    monkeypatch.setenv('APP_ENCRYPTION_KEY',Fernet.generate_key().decode())
    existing={'connector_id':'adobe','settings':{'company_id':'example'},'secrets':{'access_token':'persisted-token','client_id':'client'},'last_status':'verified'}
    monkeypatch.setattr(workspaces,'connector_config',lambda *args:existing)
    calls=[]
    class Connection:
        def execute(self,sql,params):calls.append((sql,params))
    @contextmanager
    def fake_connection(**kwargs):yield Connection()
    monkeypatch.setattr(workspaces,'connection',fake_connection)
    workspaces.save_connector('hash','adobe',{'report_suite_id':'suite'},{'access_token':''})
    assert workspaces.decrypt_secrets(calls[0][1][3])['access_token']=='persisted-token'
    assert "last_status='configured'" in calls[0][0]
    assert 'persisted-token' not in str(calls)


@pytest.mark.parametrize('endpoint',['http://example.com/mcp','https://127.0.0.1/mcp','https://[::1]/mcp','https://localhost/mcp','https://host.internal/mcp','https://user:pass@example.com/mcp','https://example.com:8080/mcp','https://example.com/mcp?token=private'])
def test_unsafe_mcp_endpoint_is_rejected(endpoint):
    with pytest.raises(HTTPException):connectors.validate_endpoint(endpoint)


def test_public_https_endpoint_is_syntactically_allowed():
    assert connectors.validate_endpoint('https://aa-mcp.adobe.io/mcp')=='https://aa-mcp.adobe.io/mcp'


def test_public_dns_rejects_private_or_mixed_addresses(monkeypatch):
    async def run():
        loop=asyncio.get_running_loop()
        async def fake(*args,**kwargs):return [(2,1,6,'',('8.8.8.8',443)),(2,1,6,'',('10.0.0.1',443))]
        monkeypatch.setattr(loop,'getaddrinfo',fake)
        with pytest.raises(httpcore.ConnectError):await connectors.public_addresses('public.example',443)
    asyncio.run(run())


def test_transport_pins_validated_address_instead_of_resolving_again(monkeypatch):
    async def run():
        async def addresses(*args):return ['8.8.8.8']
        monkeypatch.setattr(connectors,'public_addresses',addresses)
        backend=connectors.PublicNetworkBackend();seen=[]
        class Delegate:
            async def connect_tcp(self,host,port,**kwargs):seen.append((host,port));return object()
        backend.delegate=Delegate()
        await backend.connect_tcp('changing-dns.example',443,timeout=2)
        assert seen==[('8.8.8.8',443)]
    asyncio.run(run())


def test_auth_and_settings_are_allowlisted():
    with pytest.raises(HTTPException):connectors.validate_settings('mcp',connectors.ConnectorUpdate(settings={'auth_type':'api_key','auth_header':'Host'}))
    with pytest.raises(HTTPException):connectors.validate_settings('adobe',connectors.ConnectorUpdate(settings={'endpoint':'https://attacker.example'}))
    with pytest.raises(HTTPException):connectors.validate_settings('ollama',connectors.ConnectorUpdate(secrets={'api_key':'token\r\nHost: attacker'}))
    with pytest.raises(ValueError):providers.validate_model('ollama','nonexistent-model:999b')


def test_adobe_report_uses_only_actual_values_and_inclusive_date_boundary(monkeypatch):
    seen=[]
    class Client:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,url,headers,json):
            seen.append((url,json))
            return httpx.Response(200,json={'rows':[{'itemId':'1','value':'2026-10-04','data':[123,19]}],'summaryData':{'totals':[123,19]},'number':0,'totalPages':1,'totalElements':1,'lastPage':True})
    async def headers(*args):return {'Authorization':'Bearer private'}
    monkeypatch.setattr(connectors,'adobe_headers',headers)
    monkeypatch.setattr(connectors.httpx,'AsyncClient',Client)
    config={'settings':{'company_id':'company','report_suite_id':'suite'},'secrets':{}}
    body=connectors.AdobeReportRequest(start_date=date(2026,10,4),end_date=date(2026,10,4),metrics=['metrics/visits','metrics/pageviews'])
    result=asyncio.run(connectors.adobe_report('workspace',config,body))
    assert seen[0][0]=='https://analytics.adobe.io/api/company/reports'
    assert seen[0][1]['globalFilters'][0]['dateRange']=='2026-10-04T00:00:00.000/2026-10-05T00:00:00.000'
    assert result['rows'][0]['values']=={'metrics/visits':123,'metrics/pageviews':19}
    assert result['synthetic'] is False
    assert 'significant' not in result


def test_adobe_errors_do_not_fabricate_report_rows(monkeypatch):
    class Client:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,*args,**kwargs):return httpx.Response(403,json={'error':'forbidden'})
    async def headers(*args):return {}
    monkeypatch.setattr(connectors,'adobe_headers',headers)
    monkeypatch.setattr(connectors.httpx,'AsyncClient',Client)
    with pytest.raises(HTTPException) as exc:asyncio.run(connectors.adobe_report('workspace',{'settings':{'company_id':'company','report_suite_id':'suite'},'secrets':{}},connectors.AdobeReportRequest(start_date='2026-10-01',end_date='2026-10-04')))
    assert exc.value.status_code==502


def test_singleflight_runs_one_operation_for_concurrent_identical_selection():
    count=[0];lock=threading.Lock()
    def expensive():
        with lock:count[0]+=1
        time.sleep(.05)
        return {'actual':'result'}
    with ThreadPoolExecutor(max_workers=6) as pool:results=list(pool.map(lambda _:cached('singleflight-unit',None,expensive),range(6)))
    assert count[0]==1
    assert all(value=={'actual':'result'} for value in results)


def test_dataset_cache_version_changes_with_mapping_and_invalidation():
    first=dataset_cache_name('workspace','dataset','overview',{'kind':'jobs','mapping':{'job_title':'title'}})
    second=dataset_cache_name('workspace','dataset','overview',{'kind':'sessions','mapping':{'job_title':'title','session_id':'session'}})
    assert first!=second
    invalidate_dataset_cache('workspace','dataset')
    assert first!=dataset_cache_name('workspace','dataset','overview',{'kind':'jobs','mapping':{'job_title':'title'}})


def test_remote_token_echo_is_redacted():
    result=connectors.redact_result({'content':[{'text':'Token private-secret appears'}]},{'secrets':{'token':'private-secret'}})
    assert 'private-secret' not in json.dumps(result)


def test_role_explanation_preserves_unavailable_session_denominator(monkeypatch):
    import api.index as index
    from api.analytics import upload_analysis
    monkeypatch.setattr(index,'resolve_provider',lambda *args:('gemma4:31b',None))
    monkeypatch.setattr(index,'workspace_identity',lambda *args:'authorized')
    monkeypatch.setattr(upload_analysis,'role_drivers',lambda *args:{'support':{'row_count':12,'session_count':None},'arms':[],'limitations':['Catalog supply only']})
    async def answer(question,visualize,provider,filters,selected,*args,**kwargs):return selected
    monkeypatch.setattr(index,'investigate',answer)
    response=TestClient(app).post('/api/ai/investigate',json={'question':'Explain this role','role':'Product Analyst','dataset_id':'12345678-1234-1234-1234-123456789abc'},headers={'X-Workspace-Token':'a'*64})
    assert response.status_code==200
    assert response.json()['evidence'][0]['value'] is None
    assert 'denominator is unavailable' in response.json()['answer']


def test_uploaded_analyst_error_is_explicit_instead_of_server_failure(monkeypatch):
    import api.index as index
    from api.analytics import upload_analysis
    from api.analytics.uploads import UploadError
    monkeypatch.setattr(index,'resolve_provider',lambda *args:('gemma4:31b',None))
    monkeypatch.setattr(index,'workspace_identity',lambda *args:'authorized')
    def unavailable(*args):raise UploadError('Dataset was not found in this workspace.')
    monkeypatch.setattr(upload_analysis,'uploaded_evidence',unavailable)
    response=TestClient(app).post('/api/ai/investigate',json={'question':'Visualize data','dataset_id':'12345678-1234-1234-1234-123456789abc'},headers={'X-Workspace-Token':'a'*64})
    assert response.status_code==422
    assert response.json()['code']=='uploaded_evidence_unavailable'


def test_database_failure_logs_only_class_and_sqlstate(monkeypatch,caplog):
    import psycopg
    from api.analytics import db
    monkeypatch.setenv('DATABASE_URL','private-dsn')
    def failed(*args,**kwargs):raise psycopg.OperationalError('password=private-secret host=private-host')
    monkeypatch.setattr(db.psycopg,'connect',failed)
    with pytest.raises(db.DatabaseUnavailable):
        with db.connection():pass
    assert 'OperationalError' in caplog.text
    assert 'private-secret' not in caplog.text
    assert 'private-host' not in caplog.text
