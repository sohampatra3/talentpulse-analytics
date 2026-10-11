"""Additive migration and deterministic synthetic catalog; never prints credentials."""
import argparse
import asyncio
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
from psycopg.types.json import Jsonb
load_dotenv('.env.local');load_dotenv('.env')
from api.analytics.db import connection
from api.analytics.search_quality import synthetic_documents,benchmark_queries,VERSION,EMBEDDING_MODEL
from api.analytics.search_lab import PUBLIC_CORPUS,document_hash,embeddings
from api.analytics.ai_budget import client_context

async def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');parser.add_argument('--index',action='store_true');args=parser.parse_args()
    sql=Path('database/migrations/005_search_lab.sql').read_text()
    with connection(readonly=False) as conn:
        conn.execute("SET LOCAL statement_timeout='120000ms'")
        conn.execute(sql)
        if args.check:
            print('Migration validates; transaction rolled back.');conn.rollback();return
        conn.execute('INSERT INTO talentpulse.search_corpora(corpus_id,source,version,metadata) VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING',(PUBLIC_CORPUS,'Synthetic benchmark',VERSION,Jsonb({'source_type':'synthetic','generation':'Deterministic fictional postings; no real employer assertions.'})))
        conn.cursor().executemany('INSERT INTO talentpulse.search_documents(corpus_id,job_id,metadata,body,content_hash) VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',[(PUBLIC_CORPUS,meta['job_id'],Jsonb(meta),body,document_hash(body)) for meta,body in synthetic_documents()])
        conn.cursor().executemany('INSERT INTO talentpulse.search_queries(query_id,query,intent,language,split,rubric,version) VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(query_id) DO UPDATE SET query=EXCLUDED.query,intent=EXCLUDED.intent,split=EXCLUDED.split,rubric=EXCLUDED.rubric',[(q['query_id'],q['query'],q['intent'],q['language'],q['split'],Jsonb(q['rubric']),q['version']) for q in benchmark_queries()])
    print('Migration committed; 2,000 synthetic job documents and 60 query scenarios available.',flush=True)
    if args.index:
        context=client_context.set('search-lab-release-indexer')
        try:
            while True:
                with connection() as conn:docs=conn.execute('SELECT job_id,body,content_hash FROM talentpulse.search_documents WHERE corpus_id=%s AND embedding IS NULL ORDER BY job_id LIMIT 100',(PUBLIC_CORPUS,)).fetchall()
                if not docs:break
                vectors,_,_=await embeddings([d['body'] for d in docs],None)
                with connection(readonly=False) as conn:
                    conn.cursor().executemany('UPDATE talentpulse.search_documents SET embedding=%s::vector,embedding_model=%s WHERE corpus_id=%s AND job_id=%s AND content_hash=%s',[(str(v),EMBEDDING_MODEL,PUBLIC_CORPUS,d['job_id'],d['content_hash']) for d,v in zip(docs,vectors)])
                print('Indexed batch:',len(docs),'last document:',docs[-1]['job_id'],flush=True)
        finally:client_context.reset(context)

if __name__=='__main__':asyncio.run(main())
