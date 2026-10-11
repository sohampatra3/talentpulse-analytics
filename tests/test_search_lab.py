import pytest
from api.analytics.search_quality import ranking_metrics,reference_grade,power_plan,paired_interval,synthetic_documents,benchmark_queries
from api.analytics.search_lab import safe_ranking,RunRequest,eligible_sql
from api.analytics.providers import ProviderFailure

def test_unjudged_jobs_never_become_zero_relevance():
    assert ranking_metrics([1,2],{'1':3})['ndcg'] is None
    assert ranking_metrics([1,2],{'1':3})['coverage']==.5

def test_ndcg_reacts_to_order_not_just_same_jobs():
    grades={'1':3,'2':0,'3':2}
    assert ranking_metrics([1,3,2],grades)['ndcg']==pytest.approx(1)
    assert ranking_metrics([2,3,1],grades)['ndcg']<1

def test_nonexistent_duplicate_and_boolean_ids_are_measured():
    parsed=safe_ranking('{"ranked_job_ids":[true,1,999,1],"citations":[{"job_id":1,"quote":"invented"}]}',[{'job_id':1,'body':'real source'}],10)
    assert parsed['invalid_count']==3
    assert parsed['unsupported_citations']==1
    assert len(parsed['jobs'])==1

def test_empty_ranking_is_explicit_abstention():
    assert safe_ranking('{"ranked_job_ids":[]}',[{'job_id':1}],5)['jobs']==[]
    with pytest.raises(ProviderFailure):safe_ranking('not json',[{'job_id':1}],5)

def test_citation_must_exist_in_exact_job_document():
    value=safe_ranking('{"ranked_job_ids":[1],"citations":[{"job_id":1,"quote":"SQL required"}]}',[{'job_id':1,'body':'SQL required. Hybrid work.'}],5)
    assert value['citation_coverage']==1

def test_power_plan_and_invalid_rates():
    plan=power_plan(8,1)
    assert plan['users_per_arm']==14784
    assert plan['relative_lift_pct']==12.5
    with pytest.raises(ValueError):power_plan(99,2)

def test_small_sample_has_no_confidence_interval():
    assert paired_interval([.2,.3]) is None
    lo,hi=paired_interval([.2]*8)
    assert lo==pytest.approx(.2) and hi==pytest.approx(.2)

def test_catalog_and_benchmark_are_versioned_and_deterministic():
    docs=list(synthetic_documents());queries=list(benchmark_queries())
    assert len(docs)==2000 and len(queries)==60
    assert sum(q['split']=='held_out' for q in queries)==20
    assert docs==list(synthetic_documents())
    assert len({q['query'] for q in queries})==60
    assert all('Synthetic' in body and meta['currency']=='EUR' for meta,body in docs)

def test_filters_are_bound_and_missing_salary_is_ineligible():
    where,params=eligible_sql(RunRequest(query='analyst',location="Berlin'; DROP TABLE jobs;--",salary_min=50000))
    assert 'DROP' not in where
    assert any('DROP' in str(p) for p in params)
    assert 'ELSE false' in where

def test_explicit_work_constraints_override_reference_match():
    assert reference_grade('Product Analyst remote',{'job_title':'Product Analyst','remote_type':'On-site'})==0

def test_cards_cannot_claim_document_citations():
    parsed=safe_ranking('{"ranked_job_ids":[1],"citations":[{"job_id":1,"quote":"SQL required"}]}',[{'job_id':1,'body':'SQL required','provided_evidence':''}],5)
    assert parsed['unsupported_citations']==1
    assert parsed['citation_coverage']==0

def test_private_job_description_and_status_are_typed():
    from api.analytics.uploads import prepare_rows,UploadError
    data={'title':'Analyst','description':'SQL, experimentation and German language','working_language':'German','is_active':'false','expiry_date':'2026-10-01'}
    prepared=prepare_rows(list(data),[data])
    assert prepared['normalized'][0]['job_description']==data['description']
    assert prepared['normalized'][0]['active'] is False
    assert prepared['normalized'][0]['expires_at']=='2026-10-01'
    with pytest.raises(UploadError):prepare_rows(['expiry_date'],[{'expiry_date':'invalid'}])

def test_review_requires_current_document_hash_and_entire_pool(monkeypatch):
    from api.analytics import search_lab as lab
    record={'run_id':'r','workspace_hash':'private','config':{'query_id':'q','reference_grades':{'1':3,'2':0}},'corpus_id':'upload-private','candidates':[{'job_id':1,'content_hash':'new'}],'baselines':[{'jobs':[{'job_id':2,'content_hash':'b'}],'metrics':{'ndcg':1}}],'status':'complete','created_at':'today','updated_at':'today','reserved_usd':0}
    reviews=[{'job_id':1,'grade':3,'content_hash':'old'},{'job_id':2,'grade':0,'content_hash':'b'}]
    view=lab.decorate_run(record,[],reviews)
    assert view['review']['completed']==1
    assert view['review']['fully_reviewed'] is False
    assert view['baselines'][0]['reviewed_metrics']['ndcg'] is None
    assert view['baselines'][0]['metrics']['ndcg'] is None
    assert 'reference_grades' not in view['config']

def test_reasoning_model_has_room_for_final_answer_and_no_trace_is_exposed(monkeypatch):
    import asyncio
    from api.analytics import providers as p
    observed={}
    class Response:
        status_code=200
        def json(self):return {'message':{'content':'{"ranked_job_ids":[1]}','thinking':'private reasoning'},'eval_count':1200}
    class Client:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,url,headers,json):observed.update(json);return Response()
    monkeypatch.setattr(p.httpx,'AsyncClient',Client)
    value=asyncio.run(p.complete('ollama','Rank jobs','data',json_mode=True,max_tokens=750,model='gpt-oss:120b',api_key='unit-test'))
    assert observed['options']['num_predict']==3072
    assert observed['think']=='low'
    assert 'format' not in observed
    assert 'thinking' not in value
    assert value['cost_usd'] is None
