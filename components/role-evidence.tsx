"use client";

import { useEffect, useState } from "react";
import {
  ArrowUpRight,
  BarChart3,
  CheckCircle2,
  ExternalLink,
  Info,
  LoaderCircle,
  ShieldCheck,
  Sparkles,
  Target,
} from "lucide-react";
import research from "@/public/research-context.json";
import {
  apiFetch,
  apiFilters,
  formatNumber,
  formatPercent,
  useApi,
  type Filters,
} from "@/lib/api";
import type { AnalystAnswer } from "@/lib/types";
import { AnalystChart } from "./charts";
import { EmptyState, Panel, PanelHeading, Pill, RequestStatus } from "./ui";
import { useWorkspace } from "./workspace";

type RoleArm = {
  arm?: string;
  variant?: string;
  label: string;
  sessions?: number;
  applications?: number;
  exposed_users?: number | null;
  users?: number | null;
  conversion_rate: number | null;
  completion_rate?: number | null;
  latency_ms?: number | null;
  cost_usd?: number | null;
  p_value?: number | null;
  significant?: boolean;
  decision?: string;
};
type DriverGroup = {
  name: string;
  label?: string;
  sessions?: number | null;
  exposed_users?: number | null;
  users?: number | null;
  applications?: number;
  conversion_rate?: number | null;
  metric_value: number | null;
};
type RoleEvidenceData = {
  meta?: { source?: string; synthetic?: boolean };
  role: string | null;
  role_options: string[];
  support: {
    row_count?: number;
    session_count?: number;
    unique_users?: number;
    grain?: string;
    randomized_status?: string;
    denominator?: string;
    id_validation_status?: string;
    denominator_available?: boolean;
  };
  arms: RoleArm[];
  drivers: { factor: string; groups: DriverGroup[]; interpretation: string }[];
  limitations: string[];
  suggested_experiment?: string;
  measurement_readiness?: {
    label: string;
    value: string | number | null;
    status?: string;
    detail?: string;
  }[];
};
const human = (value: string) => value.replaceAll("_", " ");
const FACTORS: Record<string, string> = {
  device_type: "Device",
  market: "Market",
  traffic_source: "Acquisition source",
  experience_level: "Experience",
  job_category: "Job category",
  user_type: "Candidate type",
};

export function RoleEvidence({ filters }: { filters: Filters }) {
  const workspace = useWorkspace();
  const [role, setRole] = useState("");
  const [factor, setFactor] = useState("device_type");
  const [answer, setAnswer] = useState<AnalystAnswer | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setRole("");
    setAnswer(null);
  }, [filters.dataset_id]);
  const response = useApi<RoleEvidenceData>(
    `/experiments/drivers${role ? `?role=${encodeURIComponent(role)}` : ""}`,
    filters,
  );
  async function investigate(question: string) {
    setBusy(true);
    setError(null);
    try {
      setAnswer(
        await apiFetch<AnalystAnswer>(
          "/ai/investigate",
          {
            method: "POST",
            body: JSON.stringify({
              question: question.slice(0, 800),
              role: role || "all",
              dataset_id: filters.dataset_id,
              filters: apiFilters(filters),
              visualize: true,
              provider:
                workspace.models?.defaults?.analyst.provider || "openrouter",
            }),
          },
          45_000,
        ),
      );
    } catch (failure) {
      setError(
        failure instanceof Error
          ? failure.message
          : "Investigation could not be completed.",
      );
    } finally {
      setBusy(false);
    }
  }
  const data = response.data;
  const selectedDriver =
    data?.drivers.find((item) => item.factor === factor) || data?.drivers[0];
  const readiness = data?.measurement_readiness || [
    {
      label: "Rows in analysis",
      value:
        data?.support.row_count === undefined
          ? "Not reported"
          : `${formatNumber(data.support.row_count)}${workspace.dataset ? ` of ${formatNumber(workspace.dataset.row_count)} uploaded rows` : " observed sessions"}`,
    },
    {
      label: "Conversion denominator",
      value: data?.support.denominator || "Not supplied",
    },
    {
      label: "Identifier validation",
      value:
        data?.support.id_validation_status || "Not reported by this analysis",
    },
    {
      label: "Inference design",
      value: human(data?.support.randomized_status || "not reported"),
    },
    {
      label: "Numeric evidence source",
      value:
        data?.meta?.source ||
        (workspace.dataset
          ? workspace.dataset.name
          : "Neon synthetic telemetry"),
    },
  ];
  return (
    <>
      <div className="section-label">
        <h2>Which roles deserve a closer look?</h2>
        <span>Measured evidence → testable hypotheses</span>
      </div>
      <Panel className="role-evidence">
        <PanelHeading
          eyebrow="Role-level deep dive"
          title="Relevance, cohort mix, and observed drivers"
          description="Understand the slice before deciding that a model wins."
          action={<Target size={18} className="muted" />}
        />
        <div className="panel-content">
          <div className="role-toolbar">
            <label>
              <span>Job role</span>
              <select
                aria-label="Role for experiment deep dive"
                value={role}
                onChange={(event) => {
                  setRole(event.target.value);
                  setAnswer(null);
                }}
              >
                <option value="">All observed roles</option>
                {data?.role_options.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>
            <button
              className="button subtle"
              onClick={() =>
                investigate(
                  `Investigate ${role || "all observed job roles"}: compare manual and AI search, explain the measured device, market and acquisition associations, and propose a pre-registered relevance experiment. Separate observed patterns from causal claims.`,
                )
              }
              disabled={busy || !data}
            >
              <Sparkles size={13} />
              {busy ? "Investigating…" : "Explain observed factors"}
            </button>
          </div>
          <RequestStatus
            refreshing={response.refreshing}
            error={data ? response.error : null}
            retry={response.retry}
            lastUpdated={response.lastUpdated}
          />
          {response.loading ? (
            <div className="role-loading">
              <LoaderCircle size={19} className="spin" />
              <span>
                Reading role-level evidence… Other workspaces remain available.
              </span>
            </div>
          ) : !data ? (
            <div className="inline-error">
              <Info size={14} />
              {response.error ||
                "This dataset does not provide role-level evidence."}
              <button className="text-link" onClick={response.retry}>
                Retry
              </button>
            </div>
          ) : (
            <>
              <div className="measurement-grid">
                {readiness.map((item) => (
                  <div className="measurement-item" key={item.label}>
                    <span>{item.label}</span>
                    <strong>
                      {typeof item.value === "number"
                        ? item.label === "Mapped column coverage"
                          ? formatPercent(item.value * 100)
                          : formatNumber(item.value, 2)
                        : (item.value ?? "Unavailable")}
                    </strong>
                    {item.detail ? <p>{item.detail}</p> : null}
                  </div>
                ))}
              </div>
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Search arm</th>
                      <th>Denominator</th>
                      <th>Applications</th>
                      <th>Observed conversion</th>
                      <th>Adjusted p-value</th>
                      <th>Inference readiness</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.arms.map((arm) => (
                      <tr key={arm.arm || arm.variant || arm.label}>
                        <td className="table-primary">{arm.label}</td>
                        <td>
                          {formatNumber(
                            arm.exposed_users ?? arm.users ?? arm.sessions,
                          )}
                          <div className="table-sub">
                            {data.support.denominator || "Supplied denominator"}
                          </div>
                        </td>
                        <td>{formatNumber(arm.applications)}</td>
                        <td>{formatPercent(arm.conversion_rate, 2)}</td>
                        <td>
                          {arm.p_value === null || arm.p_value === undefined
                            ? "Not supported"
                            : arm.p_value < 0.001
                              ? "< 0.001"
                              : arm.p_value.toFixed(3)}
                        </td>
                        <td>
                          <Pill
                            tone={
                              arm.p_value === null || arm.p_value === undefined
                                ? "neutral"
                                : arm.significant
                                  ? "green"
                                  : "amber"
                            }
                          >
                            {arm.p_value === null || arm.p_value === undefined
                              ? "Descriptive"
                              : arm.significant
                                ? "Supported evidence"
                                : "Inconclusive"}
                          </Pill>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {selectedDriver ? (
                <div className="driver-explorer">
                  <div className="driver-heading">
                    <h3>Where the mix changes</h3>
                    <select
                      aria-label="Observed factor"
                      value={selectedDriver.factor}
                      onChange={(event) => setFactor(event.target.value)}
                    >
                      {data.drivers.map((driver) => (
                        <option key={driver.factor} value={driver.factor}>
                          {FACTORS[driver.factor] || human(driver.factor)}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="driver-groups">
                    {selectedDriver.groups.map((group) => (
                      <div key={group.name}>
                        <span>{group.label || human(group.name)}</span>
                        <div>
                          <strong>
                            {formatPercent(
                              group.conversion_rate ?? group.metric_value,
                              2,
                            )}
                          </strong>
                          <small>
                            {formatNumber(
                              group.exposed_users ??
                                group.users ??
                                group.sessions,
                            )}{" "}
                            {group.exposed_users !== undefined ||
                            group.users !== undefined
                              ? "observed users"
                              : "observed sessions"}
                          </small>
                        </div>
                      </div>
                    ))}
                  </div>
                  <p>{selectedDriver.interpretation}</p>
                </div>
              ) : (
                <EmptyState
                  title="No observed factors available"
                  description="Supply mapped role, device, market, and acquisition fields to inspect these associations."
                />
              )}
              {data.limitations?.map((limitation) => (
                <p className="control-caption" key={limitation}>
                  <Info size={11} /> {limitation}
                </p>
              ))}
              {data.suggested_experiment ? (
                <div className="next-experiment">
                  <ShieldCheck size={16} />
                  <p>{data.suggested_experiment}</p>
                </div>
              ) : null}
            </>
          )}
          {error ? (
            <div className="inline-error" role="alert">
              <Info size={14} />
              {error}
            </div>
          ) : null}
          {answer ? (
            <div className="role-investigation">
              <div className="section-label">
                <h2>Investigation of this dataset</h2>
                <Pill tone={answer.mode === "provider" ? "green" : "amber"}>
                  {answer.mode === "provider"
                    ? answer.model || "Model interpretation"
                    : "Evidence only"}
                </Pill>
              </div>
              <p className="answer-narrative">
                {answer.answer.replaceAll("**", "")}
              </p>
              {answer.chart ? <AnalystChart chart={answer.chart} /> : null}
              {answer.limitations.map((limitation) => (
                <p className="control-caption" key={limitation}>
                  {limitation}
                </p>
              ))}
            </div>
          ) : null}
        </div>
      </Panel>
      <Panel className="research-context">
        <PanelHeading
          eyebrow={`Public research · reviewed ${research.reviewed_at}`}
          title={research.title}
          description={research.scope}
        />
        <div className="research-cards">
          {research.opportunities.map((opportunity) => (
            <article key={opportunity.id}>
              <div className="research-card-heading">
                <BarChart3 size={15} />
                <Pill>{opportunity.evidence_type}</Pill>
              </div>
              <h3>{opportunity.title}</h3>
              <p>{opportunity.hypothesis}</p>
              <div className="research-measure">
                <strong>Measure</strong>
                <p>{opportunity.measure}</p>
              </div>
              <button
                className="text-link"
                disabled={busy}
                onClick={() =>
                  investigate(
                    `Investigate this hypothesis in the selected dataset: ${opportunity.hypothesis} Evidence to inspect: ${opportunity.measure} Explain what the actual columns support and what is missing. Treat the public signal as a hypothesis, never as an established StepStone incident.`,
                  )
                }
              >
                Investigate this dataset <ArrowUpRight size={12} />
              </button>
              <details>
                <summary>Public signal & sources</summary>
                <p>{opportunity.signal}</p>
                <a href={opportunity.url} target="_blank" rel="noreferrer">
                  {opportunity.source}
                  <ExternalLink size={11} />
                </a>
                {"additional_url" in opportunity &&
                opportunity.additional_url ? (
                  <a
                    href={opportunity.additional_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Additional discussion
                    <ExternalLink size={11} />
                  </a>
                ) : null}
              </details>
            </article>
          ))}
        </div>
      </Panel>
    </>
  );
}
