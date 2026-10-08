"""Authenticated upload routes; no upload data is exposed without its workspace."""
from __future__ import annotations

import csv
import asyncio
import io
import json
import random

from fastapi import APIRouter,Depends,File,Form,HTTPException,Request,Response,UploadFile
from pydantic import BaseModel,ConfigDict

from .exports import csv_text
from .filters import Filters
from .providers import consume_usage
from .upload_analysis import analyze_dataset
from .uploads import ALIASES,KINDS,MAX_BYTES,UploadError,dataset_rows,delete_dataset,get_dataset,list_datasets,parse_file,prepare_rows,search_rows,semantic_metadata,store_dataset,update_mapping
from .workspaces import require_workspace_token

router=APIRouter(prefix='/api/uploads',tags=['Private workspace uploads'])


def fail(exc):raise HTTPException(status_code=422,detail=str(exc)) from exc


@router.get('/schema')
def schema():
    return {'mapping_fields':sorted(ALIASES),'kinds':sorted(KINDS),'model_choices':['gemma4:31b','gpt-oss:120b'],'max_bytes':MAX_BYTES,'max_rows':10000,'max_columns':20,'mapping_direction':'canonical_field → source_column','templates':[{'kind':kind,'url':f'/api/uploads/templates/{kind}'} for kind in ('jobs','sessions','user_outcomes','experiment_summary')]}


@router.get('/templates/{kind}')
def template(kind:str):
    rng=random.Random(2048)
    if kind=='jobs':
        fields=['job_id','job_title','job_category','market','location','salary_min','salary_max','remote_type','experience_level']
        data=[dict(zip(fields,[f'J{i}',role,'Data & Analytics','Germany','Düsseldorf',55000+i*500,72000+i*500,'hybrid','mid'])) for i,role in enumerate(['Product Analyst','Data Analyst','Analytics Engineer','BI Analyst','Data Scientist'],1)]
    elif kind=='sessions':
        fields=['date','session_id','user_id','job_title','job_category','market','device_type','user_type','variant','search_completed','job_viewed','apply_clicked','application_started','cv_uploaded','application_submitted','application_error']
        data=[]
        for i in range(300):
            viewed=rng.random()<.73;apply=viewed and rng.random()<.2;started=apply and rng.random()<.92;cv=started and rng.random()<.72;submitted=cv and rng.random()<.75
            data.append(dict(zip(fields,['2026-09-'+str(21+i%10),f'S{i}',f'U{i//2}','Product Analyst','Data & Analytics','Germany','mobile' if i%2 else 'desktop','new' if i%3==0 else 'returning','control',True,viewed,apply,started,cv,submitted,started and not cv])))
    elif kind=='user_outcomes':
        fields=['date','user_id','variant','assignment_unit','randomized','exposed','converted','job_engaged','market','job_title']
        data=[]
        for i in range(3000):
            arm=rng.choice(['control','gpt4o','ollama']);exposed=rng.random()<.9;converted=exposed and rng.random()<{'control':.08,'gpt4o':.10,'ollama':.095}[arm]
            data.append(dict(zip(fields,['2026-10-04',f'U{i}',arm,'user',True,exposed,converted,exposed and rng.random()<.7,'Germany','Product Analyst'])))
    elif kind=='experiment_summary':
        fields=['variant','samples','conversions','assignment_unit']
        data=[dict(zip(fields,values)) for values in [('control',1000,80,'user'),('gpt4o',1000,102,'user'),('ollama',1000,96,'user')]]
    else:raise HTTPException(status_code=404,detail='Unknown template kind')
    return Response(csv_text(data),media_type='text/csv',headers={'Content-Disposition':f'attachment; filename="synthetic-example-{kind}.csv"','X-Data-Provenance':'Synthetic template, not provider evaluation'})


@router.get('')
def datasets(response:Response,search:str='',token:str=Depends(require_workspace_token)):
    response.headers['Cache-Control']='no-store'
    return list_datasets(token,search)


@router.post('')
async def upload(request:Request,file:UploadFile=File(...),kind:str=Form('auto'),mapping:str|None=Form(None),ingestion_model:str|None=Form(None),token:str=Depends(require_workspace_token)):
    try:
        content=await file.read(MAX_BYTES+1)
        columns,raw,warnings=await asyncio.to_thread(parse_file,content,file.filename or '')
        mapped=json.loads(mapping) if mapping else None
        if mapped is not None and not isinstance(mapped,dict):raise UploadError('Mapping must be a JSON object.')
        prepared=await asyncio.to_thread(prepare_rows,columns,raw,mapped,kind)
        # Ingestion can spend provider credits only after deterministic parsing succeeds.
        import os
        if os.getenv('OLLAMA_API_KEY'):
            address=request.headers.get('x-vercel-forwarded-for',request.headers.get('x-forwarded-for',request.client.host if request.client else 'unknown')).split(',')[0].strip()
            await asyncio.to_thread(consume_usage,address)
        semantic=await semantic_metadata(columns,raw,prepared['profile'],ingestion_model,token)
        result=await asyncio.to_thread(store_dataset,token,file.filename or 'Uploaded dataset',content,columns,raw,prepared,semantic)
        return {**result,'warnings':warnings}
    except (UploadError,json.JSONDecodeError) as exc:fail(exc)
    finally:await file.close()


@router.get('/{dataset_id}')
def detail(dataset_id:str,response:Response,token:str=Depends(require_workspace_token)):
    response.headers['Cache-Control']='no-store'
    try:
        dataset,records=dataset_rows(dataset_id,token)
        return {**dataset,'preview':[record['row_data'] for record in records[:50]]}
    except UploadError as exc:fail(exc)


@router.get('/{dataset_id}/search')
def search(dataset_id:str,response:Response,q:str='',token:str=Depends(require_workspace_token)):
    response.headers['Cache-Control']='no-store'
    try:return search_rows(dataset_id,token,q)
    except UploadError as exc:fail(exc)


class MappingRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    mapping:dict[str,str]
    kind:str='auto'


@router.patch('/{dataset_id}/mapping')
def mapping(dataset_id:str,body:MappingRequest,token:str=Depends(require_workspace_token)):
    try:return update_mapping(dataset_id,token,body.mapping,body.kind)
    except UploadError as exc:fail(exc)


@router.delete('/{dataset_id}')
def delete(dataset_id:str,token:str=Depends(require_workspace_token)):
    try:return delete_dataset(dataset_id,token)
    except UploadError as exc:fail(exc)


@router.get('/{dataset_id}/export')
def export(dataset_id:str,token:str=Depends(require_workspace_token)):
    try:
        dataset,records=dataset_rows(dataset_id,token)
        return Response(csv_text([r['row_data'] for r in records]),media_type='text/csv',headers={'Cache-Control':'no-store','Content-Disposition':f'attachment; filename="private-upload-{dataset_id}.csv"'})
    except UploadError as exc:fail(exc)


@router.get('/{dataset_id}/analysis')
def analysis(dataset_id:str,response:Response,view:str='overview',dimension:str='device_type',metric:str='completion_rate',start_date:str|None=None,end_date:str|None=None,token:str=Depends(require_workspace_token)):
    response.headers['Cache-Control']='no-store'
    try:
        dataset=get_dataset(dataset_id,token);bounds=dataset.get('date_range') or Filters().window()
        filters=Filters(start_date=start_date or bounds['start_date'],end_date=end_date or bounds['end_date'])
        return analyze_dataset(view,dataset_id,token,filters,dimension,metric)
    except (UploadError,ValueError) as exc:fail(exc)
