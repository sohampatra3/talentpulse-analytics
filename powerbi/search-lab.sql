-- Authorized read-only connection. Published synthetic runs only.
SELECT run_id, corpus_id, created_at, query, model, evidence, status,
       latency_ms, cost_usd,
       (metrics->>'ndcg')::double precision AS synthetic_reference_ndcg,
       (metrics->>'precision5')::double precision AS synthetic_reference_precision5
FROM talentpulse.v_search_lab_results
ORDER BY created_at DESC, run_id, ordinal;

-- Unknown billing stays NULL; show support next to averages.
SELECT model, evidence, count(*) AS attempts,
       count(cost_usd) AS attempts_with_billing,
       avg(cost_usd) AS mean_known_generation_cost_usd,
       avg(latency_ms) AS mean_measured_latency_ms
FROM talentpulse.v_search_lab_results
GROUP BY model, evidence;
