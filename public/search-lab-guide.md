# TalentPulse Search Quality & Experiment Lab

Created by Soham Patra · [Live application](https://talentpulse-analytics.vercel.app/#experiments) · [Code](https://github.com/sohampatra3/talentpulse-analytics)

## Product question

Which retrieval and recommendation approach helps candidates find suitable, current jobs, and what evidence would justify an online experiment?

Stepstone's public 2026 webinar programme discusses increasing application volume and signal quality. Its candidate-journey research describes different uses for conventional search and AI. These signals motivate an independent lab; they do not establish a specific internal conversion defect.

## Five-minute demonstration

1. **Decision overview:** inspect the source banner and a published fictional-catalog example. Offline relevance does not measure real application uplift.
2. **Compare models:** select a query, retrieval strategy and model. Compare GPT-4o, GPT-OSS 120B and Gemma 4 31B, or another catalog model. Cards versus document RAG uses identical candidate IDs.
3. **Retrieval & RAG:** inspect ranking movements, exact source quotes, invalid IDs, response timing and unknown billing. Ask the analyst for hypotheses; graph values come from saved results.
4. **Journey & segments:** retain the historical synthetic experiment separately. Map Adobe eVars/events and load an authorized report to investigate roles, devices, acquisition and application routes.
5. **Evidence & decisions:** review relevance, calculate sample requirements, export evidence and save an experiment brief.

## Metrics and evidence

nDCG@10 weights graded relevance toward early positions. Precision@5 divides relevant jobs in the first five positions by five. MRR records the reciprocal position of the first relevant job. Retrieval coverage asks whether the known synthetic reference set was found. Operational measurements include actual timing, tokens when returned, failures, invalid output and billing provenance.

Synthetic reference grades are automated and remain labelled. Complete workspace reviews enable reviewed-pool scores. Small samples do not produce fabricated confidence intervals. Application conversion requires eligible users and confirmed submissions. Application usefulness requires recruiter shortlist/interview outcomes from an ATS or equivalent source.

## Bring your own data

Upload CSV or Excel on any page and review the mapping. A mapped job catalog becomes a private versioned search corpus. Index changed documents in bounded batches, then use semantic or hybrid retrieval. Outcome datasets stay in analytics views; catalog rows cannot provide conversion denominators.

## Adobe and Power BI

The dedicated Adobe tab supports authentication and authorized REST/MCP reports. The measurement map records event/dimension meanings. Aggregate reports support descriptive investigation; assignment and outcome records are needed for user-level inference. External application handoffs remain unknown until confirmed.

The Power BI tab supports report connections and curated views. `talentpulse.v_search_lab_results` exposes published synthetic comparisons only. Authenticated CSV/JSON exports retain private result evidence.

## Public sources

- [Hiring Trends Update 2026](https://www.stepstone.de/e-recruiting/hr-wissen/webinare-events/arbeitsmarkt-recruiting-trends-juni-2026/ueber-stepstone/privatsphaere/)
- [Stepstone candidate journey research](https://www.stepstone.de/e-recruiting/hr-wissen/recruiting/stepstone-studie-2025-ki-und-jobsuche/)
- [Stepstone / QuantPi / TÜV AI.Lab study](https://www.thestepstonegroup.com/english/insights/articles/white-paper-uncovering-bias-in-ai-recruitment/)
- [Historical application-journey design case](https://www.szeja.design/afterapply)
- [Adobe and Power BI connection guide](https://talentpulse-analytics.vercel.app/integration-guide.md)

The lab uses synthetic history, fictional job documents and actual model calls. Uploaded records and connected reports preserve their own provenance.
