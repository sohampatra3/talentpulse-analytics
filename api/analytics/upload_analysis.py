"""Analytics of private mapped rows; missing measures are never invented."""
from __future__ import annotations

from collections import defaultdict
from datetime import date,timedelta
from statistics import mean

from analytics.experiments import analyze_experiment
from .filters import Filters
from .db import read_transaction
from .uploads import UploadError,dataset_rows,get_dataset,search_rows

STAGES=[('search_started','Search started'),('search_completed','Search completed'),('job_viewed','Job viewed'),('apply_clicked','Apply clicked'),('application_started','Application started'),('cv_uploaded','CV uploaded'),('application_submitted','Application submitted')]
DIMENSIONS=['market','device_type','user_type','job_category','job_title','traffic_source','experience_level','variant']
METRICS=['conversion_rate','completion_rate','job_view_rate','error_rate','avg_load_time_ms','sessions']


def pct(n,d):return n/d*100 if d and n is not None else None


def measurement_readiness(dataset,values,sessions):
    n=len(values);users=[v.get('user_id') for v in values];ids=[v.get('session_id') for v in values]
    outcomes=sum(isinstance(v.get('converted'),bool) or isinstance(v.get('application_submitted'),bool) for v in values)
    denominator=bool(sessions) or dataset['kind'] in {'user_outcomes','experiment_summary'}
    return [
        {'label':'Mapped column coverage','value':dataset.get('evidence_quality',{}).get('mapped_column_coverage'),'status':'observed','detail':f"{len(set(dataset['mapping'].values()))} of {len(dataset['columns'])} source columns are mapped; this is coverage, not a quality score."},
        {'label':'Identifier coverage','value':sum(bool(v) for v in (ids if dataset['kind'] in {'sessions','events'} else users)),'status':'observed' if any(ids) or any(users) else 'unavailable','detail':f'{n} selected rows; identifiers are checked for presence and session uniqueness, without verifying external identity.'},
        {'label':'Conversion denominator','value':len(sessions) if sessions else len({v["user_id"] for v in values if v.get('user_id') and v.get('exposed') is True}) if dataset['kind']=='user_outcomes' else sum(v.get('samples') or 0 for v in values) if dataset['kind']=='experiment_summary' else None,'status':'observed' if denominator else 'unavailable','detail':'Observed sessions or explicit exposed-user/sample counts. Catalog rows do not supply a conversion denominator.'},
        {'label':'Outcome coverage','value':outcomes,'status':'observed' if outcomes else 'unavailable','detail':f'{n} selected rows; missing outcome values are not assumed to be failures.'},
        {'label':'Randomization provenance','value':dataset.get('evidence_quality',{}).get('randomized_status','unknown'),'status':'declared' if dataset.get('evidence_quality',{}).get('randomized_status')=='user_declared' else 'unavailable','detail':'User declarations have not been independently audited; role slices remain exploratory.'},
        {'label':'Numeric evidence source','value':'Stored typed uploaded rows','status':'observed','detail':'Numeric charts are deterministic calculations from authorized Neon rows; model suggestions cannot replace them.'},
    ]


def source_meta(dataset,filters):
    return {'synthetic':None,'source':f"Private upload · {dataset['name']}",'source_type':'uploaded','dataset_id':dataset['dataset_id'],'grain':dataset['kind'],**filters.window(),'observation_window':dataset.get('date_range'),'date_filter_applied':'date' in dataset['mapping'],'date_filter_note':None if 'date' in dataset['mapping'] else 'Dates are not mapped. The requested date selection cannot filter these rows or establish an observation window.','evidence_quality':dataset.get('evidence_quality',{}),'readiness':dataset['readiness']}


def select_rows(records,filters,role=None,kind=None):
    if kind=='events':
        # Filter cohorts after session attribution; event rows often omit dimensions
        # repeated on the initiating event. Dropping those rows would drop outcomes.
        cohorts=behavioral_sessions([r['normalized_data'] for r in records],'events')
        selected=select_rows([{'normalized_data':v,'row_number':i} for i,v in enumerate(cohorts)],filters,role)
        by_session={v['session_id']:v for v in selected}
        return [{**r['normalized_data'],**{key:by_session[r['normalized_data']['session_id']].get(key) for key in DIMENSIONS+['user_id','job_title','date']},'_row_number':r['row_number']} for r in records if r['normalized_data'].get('session_id') in by_session]
    values=[]
    for record in records:
        item=dict(record['normalized_data']);item['_row_number']=record['row_number']
        if item.get('date') and not str(filters.start_date)<=item['date']<=str(filters.end_date):continue
        if any(getattr(filters,key,None) is not None and item.get(key)!=getattr(filters,key) for key in DIMENSIONS if key!='job_title'):continue
        if role and role not in {item.get('job_title'),item.get('job_category')}:continue
        values.append(item)
    return values


def behavioral_sessions(values,kind):
    if kind=='sessions':
        grouped={}
        for item in values:
            key=item.get('session_id')
            if key is None:continue
            if key in grouped:raise UploadError('Session-grain analytics requires unique session IDs; duplicate session rows were found.')
            grouped[key]={**item,'search_started':True}
        return list(grouped.values())
    if kind=='events':
        grouped={}
        observed_events={item.get('event_name') for item in values}
        for item in values:
            key=item.get('session_id')
            if key is None:continue
            previous=grouped.setdefault(key,{**item,**{stage:False if stage in observed_events else None for stage,_ in STAGES},'application_error':False if 'application_error' in observed_events else None})
            for identifier in ('user_id','variant'):
                if previous.get(identifier) is not None and item.get(identifier) is not None and previous[identifier]!=item[identifier]:
                    raise UploadError('A session has conflicting user or experiment attribution.')
            for field in DIMENSIONS+['user_id','job_title']:
                if previous.get(field) is None and item.get(field) is not None:previous[field]=item[field]
            if item.get('date') and (not previous.get('date') or item['date']<previous['date']):previous['date']=item['date']
            event=item.get('event_name')
            if event in dict(STAGES):previous[event]=True
            if event=='application_error':previous['application_error']=True
        return list(grouped.values())
    return []


def aggregate_sessions(values):
    n=len(values)
    def observed(field):return sum(item.get(field) is True for item in values) if values and all(item.get(field) is not None for item in values) else None
    starts=observed('application_started');applications=observed('application_submitted');views=observed('job_viewed');errors=observed('application_error')
    complete_outcome=bool(values) and all(item.get('application_submitted') is not None for item in values)
    latency=[item['load_time_ms'] for item in values if item.get('load_time_ms') is not None]
    return {'sessions':n,'searches':n,'application_starts':starts,'applications':applications,'job_views':views,'errors':errors,'conversion_rate':pct(applications,n) if complete_outcome else None,'completion_rate':pct(applications,starts) if complete_outcome and starts is not None else None,'job_view_rate':pct(views,n) if views is not None else None,'error_rate':pct(errors,n) if errors is not None else None,'avg_load_time_ms':mean(latency) if latency else None,'latency_ms':mean(latency) if latency else None}


def aggregate_users(values):
    complete=bool(values) and all(v.get('user_id') and isinstance(v.get('exposed'),bool) and isinstance(v.get('converted'),bool) for v in values)
    exposed={v['user_id'] for v in values if v.get('user_id') and v.get('exposed') is True}
    converted={v['user_id'] for v in values if v.get('user_id') and v.get('exposed') is True and v.get('converted') is True}
    return {'users':len({v['user_id'] for v in values if v.get('user_id')}) if complete else None,'exposed_users':len(exposed) if complete else None,'applications':len(converted) if complete else None,'conversion_rate':pct(len(converted),len(exposed)) if complete else None,'sessions':None,'searches':None,'completion_rate':None,'job_view_rate':None,'error_rate':None,'latency_ms':None,'avg_load_time_ms':None}


def user_segments(values,dimension,metric):
    groups=defaultdict(list)
    for item in values:groups[str(item.get(dimension) or 'Unspecified')].append(item)
    return [{'name':label,'label':label,dimension:label,**aggregate_users(items),'metric_value':aggregate_users(items).get(metric),'rows':len(items)} for label,items in sorted(groups.items())]


def unavailable(view,meta,reason):
    base={'meta':meta,'available':False,'reason':reason,'insights':[{'title':'Analysis unavailable','detail':reason,'severity':'info'}]}
    if view=='overview':return {**base,'kpis':[],'product_metrics':{},'trend':[],'markets':[],'devices':[]}
    if view=='funnel':return {**base,'steps':[],'overall_conversion_rate':None,'biggest_drop':None}
    if view=='segments':return {**base,'rows':[],'dimensions':DIMENSIONS,'metrics':METRICS}
    if view=='releases':return {**base,'releases':[],'disclaimer':reason}
    return {**base,'arms':[],'variants':[],'comparisons':[],'guardrails':[],'allocation':[],'srm':{'status':'unavailable','mismatch':False,'p_value':None},'status':'unavailable','limitations':[reason]}


def segment_rows(values,dimension,metric):
    groups=defaultdict(list)
    for item in values:groups[str(item.get(dimension) or 'Unspecified')].append(item)
    result=[]
    for label,items in groups.items():
        data=aggregate_sessions(items)
        result.append({**data,'name':label,'label':label,dimension:label,'metric_value':data[metric],'application_rate':data['conversion_rate'],'share':pct(len(items),len(values))})
    return sorted(result,key=lambda item:item['sessions'],reverse=True)


def uploaded_experiment(dataset,values,meta,force_descriptive=False):
    groups=defaultdict(dict);contamination=defaultdict(set)
    incomplete_arms=set();seen_rows=set();duplicate_users=False
    if dataset['kind']=='experiment_summary':
        totals=defaultdict(lambda:{'assigned':0,'exposed':0,'converted':0})
        for item in values:
            arm=item.get('variant');sample=item.get('samples');converted=item.get('conversions')
            if arm is None or sample is None or converted is None:continue
            totals[arm]['assigned']+=int(sample);totals[arm]['exposed']+=int(sample);totals[arm]['converted']+=int(converted)
        arm_data=[{'variant':arm,'assigned_users':data['assigned'],'exposed_users':data['exposed'],'converted_users':data['converted'],'engaged_users':0,'sessions':0,'errors':0,'avg_load_time_ms':0,'model_cost_usd':0} for arm,data in totals.items()]
        declared=False
    else:
        for item in values:
            user=item.get('user_id');arm=item.get('variant')
            if user is None or arm is None:continue
            if (user,arm) in seen_rows:duplicate_users=True
            seen_rows.add((user,arm))
            if dataset['kind']=='user_outcomes' and (not isinstance(item.get('converted'),bool) or not isinstance(item.get('exposed'),bool)):incomplete_arms.add(arm)
            if dataset['kind']=='sessions' and not isinstance(item.get('application_submitted'),bool) and not isinstance(item.get('converted'),bool):incomplete_arms.add(arm)
            contamination[user].add(arm)
            outcome=groups[arm].setdefault(user,{'converted':False,'engaged':False,'exposed':False})
            outcome['converted']|=item.get('converted') is True or item.get('application_submitted') is True or item.get('event_name')=='application_submitted'
            outcome['engaged']|=item.get('job_engaged') is True or item.get('job_viewed') is True or item.get('event_name')=='job_viewed'
            outcome['exposed']|=item.get('exposed') is True if dataset['kind']=='user_outcomes' else True
        arm_data=[{'variant':arm,'assigned_users':len(users),'exposed_users':sum(o['exposed'] for o in users.values()),'converted_users':sum(o['converted'] and o['exposed'] for o in users.values()),'engaged_users':sum(o['engaged'] and o['exposed'] for o in users.values()),'sessions':0,'errors':0,'avg_load_time_ms':0,'model_cost_usd':0} for arm,users in groups.items()]
        declared=bool(values) and all(item.get('randomized') is True and item.get('assignment_unit')=='user' and item.get('user_id') and item.get('variant') and isinstance(item.get('converted'),bool) and isinstance(item.get('exposed'),bool) for item in values)
    contamination_count=sum(len(arms)>1 for arms in contamination.values())
    inferential=declared and not contamination_count and not duplicate_users and not force_descriptive and dataset['kind']=='user_outcomes' and len(arm_data)>=2 and 'date' in dataset['mapping'] and all(v.get('date') for v in values) and 'control' in {arm['variant'] for arm in arm_data}
    if inferential:
        result=analyze_experiment(arm_data)
        result['synthetic']=None;result['window_start']=meta['start_date'];result['window_end']=meta['end_date']
        # Uploaded allocation plans are unknown; assuming equal arms would invent an SRM hypothesis.
        result['srm']={'status':'planned_allocation_unknown','mismatch':False,'p_value':None,'observed':[arm['assigned_users'] for arm in arm_data]}
        result['status']='analyzed' if any(c['p_value'] is not None for c in result['comparisons']) else 'insufficient_data'
        for c in result['comparisons']:c['adjustment']=f"Holm across {len(result['comparisons'])} uploaded treatment-versus-control comparisons"
        result['limitations']=['Randomization and observation-window provenance are user-declared and have not been independently audited.','Planned treatment allocation is not supplied, so no sample-ratio-mismatch hypothesis is tested.','Exploratory filtering is not an adjusted confirmatory subgroup analysis.','Exposed-user inference requires exposure selection to be unaffected by treatment; no causal winner is independently verified.']
        for guardrail in result['guardrails']:
            guardrail.update({'avg_load_time_ms':None,'latency_delta_ms':None,'model_cost_usd':None,'cost_per_search_usd':None,'application_error_rate':None,'latency_budget_passed':None})
    else:
        for arm in arm_data:
            if arm['variant'] in incomplete_arms:arm['converted_users']=None
        result={'variants':[{**arm,'conversion_rate':arm['converted_users']/arm['exposed_users'] if arm['exposed_users'] and arm['converted_users'] is not None else None} for arm in arm_data],'comparisons':[],'guardrails':[],'srm':{'status':'assignment_provenance_unavailable','mismatch':False,'p_value':None},'status':'descriptive_only','limitations':['No inferential winner: complete unique user-grain assignments, declared randomization, a control arm and unambiguous outcomes are required.','Role/category breakdowns are exploratory associations; role engagement may occur after assignment.','Arms with missing outcomes have unavailable conversion rates, rather than assumed failures.']}
    comparisons={item['variant']:item for item in result['comparisons']}
    result['arms']=[]
    for arm in result['variants']:
        comparison=comparisons.get(arm['variant'],{});ci=comparison.get('simultaneous_confidence_interval_pp')
        result['arms'].append({'arm':arm['variant'],'variant':arm['variant'],'label':arm['variant'],'provider':'uploaded','model':None,'assigned_users':arm['assigned_users'],'exposed_users':arm['exposed_users'],'users':arm['exposed_users'],'applications':arm['converted_users'],'sessions':0,'conversion_rate':pct(arm['converted_users'],arm['exposed_users']),'exposure_rate':pct(arm['exposed_users'],arm['assigned_users']),'lift_pct':comparison.get('relative_lift')*100 if comparison.get('relative_lift') is not None else None,'absolute_lift_pp':comparison.get('absolute_lift_pp'),'ci_low':ci[0] if ci else None,'ci_high':ci[1] if ci else None,'p_value':comparison.get('adjusted_p_value'),'significant':comparison.get('significant',False),'latency_ms':None,'cost_usd':None,'decision':comparison.get('decision','Descriptive association')})
    return {**result,'meta':meta,'available':True,'primary_metric':'Users with observed conversion / exposed uploaded users' if dataset['kind']!='experiment_summary' else 'Explicit uploaded conversions / explicit uploaded samples','analysis_unit':'user' if dataset['kind']!='experiment_summary' else 'user-declared aggregate sample','assignment_unit':'user' if declared else 'unknown','window_start':meta['start_date'],'window_end':meta['end_date'],'allocation':[{'name':a['label'],'variant':a['variant'],'users':a['assigned_users']} for a in result['arms']],'filter_note':'Uploaded user/window provenance. All role breakdowns are exploratory; historical synthetic experiment data is not mixed with these rows.','contaminated_users':contamination_count,'randomized_status':'user_declared' if declared else 'unknown','rate_units':{'arms':'percent','variants':'fraction','comparisons':'fraction except *_pp'}}


@read_transaction
def analyze_dataset(kind,dataset_id,workspace_token,filters,dimension='device_type',metric='completion_rate'):
    dataset,records=dataset_rows(dataset_id,workspace_token);meta=source_meta(dataset,filters)
    values=select_rows(records,filters,kind=dataset['kind'])
    if kind=='filters':return {**dataset.get('filter_options',{}),'date_range':dataset.get('date_range') or filters.window(),'synthetic':None,'dataset_id':dataset_id,'readiness':dataset['readiness']}
    if kind=='quality':
        identifiers=[v.get('user_id') for v in values if v.get('user_id')];session_ids=[v.get('session_id') for v in values if v.get('session_id')]
        checks=[{'key':'parsed_rows','label':'Stored parsed rows','status':'pass' if records else 'fail','observed':len(records),'threshold':1,'unit':'rows','detail':'Rows parsed and stored with typed mapped values.'},{'key':'mapped_fields','label':'Mapped fields','status':'pass' if dataset['mapping'] else 'fail','observed':len(dataset['mapping']),'threshold':1,'unit':'fields','detail':'Mapping is explicit; unsupported analyses remain unavailable.'}]
        return {'meta':meta,'score':None,'status':'observed_evidence','checks':checks,'daily':[],'event_volume':len(values) if dataset['kind']=='events' else None,'session_volume':len(set(session_ids)) if session_ids else None,'evidence_quality':{**dataset.get('evidence_quality',{}),'selected_rows':len(values),'selected_unique_users':len(set(identifiers))},'note':'Readiness reports observed coverage and grain, not an invented quality score.'}
    if kind=='tracking':
        counts=defaultdict(int)
        for item in values:
            if item.get('event_name'):counts[item['event_name']]+=1
        return {'meta':meta,'available':dataset['kind']=='events','events':[{'name':name,'description':'User-provided mapped event','trigger':'Defined by uploaded source','required_properties':list(dataset['mapping']),'owner':'Uploaded source','status':'observed','volume':count} for name,count in sorted(counts.items())],'common_properties':list(dataset['mapping'])}
    if kind not in {'overview','funnel','segments','experiments','releases'}:raise UploadError('Choose a supported analytics view.')
    if not dataset['readiness'].get(kind):return unavailable(kind,meta,dataset.get('reasons',{}).get(kind,'Required mapped fields are unavailable.'))
    if kind=='experiments':return uploaded_experiment(dataset,values,meta,force_descriptive=any(getattr(filters,d,None) for d in DIMENSIONS))
    if dataset['kind']=='user_outcomes':
        metrics=['conversion_rate','users','exposed_users','applications']
        if kind=='segments':
            chosen=metric if metric in metrics else 'conversion_rate'
            return {'meta':meta,'available':True,'dimension':dimension,'metric':chosen,'rows':user_segments(values,dimension,chosen),'dimensions':[d for d in DIMENSIONS if d in dataset['mapping']],'metrics':metrics,'metric_note':'Distinct exposed-user conversion; cohort breakdowns are observational and may overlap.'}
        totals=aggregate_users(values);daily=defaultdict(list)
        for v in values:
            if v.get('date'):daily[v['date']].append(v)
        return {'meta':{**meta,'denominator':'distinct exposed uploaded users','comparison_available':False},'available':True,'kpis':[{'key':key,'label':label,'value':totals[key],'unit':unit,'delta':None,'previous_value':None,'description':'Distinct mapped uploaded user outcomes; complete IDs and explicit outcomes are required.'} for key,label,unit in [('users','Uploaded users','number'),('exposed_users','Exposed users','number'),('applications','Converted users','number'),('conversion_rate','Exposed-user conversion','percent')]],'product_metrics':{'dau':None,'wau':None,'job_views':None,'application_starts':None,'search_success_rate':None},'trend':[{'date':day,**aggregate_users(items)} for day,items in sorted(daily.items())],'markets':user_segments(values,'market','conversion_rate'),'devices':user_segments(values,'device_type','conversion_rate'),'insights':[{'title':'User outcome denominator','detail':'Uploaded users are deduplicated. These outcomes do not imply measured sessions, latency or causal subgroup effects.','severity':'info'}]}
    sessions=behavioral_sessions(values,dataset['kind'])
    if dataset['kind'] not in {'sessions','events'}:
        groups=defaultdict(int)
        for item in values:groups[str(item.get('job_category') or item.get('job_title') or 'Unspecified')]+=1
        if kind=='segments':return {'meta':meta,'available':True,'dimension':'job_category','metric':'rows','rows':[{'name':label,'label':label,'sessions':None,'applications':None,'metric_value':count,'rows':count,'share':pct(count,len(values))} for label,count in groups.items()],'dimensions':[f for f in DIMENSIONS if f in dataset['mapping']],'metrics':['rows'],'metric_note':'Catalog supply counts; behavioral conversion is unavailable.'}
        return {'meta':meta,'available':True,'kpis':[{'key':'uploaded_rows','label':'Uploaded catalog rows' if dataset['kind']=='jobs' else 'Uploaded rows','value':len(values),'unit':'number','delta':None,'previous_value':None,'description':'Observed uploaded records. No user conversion is inferred.'}],'product_metrics':{'dau':None,'wau':None,'job_views':None,'search_success_rate':None},'trend':[],'markets':[],'devices':[],'catalog_breakdown':[{'role':key,'rows':count} for key,count in groups.items()],'insights':[{'title':'Behavioral data required','detail':'Catalog counts describe job supply. Add session/user outcomes to estimate conversion and experiment effects.','severity':'info'}]}
    aggregate=aggregate_sessions(sessions)
    if kind=='overview':
        definitions=[('sessions','Search sessions','number'),('applications','Submitted applications','number'),('conversion_rate','Search → application','percent'),('completion_rate','Application completion','percent'),('avg_load_time_ms','Mean latency','ms'),('error_rate','Application error rate','percent')]
        daily_groups=defaultdict(list)
        for item in sessions:
            if item.get('date'):daily_groups[item['date']].append(item)
        activity_filters=filters.model_copy(update={'start_date':filters.end_date-timedelta(days=6)})
        activity_sessions=behavioral_sessions(select_rows(records,activity_filters,kind=dataset['kind']),dataset['kind'])
        identity_available=all(field in dataset['mapping'] for field in ('user_id','date')) and all(i.get('user_id') and i.get('date') for i in activity_sessions)
        return {'meta':{**meta,'sessions':len(sessions),'events':len(values) if dataset['kind']=='events' else None,'comparison_available':False,'comparison_note':'Uploaded dataset: no comparison is inferred without a complete declared observation window.'},'available':True,'kpis':[{'key':key,'label':label,'unit':unit,'value':aggregate[key],'delta':None,'previous_value':None,'description':'Calculated from mapped uploaded session records; incomplete field coverage is unavailable.'} for key,label,unit in definitions],'product_metrics':{'dau':len({i['user_id'] for i in activity_sessions if i.get('date')==str(filters.end_date)}) if identity_available else None,'wau':len({i['user_id'] for i in activity_sessions}) if identity_available else None,'job_views':aggregate['job_views'],'application_starts':aggregate['application_starts'],'search_success_rate':pct(sum(i.get('search_completed') is True for i in sessions),len(sessions)) if sessions and all(i.get('search_completed') is not None for i in sessions) else None},'trend':[{'date':day,**aggregate_sessions(items)} for day,items in sorted(daily_groups.items())],'markets':segment_rows(sessions,'market','conversion_rate'),'devices':segment_rows(sessions,'device_type','conversion_rate'),'insights':[{'title':'Private uploaded evidence','detail':'Only mapped fields and observed uploaded records contribute to these metrics. Missing measures are unavailable. DAU and WAU describe observed uploaded activity, without assuming complete calendar coverage.','severity':'info'}]}
    if kind=='segments':
        if dimension not in DIMENSIONS or metric not in METRICS:raise UploadError('Choose a supported dimension and metric.')
        return {'meta':meta,'available':True,'dimension':dimension,'metric':metric,'rows':segment_rows(sessions,dimension,metric),'dimensions':[d for d in DIMENSIONS if d in dataset['mapping']],'metrics':METRICS}
    if kind=='funnel':
        selected=[stage for stage in STAGES if stage[0]!='cv_uploaded' or 'cv_uploaded' in dataset['mapping'] or any(i.get('cv_uploaded') is not None for i in sessions)]
        if any(any(item.get(stage) is None for item in sessions) for stage,_ in selected):return unavailable(kind,meta,'A mapped funnel stage has missing coverage; missing observations cannot be treated as zero.')
        counts=[sum(item.get(stage) is True for item in sessions) for stage,_ in selected]
        if any(b>a for a,b in zip(counts,counts[1:])):return unavailable(kind,meta,'Observed events are not a complete monotonic funnel. Missing earlier events must be investigated.')
        steps=[];previous=counts[0] if counts else 0
        for (field,label),count in zip(selected,counts):
            steps.append({'key':field,'label':label,'count':count,'conversion_rate':pct(count,counts[0]),'step_conversion_rate':pct(count,previous),'drop_off':previous-count,'drop_off_rate':pct(previous-count,previous)});previous=count
        biggest_index=max(range(1,len(steps)),key=lambda i:steps[i]['drop_off_rate'] or 0) if len(steps)>1 else None
        biggest={'from':steps[biggest_index-1]['label'],'to':steps[biggest_index]['label'],'count':steps[biggest_index]['drop_off'],'rate':steps[biggest_index]['drop_off_rate']} if biggest_index else None
        return {'meta':meta,'available':True,'steps':steps,'overall_conversion_rate':pct(counts[-1],counts[0]) if counts else None,'biggest_drop':biggest,'insights':[]}
    releases={}
    for item in values:
        if item.get('release_id') and item.get('release_date'):releases[item['release_id']]=item
    output=[]
    for release_id,release in releases.items():
        day=date.fromisoformat(release['release_date']);before=aggregate_sessions([i for i in sessions if i.get('date') and str(day-timedelta(days=7))<=i['date']<str(day)]);after=aggregate_sessions([i for i in sessions if i.get('date') and str(day)<=i['date']<=str(day+timedelta(days=6))])
        impact=after['completion_rate']-before['completion_rate'] if before['completion_rate'] is not None and after['completion_rate'] is not None else None
        output.append({'id':release_id,'name':release.get('release_name') or release_id,'feature':'Uploaded release marker','release_date':str(day),'market':'Uploaded selection','platform':'Uploaded selection','before':before,'after':after,'impact_pp':impact,'relative_lift_pct':None,'latency_change_ms':None,'before_window':{'start_date':str(day-timedelta(days=7)),'end_date':str(day-timedelta(days=1))},'after_window':{'start_date':str(day),'end_date':str(day+timedelta(days=6))},'confidence':'Observational association' if impact is not None else 'Insufficient baseline','interpretation':'Uploaded release windows are observational; traffic mix and exposure may confound differences.'})
    return {'meta':meta,'available':True,'releases':output,'disclaimer':'Associations do not establish causal release impact.'}


@read_transaction
def role_drivers(dataset_id,token,role,filters):
    dataset,records=dataset_rows(dataset_id,token);all_values=select_rows(records,filters,kind=dataset['kind'])
    options=sorted({str(v.get('job_title') or v.get('job_category')) for v in all_values if v.get('job_title') or v.get('job_category')})
    values=[v for v in all_values if not role or role in {v.get('job_title'),v.get('job_category')}]
    sessions=behavioral_sessions(values,dataset['kind'])
    support={'row_count':len(values),'session_count':len(sessions) if dataset['kind'] in {'sessions','events'} else None,'unique_users':len({v['user_id'] for v in values if v.get('user_id')}) if 'user_id' in dataset['mapping'] else None,'grain':dataset['kind'],'randomized_status':dataset.get('evidence_quality',{}).get('randomized_status','unknown'),'denominator':'observed search sessions' if sessions else 'explicit exposed uploaded users' if dataset['kind']=='user_outcomes' else 'uploaded catalog records; conversion unavailable'}
    drivers=[]
    for factor in ('device_type','market','traffic_source','experience_level','job_category'):
        if factor in dataset['mapping']:
            groups=segment_rows(sessions,factor,'conversion_rate') if sessions else []
            if dataset['kind']=='user_outcomes':
                bucket=defaultdict(list)
                for item in values:bucket[str(item.get(factor) or 'Unspecified')].append(item)
                groups=[]
                for label,items in bucket.items():
                    exposed={i['user_id'] for i in items if i.get('user_id') and i.get('exposed') is True};converted={i['user_id'] for i in items if i.get('user_id') and i.get('exposed') is True and i.get('converted') is True}
                    groups.append({'name':label,'label':label,**aggregate_users(items)})
            drivers.append({'factor':factor,'groups':groups,'interpretation':'Observed association; cohort mix and post-assignment selection can confound this breakdown.'})
    experiment=uploaded_experiment(dataset,values,source_meta(dataset,filters),True) if dataset['readiness']['experiments'] else {'arms':[]}
    return {'role':role,'role_options':options,'support':support,'arms':experiment['arms'],'drivers':drivers,'evidence_quality':dataset.get('evidence_quality',{}),'measurement_readiness':measurement_readiness(dataset,values,sessions),'limitations':['Role selection can occur after treatment assignment. No role-specific winner or causal driver is inferred.','Catalog-only uploads describe supply, not conversion.'],'suggested_experiment':'Pre-register a user-randomized role-relevance or freshness test, using observed application conversion and measured latency/error guardrails.'}


@read_transaction
def uploaded_job_candidates(dataset_id,token,query,market,category,count=40):
    dataset,records=dataset_rows(dataset_id,token)
    if dataset['kind']!='jobs':raise UploadError('Live job ranking requires a mapped job-catalog dataset.')
    candidates=[];terms=query.lower().split()
    for record in records:
        item=record['normalized_data']
        if market and market.lower()!='all' and item.get('market')!=market:continue
        if category and category.lower()!='all' and item.get('job_category')!=category:continue
        searchable=' '.join(str(v) for v in item.values()).lower();score=sum(term in searchable for term in terms)
        candidates.append({**item,'job_id':record['row_number'],'uploaded_job_id':item.get('job_id'),'job_title':item.get('job_title'),'job_category':item.get('job_category'),'location':item.get('location'),'market':item.get('market'),'salary_min':item.get('salary_min'),'salary_max':item.get('salary_max'),'remote_type':item.get('remote_type'),'experience_level':item.get('experience_level'),'posted_date':item.get('date'),'lexical_score':score})
    matched=[c for c in candidates if c['lexical_score']>0]
    return sorted(matched or candidates,key=lambda i:(-i['lexical_score'],i['job_id']))[:count],len(candidates),not bool(matched)


@read_transaction
def uploaded_evidence(dataset_id,token,question,filters):
    dataset,records=dataset_rows(dataset_id,token)
    if any(term in question.lower() for term in ('experiment','model','a/b','ranking')) and dataset['readiness']['experiments']:
        result=analyze_dataset('experiments',dataset_id,token,filters);data=[{'variant':a['label'],'conversion_rate':a['conversion_rate'],'users':a['exposed_users']} for a in result['arms']]
        answer='Uploaded user outcomes are summarized with their explicit denominators. '+('Inference follows user-declared randomization.' if result['status']=='analyzed' else 'The evidence supports descriptive comparisons; no inferential winner is declared.')
        chart={'type':'bar','title':'Uploaded user conversion (%)','x_key':'variant','y_key':'conversion_rate','data':data}
    elif dataset['kind'] in {'sessions','events','user_outcomes'}:
        dimension=next((field for word,field in [('device','device_type'),('market','market'),('country','market'),('traffic','traffic_source'),('variant','variant'),('model','variant')] if word in question.lower()),'job_category')
        result=analyze_dataset('segments',dataset_id,token,filters,dimension,'conversion_rate');data=result['rows']
        denominator='distinct exposed uploaded users' if dataset['kind']=='user_outcomes' else 'observed search sessions'
        answer=f'Uploaded conversion is calculated from {denominator}. Differences are exploratory associations and can reflect traffic or cohort mix.'
        chart={'type':'bar','title':f'Uploaded {dimension.replace("_"," ")} conversion (%)','x_key':'name','y_key':'conversion_rate','data':data}
    else:
        matches=search_rows(dataset_id,token,question);result={'matches':matches,'evidence_quality':dataset.get('evidence_quality',{})}
        groups=defaultdict(int)
        selected_values=select_rows(records,filters)
        for item in selected_values:groups[str(item.get('job_category') or 'Unspecified')]+=1
        data=[{'role':key,'rows':value} for key,value in groups.items()]
        answer=f"This private upload contains {dataset['row_count']} records. Catalog counts and searchable content are available; conversion requires behavioral outcomes."
        chart={'type':'bar','title':'Uploaded catalog supply','x_key':'role','y_key':'rows','data':data}
    return {'answer':answer,'evidence':[{'label':'Uploaded records','value':dataset['row_count'],'unit':'rows'}],'chart':chart,'context':result,'limitations':['Only authorized workspace rows are used. Numeric results are deterministic backend calculations; model prose cannot override them.','Uploaded provenance is user-provided; causal validity is not independently audited.']}
