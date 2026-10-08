"use client";

import { useState } from "react";
import {
  ArrowUpRight,
  BookOpen,
  ChartNoAxesCombined,
  Database,
  ExternalLink,
  Info,
  LoaderCircle,
  Monitor,
  RefreshCw,
  ShieldCheck,
  X,
} from "lucide-react";
import { apiFetch, apiFilters, formatNumber, type Filters } from "@/lib/api";
import type { AnalystAnswer } from "@/lib/types";
import { AnalystChart } from "./charts";
import { ConnectorStudio } from "./connectors";
import { EmptyState, Panel, PanelHeading, Pill } from "./ui";
import { useWorkspace } from "./workspace";
import styles from "./integration-hubs.module.css";

type HubProps = { filters: Filters };
type CheckResult = {
  status: string;
  verified: boolean;
  detail: string;
  details?: { reports?: unknown[]; companies?: unknown[] };
};
type PowerBIReport = {
  id: string;
  name: string;
  web_url: string;
  embed_url?: string;
};
type AdobeReport = {
  source: string;
  synthetic: boolean;
  rows?: {
    item_id: string;
    label: string;
    values: Record<string, number | null>;
  }[];
  totals?: Record<string, number | null>;
  chart?: {
    type: "line" | "bar";
    title: string;
    x_key: string;
    y_keys: string[];
    data: Record<string, string | number | null>[];
  };
  pagination?: {
    page: number;
    total_pages?: number;
    total_rows?: number;
    last_page?: boolean;
  };
  provenance?: {
    fetched_at?: string;
    endpoint: string;
    window: { start_date: string; end_date: string };
  };
  content?: unknown[];
  limitations?: string[];
  metrics?: string[];
  dimension?: string;
};

function ErrorMessage({ message }: { message: string | null }) {
  return message ? (
    <div className="inline-error" role="alert">
      <Info size={16} />
      {message}
    </div>
  ) : null;
}

/** Revalidate external URLs at render time, including URLs returned by discovery. */
function powerBIUrl(value: unknown, embed = false): string | null {
  if (typeof value !== "string") return null;
  try {
    const url = new URL(value);
    if (
      url.protocol !== "https:" ||
      !["app.powerbi.com", "app.powerbigov.us"].includes(url.hostname) ||
      url.username ||
      url.password ||
      (url.port && url.port !== "443")
    )
      return null;
    if (
      [...url.searchParams.keys()].some((key) =>
        /^(access_token|token|api_key|authorization)$/i.test(key),
      )
    )
      return null;
    if (embed && url.pathname.toLowerCase() !== "/reportembed") return null;
    return url.href;
  } catch {
    return null;
  }
}

function discoveredReports(result?: CheckResult | null): PowerBIReport[] {
  return (result?.details?.reports || []).flatMap((value) => {
    if (!value || typeof value !== "object") return [];
    const report = value as Record<string, unknown>;
    const href = powerBIUrl(report.web_url);
    if (
      !href ||
      typeof report.name !== "string" ||
      typeof report.id !== "string"
    )
      return [];
    return [
      {
        id: report.id,
        name: report.name,
        web_url: href,
        embed_url: powerBIUrl(report.embed_url, true) || undefined,
      },
    ];
  });
}

export function PowerBIHub({ filters }: HubProps) {
  const workspace = useWorkspace();
  const connector = workspace.connectors.find((item) => item.id === "powerbi");
  const [checking, setChecking] = useState(false);
  const [check, setCheck] = useState<CheckResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [frameUrl, setFrameUrl] = useState<string | null>(null);
  const result = connector?.configured
    ? check || (connector.last_result as CheckResult | null | undefined)
    : null;
  const reports = discoveredReports(result);
  const reportUrl = powerBIUrl(connector?.settings.embed_url);
  const embedUrl = powerBIUrl(connector?.settings.embed_url, true);
  const verified =
    connector?.status === "verified" &&
    connector.last_result?.verified === true;
  async function discover() {
    setChecking(true);
    setError(null);
    try {
      setCheck(
        await apiFetch<CheckResult>(
          "/workspace/connectors/powerbi/check",
          { method: "POST", body: "{}" },
          45_000,
        ),
      );
      workspace.refreshConnectors();
    } catch (failure) {
      setError(
        failure instanceof Error
          ? failure.message
          : "Power BI discovery failed.",
      );
    } finally {
      setChecking(false);
    }
  }
  return (
    <div className={styles.hub}>
      <Panel className={styles.hero}>
        <div className={styles.status}>
          <Pill tone="amber">
            <ChartNoAxesCombined size={13} /> Power BI
          </Pill>
          <Pill tone={verified ? "green" : "neutral"} dot>
            {workspace.connectorsLoading
              ? "Loading private settings"
              : verified
                ? "REST access verified"
                : connector?.configured
                  ? "Configured · sign-in required"
                  : "Disconnected"}
          </Pill>
        </div>
        <h2>Your leadership reporting workspace.</h2>
        <p>
          Connect an authorized Power BI report, verify access, and open the
          interactive view. Microsoft controls report permissions and sign-in.
        </p>
        <a
          className="text-link"
          href="/integration-guide.md"
          target="_blank"
          rel="noreferrer"
        >
          <BookOpen size={15} />
          Full Power BI & Adobe setup guide
          <ArrowUpRight size={14} />
        </a>
      </Panel>
      <div className={styles.grid}>
        <div>
          <ConnectorStudio only={["powerbi"]} />
        </div>
        <Panel>
          <PanelHeading
            title="Connect in three steps"
            description="Use your own published report and organization account."
          />
          <div className={styles.content}>
            <ol className={styles.guide}>
              <li>
                <div>
                  <strong>Publish your analysis</strong>
                  <p>
                    Build a report from your approved dataset. Keep the metric
                    definitions and data source visible to reviewers.
                  </p>
                </div>
              </li>
              <li>
                <div>
                  <strong>Copy the secure report URL</strong>
                  <p>
                    In Power BI, choose File → Embed report → Website or portal.
                    Save that URL in your private connection.
                  </p>
                </div>
              </li>
              <li>
                <div>
                  <strong>Verify or open</strong>
                  <p>
                    An optional authorized REST token lists accessible reports.
                    Opening a secure report prompts Microsoft sign-in when
                    needed.
                  </p>
                </div>
              </li>
            </ol>
            <div className={styles.links}>
              <a
                href="https://learn.microsoft.com/en-us/power-bi/collaborate-share/service-embed-secure"
                target="_blank"
                rel="noopener noreferrer"
              >
                <BookOpen size={14} />
                Secure embed guide
                <ArrowUpRight size={13} />
              </a>
              <a
                href="https://learn.microsoft.com/en-us/rest/api/power-bi/reports/get-reports-in-group"
                target="_blank"
                rel="noopener noreferrer"
              >
                REST permissions
                <ArrowUpRight size={13} />
              </a>
            </div>
          </div>
        </Panel>
      </div>
      <Panel>
        <PanelHeading
          eyebrow="Authorized report access"
          title="Open your Power BI report"
          description="REST verification and browser report access are separate checks."
          action={
            <button
              className="button subtle"
              disabled={!connector?.configured || checking}
              onClick={discover}
            >
              {checking ? (
                <LoaderCircle size={14} className="spin" />
              ) : (
                <RefreshCw size={14} />
              )}
              Verify & discover reports
            </button>
          }
        />
        <div className={styles.content}>
          <ErrorMessage message={error} />
          {result?.detail ? (
            <p className={styles.caption}>{result.detail}</p>
          ) : null}
          <div className={styles.cards}>
            {reportUrl ? (
              <div className={styles.report}>
                <div>
                  <strong>Your configured report</strong>
                  <small>
                    {new URL(reportUrl).hostname} · Microsoft authentication
                    applies
                  </small>
                </div>
                <div className="button-row">
                  <a
                    className="button primary"
                    href={reportUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <ExternalLink size={14} />
                    Open Power BI
                  </a>
                  {embedUrl ? (
                    <button
                      className="button subtle"
                      onClick={() => setFrameUrl(embedUrl)}
                    >
                      <Monitor size={14} />
                      View here
                    </button>
                  ) : null}
                </div>
              </div>
            ) : null}
            {reports.map((report) => (
              <div className={styles.report} key={report.id}>
                <div>
                  <strong>{report.name}</strong>
                  <small>Returned by the authorized Power BI REST API</small>
                </div>
                <a
                  className="button subtle"
                  href={report.web_url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <ExternalLink size={14} />
                  Open report
                </a>
              </div>
            ))}
          </div>
          {!reportUrl && !reports.length ? (
            <EmptyState
              title="No connected report yet"
              description="Configure your secure report URL above, or save a REST token and discover the reports you can access."
            />
          ) : null}
          {connector?.settings.embed_url && !reportUrl ? (
            <ErrorMessage message="The saved report URL is unsupported. Use an HTTPS app.powerbi.com report URL without credentials in the URL." />
          ) : null}
          {frameUrl && connector?.configured && frameUrl === embedUrl ? (
            <div>
              <div className={styles.links}>
                <Pill tone="blue">Microsoft-hosted report</Pill>
                <button
                  className="button ghost"
                  onClick={() => setFrameUrl(null)}
                >
                  <X size={14} />
                  Close embedded view
                </button>
              </div>
              <p className={styles.caption}>
                Power BI handles authentication, licenses, and row access. If
                sign-in is blocked in this frame, use Open Power BI above.
              </p>
              <iframe
                className={styles.frame}
                src={frameUrl}
                title="Your authorized Power BI report"
                loading="lazy"
                allowFullScreen
                referrerPolicy="strict-origin-when-cross-origin"
              />
            </div>
          ) : null}
          <details className={styles.details}>
            <summary>Permissions, licensing & freshness</summary>
            <p>
              Secure embedding requires viewer access. Viewers generally need
              Pro or PPU unless both the report and semantic model are on
              qualifying Premium or Fabric F64+ capacity.{" "}
              <a
                href="https://learn.microsoft.com/en-us/power-bi/collaborate-share/service-embed-secure"
                target="_blank"
                rel="noopener noreferrer"
              >
                Microsoft licensing guidance
              </a>
            </p>
            <p>
              Define and test row-level security in the semantic model.
              Workspace Viewer permissions respect RLS; Admin, Member, and
              Contributor roles have broader access.{" "}
              <a
                href="https://learn.microsoft.com/en-us/fabric/security/service-admin-row-level-security"
                target="_blank"
                rel="noopener noreferrer"
              >
                RLS guidance
              </a>
            </p>
            <p>
              Import models need data refresh. Configure source credentials and
              a schedule in Power BI; this workspace opens reports and does not
              refresh their semantic models.{" "}
              <a
                href="https://learn.microsoft.com/en-us/power-bi/connect-data/refresh-data"
                target="_blank"
                rel="noopener noreferrer"
              >
                Refresh guidance
              </a>
            </p>
            <p>
              For REST discovery, use an organizational Microsoft Entra app and
              an authorized token with Report.Read.All. Tokens are encrypted on
              the server and must be replaced when expired.{" "}
              <a
                href="https://learn.microsoft.com/en-us/power-bi/developer/embedded/register-app"
                target="_blank"
                rel="noopener noreferrer"
              >
                App registration
              </a>
            </p>
          </details>
          <p className={styles.caption}>
            Current analytics selection: {apiFilters(filters).start_date} →{" "}
            {apiFilters(filters).end_date}. Set corresponding report filters
            inside Power BI; they are not automatically mapped to external
            report fields.
          </p>
        </div>
      </Panel>
    </div>
  );
}

export function AdobeAnalyticsHub({ filters }: HubProps) {
  const workspace = useWorkspace();
  const connector = workspace.connectors.find((item) => item.id === "adobe");
  const dates = apiFilters(filters);
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [dimension, setDimension] = useState("");
  const [metricIds, setMetricIds] = useState("");
  const [segmentId, setSegmentId] = useState("");
  const [result, setResult] = useState<AdobeReport | null>(null);
  const [chartMetric, setChartMetric] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isMcp = connector?.settings.transport === "mcp";
  const metrics =
    metricIds ||
    (Array.isArray(connector?.settings.metric_ids)
      ? connector.settings.metric_ids.join(", ")
      : "metrics/visits, metrics/pageviews, metrics/uniquevisitors");
  const selectedMetric = chartMetric || result?.chart?.y_keys[0];
  const chart: AnalystAnswer["chart"] =
    result?.chart && selectedMetric
      ? { ...result.chart, y_key: selectedMetric }
      : null;
  async function fetchReport(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const response = await apiFetch<AdobeReport>(
        isMcp ? "/workspace/adobe/mcp/report" : "/workspace/adobe/report",
        {
          method: "POST",
          body: JSON.stringify({
            start_date: startDate || dates.start_date,
            end_date: endDate || dates.end_date,
            dimension:
              dimension ||
              connector?.settings.dimension_id ||
              "variables/daterangeday",
            metrics: metrics
              .split(",")
              .map((value) => value.trim())
              .filter(Boolean),
            ...(segmentId.trim() ? { segment_id: segmentId.trim() } : {}),
            limit: 50,
          }),
        },
        60_000,
      );
      setResult(response);
      setChartMetric(response.chart?.y_keys[0] || "");
    } catch (failure) {
      setError(
        failure instanceof Error
          ? failure.message
          : "Adobe could not return this report.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className={styles.hub}>
      <Panel className={styles.hero}>
        <div className={styles.status}>
          <Pill tone="amber">
            <Database size={13} />
            Adobe Analytics
          </Pill>
          <Pill
            tone={connector?.status === "verified" ? "green" : "neutral"}
            dot
          >
            {workspace.connectorsLoading
              ? "Loading private settings"
              : connector?.status === "verified"
                ? "Access verified"
                : connector?.configured
                  ? "Configured · verification pending"
                  : "Disconnected"}
          </Pill>
        </div>
        <h2>Bring verified product telemetry into view.</h2>
        <p>
          Read reports from your authorized Adobe account, choose the metrics
          behind a product question, and inspect the returned evidence.
        </p>
        <p className={styles.caption}>
          The portfolio’s synthetic data remains separate. Adobe charts appear
          only after a successful report request.
        </p>
        <a
          className="text-link"
          href="/integration-guide.md"
          target="_blank"
          rel="noreferrer"
        >
          <BookOpen size={15} />
          Full Power BI & Adobe setup guide
          <ArrowUpRight size={14} />
        </a>
      </Panel>
      <div className={styles.grid}>
        <div>
          <ConnectorStudio only={["adobe"]} />
        </div>
        <Panel>
          <PanelHeading
            title="Connect your own Adobe organization"
            description="Use an account with Analytics API and report-suite permissions."
          />
          <div className={styles.content}>
            <ol className={styles.guide}>
              <li>
                <div>
                  <strong>Enable Analytics access</strong>
                  <p>
                    Assign the API credential to an Adobe Analytics product
                    profile with access to the required report suites.
                  </p>
                </div>
              </li>
              <li>
                <div>
                  <strong>Choose authentication</strong>
                  <p>
                    Save an authorized access token and client ID, or use
                    server-to-server OAuth with client secret and the scopes
                    from Developer Console.
                  </p>
                </div>
              </li>
              <li>
                <div>
                  <strong>Choose REST or MCP</strong>
                  <p>
                    REST returns structured report rows. Adobe’s official MCP
                    endpoint discovers tools and runs a read-only report; its
                    raw returned evidence stays visible.
                  </p>
                </div>
              </li>
            </ol>
            <div className={styles.links}>
              <a
                href="https://developer.adobe.com/analytics-apis/docs/2.0/guides/"
                target="_blank"
                rel="noopener noreferrer"
              >
                <BookOpen size={14} />
                API setup
                <ArrowUpRight size={13} />
              </a>
              <a
                href="https://developer.adobe.com/analytics-mcp/docs/guides/"
                target="_blank"
                rel="noopener noreferrer"
              >
                MCP setup
                <ArrowUpRight size={13} />
              </a>
            </div>
          </div>
        </Panel>
      </div>
      <Panel>
        <PanelHeading
          eyebrow="Actual account evidence"
          title="Build an Adobe report"
          description="Dates use your report-suite timezone. Add your own segment for a role, device, or experiment cohort."
          action={
            <Pill tone="blue">
              {isMcp ? "Adobe MCP" : "Analytics REST 2.0"}
            </Pill>
          }
        />
        <div className={styles.content}>
          <form className={styles.form} onSubmit={fetchReport}>
            <label className={styles.field}>
              <span>Start date</span>
              <input
                type="date"
                required
                value={startDate || dates.start_date}
                onChange={(event) => setStartDate(event.target.value)}
              />
            </label>
            <label className={styles.field}>
              <span>End date · inclusive</span>
              <input
                type="date"
                required
                min={startDate || dates.start_date}
                value={endDate || dates.end_date}
                onChange={(event) => setEndDate(event.target.value)}
              />
            </label>
            <label className={styles.field}>
              <span>Dimension ID</span>
              <input
                value={
                  dimension ||
                  String(
                    connector?.settings.dimension_id ||
                      "variables/daterangeday",
                  )
                }
                onChange={(event) => setDimension(event.target.value)}
                placeholder="variables/daterangeday"
              />
            </label>
            <label className={styles.field}>
              <span>Adobe segment ID · optional</span>
              <input
                value={segmentId}
                onChange={(event) => setSegmentId(event.target.value)}
                placeholder="Your authorized cohort segment"
              />
            </label>
            <label className={`${styles.field} ${styles.wide}`}>
              <span>Metric IDs · comma separated</span>
              <input
                value={metrics}
                onChange={(event) => setMetricIds(event.target.value)}
                placeholder="metrics/visits, metrics/pageviews"
              />
            </label>
            <div className={styles.wide}>
              <button
                className="button primary"
                disabled={!workspace.ready || !connector?.configured || busy}
              >
                {busy ? (
                  <LoaderCircle className="spin" size={15} />
                ) : (
                  <Database size={15} />
                )}
                {busy ? "Retrieving Adobe evidence…" : "Fetch actual report"}
              </button>
            </div>
          </form>
          <p className={styles.caption}>
            {connector?.configured
              ? `Report suite: ${String(connector.settings.report_suite_id || "not specified")} · up to 50 returned rows. Market, device, and role require your own Adobe mappings or segment.`
              : "Adobe is disconnected. Configure your private connection above to enable a real report request."}
          </p>
          <ErrorMessage message={error} />
          {result ? (
            <div>
              <div className={styles.links}>
                <Pill tone="green" dot>
                  Actual Adobe response
                </Pill>
                <span className={styles.caption}>
                  {result.provenance?.window.start_date} →{" "}
                  {result.provenance?.window.end_date}
                </span>
              </div>
              {result.totals ? (
                <div className={styles.totals}>
                  {Object.entries(result.totals).map(([metric, value]) => (
                    <div key={metric}>
                      <span>{metric}</span>
                      <strong>{formatNumber(value, 2)}</strong>
                    </div>
                  ))}
                </div>
              ) : null}
              {chart ? (
                <>
                  <label className={styles.field}>
                    <span>Visualize metric</span>
                    <select
                      value={selectedMetric}
                      onChange={(event) => setChartMetric(event.target.value)}
                    >
                      {result.chart?.y_keys.map((metric) => (
                        <option key={metric} value={metric}>
                          {metric}
                        </option>
                      ))}
                    </select>
                  </label>
                  <AnalystChart chart={chart} />
                </>
              ) : null}
              {result.rows?.length ? (
                <div className="table-wrap">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Dimension value</th>
                        {result.metrics?.map((metric) => (
                          <th key={metric}>{metric}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {result.rows.map((row, index) => (
                        <tr key={`${row.item_id}:${index}`}>
                          <td>{row.label}</td>
                          {result.metrics?.map((metric) => (
                            <td key={metric}>
                              {formatNumber(row.values[metric], 2)}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
              {result.rows && !result.rows.length ? (
                <EmptyState
                  title="Adobe returned no dimension rows"
                  description="Review the selected date window, report suite, and segment. Any returned totals above are retained."
                />
              ) : null}
              {result.content ? (
                <details className={styles.details} open>
                  <summary>Read-only MCP report evidence</summary>
                  <pre className={styles.payload}>
                    {JSON.stringify(result.content, null, 2)}
                  </pre>
                </details>
              ) : null}
              <p className={styles.caption}>
                {result.pagination
                  ? `Page ${(result.pagination.page || 0) + 1}${result.pagination.total_pages ? ` of ${result.pagination.total_pages}` : ""}. This view shows only the returned report page. `
                  : ""}
                {result.provenance?.fetched_at
                  ? `Retrieved ${new Date(result.provenance.fetched_at).toLocaleString()}. `
                  : ""}
                {result.provenance?.endpoint}
              </p>
              {result.limitations?.map((limitation) => (
                <p key={limitation} className={styles.caption}>
                  {limitation}
                </p>
              ))}
            </div>
          ) : !busy && !error ? (
            <EmptyState
              title="Your Adobe report will appear here"
              description="Fetch evidence to see actual metric totals, returned rows, and a chart. No sample Adobe data is substituted."
            />
          ) : null}
          <details className={styles.details}>
            <summary>Role comparisons, OAuth & troubleshooting</summary>
            <p>
              Map job role, experiment assignment, and application milestones to
              the dimensions and events in your own report suite. Fetch cohort
              segments separately and compare their denominators before
              interpreting differences. Adobe counts alone do not establish a
              randomized winner or a causal explanation.
            </p>
            <p>
              Bearer tokens expire and need replacement. Server-to-server OAuth
              renews tokens using encrypted credentials and the authorized
              scopes from your project.{" "}
              <a
                href="https://developer.adobe.com/developer-console/docs/guides/authentication/ServerToServerAuthentication/"
                target="_blank"
                rel="noopener noreferrer"
              >
                Adobe authentication guide
              </a>
            </p>
            <p>
              A 401 usually requires a valid token; a 403 requires the correct
              organization/product-profile access. Review report-suite
              permissions and exact dimension/metric IDs when a request is
              rejected.{" "}
              <a
                href="https://developer.adobe.com/analytics-apis/docs/2.0/guides/endpoints/reports/"
                target="_blank"
                rel="noopener noreferrer"
              >
                Reporting API guide
              </a>
            </p>
            <p>
              MCP requires the MCP Access permission in your Adobe product
              profile. It uses https://aa-mcp.adobe.io/mcp with your
              organization and company IDs. This lab calls discovery and
              reporting tools only.{" "}
              <a
                href="https://developer.adobe.com/analytics-mcp/docs/guides/"
                target="_blank"
                rel="noopener noreferrer"
              >
                MCP access setup
              </a>{" "}
              ·{" "}
              <a
                href="https://developer.adobe.com/analytics-mcp/docs/aa/reference"
                target="_blank"
                rel="noopener noreferrer"
              >
                Tool reference
              </a>
            </p>
          </details>
        </div>
      </Panel>
      <div className={styles.status}>
        <ShieldCheck size={16} />
        <span className={styles.caption}>
          Credentials stay encrypted in your private workspace. Numeric Adobe
          reports remain separate from uploaded and synthetic experiment
          decisions.
        </span>
      </div>
    </div>
  );
}
