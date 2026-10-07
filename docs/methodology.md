# Analytical methodology

## Population and grains

The dimensions describe synthetic users, jobs, dates and releases. `fact_sessions` holds one behavioral session, with a monotonic sequence of search, job view, apply click, start and submit flags. `fact_events` stores individual timestamped events. `fact_applications` records application attempts. Assignment is fixed at the user grain: repeated visits cannot switch experiment arms.

The primary funnel uses ordered session behavior. A person can contribute several sessions; its figures must be described as sessions rather than unique users unless the endpoint explicitly deduplicates people. A cross-session lifetime funnel would answer a different question. Session ordering prevents an unrelated submit from creating a conversion without a preceding start.

## KPI dictionary

| Metric | Numerator | Denominator |
|---|---|---|
| Application conversion | Sessions with submission | Search sessions |
| Application completion | Sessions with submission | Sessions with application start |
| Search success | Sessions with completed search | Search sessions |
| Job engagement | Sessions with job view | Search sessions |
| Application error rate | Application error sessions | All search sessions |
| DAU | Distinct active users on one day | None |
| WAU | Distinct active users in a rolling seven-day window | None |

Each response states its date range, units and denominator. Compare equal-length prior periods where data exists; unavailable comparisons remain unavailable. A percentage-point change and a relative percent change are different quantities.

## Experiment design

The lab uses a randomized three-arm search-ranking experiment: manual SQL ranking, simulated GPT-4o ranking, and simulated GPT-OSS 120B ranking. The assignment is one third per arm, randomized once per user. There are two planned comparisons against the same control.

The primary result uses a fixed observation window and one binary user-level outcome: any eligible submitted application. Repeated events do not increase the statistical sample size. A per-session engagement chart is descriptive and cannot replace user-level inference. Report exposure counts and investigate selection or missing telemetry before making a rollout decision.

A two-sided proportions test and a confidence interval for the absolute conversion difference describe uncertainty. Holm correction controls the family-wise error rate across the two planned comparisons. Confidence intervals are pointwise unless explicitly labelled as adjusted. A sample-ratio mismatch check compares assignment counts with the planned allocation. Small or empty samples must return an insufficient-data result rather than a confident winner.

Latency, application failures and model cost are guardrails. A statistically detectable conversion lift alone is insufficient for rollout if operational or experience guardrails are unacceptable. Cost and latency in the historical generator are modeled; only live provider records describe actual API performance.

Do not repeatedly peek at fixed-horizon p-values and treat the first significant result as a stopping rule. The portfolio example is a completed, pre-specified synthetic analysis. A production sequential design requires a valid sequential testing method and a pre-agreed decision policy.

## Release and segment analysis

Before/after comparisons are observational. Keep windows equal, identify devices and markets affected, inspect errors, and consider traffic mix and concurrent experiments. Differences suggest hypotheses; they do not establish causality. Segment drill-downs should show both counts and rates, so a tiny segment with an extreme rate does not dominate the recommendation.

## AI evidence contract

The server selects supported analytical tools, runs parameterized SQL, and produces structured evidence. The model can explain the evidence and propose hypotheses. The model cannot execute arbitrary SQL, invent observations or create numerical chart data. Chart drafts use the server's result rows. Responses disclose evidence mode or a provider failure, and a recommendation remains subject to analyst review.

## Synthetic realism

Users, jobs, sessions, application progress and event timestamps are linked relationally. Market, device, experience and acquisition source influence behavior. The generator adds plausible weekday/traffic variation and localized product friction. The synthetic causal rules are generation assumptions, not facts about an employer or a model. A fixed seed makes results reproducible.
