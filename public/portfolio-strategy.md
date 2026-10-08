# TalentPulse Lab: portfolio and referral strategy

Created by **Soham Patra**. Independent product analytics portfolio; no affiliation with Stepstone.

Live application: https://talentpulse-analytics.vercel.app
Source and reproducible methods: https://github.com/sohampatra3/talentpulse-analytics

## Position the project around a decision

Lead with: **“How would we decide whether AI job discovery improves the candidate journey enough to justify its latency, cost and quality trade-offs?”**

The project demonstrates how I frame a product question, define behavioral events, validate data, compare search variants, interpret uncertainty and communicate a recommendation. Its value is the analytical judgment behind the product, together with a working system that lets another analyst examine the evidence.

The Stepstone Product Analyst description explicitly includes discovery and hypothesis generation, tracking validation, A/B tests, Adobe Analytics, Power BI, Python, and stakeholder storytelling. These are public role requirements, not evidence of an undisclosed company problem. See the [official role listing](https://www.stepstone.de/stellenangebote--Product-Analyst-Dusseldorf-The-Stepstone-Group-GmbH--14495892-inline.html).

## What can be demonstrated today

- SQL-backed Neon telemetry and a Python analytics/statistical service, delivered through a deployed Vercel application.
- A labelled synthetic candidate journey: 50,000 users, 100,000 jobs, 350,000 sessions and more than 2.5 million events. These are generated records, not production usage or business impact.
- Historical simulated outcomes for database search, an OpenRouter GPT-4o arm and an Ollama GPT-OSS arm. New live model search runs show actual retrieval/inference latency and model responses; they do not produce historical conversion lift.
- Experiment denominators, allocation checks, adjusted comparisons, uncertainty, latency/error/cost guardrails, and an explicit distinction between observational segment findings and randomized evidence.
- Private CSV/Excel ingestion, reviewed field mapping and Gemma-assisted semantic metadata. Missing tracking or outcome fields stay unavailable rather than becoming invented zeroes.
- A role-focused investigation that connects conversion differences with device, acquisition and candidate context. AI drafts explanations from measured evidence; possible causes remain hypotheses.
- Dedicated Adobe REST/MCP and Power BI connection workspaces with encrypted server-side credentials. A configured URL is distinct from verified API access. Actual company credentials are required for real external evidence.
- A private feedback-to-decision board with observations, hypotheses, metrics, guardrails, success criteria, workflow stages and export.

## A five-minute demonstration

**0:00–0:40 — Frame the problem.** Start on Overview. State the decision, candidate outcome and data provenance. Explain which dates and population are being analyzed. Show the creator attribution and source badge briefly.

**0:40–1:30 — Find the opportunity.** Open Funnel & segments. Compare mobile and desktop or a selected market. Identify a point where the journey loses candidates. Check event coverage before interpreting that change. A larger drop-off is an opportunity to investigate, not proof of a specific cause.

**1:30–2:40 — Read the experiment.** Open Search experiments. Compare manual search with the two AI arms. Explain the numerator and exposed-user denominator, the allocation check, interval and adjusted significance. Show guardrails next to conversion. A statistically detectable increase can still be too small or too costly to ship.

**2:40–3:30 — Explain the next question.** Select a job role and investigate “Why could conversion be higher for this role?” Compare candidate mix, device, traffic source and tracking coverage. Ask the AI analyst to visualize a measured result. Explain that the model helps organize investigation; controlled follow-up or richer evidence is needed to identify a cause.

**3:30–4:15 — Demonstrate integration readiness.** Open Adobe Analytics and Power BI tabs. Show the exact setup, permissions and report controls. If you do not have organization access, say “These adapters are implemented; live organization access has not been supplied.” Use the uploaded-data flow to demonstrate real evidence ingestion instead.

**4:15–5:00 — Make the recommendation.** Open Feedback & decisions. Write one test brief with a primary metric, a guardrail and a success criterion. Finish with the decision you would take now, the uncertainty you would communicate, and the next test you would run.

## Example decision brief

**Question:** Does AI ranking help candidates find relevant jobs and complete an application?

**Population:** Eligible candidate users, assigned once at user level. Define eligibility, exposure, time window and exclusions before looking at outcomes.

**Primary metric:** Unique exposed candidates who submit an application / unique exposed candidates.

**Secondary evidence:** Search success, job-detail engagement, application completion, relevance judgments and time to relevant job.

**Guardrails:** Application errors, latency (include tail latency where available), inference cost per successful outcome, low-volume segment uncertainty, and recruiter-assessed application quality. Do not claim fairness from broad conversion rates alone.

**Design:** Pre-register the minimum practically useful effect, target sample size, allocation, analysis unit, comparison adjustment and stopping rule. Validate assignment and exposure events. Keep repeated sessions from inflating the user denominator.

**Readout:** Summarize absolute and relative effects with uncertainty. Inspect allocation and tracking. Explain whether guardrails permit rollout, whether more data is needed, or whether the hypothesis should be revised.

**Next investigation:** If a role segment performs better, test whether that difference persists after checking candidate mix and device/source effects. Use Adobe cohort reports only when dimensions and denominators are comparable. Treat retrospective subgroup analysis as exploratory.

Stepstone’s [responsible product and technology principles](https://www.thestepstonegroup.com/english/sustainability/responsible-product-and-technology/) emphasize autonomy, fairness, explainability and preventing harm. A portfolio can reflect these principles through provenance, transparent model comparisons and explicit limits; it cannot certify a real hiring system’s fairness.

## Referral outreach draft

Hi [Name],

I applied for the Product Analyst role in Düsseldorf and built TalentPulse Lab to demonstrate the work described in the role: behavioral tracking, SQL/Python analysis, experiments, Adobe/Power BI integration and clear product recommendations.

The live demo compares conventional job search with two AI search arms using explicitly synthetic candidate telemetry. It also accepts private CSV/Excel evidence and includes a feedback-to-experiment workflow. I can walk through the analytical choices and limitations in five minutes.

Would you be open to a short look and feedback on whether this demonstrates the analytical ownership your team values? If you feel it is a good fit, I would appreciate a referral or introduction to the relevant team.

Live demo: https://talentpulse-analytics.vercel.app
Source: https://github.com/sohampatra3/talentpulse-analytics

Thank you,
Soham Patra

Personalize the opening to the recipient’s actual work. Ask for a focused review rather than sending an exhaustive feature list. This draft is not sent by the application.

## Evidence packet to prepare

1. A short screen recording of the five-minute story, with the source badge visible.
2. One decision brief with the metric definition, sample, uncertainty, guardrail and recommendation.
3. One example of a data-quality issue discovered and how it changed the interpretation.
4. A reproducible source link and method notes; be ready to explain one SQL transformation and one statistical choice.
5. Clear provenance: simulated outcomes, actual uploaded evidence, live model responses and actual external reports are different sources.

Review the packet as if you were the product manager: “What should I decide, why should I trust the number, and what risk remains?” Improve those answers before adding another feature.

## Interview discussion and future work

Be ready to discuss selection bias, sample-ratio mismatch, statistical versus practical significance, repeated exposure, multiple comparisons, seasonality, tracking gaps and model costs. Explain how a rollout recommendation changes if latency worsens or relevant application quality declines.

Potential next steps, explicitly **future work**, are an authenticated multi-user team workspace, structured human relevance evaluations, approved production telemetry joins, operational monitoring and a native Power BI semantic model published in an authorized tenant. Do not describe these as already shipped.

For an initial team assignment, propose a narrow discovery cycle: agree one decision and baseline; audit its tracking and denominators; produce a reproducible readout; then pre-register one focused experiment with the product team. Let the actual team context determine scope and success.
