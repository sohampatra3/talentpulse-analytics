"use client";

import { useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  Bot,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleHelp,
  Clock3,
  Copy,
  Database,
  Download,
  FileChartColumn,
  FlaskConical,
  Globe2,
  Info,
  Laptop,
  Layers3,
  Link2,
  LoaderCircle,
  MessageSquare,
  MonitorSmartphone,
  Plug,
  Rocket,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Target,
  TrendingUp,
  Users,
  WandSparkles,
  X,
} from "lucide-react";
import {
  apiFetch,
  apiFilters,
  downloadText,
  filterQuery,
  formatDate,
  formatNumber,
  formatPercent,
  useApi,
  type Filters,
} from "@/lib/api";
import type {
  AnalystAnswer,
  ExperimentArm,
  ExperimentsData,
  FunnelData,
  Integration,
  IntegrationData,
  ModelsData,
  OverviewData,
  QualityData,
  Release,
  ReleaseData,
  SearchResult,
  SegmentData,
  TrackingData,
} from "@/lib/types";
import { AnalystChart, ExperimentBars, ProductTrend } from "./charts";
import { ConnectorStudio, ExternalEvidence } from "./connectors";
import { ModelPicker, useWorkspace } from "./workspace";
import { DatasetReadiness } from "./uploads";
import { RoleEvidence } from "./role-evidence";
import {
  ActionFeedback,
  EmptyState,
  ErrorState,
  ExportButton,
  LoadingState,
  Metric,
  Note,
  Panel,
  PanelHeading,
  Pill,
  RequestStatus,
} from "./ui";

export type ViewName =
  | "overview"
  | "experiments"
  | "funnel"
  | "releases"
  | "analyst"
  | "powerbi"
  | "adobe"
  | "feedback"
  | "connections";
type ViewProps = { filters: Filters; navigate: (view: ViewName) => void };

function Insights({
  insights,
  navigate,
}: {
  insights: OverviewData["insights"];
  navigate?: (view: ViewName) => void;
}) {
  const icons = [
    <Target size={18} key="target" />,
    <MonitorSmartphone size={18} key="device" />,
    <TrendingUp size={18} key="trend" />,
  ];
  if (!insights.length) return null;
  return (
    <>
      <div className="section-label">
        <h2>Signals worth exploring</h2>
        <span>From the selected dataset</span>
      </div>
      <div className="insights-grid">
        {insights.map((insight, index) => (
          <Panel className="insight-card" key={insight.title}>
            <div className="insight-icon">{icons[index % icons.length]}</div>
            <h3>{insight.title}</h3>
            <p>{insight.detail}</p>
            {navigate ? (
              <button
                className="text-link insight-card-footer"
                onClick={() => navigate(index === 0 ? "funnel" : "analyst")}
              >
                Explore the evidence <ArrowUpRight size={12} />
              </button>
            ) : null}
          </Panel>
        ))}
      </div>
    </>
  );
}

export function OverviewView({ filters, navigate }: ViewProps) {
  const { data, loading, refreshing, error, retry, lastUpdated } =
    useApi<OverviewData>("/overview", filters);
  const [metric, setMetric] = useState<
    "searches" | "applications" | "completion_rate"
  >("searches");
  if (loading) return <LoadingState />;
  if (!data)
    return (
      <ErrorState
        message={error || "The analytics service did not return a response."}
        retry={retry}
      />
    );
  return (
    <>
      <RequestStatus
        refreshing={refreshing}
        error={error}
        retry={retry}
        lastUpdated={lastUpdated}
      />
      <section className="hero-panel panel">
        <div>
          <div className="eyebrow">Your product intelligence workspace</div>
          <h2>
            Better job discovery.
            <br />
            Backed by better evidence.
          </h2>
          <p>
            Follow the candidate journey, measure what changes, and discover
            where AI can make the next opportunity easier to find.
          </p>
          <div className="hero-links">
            <button
              className="button primary"
              onClick={() => navigate("experiments")}
            >
              Explore search experiment <ArrowUpRight size={13} />
            </button>
            <button className="text-link" onClick={() => navigate("analyst")}>
              Ask your AI analyst <ArrowRight size={13} />
            </button>
          </div>
        </div>
        <div className="hero-art" aria-hidden="true">
          <div className="orbital">
            <div className="orbital-core">
              <FlaskConical size={25} strokeWidth={1.6} />
            </div>
            <div className="orbit-node orbit-one">
              <Search size={12} /> Discover
            </div>
            <div className="orbit-node orbit-two">
              <Sparkles size={12} /> Experiment
            </div>
            <div className="orbit-node orbit-three">
              <BarChart3 size={12} /> Understand
            </div>
          </div>
        </div>
      </section>
      <div
        className={`metrics-grid ${data.kpis.length > 4 ? "metrics-six" : ""}`}
      >
        {data.kpis.map((kpi) => (
          <Metric
            key={kpi.key}
            label={kpi.label}
            value={kpi.value}
            unit={
              kpi.unit === "count" || kpi.unit === "number"
                ? undefined
                : kpi.unit === "percent"
                  ? "%"
                  : kpi.unit
            }
            delta={kpi.delta}
            lowerIsBetter={
              kpi.key.includes("error") ||
              kpi.key.includes("load") ||
              kpi.key.includes("latency")
            }
          />
        ))}
      </div>
      {data.product_metrics ? (
        <Panel className="product-pulse">
          <div className="pulse-heading">
            <Users size={15} />
            <span>Candidate activity</span>
          </div>
          <div>
            <span>Daily active candidates</span>
            <strong>{formatNumber(data.product_metrics.dau)}</strong>
          </div>
          <div>
            <span>Weekly active candidates</span>
            <strong>{formatNumber(data.product_metrics.wau)}</strong>
          </div>
          <div>
            <span>Job views</span>
            <strong>{formatNumber(data.product_metrics.job_views)}</strong>
          </div>
          <div>
            <span>Search success</span>
            <strong>
              {formatPercent(data.product_metrics.search_success_rate)}
            </strong>
          </div>
        </Panel>
      ) : null}
      <div className="two-column">
        <Panel>
          <PanelHeading
            title="The rhythm of your product"
            description="Daily activity across the candidate journey"
            action={
              <select
                aria-label="Chart metric"
                className="chart-select"
                value={metric}
                onChange={(event) =>
                  setMetric(event.target.value as typeof metric)
                }
              >
                <option value="searches">Searches</option>
                <option value="applications">Applications</option>
                <option value="completion_rate">Completion rate</option>
              </select>
            }
          />
          <div className="chart-legend">
            <span className="legend-item">
              <i
                className="legend-dot"
                style={{ background: "var(--accent-bright)" }}
              />
              {metric === "searches"
                ? "Search sessions"
                : metric === "applications"
                  ? "Submitted applications"
                  : "Applications / application starts"}
            </span>
            <span className="pill pill-neutral">Daily</span>
          </div>
          {data.trend.length ? (
            <ProductTrend data={data.trend} metric={metric} />
          ) : (
            <EmptyState />
          )}
          <Note>
            Previous-period comparisons use the immediately preceding window.
          </Note>
        </Panel>
        <Panel>
          <PanelHeading
            title="A view across markets"
            description="Search share and application conversion"
            action={<Globe2 size={16} className="muted" />}
          />
          <div className="market-list">
            {data.markets.length ? (
              data.markets.map((market) => (
                <div className="market-row" key={market.market}>
                  <div className="market-row-top">
                    <span className="market-name">
                      <span className="market-code">
                        {market.market.slice(0, 2)}
                      </span>
                      {market.name || market.market}
                    </span>
                    <span className="market-stats">
                      {formatNumber(market.searches)} searches
                      <strong>{formatPercent(market.application_rate)}</strong>
                    </span>
                  </div>
                  <div className="market-track">
                    <div
                      className="market-fill"
                      style={{
                        width: `${Math.min(100, Math.max(0, market.share))}%`,
                      }}
                    />
                  </div>
                </div>
              ))
            ) : (
              <EmptyState />
            )}
          </div>
          <Note>
            Conversion = submitted applications / all search sessions.
          </Note>
        </Panel>
      </div>
      <Insights insights={data.insights} navigate={navigate} />
      <div className="footer-note">
        <div>
          <Database size={12} />
          {data.meta.source || "Neon PostgreSQL"} ·{" "}
          {typeof data.meta.events === "number"
            ? `${formatNumber(data.meta.events)} events in selection`
            : "Observed uploaded evidence"}
        </div>
        <span>
          Real queries.{" "}
          {data.meta.synthetic
            ? "Realistic synthetic telemetry."
            : "Workspace-private uploaded evidence."}{" "}
          <span className="hide-mobile">Built for product decisions.</span>
        </span>
      </div>
    </>
  );
}

function PValue({ value }: { value: number | null }) {
  return (
    <>{value === null ? "—" : value < 0.001 ? "< 0.001" : value.toFixed(3)}</>
  );
}
function Signed({
  value,
  suffix = "",
}: {
  value: number | null | undefined;
  suffix?: string;
}) {
  return (
    <>
      {value === null || value === undefined
        ? "—"
        : `${value > 0 ? "+" : ""}${value.toFixed(2)}${suffix}`}
    </>
  );
}
function ArmName({ arm }: { arm: ExperimentArm }) {
  return (
    <div className="arm-label">
      <span className={`arm-dot ${arm.arm}`} />
      <div>
        <div className="table-primary">{arm.label}</div>
        <div className="table-sub">
          {arm.provider} · {arm.arm === "control" ? "Control" : "Treatment"}
        </div>
      </div>
    </div>
  );
}

export function ExperimentsView({ filters, navigate }: ViewProps) {
  const workspace = useWorkspace();
  const supportsExperiments =
    !workspace.dataset || workspace.dataset.readiness.experiments !== false;
  const { data, loading, refreshing, error, retry, lastUpdated } =
    useApi<ExperimentsData>("/experiments", filters, supportsExperiments);
  if (!supportsExperiments)
    return (
      <>
        <DatasetReadiness view="experiments" onOpen={workspace.openUploads} />
        <LiveSearch filters={filters} navigate={navigate} />
        <RoleEvidence filters={filters} />
        <ExternalEvidence filters={filters} />
      </>
    );
  if (loading) return <LoadingState />;
  if (!data)
    return (
      <ErrorState
        message={error || "Experiment results are unavailable."}
        retry={retry}
      />
    );
  return (
    <>
      <RequestStatus
        refreshing={refreshing}
        error={error}
        retry={retry}
        lastUpdated={lastUpdated}
      />
      <div className="experiment-summary">
        <div className="experiment-summary-icon">
          <FlaskConical size={19} />
        </div>
        <div className="experiment-summary-copy">
          <h3>
            {filters.dataset_id
              ? "What do the uploaded arm outcomes support?"
              : "Can AI ranking help more candidates apply?"}
          </h3>
          <p>
            {filters.dataset_id ? (
              "Observed uploaded outcomes, explicit denominators, and declared assignment provenance. Missing guardrails remain unavailable."
            ) : (
              <>
                Three randomized arms. One fixed observation window. Compare{" "}
                <strong>user-level application conversion</strong> with cost,
                speed, and errors.
              </>
            )}
          </p>
        </div>
        <Pill tone="green" dot>
          {filters.dataset_id
            ? `${formatDate(apiFilters(filters).start_date, true)} — ${formatDate(apiFilters(filters).end_date, true)}`
            : "21 Sep — 4 Oct 2026"}
        </Pill>
      </div>
      <Panel>
        <PanelHeading
          eyebrow={
            filters.dataset_id
              ? "Private uploaded experiment evidence"
              : "Historical experiment · synthetic outcomes"
          }
          title="Manual search vs. AI recommendations"
          description={
            filters.dataset_id
              ? data.primary_metric ||
                "Uploaded outcome conversion with the supplied denominator"
              : "Primary metric: users who submitted an application / exposed users"
          }
          action={
            <ExportButton
              url={
                filters.dataset_id
                  ? `/api/uploads/${filters.dataset_id}/export`
                  : `/api/export/experiments?${filterQuery(filters)}`
              }
              label="CSV"
              authenticated={Boolean(filters.dataset_id)}
            />
          }
        />
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Search experience</th>
                <th>Exposed users</th>
                <th>Converted users</th>
                <th>Conversion</th>
                <th>Relative lift</th>
                <th>Lift interval · pp</th>
                <th>Adjusted p</th>
                <th>Evidence</th>
              </tr>
            </thead>
            <tbody>
              {data.arms.map((arm) => (
                <tr key={arm.arm}>
                  <td>
                    <ArmName arm={arm} />
                  </td>
                  <td>
                    {formatNumber(arm.exposed_users)}
                    <div className="table-sub">
                      {formatNumber(arm.assigned_users)} assigned
                    </div>
                  </td>
                  <td>{formatNumber(arm.applications)}</td>
                  <td className="table-primary">
                    {formatPercent(arm.conversion_rate, 2)}
                  </td>
                  <td
                    className={
                      arm.significant && (arm.lift_pct || 0) > 0
                        ? "positive"
                        : ""
                    }
                  >
                    {arm.arm === "control" ? (
                      "Baseline"
                    ) : (
                      <Signed value={arm.lift_pct} suffix="%" />
                    )}
                  </td>
                  <td>
                    {arm.ci_low === null
                      ? "—"
                      : `${arm.ci_low.toFixed(2)} to ${arm.ci_high?.toFixed(2)}`}
                  </td>
                  <td>
                    <PValue value={arm.p_value} />
                  </td>
                  <td>
                    <Pill
                      tone={
                        arm.arm === "control"
                          ? "neutral"
                          : arm.significant
                            ? "green"
                            : "amber"
                      }
                    >
                      {arm.arm === "control"
                        ? "Control"
                        : arm.significant
                          ? "Significant"
                          : "Inconclusive"}
                    </Pill>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Note>
          {filters.dataset_id
            ? "Adjusted p-values and lift intervals are displayed only when supplied assignment provenance permits an inferential readout. User declarations are not independently audited."
            : "Two comparisons against control. Holm-adjusted p-values and simultaneous 95% lift intervals. Repeated sessions never count as independent users."}
        </Note>
      </Panel>
      <div className="two-column equal-column" style={{ marginTop: 19 }}>
        <Panel>
          <PanelHeading
            title="Application conversion by arm"
            description="Exposed-user denominator · one outcome per user"
          />
          <ExperimentBars data={data.arms} />
          <Note>
            {filters.dataset_id
              ? "Uploaded arm outcomes and supplied denominators. These rates remain separate from live model responses."
              : "Historical synthetic experiment; these rates do not evaluate live model responses."}
          </Note>
        </Panel>
        <Panel>
          <PanelHeading
            title="Trust the measurement"
            description="Allocation, decision criteria, and practical constraints"
            action={<ShieldCheck size={17} className="muted" />}
          />
          <div className="panel-content">
            <div className="quality-check">
              <CheckCircle2 size={16} />
              <div>
                <strong>Sample ratio check</strong>
                <p>Assigned-user allocation against equal split</p>
              </div>
              <Pill tone={data.srm.mismatch ? "amber" : "green"}>
                {data.srm.status.replaceAll("_", " ")}
              </Pill>
            </div>
            <div className="quality-check">
              <Users size={16} />
              <div>
                <strong>Unit of analysis</strong>
                <p>
                  {filters.dataset_id
                    ? "Assignment grain supplied in the uploaded evidence"
                    : "Randomized and measured at candidate level"}
                </p>
              </div>
              <span>
                {filters.dataset_id
                  ? data.analysis_unit?.replaceAll("_", " ") || "Not declared"
                  : "User"}
              </span>
            </div>
            <div className="quality-check">
              <Target size={16} />
              <div>
                <strong>SRM p-value</strong>
                <p>A low p-value flags unexpected allocation</p>
              </div>
              <span>
                <PValue value={data.srm.p_value} />
              </span>
            </div>
            {data.arms
              .filter((arm) => arm.arm !== "control")
              .map((arm) => (
                <div className="quality-check" key={arm.arm}>
                  <CircleHelp size={16} />
                  <div>
                    <strong>{arm.label}</strong>
                    <p>{arm.decision}</p>
                  </div>
                </div>
              ))}
          </div>
        </Panel>
      </div>
      <Panel>
        <PanelHeading
          title="Keep the guardrails in view"
          description="Operational tradeoffs across the same experiment population"
        />
        <div className="panel-content">
          {!data.guardrails.length ? (
            <EmptyState
              title="Guardrails not supplied"
              description="Add observed latency, application errors, and model costs to evaluate operational tradeoffs."
            />
          ) : null}
          <div className="guardrail-grid">
            {data.guardrails.map((guardrail) => (
              <div className="guardrail" key={guardrail.variant}>
                <div>
                  <Clock3 size={13} />
                  {data.arms.find((arm) => arm.arm === guardrail.variant)
                    ?.label || guardrail.variant}
                </div>
                <strong>
                  {formatNumber(guardrail.avg_load_time_ms)}{" "}
                  <span className="small muted">ms</span>
                </strong>
                <p>
                  {formatPercent(
                    guardrail.application_error_rate === null
                      ? null
                      : guardrail.application_error_rate * 100,
                    2,
                  )}{" "}
                  application error rate
                  <br />${formatNumber(guardrail.model_cost_usd, 2)} historical
                  model cost · ${formatNumber(guardrail.cost_per_search_usd, 5)}{" "}
                  / search
                </p>
              </div>
            ))}
          </div>
        </div>
        <Note>{data.filter_note}</Note>
        {filters.dataset_id
          ? data.limitations?.map((limitation) => (
              <Note key={limitation}>{limitation}</Note>
            ))
          : null}
      </Panel>
      <LiveSearch filters={filters} navigate={navigate} />
      <RoleEvidence filters={filters} />
      <ExternalEvidence filters={filters} />
    </>
  );
}

function LiveSearch({
  filters,
  navigate,
}: {
  filters: Filters;
  navigate: (view: ViewName) => void;
}) {
  const workspace = useWorkspace();
  const models = workspace.models;
  const [searchModels, setSearchModels] = useState({
    openrouter: "",
    ollama: "",
  });
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<SearchResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function compare(event: React.FormEvent) {
    event.preventDefault();
    if (!query.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      setResult(
        await apiFetch<SearchResult>(
          "/search/compare",
          {
            method: "POST",
            body: JSON.stringify({
              query: query.trim(),
              market: filters.market === "all" ? undefined : filters.market,
              limit: 3,
              dataset_id: filters.dataset_id,
              models: {
                openrouter:
                  searchModels.openrouter ||
                  models?.defaults?.search.openrouter,
                ollama: searchModels.ollama || models?.defaults?.search.ollama,
              },
            }),
          },
          45_000,
        ),
      );
    } catch (failure) {
      setError(
        failure instanceof Error
          ? failure.message
          : "Search comparison failed.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="compare-title">
        <div>
          <h2>Try the search experience</h2>
          <p>
            Live retrieval and real model ranking, using the same{" "}
            {workspace.datasetId
              ? "private uploaded job catalog"
              : "synthetic job catalog"}
            .
          </p>
        </div>
        <Pill tone="blue">
          <Activity size={10} /> Live search lab
        </Pill>
      </div>
      <Panel>
        <div className="panel-content">
          <form onSubmit={compare}>
            <div className="model-selection-row">
              <ModelPicker
                provider="openrouter"
                purpose="search"
                value={searchModels.openrouter}
                onChange={(value) =>
                  setSearchModels((previous) => ({
                    ...previous,
                    openrouter: value,
                  }))
                }
              />
              <ModelPicker
                provider="ollama"
                purpose="search"
                value={searchModels.ollama}
                onChange={(value) =>
                  setSearchModels((previous) => ({
                    ...previous,
                    ollama: value,
                  }))
                }
              />
            </div>
            <label className="eyebrow" htmlFor="job-query">
              What would your next role look like?
            </label>
            <div className="query-form">
              <input
                id="job-query"
                className="query-input"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                maxLength={models?.policy.max_query_length || 400}
                placeholder="Product analyst in Düsseldorf · SQL, Python and experimentation"
                required
              />
              <button
                type="submit"
                className="button primary"
                disabled={
                  busy ||
                  !query.trim() ||
                  Boolean(
                    workspace.dataset && !workspace.dataset.readiness.jobs,
                  )
                }
              >
                {busy ? (
                  <LoaderCircle size={14} className="spin" />
                ) : (
                  <Search size={14} />
                )}
                {busy ? "Comparing…" : "Compare all three"}
              </button>
            </div>
          </form>
          <div className="provider-readiness">
            {models?.providers.map((provider) => (
              <span
                className={provider.configured ? "ready" : "not-ready"}
                key={provider.id}
              >
                {provider.configured ? <Check size={11} /> : <Info size={11} />}
                {provider.label}:{" "}
                {provider.configured
                  ? "credentials configured"
                  : "setup required"}
              </span>
            ))}
          </div>
          <p className="control-caption">
            {workspace.dataset && !workspace.dataset.readiness.jobs
              ? "This upload does not contain a searchable job catalog. Select a jobs upload or synthetic telemetry to try model ranking. "
              : ""}
            Market follows your active filter. A successful live call verifies
            provider connectivity. Historical experiment results remain
            separate.
          </p>
          {error ? (
            <div className="inline-error" role="alert">
              <Info size={14} />
              {error}
            </div>
          ) : null}
          {result ? (
            <>
              <div className="comparison-grid">
                {result.arms.map((arm) => (
                  <SearchArmCard key={arm.id} arm={arm} navigate={navigate} />
                ))}
              </div>
              <div className="control-caption">{result.measurement_note}</div>
            </>
          ) : null}
        </div>
      </Panel>
    </>
  );
}

function SearchArmCard({
  arm,
  navigate,
}: {
  arm: SearchResult["arms"][number];
  navigate: (view: ViewName) => void;
}) {
  const workspace = useWorkspace();
  const catalogLabel = workspace.models?.catalog?.find(
    (model) => model.id === arm.model && model.provider === arm.provider,
  )?.label;
  const modelLabel =
    catalogLabel ||
    (arm.model?.includes("gpt-4o")
      ? "GPT-4o"
      : arm.model?.startsWith("gpt-oss:120b")
        ? "GPT-OSS 120B"
        : arm.model?.startsWith("gemma4:31b")
          ? "Gemma 4 31B"
          : arm.model);
  const label = arm.model ? `${modelLabel} recommendation` : arm.label;
  const notCalled =
    arm.latency_ms === null ||
    ["not_configured", "rate_limited", "no_candidates"].includes(arm.status);
  const emptyTitle =
    arm.status === "not_configured"
      ? "Connect this model"
      : arm.status === "error"
        ? "Model request unavailable"
        : arm.status === "rate_limited"
          ? "Usage limit reached"
          : "No matching jobs";
  const emptyDescription =
    arm.status === "not_configured"
      ? "Add server credentials in Data & connections."
      : arm.status === "error"
        ? "Try again or review the provider configuration."
        : arm.status === "rate_limited"
          ? "The request exceeded the configured usage limit."
          : "Try broader skills or a different market.";
  return (
    <div className="comparison-card">
      <div className="comparison-head">
        <div>
          <h3>{label}</h3>
          <p>{arm.model || "Parameterized PostgreSQL"}</p>
        </div>
        <Pill
          tone={
            arm.status === "success" || arm.status === "ok" ? "green" : "amber"
          }
        >
          {arm.status.replaceAll("_", " ")}
        </Pill>
      </div>
      <div className="comparison-meta">
        <span>
          {notCalled ? "— latency" : `${formatNumber(arm.latency_ms)} ms`}
        </span>
        <span>
          {arm.cost_usd === null
            ? notCalled
              ? "— cost"
              : "Cost unavailable"
            : `$${formatNumber(arm.cost_usd, 5)}`}
        </span>
      </div>
      {arm.error ? (
        <div className="job-card">
          <h4>Model request unavailable</h4>
          <p className="job-reason">{arm.error}</p>
        </div>
      ) : null}
      {arm.jobs.map((job, index) => (
        <div className="job-card" key={job.job_id}>
          <h4>
            <span className="muted">{index + 1}. </span>
            {job.job_title}
          </h4>
          <p>
            {job.location} · {job.remote_type?.replaceAll("_", " ")}
          </p>
          <div className="job-tags">
            <span>{job.experience_level?.replaceAll("_", " ")}</span>
            <span>
              {job.market === "UK" ? "£" : "€"}
              {formatNumber(job.salary_min)}–{formatNumber(job.salary_max)}
            </span>
          </div>
        </div>
      ))}
      {arm.explanation ? (
        <div className="job-card">
          <p className="job-reason">{arm.explanation}</p>
        </div>
      ) : null}
      {!arm.jobs.length && !arm.error ? (
        <div className="comparison-empty">
          <EmptyState title={emptyTitle} description={emptyDescription} />
          {arm.status === "not_configured" ? (
            <button
              className="text-link"
              onClick={() => navigate("connections")}
            >
              Data & connections <ArrowUpRight size={12} />
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export function FunnelView({ filters, navigate }: ViewProps) {
  const funnel = useApi<FunnelData>("/funnel", filters);
  const [dimension, setDimension] = useState("device_type");
  const [metric, setMetric] = useState("completion_rate");
  const segments = useApi<SegmentData>(
    `/segments?dimension=${dimension}&metric=${metric}`,
    filters,
  );
  const labels: Record<string, string> = {
    device_type: "Device",
    market: "Market",
    user_type: "User type",
    job_category: "Job category",
    traffic_source: "Acquisition",
    experience_level: "Experience",
    variant: "Search arm",
    conversion_rate: "Search-to-application conversion",
    completion_rate: "Application completion",
    job_view_rate: "Job detail view rate",
    error_rate: "Application error rate",
    avg_load_time_ms: "Mean search latency",
    sessions: "Search sessions",
  };
  if (funnel.loading) return <LoadingState />;
  if (!funnel.data)
    return (
      <ErrorState
        message={funnel.error || "Funnel data is unavailable."}
        retry={funnel.retry}
      />
    );
  const data = funnel.data;
  return (
    <>
      <RequestStatus
        refreshing={funnel.refreshing}
        error={funnel.error}
        retry={funnel.retry}
        lastUpdated={funnel.lastUpdated}
      />
      <div className="metrics-grid">
        <Metric
          label="Search-to-application conversion"
          value={data.overall_conversion_rate}
          unit="%"
          note="Submitted / all search sessions"
          icon={<Target size={15} />}
        />
        <Metric
          label="Journey starts"
          value={data.steps[0]?.count}
          note="Search sessions"
          icon={<Search size={15} />}
        />
        <Metric
          label="Applications submitted"
          value={data.steps.at(-1)?.count}
          note="Last step of the journey"
          icon={<CheckCircle2 size={15} />}
        />
        <Metric
          label="Largest step drop-off"
          value={data.biggest_drop?.rate}
          unit="%"
          note={
            data.biggest_drop
              ? `${data.biggest_drop.from.replaceAll("_", " ")} → ${data.biggest_drop.to.replaceAll("_", " ")}`
              : "Selected period"
          }
          icon={<Activity size={15} />}
        />
      </div>
      <div className="two-column">
        <Panel>
          <PanelHeading
            title="Every step is an opportunity"
            description="The candidate journey from discovery to submitted application"
            action={<Pill>Session funnel</Pill>}
          />
          <div className="funnel-stack">
            {data.steps.map((step, index) => (
              <div className="funnel-step" key={step.key}>
                <div className="funnel-index">0{index + 1}</div>
                <div className="funnel-bar-wrap">
                  <div className="funnel-step-head">
                    <span>{step.label}</span>
                    <strong>{formatNumber(step.count)}</strong>
                  </div>
                  <div className="funnel-bar">
                    <div
                      className="funnel-fill"
                      style={{
                        width: `${Math.min(100, step.conversion_rate || 0)}%`,
                      }}
                    />
                  </div>
                </div>
                <div className="funnel-value">
                  {formatPercent(step.step_conversion_rate)}
                  <div className="table-sub">from prior</div>
                </div>
              </div>
            ))}
          </div>
          <Note>
            Each count is a session reaching that step. Bar width is relative to
            all search sessions.
          </Note>
        </Panel>
        <Panel>
          <PanelHeading
            title="Look beneath the average"
            description="Explore where experiences diverge"
          />
          <div className="panel-content" style={{ paddingBottom: 0 }}>
            <div className="query-options" style={{ marginTop: 0 }}>
              <label>
                Group by
                <select
                  aria-label="Segment dimension"
                  value={dimension}
                  onChange={(event) => setDimension(event.target.value)}
                >
                  {(
                    segments.data?.dimensions || [
                      "device_type",
                      "market",
                      "user_type",
                      "job_category",
                      "traffic_source",
                      "experience_level",
                      "variant",
                    ]
                  ).map((item) => (
                    <option key={item} value={item}>
                      {labels[item] || item.replaceAll("_", " ")}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Metric
                <select
                  aria-label="Segment metric"
                  value={metric}
                  onChange={(event) => setMetric(event.target.value)}
                >
                  {(
                    segments.data?.metrics || [
                      "conversion_rate",
                      "completion_rate",
                      "job_view_rate",
                      "error_rate",
                      "avg_load_time_ms",
                      "sessions",
                    ]
                  ).map((item) => (
                    <option key={item} value={item}>
                      {labels[item] || item.replaceAll("_", " ")}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </div>
          {segments.error ? (
            <div className="panel-content">
              <div className="inline-error">{segments.error}</div>
              <button
                className="button subtle small-button"
                onClick={segments.retry}
              >
                Retry segments
              </button>
            </div>
          ) : segments.loading ? (
            <div className="empty-state">
              <LoaderCircle size={20} className="spin" />
            </div>
          ) : (
            <div className="segment-list">
              {segments.data?.rows.length ? (
                segments.data.rows.map((row) => (
                  <div className="segment-row" key={row.name}>
                    <div className="segment-icon">
                      {dimension === "device_type" ? (
                        <MonitorSmartphone size={15} />
                      ) : dimension === "market" ? (
                        <Globe2 size={15} />
                      ) : (
                        <Users size={15} />
                      )}
                    </div>
                    <div className="segment-copy">
                      <h3>{row.label || row.name}</h3>
                      <p>
                        {formatNumber(row.sessions)} sessions ·{" "}
                        {formatNumber(row.applications)} applications
                      </p>
                    </div>
                    <div className="segment-rate">
                      {metric === "sessions"
                        ? formatNumber(row.metric_value)
                        : metric === "avg_load_time_ms"
                          ? `${formatNumber(row.metric_value)} ms`
                          : formatPercent(row.metric_value)}
                      <small>{labels[metric]}</small>
                    </div>
                  </div>
                ))
              ) : (
                <EmptyState />
              )}
            </div>
          )}
          <Note>
            Application completion uses application starts as its denominator.
          </Note>
        </Panel>
      </div>
      <Insights insights={data.insights} navigate={navigate} />
    </>
  );
}

export function ReleasesView({ filters }: ViewProps) {
  const { data, loading, refreshing, error, retry, lastUpdated } =
    useApi<ReleaseData>("/releases", filters);
  if (loading) return <LoadingState />;
  if (!data)
    return (
      <ErrorState
        message={error || "Release impact data is unavailable."}
        retry={retry}
      />
    );
  return (
    <>
      <RequestStatus
        refreshing={refreshing}
        error={error}
        retry={retry}
        lastUpdated={lastUpdated}
      />
      <Panel className="notice-panel">
        <Info size={15} />
        <div>{data.disclaimer}</div>
      </Panel>
      <div className="two-column">
        <div className="release-list">
          {data.releases.length ? (
            data.releases.map((release) => (
              <ReleaseCard key={release.id} release={release} />
            ))
          ) : (
            <Panel>
              <EmptyState
                title="No releases match this selection"
                description="Expand your date range or change the market and device filters."
              />
            </Panel>
          )}
        </div>
        <Panel className="methodology">
          <h3>
            <ShieldCheck size={15} /> Read impact responsibly
          </h3>
          <p>
            A release can coincide with a change in behavior. This view helps
            form hypotheses for a controlled follow-up.
          </p>
          <ul>
            <li>
              <CheckCircle2 size={13} />
              Compare matching windows around each release date.
            </li>
            <li>
              <CheckCircle2 size={13} />
              Review market mix, device mix, and acquisition shifts.
            </li>
            <li>
              <CheckCircle2 size={13} />
              Check application errors and latency alongside completion.
            </li>
            <li>
              <CheckCircle2 size={13} />
              Use the randomized search experiment for causal claims.
            </li>
          </ul>
          <div className="control-caption" style={{ marginTop: 24 }}>
            Completion = submitted applications / application starts.{" "}
            {filters.dataset_id
              ? "Release comparisons use the selected uploaded observations."
              : "Historical releases and telemetry are synthetic."}
          </div>
        </Panel>
      </div>
    </>
  );
}

function ReleaseCard({ release }: { release: Release }) {
  const hasBaseline = release.before.sessions > 0;
  const impact = hasBaseline ? release.impact_pp : null;
  const errorChange = hasBaseline ? release.error_change_pp : null;
  return (
    <Panel className="release-card">
      <div className="release-card-header">
        <div className="release-icon">
          <Rocket size={18} />
        </div>
        <div style={{ flex: 1 }}>
          <h3>{release.name}</h3>
          <div className="release-date">
            {formatDate(release.release_date)} 2026 · {release.market} ·{" "}
            {release.platform}
          </div>
        </div>
        <Pill
          tone={impact === null ? "neutral" : impact > 0 ? "green" : "amber"}
        >
          {!hasBaseline || impact === null
            ? "Insufficient baseline"
            : release.confidence}
        </Pill>
      </div>
      <p>{release.interpretation}</p>
      <div className="release-metrics">
        <div>
          <span>Completion change</span>
          <strong
            className={
              impact === null ? "muted" : impact > 0 ? "positive" : "negative"
            }
          >
            <Signed value={impact} suffix=" pp" />
          </strong>
        </div>
        <div>
          <span>Before → after</span>
          <strong>
            {formatPercent(hasBaseline ? release.before.completion_rate : null)}{" "}
            <span style={{ display: "inline" }}>→</span>{" "}
            {formatPercent(release.after.completion_rate)}
          </strong>
        </div>
        <div>
          <span>Load-time change</span>
          <strong>
            <Signed
              value={hasBaseline ? release.latency_change_ms : null}
              suffix=" ms"
            />
          </strong>
        </div>
      </div>
      <div
        className="release-error-row"
        title="Application error sessions / all search sessions"
      >
        <div>
          <span>Application error rate</span>
          <strong>
            {formatPercent(hasBaseline ? release.before.error_rate : null, 2)}{" "}
            <span className="muted">→</span>{" "}
            {formatPercent(release.after.error_rate, 2)}
          </strong>
        </div>
        <div>
          <span>Error-rate change</span>
          <strong
            className={
              errorChange === null || errorChange === undefined
                ? "muted"
                : errorChange <= 0
                  ? "positive"
                  : "negative"
            }
          >
            <Signed value={errorChange} suffix=" pp" />
          </strong>
        </div>
      </div>
      <div className="control-caption">
        Before: {formatDate(release.before_window.start_date, true)}–
        {formatDate(release.before_window.end_date, true)} · After:{" "}
        {formatDate(release.after_window.start_date, true)}–
        {formatDate(release.after_window.end_date, true)}
        <br />
        Error rate = application error sessions / all search sessions.
      </div>
    </Panel>
  );
}

const EXAMPLE_QUESTIONS = [
  "Visualize application completion by device",
  "Compare AI search with manual search",
  "Show the application funnel and biggest drop-off",
  "Visualize daily application completion trends",
];
type SavedInsight = { question: string; answer: string; date: string };
const csvCell = (value: unknown) =>
  `"${String(value ?? "").replaceAll('"', '""')}"`;

export function AnalystView({ filters }: ViewProps) {
  const workspace = useWorkspace();
  const models = workspace.models;
  const [question, setQuestion] = useState("");
  const [provider, setProvider] = useState("openrouter");
  const [selectedModel, setSelectedModel] = useState("");
  const [answer, setAnswer] = useState<AnalystAnswer | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<SavedInsight[]>([]);
  const [feedback, setFeedback] = useState("");
  const [lastQuestion, setLastQuestion] = useState("");
  const chartRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    try {
      const existing = JSON.parse(
        localStorage.getItem("talentpulse.insights.v1") || "[]",
      );
      if (Array.isArray(existing))
        setSaved(
          existing
            .filter(
              (item) =>
                typeof item.question === "string" &&
                typeof item.answer === "string",
            )
            .slice(0, 5),
        );
    } catch {}
  }, []);
  async function ask(event: React.FormEvent) {
    event.preventDefault();
    if (!question.trim() || busy) return;
    setBusy(true);
    setError(null);
    setFeedback("");
    try {
      const response = await apiFetch<AnalystAnswer>(
        "/ai/investigate",
        {
          method: "POST",
          body: JSON.stringify({
            question: question.trim(),
            visualize: true,
            provider,
            model: selectedModel || undefined,
            dataset_id: filters.dataset_id,
            filters: apiFilters(filters),
          }),
        },
        45_000,
      );
      setAnswer(response);
      setLastQuestion(question.trim());
    } catch (failure) {
      setError(
        failure instanceof Error
          ? failure.message
          : "The analyst request failed.",
      );
    } finally {
      setBusy(false);
    }
  }
  function saveInsight() {
    if (!answer) return;
    const next = [
      {
        question: lastQuestion,
        answer: answer.answer,
        date: new Date().toISOString(),
      },
      ...saved,
    ].slice(0, 5);
    setSaved(next);
    try {
      localStorage.setItem("talentpulse.insights.v1", JSON.stringify(next));
      setFeedback("Insight saved in this browser.");
    } catch {
      setFeedback("Saved for this session. Browser storage is unavailable.");
    }
  }
  function exportChart() {
    if (!answer?.chart) return;
    const keys = Array.from(
      new Set(answer.chart.data.flatMap((row) => Object.keys(row))),
    );
    downloadText(
      [
        keys.map(csvCell).join(","),
        ...answer.chart.data.map((row) =>
          keys.map((key) => csvCell(row[key])).join(","),
        ),
      ].join("\n"),
      "talentpulse-chart-data.csv",
      "text/csv;charset=utf-8",
    );
  }
  function exportSvg() {
    const svg = chartRef.current?.querySelector("svg");
    if (!svg) return;
    const styles = getComputedStyle(document.documentElement);
    const content = new XMLSerializer()
      .serializeToString(svg)
      .replace(/var\((--[a-z-]+)\)/g, (_, token: string) =>
        styles.getPropertyValue(token).trim(),
      );
    downloadText(content, "talentpulse-chart-draft.svg", "image/svg+xml");
  }
  const selected = apiFilters(filters);
  return (
    <div className="analyst-layout">
      <div>
        <Panel>
          <div className="analyst-welcome">
            <div className="analyst-orb">
              <WandSparkles size={23} strokeWidth={1.5} />
            </div>
            <div className="eyebrow">A thinking partner for your data</div>
            <h2>Ask a question. Find your next insight.</h2>
            <p>
              Explore the candidate journey in plain language. Your analyst
              works with verified aggregate evidence and prepares a chart draft
              you can take into your next review.
            </p>
            <div className="prompt-examples">
              {EXAMPLE_QUESTIONS.map((example, index) => (
                <button
                  key={example}
                  className="prompt-example"
                  onClick={() => setQuestion(example)}
                >
                  {index % 2 === 0 ? (
                    <BarChart3 size={14} />
                  ) : (
                    <Sparkles size={14} />
                  )}
                  <span>{example}</span>
                </button>
              ))}
            </div>
          </div>
          <form className="analyst-composer" onSubmit={ask}>
            <label className="sr-only" htmlFor="analyst-question">
              Your analytics question
            </label>
            <textarea
              id="analyst-question"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="What would you like to understand? Ask me to visualize it…"
              maxLength={800}
              required
            />
            <div className="composer-footer">
              <select
                aria-label="AI analyst provider"
                value={provider}
                onChange={(event) => {
                  setProvider(event.target.value);
                  setSelectedModel("");
                }}
              >
                <option value="openrouter">GPT-4o · OpenRouter</option>
                <option value="ollama">GPT-OSS 120B · Ollama</option>
              </select>
              <ModelPicker
                provider={provider}
                purpose="analyst"
                value={selectedModel}
                onChange={setSelectedModel}
                label="Interpretation model"
              />
              <button
                className="button primary"
                disabled={busy || !question.trim()}
              >
                {busy ? (
                  <LoaderCircle size={14} className="spin" />
                ) : (
                  <Send size={13} />
                )}
                {busy ? "Investigating…" : "Ask & visualize"}
              </button>
            </div>
            <p className="control-caption">
              Charts use database aggregates. Model-generated explanations are
              accompanied by their evidence.
            </p>
            {error ? (
              <div className="inline-error" role="alert">
                <Info size={14} />
                {error}
              </div>
            ) : null}
          </form>
        </Panel>
        {answer ? (
          <Panel className="analyst-answer">
            <div className="answer-header">
              <h3>
                <Sparkles size={15} className="positive" /> Your investigation
              </h3>
              <Pill tone={answer.mode === "provider" ? "green" : "amber"}>
                {answer.mode === "provider"
                  ? answer.model || "AI response"
                  : "Evidence mode"}
              </Pill>
            </div>
            <div className="answer-narrative">
              {answer.answer.replaceAll("**", "")}
            </div>
            {answer.chart ? (
              <div ref={chartRef}>
                <PanelHeading
                  eyebrow={
                    answer.synthetic
                      ? "Chart draft · synthetic data"
                      : "Chart draft · uploaded evidence"
                  }
                  title={answer.chart.title}
                />
                <AnalystChart chart={answer.chart} />
              </div>
            ) : null}
            {answer.evidence.length ? (
              <div className="evidence-strip">
                {answer.evidence.map((evidence) => (
                  <div key={evidence.label}>
                    <span>{evidence.label}</span>
                    <strong>
                      {formatNumber(
                        evidence.value,
                        evidence.unit === "%" || evidence.unit === "percent"
                          ? 2
                          : 0,
                      )}
                      {evidence.unit === "count"
                        ? ""
                        : evidence.unit === "percent"
                          ? "%"
                          : ` ${evidence.unit}`}
                    </strong>
                  </div>
                ))}
              </div>
            ) : null}
            <div className="answer-actions">
              <button
                className="button subtle small-button"
                onClick={saveInsight}
              >
                <FileChartColumn size={12} /> Save insight
              </button>
              {answer.chart ? (
                <>
                  <button
                    className="button subtle small-button"
                    onClick={exportChart}
                  >
                    <Download size={12} /> Chart CSV
                  </button>
                  <button
                    className="button subtle small-button"
                    onClick={exportSvg}
                  >
                    <Download size={12} /> SVG draft
                  </button>
                </>
              ) : null}
            </div>
            {feedback ? (
              <div style={{ padding: "0 22px 10px" }}>
                <ActionFeedback>{feedback}</ActionFeedback>
              </div>
            ) : null}
            {answer.limitations.map((limitation) => (
              <Note key={limitation}>{limitation}</Note>
            ))}
            {answer.suggested_questions.length ? (
              <div className="answer-followups">
                {answer.suggested_questions.map((item) => (
                  <button
                    className="text-link"
                    key={item}
                    onClick={() => setQuestion(item)}
                  >
                    {item}
                    <ChevronRight size={12} />
                  </button>
                ))}
              </div>
            ) : null}
          </Panel>
        ) : null}
      </div>
      <aside className="analyst-sidebar">
        <Panel className="analyst-side-card">
          <h3>
            <Layers3 size={14} /> Your analysis context
          </h3>
          <div className="context-line">
            <span>Dataset</span>
            <strong>
              {workspace.dataset ? "Private upload" : "Synthetic telemetry"}
            </strong>
          </div>
          <div className="context-line">
            <span>Period</span>
            <strong>{filters.days} days</strong>
          </div>
          <div className="context-line">
            <span>Market</span>
            <strong>
              {filters.market === "all" ? "All markets" : filters.market}
            </strong>
          </div>
          <div className="context-line">
            <span>Device</span>
            <strong>
              {filters.device === "all" ? "All devices" : filters.device}
            </strong>
          </div>
          <div className="context-line">
            <span>Window ends</span>
            <strong>{formatDate(selected.end_date, true)} 2026</strong>
          </div>
        </Panel>
        <Panel className="analyst-side-card">
          <h3>
            <ShieldCheck size={14} /> Evidence first
          </h3>
          <p>
            Only read-only aggregate queries are available to the assistant. It
            cannot write data or execute its own SQL.
          </p>
          <div className="provider-readiness">
            {models?.providers.map((model) => (
              <span
                className={model.configured ? "ready" : "not-ready"}
                key={model.id}
              >
                {model.configured ? <Check size={11} /> : <Info size={11} />}
                {model.label}:{" "}
                {model.configured ? "configured" : "setup required"}
              </span>
            ))}
          </div>
        </Panel>
        <Panel className="analyst-side-card">
          <h3>
            <FileChartColumn size={14} /> Saved insights{" "}
            <span className="muted">{saved.length}</span>
          </h3>
          {saved.length ? (
            saved.map((item, index) => (
              <button
                className="saved-insight saved-insight-button"
                key={`${item.date}-${index}`}
                onClick={() => {
                  setQuestion(item.question);
                  setFeedback("");
                }}
              >
                {item.question}
                <time>
                  {new Date(item.date).toLocaleDateString("en-GB", {
                    day: "numeric",
                    month: "short",
                  })}{" "}
                  · saved locally
                </time>
              </button>
            ))
          ) : (
            <p>
              Your saved investigations will appear here. Keep the questions
              that move your thinking forward.
            </p>
          )}
        </Panel>
      </aside>
    </div>
  );
}

const CONNECTION_ICONS: Record<string, React.ReactNode> = {
  neon: <Database size={20} />,
  database: <Database size={20} />,
  openrouter: <Sparkles size={20} />,
  ollama: <Bot size={20} />,
  adobe: <Activity size={20} />,
  powerbi: <BarChart3 size={20} />,
};

export function ConnectionsView({ filters }: ViewProps) {
  const workspace = useWorkspace();
  const integrations = useApi<IntegrationData>("/integrations");
  const quality = useApi<QualityData>("/data-quality", filters);
  const tracking = useApi<TrackingData>("/tracking-plan", filters);
  const [modal, setModal] = useState<Integration | "mcp" | null>(null);
  const [feedback, setFeedback] = useState("");
  const [embedUrl, setEmbedUrl] = useState("");
  const [activeEmbed, setActiveEmbed] = useState("");
  const [embedError, setEmbedError] = useState("");
  const [adobeBusy, setAdobeBusy] = useState(false);
  const [adobeResult, setAdobeResult] = useState("");
  const [selectedTracking, setSelectedTracking] = useState<string | null>(null);
  useEffect(() => {
    const saved = workspace.connectors.find((item) => item.id === "powerbi")
      ?.settings.embed_url;
    if (typeof saved === "string") setEmbedUrl(saved);
  }, [workspace.connectors]);
  useEffect(() => {
    if (!modal) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setModal(null);
      if (event.key === "Tab") {
        const controls = document.querySelectorAll<HTMLElement>(
          ".modal button, .modal a[href], .modal input, .modal select",
        );
        const first = controls[0],
          last = controls[controls.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [modal]);
  async function adobeCheck() {
    setAdobeBusy(true);
    setAdobeResult("");
    try {
      const response = await apiFetch<Record<string, unknown>>(
        "/integrations/adobe/check",
        { method: "POST", body: "{}" },
      );
      setAdobeResult(JSON.stringify(response, null, 2));
    } catch (failure) {
      setAdobeResult(
        failure instanceof Error
          ? failure.message
          : "The Adobe connection could not be verified.",
      );
    } finally {
      setAdobeBusy(false);
    }
  }
  async function embed(event: React.FormEvent) {
    event.preventDefault();
    setEmbedError("");
    try {
      const parsed = new URL(embedUrl);
      if (
        parsed.protocol !== "https:" ||
        !["app.powerbi.com", "app.powerbigov.us"].includes(parsed.hostname) ||
        parsed.username ||
        parsed.password ||
        Array.from(parsed.searchParams.keys()).some((key) =>
          /^(access_token|token|password|client_secret|api_key|authorization)$/i.test(
            key,
          ),
        )
      )
        throw new Error();
      await apiFetch("/workspace/connectors/powerbi", {
        method: "PUT",
        body: JSON.stringify({
          settings: { embed_url: parsed.toString() },
          secrets: {},
        }),
      });
      setActiveEmbed(parsed.toString());
      workspace.refreshConnectors();
    } catch {
      setEmbedError(
        "Enter a valid HTTPS report embed URL from app.powerbi.com or app.powerbigov.us without credentials or API tokens.",
      );
    }
  }
  async function copyMcp() {
    try {
      await navigator.clipboard.writeText(
        `${window.location.origin}${integrations.data?.mcp.endpoint || "/api/mcp"}`,
      );
      setFeedback("MCP endpoint copied.");
    } catch {
      setFeedback("Copy the endpoint shown in the connection details.");
    }
  }
  if (integrations.loading) return <LoadingState />;
  if (!integrations.data)
    return (
      <ErrorState
        message={integrations.error || "Integration status is unavailable."}
        retry={integrations.retry}
      />
    );
  const data = integrations.data;
  return (
    <>
      <RequestStatus
        refreshing={integrations.refreshing}
        error={integrations.error}
        retry={integrations.retry}
        lastUpdated={integrations.lastUpdated}
      />
      <ConnectorStudio />
      <ExternalEvidence filters={filters} />
      <div className="section-label">
        <h2>Shared deployment defaults</h2>
        <span>Private settings override these for your workspace</span>
      </div>
      <div className="connections-grid">
        {data.integrations.map((integration) => (
          <Panel className="connection-card" key={integration.id}>
            <div className="connection-logo">
              {CONNECTION_ICONS[integration.id] || <Plug size={20} />}
            </div>
            <div className="connection-header">
              <h3>{integration.name}</h3>
              <Pill tone={integration.configured ? "green" : "neutral"} dot>
                {integration.configured ? "Configured" : "Setup required"}
              </Pill>
            </div>
            <p>{integration.description}</p>
            <div className="connection-action">
              {integration.id === "adobe" && integration.configured ? (
                <button
                  className="button subtle small-button"
                  onClick={adobeCheck}
                  disabled={adobeBusy}
                >
                  {adobeBusy ? (
                    <LoaderCircle size={12} className="spin" />
                  ) : (
                    <ShieldCheck size={12} />
                  )}{" "}
                  Verify access
                </button>
              ) : (
                <button
                  className="text-link"
                  onClick={() => {
                    setModal(integration);
                    setFeedback("");
                  }}
                >
                  Connection details <ArrowUpRight size={12} />
                </button>
              )}
              <div className="connection-detail">
                {integration.status.replaceAll("_", " ")}
              </div>
            </div>
          </Panel>
        ))}
      </div>
      {adobeResult ? (
        <Panel className="methodology" style={{ marginBottom: 20 }}>
          <h3>Adobe Analytics connection check</h3>
          <div className="code-box">{adobeResult}</div>
        </Panel>
      ) : null}
      <div className="two-column equal-column">
        <Panel className="tracking-card">
          <div className="tracking-header">
            <div>
              <h3>A shared language for events</h3>
              <p>Tracking plan · triggers, properties, and ownership</p>
            </div>
            <ExportButton url="/api/export/tracking" label="CSV" />
          </div>
          {tracking.error ? (
            <>
              <div className="inline-error">{tracking.error}</div>
              <button
                className="button subtle small-button"
                onClick={tracking.retry}
              >
                Retry tracking plan
              </button>
            </>
          ) : tracking.loading ? (
            <div className="empty-state">
              <LoaderCircle className="spin" size={18} />
            </div>
          ) : (
            tracking.data?.events.map((event) => (
              <div key={event.name}>
                <button
                  className="tracking-row tracking-button"
                  onClick={() =>
                    setSelectedTracking(
                      selectedTracking === event.name ? null : event.name,
                    )
                  }
                  aria-expanded={selectedTracking === event.name}
                >
                  <code>{event.name}</code>
                  <span>{formatNumber(event.volume)}</span>
                  <ChevronRight size={13} className="muted" />
                </button>
                {selectedTracking === event.name ? (
                  <div className="tracking-details">
                    <p>{event.description}</p>
                    <p>
                      <strong>Trigger:</strong> {event.trigger}
                    </p>
                    <p>
                      <strong>Owner:</strong> {event.owner} · {event.status}
                    </p>
                    <p>
                      <strong>Required:</strong>{" "}
                      {event.required_properties.join(", ")}
                    </p>
                  </div>
                ) : null}
              </div>
            ))
          )}
        </Panel>
        <Panel>
          <PanelHeading
            title={
              filters.dataset_id
                ? "Readiness of the uploaded evidence"
                : "Data you can trust"
            }
            description="Checks run against the selected data source"
            action={
              <Pill
                tone={
                  filters.dataset_id
                    ? "neutral"
                    : quality.data?.event_volume === 0
                      ? "neutral"
                      : quality.data && quality.data.score >= 95
                        ? "green"
                        : "amber"
                }
              >
                {quality.loading
                  ? "Checking…"
                  : filters.dataset_id
                    ? "Observed coverage"
                    : quality.data?.event_volume === 0
                      ? "No evidence"
                      : `${formatNumber(quality.data?.score, 1)} / 100`}
              </Pill>
            }
          />
          <div className="panel-content">
            {quality.error ? (
              <>
                <div className="inline-error">{quality.error}</div>
                <button
                  className="button subtle small-button"
                  onClick={quality.retry}
                >
                  Retry quality checks
                </button>
              </>
            ) : quality.loading ? (
              <div className="empty-state">
                <LoaderCircle className="spin" size={18} />
              </div>
            ) : (
              quality.data?.checks.map((check) => (
                <div className="quality-check" key={check.key}>
                  {check.status === "pass" || check.status === "passed" ? (
                    <CheckCircle2 size={15} />
                  ) : (
                    <Info size={15} />
                  )}
                  <div>
                    <strong>{check.label}</strong>
                    <p>{check.detail}</p>
                  </div>
                  <Pill
                    tone={
                      check.status === "pass" || check.status === "passed"
                        ? "green"
                        : "amber"
                    }
                  >
                    {check.status.replaceAll("_", " ")}
                  </Pill>
                </div>
              ))
            )}
          </div>
          {quality.data ? (
            <Note>
              {filters.dataset_id ? (
                "Mapped-field coverage is observed; no overall quality score is invented."
              ) : (
                <>
                  {formatNumber(quality.data.event_volume)} events ·{" "}
                  {formatNumber(quality.data.session_volume)} sessions examined
                </>
              )}
            </Note>
          ) : null}
        </Panel>
      </div>
      <div className="two-column equal-column">
        <Panel className="methodology">
          <h3>
            <Link2 size={15} /> Your data, in your workflow
          </h3>
          <p>
            Connect a read-only MCP client to the analytics tools, or import the
            CSV endpoints into your BI workspace.
          </p>
          <div className="export-actions">
            {data.exports.map((item) => (
              <ExportButton
                key={item.id}
                url={`${item.url}${item.url.includes("?") ? "&" : "?"}${filterQuery(filters)}`}
                label={item.label}
              />
            ))}
          </div>
          <div className="button-row">
            <button
              className="button subtle small-button"
              onClick={() => {
                setModal("mcp");
                setFeedback("");
              }}
            >
              <Plug size={12} /> MCP connection
            </button>
            <a
              className="button subtle small-button"
              href="/api/export/metadata"
              target="_blank"
              rel="noreferrer"
            >
              <FileChartColumn size={12} /> BI connection guide
            </a>
          </div>
          <p className="control-caption">
            Exports are served from the database. Detailed session exports are
            capped at 10,000 rows.
          </p>
        </Panel>
        <Panel className="methodology">
          <h3>
            <BarChart3 size={15} /> Bring a Power BI report
          </h3>
          <p>
            Add your own report embed URL. Access and report permissions are
            managed by Microsoft Power BI.
          </p>
          <form className="embed-form" onSubmit={embed}>
            <label className="sr-only" htmlFor="powerbi-url">
              Power BI report embed URL
            </label>
            <input
              id="powerbi-url"
              className="field-input"
              type="url"
              value={embedUrl}
              onChange={(event) => setEmbedUrl(event.target.value)}
              placeholder="https://app.powerbi.com/reportEmbed…"
              required
            />
            <button className="button primary small-button">
              Open report <ArrowUpRight size={12} />
            </button>
          </form>
          {embedError ? (
            <div className="inline-error" role="alert">
              {embedError}
            </div>
          ) : null}
          <p className="control-caption">
            The report URL is saved in your private workspace. API credentials
            remain encrypted on the server.
          </p>
        </Panel>
      </div>
      {activeEmbed ? (
        <Panel className="methodology">
          <div className="panel-heading" style={{ padding: 0 }}>
            <div>
              <h2>Your Power BI workspace</h2>
              <p>External report · governed by your Microsoft account</p>
            </div>
            <button
              className="icon-button"
              aria-label="Close Power BI report"
              onClick={() => setActiveEmbed("")}
            >
              <X size={14} />
            </button>
          </div>
          <iframe
            className="powerbi-embed"
            src={activeEmbed}
            title="Connected Power BI report"
            allowFullScreen
            sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
            referrerPolicy="strict-origin-when-cross-origin"
          />
        </Panel>
      ) : null}
      {modal ? (
        <div className="modal-backdrop" onClick={() => setModal(null)}>
          <div
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="connection-title"
            onClick={(event) => event.stopPropagation()}
          >
            <button
              className="icon-button modal-close"
              onClick={() => setModal(null)}
              aria-label="Close connection details"
              autoFocus
            >
              <X size={16} />
            </button>
            <h2 id="connection-title">
              {modal === "mcp" ? "Read-only analytics MCP" : modal.name}
            </h2>
            {modal === "mcp" ? (
              <>
                <p>
                  Connect your MCP client to the public analytics endpoint. It
                  exposes a limited set of read-only tools against the synthetic
                  database.
                </p>
                <div className="code-box">
                  {typeof window !== "undefined" ? window.location.origin : ""}
                  {data.mcp.endpoint}
                  <br />
                  Transport: {data.mcp.transport}
                  <br />
                  <br />
                  Tools: {data.mcp.tools.join(", ")}
                </div>
                <div className="button-row">
                  <button
                    className="button primary small-button"
                    onClick={copyMcp}
                  >
                    <Copy size={12} /> Copy endpoint
                  </button>
                </div>
                {feedback ? <ActionFeedback>{feedback}</ActionFeedback> : null}
              </>
            ) : (
              <>
                <p>{modal.description}</p>
                <Pill tone={modal.configured ? "green" : "amber"}>
                  {modal.status.replaceAll("_", " ")}
                </Pill>
                <p>
                  {modal.configured
                    ? "Server credentials are configured. Live requests verify access when the provider is used."
                    : "Configure these environment variables in your Vercel project, then redeploy to enable this integration."}
                </p>
                {modal.required_env.length ? (
                  <div className="code-box">
                    {modal.required_env.join("\n")}
                  </div>
                ) : null}
                <p>
                  <strong>Available capabilities:</strong>{" "}
                  {modal.capabilities.join(" · ")}
                </p>
                {modal.setup_url && modal.setup_url.startsWith("https://") ? (
                  <a
                    className="button subtle small-button"
                    href={modal.setup_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Official setup guide <ArrowUpRight size={12} />
                  </a>
                ) : null}
              </>
            )}
          </div>
        </div>
      ) : null}
    </>
  );
}
