"use client";

import { useState } from "react";
import {
  ArrowUpRight,
  CheckCircle2,
  Download,
  LoaderCircle,
  MessageSquareText,
  Plus,
  Trash2,
} from "lucide-react";
import {
  apiFetch,
  apiFilters,
  downloadApi,
  invalidateApiCache,
  useApi,
  type Filters,
} from "@/lib/api";
import { EmptyState, Panel, PanelHeading, Pill } from "./ui";
import { useWorkspace } from "./workspace";
import type { ViewName } from "./views";
import styles from "./feedback.module.css";

type Status = "new" | "investigating" | "experiment_ready" | "closed";
type FeedbackItem = {
  id: string;
  title: string;
  observation: string;
  hypothesis: string;
  primary_metric: string;
  guardrail: string;
  success_criteria: string;
  next_step: string;
  area: string;
  source: string;
  priority: string;
  status: Status;
  context: {
    dataset_name: string;
    start_date: string;
    end_date: string;
    market: string;
    device: string;
  };
  created_at: string;
};
const STATUS_LABELS: Record<Status, string> = {
  new: "New signal",
  investigating: "Investigating",
  experiment_ready: "Experiment ready",
  closed: "Closed",
};
const EMPTY = {
  title: "",
  observation: "",
  hypothesis: "",
  primary_metric: "",
  guardrail: "",
  success_criteria: "",
  next_step: "",
  area: "search",
  source: "analyst_observation",
  priority: "medium",
};
const EXAMPLE = {
  title: "Understand mobile search-to-application friction",
  observation:
    "Demo hypothesis: candidates may find relevant jobs but abandon when applying on mobile. Validate this with candidate feedback and device-level funnel evidence before making a product change.",
  hypothesis:
    "Reducing repeated fields in the mobile application flow will increase completed applications per exposed candidate.",
  primary_metric:
    "Unique candidates with an application submit / unique exposed candidates",
  guardrail:
    "Application error rate, p95 load time and recruiter-assessed application quality",
  success_criteria:
    "Pre-register a minimum practical lift and sample size after measuring baseline; evaluate the adjusted confidence interval and all guardrails.",
  next_step:
    "Inspect tracking coverage, review mobile funnel segments, and run five candidate usability sessions.",
  area: "application",
  source: "analyst_observation",
  priority: "medium",
};

export function FeedbackView({
  filters,
  navigate,
}: {
  filters: Filters;
  navigate: (view: ViewName) => void;
}) {
  const workspace = useWorkspace();
  const {
    data,
    error: loadError,
    loading,
    retry,
  } = useApi<{ items: FeedbackItem[]; limit: number }>(
    "/workspace/feedback",
    undefined,
    workspace.ready,
  );
  const [draft, setDraft] = useState(EMPTY);
  const [statusFilter, setStatusFilter] = useState<Status | "all">("all");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [actions, setActions] = useState<Record<string, string>>({});
  const [formOpen, setFormOpen] = useState(false);
  const items = data?.items || [];
  const shown = items.filter(
    (item) => statusFilter === "all" || item.status === statusFilter,
  );
  function field(key: keyof typeof EMPTY, value: string) {
    setDraft((previous) => ({ ...previous, [key]: value }));
  }
  async function save(event: React.FormEvent) {
    event.preventDefault();
    setBusy("create");
    setError(null);
    setNotice("");
    try {
      const dates = apiFilters(filters);
      await apiFetch("/workspace/feedback", {
        method: "POST",
        body: JSON.stringify({
          ...draft,
          context: {
            dataset_id: workspace.datasetId,
            dataset_name:
              workspace.dataset?.name || "Synthetic product telemetry",
            start_date: dates.start_date,
            end_date: dates.end_date,
            market: filters.market,
            device: filters.device,
            user_type: filters.user_type,
          },
        }),
      });
      setDraft(EMPTY);
      setFormOpen(false);
      setNotice(
        "Saved to your private Neon workspace. This observation is a hypothesis until tested.",
      );
      invalidateApiCache("/workspace/feedback");
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy(null);
    }
  }
  async function update(item: FeedbackItem, status: Status) {
    setBusy(item.id);
    setError(null);
    setNotice("");
    try {
      await apiFetch(`/workspace/feedback/${item.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          status,
          next_step: actions[item.id] ?? item.next_step,
        }),
      });
      invalidateApiCache("/workspace/feedback");
      setNotice(`Decision stage saved: ${STATUS_LABELS[status]}.`);
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy(null);
    }
  }
  async function remove(id: string) {
    setBusy(id);
    setError(null);
    try {
      await apiFetch(`/workspace/feedback/${id}`, { method: "DELETE" });
      setDeleteId(null);
      invalidateApiCache("/workspace/feedback");
      setNotice("Feedback item removed.");
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy(null);
    }
  }
  return (
    <div className={`view-stack ${styles.root}`}>
      <Panel className={styles.intro}>
        <div>
          <Pill tone="purple">Qualitative evidence → measurable decisions</Pill>
          <h2>Close the product feedback loop</h2>
          <p>
            Capture a signal, challenge the explanation, write a test brief, and
            record the next decision. Each item keeps the dataset and segment
            context you were using.
          </p>
        </div>
        <button
          className="button primary"
          onClick={() => setFormOpen((value) => !value)}
        >
          <Plus size={16} />
          {formOpen ? "Close brief" : "Add feedback"}
        </button>
      </Panel>
      <div className={styles.stages} aria-label="Feedback workflow">
        {(Object.keys(STATUS_LABELS) as Status[]).map((status) => (
          <button
            key={status}
            className={`${styles.stage} ${statusFilter === status ? styles.selected : ""}`}
            aria-pressed={statusFilter === status}
            onClick={() =>
              setStatusFilter(statusFilter === status ? "all" : status)
            }
          >
            <span>{STATUS_LABELS[status]}</span>
            <strong>
              {items.filter((item) => item.status === status).length}
            </strong>
            <small>
              {status === "new"
                ? "Capture the problem"
                : status === "investigating"
                  ? "Check data & context"
                  : status === "experiment_ready"
                    ? "Pre-register a test"
                    : "Record the outcome"}
            </small>
          </button>
        ))}
      </div>
      {(error || loadError || workspace.error) && (
        <div className="inline-error" role="alert">
          {error || loadError || workspace.error}
          <button
            className="text-link"
            onClick={workspace.error ? workspace.retryWorkspace : retry}
          >
            Retry
          </button>
        </div>
      )}
      {notice && (
        <div className={styles.notice} role="status">
          <CheckCircle2 size={16} />
          {notice}
        </div>
      )}
      {formOpen && (
        <Panel>
          <PanelHeading
            title="A problem worth investigating"
            description="Write observations separately from explanations. Avoid personal data; use anonymized candidate feedback."
            action={
              <button
                className="button subtle"
                onClick={() => {
                  setDraft(EXAMPLE);
                  setNotice(
                    "Example brief loaded. Edit it to match your own evidence before saving.",
                  );
                }}
              >
                Load example brief
              </button>
            }
          />
          <form onSubmit={save} className={styles.form}>
            <label className={styles.full}>
              Title
              <input
                required
                minLength={3}
                maxLength={160}
                value={draft.title}
                onChange={(event) => field("title", event.target.value)}
                placeholder="Which candidate or business problem needs attention?"
              />
            </label>
            <label>
              Product area
              <select
                value={draft.area}
                onChange={(event) => field("area", event.target.value)}
              >
                <option value="search">Search & recommendations</option>
                <option value="application">Application journey</option>
                <option value="tracking">Tracking & data quality</option>
                <option value="ai">AI trust & relevance</option>
                <option value="reporting">Reporting & communication</option>
                <option value="other">Other</option>
              </select>
            </label>
            <label>
              Source
              <select
                value={draft.source}
                onChange={(event) => field("source", event.target.value)}
              >
                <option value="analyst_observation">Analyst observation</option>
                <option value="candidate_feedback">
                  Anonymized candidate feedback
                </option>
                <option value="usability_test">Usability test</option>
                <option value="stakeholder_request">Stakeholder request</option>
              </select>
            </label>
            <label className={styles.full}>
              What did you observe?
              <textarea
                required
                minLength={10}
                maxLength={2000}
                value={draft.observation}
                onChange={(event) => field("observation", event.target.value)}
                placeholder="Describe the evidence and where it came from. A quotation alone does not establish prevalence."
                rows={3}
              />
            </label>
            <label className={styles.full}>
              Testable hypothesis
              <textarea
                maxLength={1000}
                value={draft.hypothesis}
                onChange={(event) => field("hypothesis", event.target.value)}
                placeholder="If we change X for audience Y, metric Z should improve because…"
                rows={2}
              />
            </label>
            <label>
              Primary metric
              <input
                maxLength={200}
                value={draft.primary_metric}
                onChange={(event) =>
                  field("primary_metric", event.target.value)
                }
                placeholder="Include numerator, denominator and grain"
              />
            </label>
            <label>
              Guardrails
              <textarea
                maxLength={300}
                value={draft.guardrail}
                onChange={(event) => field("guardrail", event.target.value)}
                placeholder="Latency, errors, quality, segment harms"
                rows={2}
              />
            </label>
            <label>
              Success criterion
              <textarea
                maxLength={500}
                value={draft.success_criteria}
                onChange={(event) =>
                  field("success_criteria", event.target.value)
                }
                placeholder="Minimum practical effect, uncertainty and stopping rule"
                rows={2}
              />
            </label>
            <label>
              Next action
              <textarea
                maxLength={500}
                value={draft.next_step}
                onChange={(event) => field("next_step", event.target.value)}
                placeholder="Who should investigate what next?"
                rows={2}
              />
            </label>
            <label>
              Analyst priority
              <select
                value={draft.priority}
                onChange={(event) => field("priority", event.target.value)}
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </label>
            <div className={styles.submit}>
              <span>
                Context:{" "}
                {workspace.dataset?.name || "Synthetic product telemetry"} ·{" "}
                {filters.market} markets · {filters.device} devices
              </span>
              <button
                className="button primary"
                disabled={Boolean(busy) || !workspace.ready}
              >
                {busy === "create" ? (
                  <LoaderCircle className="spin" size={16} />
                ) : (
                  <Plus size={16} />
                )}
                Save private brief
              </button>
            </div>
          </form>
        </Panel>
      )}
      <Panel>
        <PanelHeading
          title="Feedback & decision trail"
          description="Priorities are analyst judgments. Observations and proposed tests do not prove a causal effect."
          action={
            <button
              className="button subtle"
              disabled={!items.length}
              onClick={() =>
                downloadApi(
                  "/workspace/feedback/export/csv",
                  "talentpulse-feedback.csv",
                ).catch((failure) => setError(failure.message))
              }
            >
              <Download size={15} />
              Export feedback CSV
            </button>
          }
        />
        <div className={styles.boardControls}>
          <button className="text-link" onClick={() => setStatusFilter("all")}>
            Show all ({items.length}/{data?.limit || 250})
          </button>
          <span>Private to this browser workspace</span>
        </div>
        {loading ? (
          <p className={styles.loading}>
            <LoaderCircle size={16} className="spin" />
            Loading feedback…
          </p>
        ) : !shown.length ? (
          <EmptyState
            title="Start with a meaningful product question"
            description="Your private workspace has no feedback in this stage. Add your own observation or load the clearly labelled example brief."
          />
        ) : (
          <div className={styles.cards}>
            {shown.map((item) => (
              <article key={item.id} className={styles.card}>
                <div className={styles.cardTop}>
                  <Pill tone={item.priority === "high" ? "amber" : "neutral"}>
                    {item.priority} priority
                  </Pill>
                  <small>
                    {item.source.replaceAll("_", " ")} · {item.area}
                  </small>
                </div>
                <h3>{item.title}</h3>
                <p>{item.observation}</p>
                {item.hypothesis && (
                  <div className={styles.hypothesis}>
                    <strong>Hypothesis</strong>
                    <p>{item.hypothesis}</p>
                  </div>
                )}
                <dl>
                  <dt>Primary metric</dt>
                  <dd>{item.primary_metric || "Not defined"}</dd>
                  <dt>Guardrail</dt>
                  <dd>{item.guardrail || "Not defined"}</dd>
                  <dt>Success criterion</dt>
                  <dd>{item.success_criteria || "Not defined"}</dd>
                </dl>
                <div className={styles.context}>
                  Saved context: {item.context.dataset_name} ·{" "}
                  {item.context.start_date}–{item.context.end_date} ·{" "}
                  {item.context.market} · {item.context.device}
                </div>
                <label>
                  Next action
                  <textarea
                    maxLength={500}
                    rows={2}
                    value={actions[item.id] ?? item.next_step}
                    onChange={(event) =>
                      setActions((previous) => ({
                        ...previous,
                        [item.id]: event.target.value,
                      }))
                    }
                  />
                </label>
                <div className={styles.cardFooter}>
                  <label>
                    Decision stage
                    <select
                      aria-label={`Decision stage for ${item.title}`}
                      value={item.status}
                      disabled={Boolean(busy)}
                      onChange={(event) =>
                        update(item, event.target.value as Status)
                      }
                    >
                      {(Object.keys(STATUS_LABELS) as Status[]).map(
                        (status) => (
                          <option key={status} value={status}>
                            {STATUS_LABELS[status]}
                          </option>
                        ),
                      )}
                    </select>
                  </label>
                  <button
                    className="button subtle"
                    disabled={Boolean(busy)}
                    onClick={() => update(item, item.status)}
                  >
                    Save action
                  </button>
                  <button
                    className="icon-button"
                    aria-label={`Remove ${item.title}`}
                    disabled={Boolean(busy)}
                    onClick={() => setDeleteId(item.id)}
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
                {deleteId === item.id && (
                  <div className={styles.deleteConfirm}>
                    <span>Remove this private brief?</span>
                    <button
                      className="button subtle"
                      onClick={() => setDeleteId(null)}
                    >
                      Keep
                    </button>
                    <button
                      className="button subtle"
                      disabled={Boolean(busy)}
                      onClick={() => remove(item.id)}
                    >
                      Remove
                    </button>
                  </div>
                )}
              </article>
            ))}
          </div>
        )}
      </Panel>
      <Panel>
        <PanelHeading
          eyebrow="Portfolio walkthrough"
          title="Show the analyst judgment behind the dashboard"
          description="A practical demonstration for a product analytics conversation."
        />
        <div className={styles.strategy}>
          <div>
            <MessageSquareText size={20} />
            <h3>1. Frame a candidate problem</h3>
            <p>
              Choose one search or application friction point. Show the relevant
              event definitions, segments and baseline rather than listing every
              feature.
            </p>
            <button className="text-link" onClick={() => navigate("funnel")}>
              Inspect the journey <ArrowUpRight size={14} />
            </button>
          </div>
          <div>
            <CheckCircle2 size={20} />
            <h3>2. Make an evidence-led decision</h3>
            <p>
              Compare manual search, GPT-4o and GPT-OSS. Explain sample ratio
              checks, uncertainty, relevance, latency and cost. Historical
              outcomes are simulated.
            </p>
            <button
              className="text-link"
              onClick={() => navigate("experiments")}
            >
              Read the experiment <ArrowUpRight size={14} />
            </button>
          </div>
          <div>
            <ArrowUpRight size={20} />
            <h3>3. Communicate what happens next</h3>
            <p>
              Write a short recommendation, its limits and the next test.
              Demonstrate Adobe and Power BI readiness without claiming access
              to company systems.
            </p>
            <a
              className="text-link"
              href="/portfolio-strategy.md"
              target="_blank"
              rel="noreferrer"
            >
              Open the full pitch strategy <ArrowUpRight size={14} />
            </a>
          </div>
        </div>
        <p className={styles.roleLink}>
          This flow reflects the publicly described responsibilities in the{" "}
          <a
            href="https://www.stepstone.de/stellenangebote--Product-Analyst-Dusseldorf-The-Stepstone-Group-GmbH--14495892-inline.html"
            target="_blank"
            rel="noreferrer"
          >
            Stepstone Product Analyst role
          </a>
          : discovery, tracking validation, experiments and clear stakeholder
          communication.
        </p>
      </Panel>
    </div>
  );
}
