"use client";

import { useEffect, useState } from "react";
import {
  ArrowUpRight,
  Bot,
  Check,
  CircleCheck,
  Database,
  Globe2,
  Info,
  KeyRound,
  LoaderCircle,
  Plug,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import { apiFetch, apiFilters, formatNumber, type Filters } from "@/lib/api";
import type { AnalystAnswer, WorkspaceConnector } from "@/lib/types";
import { AnalystChart } from "./charts";
import { EmptyState, Panel, PanelHeading, Pill } from "./ui";
import { ModelPicker, useWorkspace } from "./workspace";

const SPECS = [
  {
    id: "adobe",
    name: "Adobe Analytics",
    icon: Database,
    description: "Authorized Analytics 2.0 reports and company discovery.",
  },
  {
    id: "mcp",
    name: "External MCP",
    icon: Plug,
    description: "Verified remote tools and explicit read-only enrichment.",
  },
  {
    id: "powerbi",
    name: "Power BI",
    icon: Globe2,
    description: "Published reports and authorized REST report discovery.",
  },
  {
    id: "openrouter",
    name: "OpenRouter",
    icon: Sparkles,
    description: "Private provider credentials and model preferences.",
  },
  {
    id: "ollama",
    name: "Ollama Cloud",
    icon: Bot,
    description: "Search, analyst, and Gemma ingestion model settings.",
  },
];
type CheckResult = {
  status: string;
  verified: boolean;
  detail: string;
  capabilities?: string[];
  checked_at?: string;
  details?: Record<string, unknown>;
};

function Field({
  label,
  value,
  onChange,
  secret = false,
  placeholder,
  multiline = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  secret?: boolean;
  placeholder?: string;
  multiline?: boolean;
}) {
  return (
    <label className="connector-field">
      <span>{label}</span>
      {multiline ? (
        <textarea
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          rows={3}
        />
      ) : (
        <input
          type={secret ? "password" : "text"}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          autoComplete={secret ? "new-password" : "off"}
          spellCheck={false}
        />
      )}
    </label>
  );
}

export function ConnectorStudio({ only }: { only?: string[] } = {}) {
  const workspace = useWorkspace();
  const [selected, setSelected] = useState<string | null>(null);
  const [settings, setSettings] = useState<Record<string, string>>({});
  const [secrets, setSecrets] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [checkResult, setCheckResult] = useState<CheckResult | null>(null);
  const connector = workspace.connectors.find((item) => item.id === selected);
  function open(id: string) {
    const existing = workspace.connectors.find((item) => item.id === id);
    const values = Object.fromEntries(
      Object.entries(existing?.settings || {}).map(([key, value]) => [
        key,
        Array.isArray(value)
          ? value.join(", ")
          : typeof value === "object" && value
            ? JSON.stringify(value, null, 2)
            : String(value ?? ""),
      ]),
    );
    const defaults: Record<string, string> =
      id === "adobe"
        ? { auth_type: "bearer", transport: "rest" }
        : id === "mcp"
          ? { auth_type: "none", auth_header: "X-API-Key" }
          : id === "ollama" || id === "openrouter"
            ? { purpose: "search" }
            : {};
    setSettings({ ...defaults, ...values });
    setSecrets({});
    setSelected(id);
    setError(null);
    setFeedback(null);
    setCheckResult(null);
  }
  function setting(key: string, value: string) {
    setSettings((previous) => ({ ...previous, [key]: value }));
  }
  function secret(key: string, value: string) {
    setSecrets((previous) => ({ ...previous, [key]: value }));
  }
  useEffect(() => {
    if (!selected) return;
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setSelected(null);
        setSecrets({});
      }
    };
    document.addEventListener("keydown", close);
    return () => document.removeEventListener("keydown", close);
  }, [selected]);
  async function verify(id: string) {
    setBusy(`check:${id}`);
    setError(null);
    setFeedback(null);
    try {
      const result = await apiFetch<CheckResult>(
        `/workspace/connectors/${id}/check`,
        { method: "POST", body: "{}" },
        45_000,
      );
      setCheckResult(result);
      setFeedback(result.detail);
      workspace.refreshConnectors();
    } catch (failure) {
      setError(
        failure instanceof Error ? failure.message : "Connection check failed.",
      );
    } finally {
      setBusy(null);
    }
  }
  async function save(event: React.FormEvent, runCheck = true) {
    event.preventDefault();
    if (!selected || busy) return;
    setBusy(`save:${selected}`);
    setError(null);
    setFeedback(null);
    setCheckResult(null);
    try {
      const allowed: Record<string, string[]> = {
        adobe: [
          "auth_type",
          "transport",
          "mcp_endpoint",
          "org_id",
          "company_id",
          "report_suite_id",
          "dimension_id",
          "metric_ids",
          "experiment_dimension_id",
          "scopes",
        ],
        powerbi: ["embed_url", "group_id"],
        mcp: [
          "endpoint",
          "auth_type",
          "auth_header",
          "tool_name",
          "tool_arguments",
        ],
        ollama: [
          "model",
          "purpose",
          "search_model",
          "analyst_model",
          "ingestion_model",
        ],
        openrouter: ["model", "purpose", "search_model", "analyst_model"],
      };
      const payload: Record<string, unknown> = Object.fromEntries(
        Object.entries(settings).filter(([key]) =>
          allowed[selected].includes(key),
        ),
      );
      if (selected === "adobe")
        payload.metric_ids = (
          settings.metric_ids ||
          "metrics/visits, metrics/pageviews, metrics/uniquevisitors"
        )
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean);
      if (selected === "mcp") {
        const argumentsObject = settings.tool_arguments
          ? JSON.parse(settings.tool_arguments)
          : {};
        if (
          !argumentsObject ||
          Array.isArray(argumentsObject) ||
          typeof argumentsObject !== "object"
        )
          throw new Error("Tool arguments must be a JSON object.");
        payload.tool_arguments = argumentsObject;
      }
      await apiFetch(`/workspace/connectors/${selected}`, {
        method: "PUT",
        body: JSON.stringify({ settings: payload, secrets }),
      });
      setSecrets({});
      workspace.refreshConnectors();
      if (runCheck) {
        const result = await apiFetch<CheckResult>(
          `/workspace/connectors/${selected}/check`,
          { method: "POST", body: "{}" },
          45_000,
        );
        setCheckResult(result);
        setFeedback(result.detail);
        workspace.refreshConnectors();
      } else
        setFeedback(
          "Saved encrypted in this workspace. Connectivity has not been verified.",
        );
    } catch (failure) {
      setError(
        failure instanceof Error
          ? failure.message
          : "Settings could not be saved.",
      );
    } finally {
      setBusy(null);
    }
  }
  async function disconnect() {
    if (!selected) return;
    setBusy(`delete:${selected}`);
    setError(null);
    try {
      await apiFetch(`/workspace/connectors/${selected}`, { method: "DELETE" });
      setSecrets({});
      setSelected(null);
      workspace.refreshConnectors();
    } catch (failure) {
      setError(
        failure instanceof Error
          ? failure.message
          : "Settings could not be removed.",
      );
    } finally {
      setBusy(null);
    }
  }
  const selectedSpec = SPECS.find((item) => item.id === selected);
  return (
    <>
      <div className="section-label">
        <h2>Your private connections</h2>
        <span>
          <ShieldCheck size={12} />
          Encrypted workspace credentials
        </span>
      </div>
      {workspace.error || workspace.connectorsError ? (
        <div className="inline-error">
          <Info size={14} />
          {workspace.error || workspace.connectorsError}
          <button
            className="text-link"
            onClick={
              workspace.error
                ? workspace.retryWorkspace
                : workspace.refreshConnectors
            }
          >
            Retry
          </button>
        </div>
      ) : null}
      <div className="private-connectors-grid">
        {SPECS.filter((spec) => !only || only.includes(spec.id)).map((spec) => {
          const stored = workspace.connectors.find(
            (item) => item.id === spec.id,
          );
          const verified =
            stored?.status === "verified" || stored?.last_result?.verified;
          const providerUsesShared =
            (spec.id === "openrouter" || spec.id === "ollama") &&
            !stored?.secrets_present.includes("api_key") &&
            workspace.models?.providers.some(
              (provider) => provider.id === spec.id && provider.configured,
            );
          return (
            <Panel className="private-connector-card" key={spec.id}>
              <div className="private-connector-heading">
                <span className="connection-logo">
                  <spec.icon size={20} />
                </span>
                <Pill
                  tone={
                    verified
                      ? "green"
                      : stored?.configured
                        ? "amber"
                        : "neutral"
                  }
                  dot
                >
                  {workspace.connectorsLoading
                    ? "Checking"
                    : verified
                      ? "Verified"
                      : stored?.configured
                        ? "Configured"
                        : providerUsesShared
                          ? "Shared settings"
                          : "Disconnected"}
                </Pill>
              </div>
              <h3>{spec.name}</h3>
              <p>{spec.description}</p>
              {providerUsesShared ? (
                <small>
                  Using a shared deployment key
                  {stored?.configured ? " with private model preferences" : ""}.
                  A live check verifies access.
                </small>
              ) : null}
              {stored?.last_result?.detail ? (
                <small>{stored.last_result.detail}</small>
              ) : null}
              <div className="button-row">
                <button
                  className="button subtle small-button"
                  onClick={() => open(spec.id)}
                  disabled={!workspace.ready}
                >
                  <KeyRound size={12} />
                  {stored?.configured ? "Edit settings" : "Configure"}
                </button>
                {stored?.configured ? (
                  <button
                    className="icon-button"
                    aria-label={`Verify ${spec.name}`}
                    disabled={Boolean(busy)}
                    onClick={() => verify(spec.id)}
                  >
                    {busy === `check:${spec.id}` ? (
                      <LoaderCircle size={13} className="spin" />
                    ) : (
                      <RefreshCw size={13} />
                    )}
                  </button>
                ) : null}
              </div>
            </Panel>
          );
        })}
      </div>
      {!selected && (feedback || error) ? (
        <div
          className={error ? "inline-error" : "action-feedback"}
          role="status"
        >
          {error || feedback}
        </div>
      ) : null}
      {selected && selectedSpec ? (
        <div
          className="modal-backdrop"
          onClick={() => {
            setSelected(null);
            setSecrets({});
          }}
        >
          <section
            className="modal connector-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="connector-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="connector-modal-heading">
              <div>
                <div className="eyebrow">Private workspace connection</div>
                <h2 id="connector-title">Connect {selectedSpec.name}</h2>
              </div>
              <button
                className="icon-button"
                aria-label="Close connector settings"
                onClick={() => {
                  setSelected(null);
                  setSecrets({});
                }}
                autoFocus
              >
                <X size={16} />
              </button>
            </div>
            <p>
              {selectedSpec.description} Credentials stay encrypted on the
              server and never enter analytics exports.
            </p>
            <form onSubmit={save}>
              <div className="connector-fields">
                {selected === "adobe" ? (
                  <>
                    <label className="connector-field">
                      <span>Adobe connection transport</span>
                      <select
                        value={settings.transport || "rest"}
                        onChange={(event) =>
                          setting("transport", event.target.value)
                        }
                      >
                        <option value="rest">Adobe Analytics REST 2.0</option>
                        <option value="mcp">
                          Official Adobe Analytics MCP
                        </option>
                      </select>
                    </label>
                    {settings.transport === "mcp" ? (
                      <>
                        <Field
                          label="Official Adobe MCP endpoint"
                          value={
                            settings.mcp_endpoint ||
                            "https://aa-mcp.adobe.io/mcp"
                          }
                          onChange={(value) => setting("mcp_endpoint", value)}
                        />
                        <Field
                          label="IMS organization ID"
                          value={settings.org_id || ""}
                          onChange={(value) => setting("org_id", value)}
                          placeholder="Your Adobe IMS organization ID"
                        />
                        <p className="connector-limit">
                          Official endpoint: https://aa-mcp.adobe.io/mcp. The
                          adapter verifies tools and uses the actual runReport
                          response; unsupported tools remain unavailable.
                        </p>
                      </>
                    ) : (
                      <p className="connector-limit">
                        Fixed REST API: https://analytics.adobe.io/api.
                        Authorized company and report-suite identifiers select
                        your data.
                      </p>
                    )}
                    <label className="connector-field">
                      <span>Authorization</span>
                      <select
                        value={settings.auth_type || "bearer"}
                        onChange={(event) =>
                          setting("auth_type", event.target.value)
                        }
                      >
                        <option value="bearer">
                          Existing OAuth bearer token
                        </option>
                        <option value="oauth_client_credentials">
                          OAuth client credentials
                        </option>
                      </select>
                    </label>
                    <Field
                      label="Company ID"
                      value={settings.company_id || ""}
                      onChange={(value) => setting("company_id", value)}
                    />
                    <Field
                      label="Report suite ID"
                      value={settings.report_suite_id || ""}
                      onChange={(value) => setting("report_suite_id", value)}
                    />
                    <Field
                      label="Client ID"
                      secret
                      value={secrets.client_id || ""}
                      onChange={(value) => secret("client_id", value)}
                      placeholder={
                        connector?.secrets_present.includes("client_id")
                          ? "Saved · leave blank to preserve"
                          : "Adobe API client ID"
                      }
                    />
                    {settings.auth_type === "oauth_client_credentials" ? (
                      <>
                        <Field
                          label="Client secret"
                          secret
                          value={secrets.client_secret || ""}
                          onChange={(value) => secret("client_secret", value)}
                          placeholder={
                            connector?.secrets_present.includes("client_secret")
                              ? "Saved · leave blank to preserve"
                              : "Adobe OAuth client secret"
                          }
                        />
                        <Field
                          label="OAuth scopes"
                          value={settings.scopes || ""}
                          onChange={(value) => setting("scopes", value)}
                          placeholder="Your authorized Adobe scopes"
                        />
                      </>
                    ) : (
                      <Field
                        label="Access token"
                        secret
                        value={secrets.access_token || ""}
                        onChange={(value) => secret("access_token", value)}
                        placeholder={
                          connector?.secrets_present.includes("access_token")
                            ? "Saved · leave blank to preserve"
                            : "Authorized Adobe OAuth token"
                        }
                      />
                    )}
                    <Field
                      label="Dimension ID"
                      value={settings.dimension_id || ""}
                      onChange={(value) => setting("dimension_id", value)}
                      placeholder="variables/daterangeday"
                    />
                    <Field
                      label="Metric IDs · comma separated"
                      value={settings.metric_ids || ""}
                      onChange={(value) => setting("metric_ids", value)}
                      placeholder="metrics/visits, metrics/pageviews"
                    />
                    <Field
                      label="Experiment dimension ID · optional"
                      value={settings.experiment_dimension_id || ""}
                      onChange={(value) =>
                        setting("experiment_dimension_id", value)
                      }
                    />
                  </>
                ) : null}
                {selected === "mcp" ? (
                  <>
                    <Field
                      label="Public HTTPS MCP endpoint"
                      value={settings.endpoint || ""}
                      onChange={(value) => setting("endpoint", value)}
                      placeholder="https://your-server.example/mcp"
                    />
                    <label className="connector-field">
                      <span>Authentication</span>
                      <select
                        value={settings.auth_type || "none"}
                        onChange={(event) =>
                          setting("auth_type", event.target.value)
                        }
                      >
                        <option value="none">No authentication</option>
                        <option value="bearer">Bearer token</option>
                        <option value="api_key">API key</option>
                      </select>
                    </label>
                    {settings.auth_type !== "none" ? (
                      <>
                        <Field
                          label="Authentication token"
                          secret
                          value={secrets.token || ""}
                          onChange={(value) => secret("token", value)}
                          placeholder={
                            connector?.secrets_present.includes("token")
                              ? "Saved · leave blank to preserve"
                              : "Token for this remote MCP server"
                          }
                        />
                        {settings.auth_type === "api_key" ? (
                          <label className="connector-field">
                            <span>API-key header</span>
                            <select
                              value={settings.auth_header || "X-API-Key"}
                              onChange={(event) =>
                                setting("auth_header", event.target.value)
                              }
                            >
                              <option value="X-API-Key">X-API-Key</option>
                              <option value="api-key">api-key</option>
                              <option value="Authorization">
                                Authorization
                              </option>
                            </select>
                          </label>
                        ) : null}
                      </>
                    ) : null}
                    <Field
                      label="Read-only enrichment tool · optional"
                      value={settings.tool_name || ""}
                      onChange={(value) => setting("tool_name", value)}
                      placeholder="A tool declared read-only by the server"
                    />
                    <Field
                      label="Tool arguments · JSON object"
                      multiline
                      value={settings.tool_arguments || ""}
                      onChange={(value) => setting("tool_arguments", value)}
                      placeholder={
                        '{"query":"your authorized evidence request"}'
                      }
                    />
                    <p className="connector-limit">
                      Checks perform MCP initialization and tool discovery.
                      Enrichment runs only an explicitly configured tool
                      declared read-only by the remote server.
                    </p>
                  </>
                ) : null}
                {selected === "powerbi" ? (
                  <>
                    <Field
                      label="HTTPS Power BI report embed URL"
                      value={settings.embed_url || ""}
                      onChange={(value) => setting("embed_url", value)}
                      placeholder="https://app.powerbi.com/reportEmbed…"
                    />
                    <Field
                      label="Group / workspace ID · optional"
                      value={settings.group_id || ""}
                      onChange={(value) => setting("group_id", value)}
                    />
                    <Field
                      label="REST OAuth access token · optional"
                      secret
                      value={secrets.access_token || ""}
                      onChange={(value) => secret("access_token", value)}
                      placeholder={
                        connector?.secrets_present.includes("access_token")
                          ? "Saved · leave blank to preserve"
                          : "Enables authorized report-list verification"
                      }
                    />
                    <p className="connector-limit">
                      An embed URL alone is configured, not authenticated or
                      verified. The optional token enables a real read-only
                      Power BI REST check.
                    </p>
                  </>
                ) : null}
                {selected === "openrouter" || selected === "ollama" ? (
                  <>
                    <label className="connector-field">
                      <span>Model purpose</span>
                      <select
                        value={settings.purpose || "search"}
                        onChange={(event) =>
                          setting("purpose", event.target.value)
                        }
                      >
                        <option value="search">Job search ranking</option>
                        <option value="analyst">
                          Analytics interpretation
                        </option>
                        {selected === "ollama" ? (
                          <option value="ingestion">
                            Upload meaning layer
                          </option>
                        ) : null}
                      </select>
                    </label>
                    <ModelPicker
                      provider={selected}
                      purpose={
                        (settings.purpose || "search") as
                          "search" | "analyst" | "ingestion"
                      }
                      value={settings.model || ""}
                      onChange={(value) => setting("model", value)}
                    />
                    <Field
                      label="Private API key override · optional"
                      secret
                      value={secrets.api_key || ""}
                      onChange={(value) => secret("api_key", value)}
                      placeholder={
                        connector?.secrets_present.includes("api_key")
                          ? "Saved · leave blank to preserve"
                          : "Use shared deployment credentials when blank"
                      }
                    />
                    <p className="connector-limit">
                      The provider URL is fixed. A workspace override changes
                      only your requests and never overwrites shared deployment
                      keys.
                    </p>
                  </>
                ) : null}
              </div>
              {error ? (
                <div className="inline-error" role="alert">
                  <Info size={14} />
                  {error}
                </div>
              ) : null}
              {feedback ? (
                <div className="connection-feedback">
                  <Pill tone={checkResult?.verified ? "green" : "amber"}>
                    {checkResult?.status || "Saved"}
                  </Pill>
                  <p>{feedback}</p>
                  {checkResult?.capabilities?.length ? (
                    <small>
                      Verified capabilities:{" "}
                      {checkResult.capabilities.join(" · ")}
                    </small>
                  ) : null}
                </div>
              ) : null}
              <div className="connector-footer">
                <button className="button primary" disabled={Boolean(busy)}>
                  {busy ? (
                    <LoaderCircle size={14} className="spin" />
                  ) : (
                    <ShieldCheck size={14} />
                  )}
                  Save & verify
                </button>
                <button
                  type="button"
                  className="button subtle"
                  disabled={Boolean(busy)}
                  onClick={(event) => save(event, false)}
                >
                  Save settings
                </button>
                {connector?.configured ? (
                  <button
                    type="button"
                    className="button ghost"
                    disabled={Boolean(busy)}
                    onClick={disconnect}
                  >
                    <Trash2 size={13} />
                    Remove private settings
                  </button>
                ) : null}
              </div>
              <p className="control-caption">
                Leave secret fields blank to preserve saved credentials. Only
                your unguessable workspace authorization token is stored in this
                browser.
              </p>
            </form>
          </section>
        </div>
      ) : null}
    </>
  );
}

type AdobeEvidence = {
  source: string;
  synthetic: boolean;
  status: string;
  detail?: string;
  rows: { item_id: string; label: string; values: Record<string, number> }[];
  totals: Record<string, number>;
  chart?: {
    type: "line" | "bar";
    title: string;
    x_key: string;
    y_keys: string[];
    data: Record<string, string | number | null>[];
  };
  provenance?: {
    fetched_at: string;
    endpoint: string;
    window: { start_date: string; end_date: string };
  };
  limitations?: string[];
};

export function ExternalEvidence({ filters }: { filters: Filters }) {
  const workspace = useWorkspace();
  const adobe = workspace.connectors.find(
    (connector) => connector.id === "adobe",
  );
  const mcp = workspace.connectors.find((connector) => connector.id === "mcp");
  const [adobeData, setAdobeData] = useState<AdobeEvidence | null>(null);
  const [remoteData, setRemoteData] = useState<unknown>(null);
  const [adobeMcpData, setAdobeMcpData] = useState<unknown>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  async function fetchEvidence(source: "adobe" | "mcp") {
    setBusy(source);
    setError(null);
    try {
      if (source === "adobe") {
        const dates = apiFilters(filters);
        const isMcp = adobe?.settings.transport === "mcp";
        const result = await apiFetch<AdobeEvidence>(
          isMcp ? "/workspace/adobe/mcp/report" : "/workspace/adobe/report",
          {
            method: "POST",
            body: JSON.stringify({
              start_date: dates.start_date,
              end_date: dates.end_date,
              limit: 50,
            }),
          },
          45_000,
        );
        if (isMcp) {
          setAdobeMcpData(result);
          setAdobeData(null);
        } else {
          setAdobeData(result);
          setAdobeMcpData(null);
        }
        workspace.refreshConnectors();
      } else {
        setRemoteData(
          await apiFetch(
            "/workspace/mcp/enrich",
            { method: "POST", body: "{}" },
            45_000,
          ),
        );
      }
    } catch (failure) {
      setError(
        failure instanceof Error
          ? failure.message
          : "External evidence could not be retrieved.",
      );
    } finally {
      setBusy(null);
    }
  }
  const chart: AnalystAnswer["chart"] = adobeData?.chart?.y_keys?.[0]
    ? { ...adobeData.chart, y_key: adobeData.chart.y_keys[0] }
    : null;
  return (
    <Panel className="external-evidence">
      <PanelHeading
        eyebrow="Authorized reference evidence"
        title="Bring the source into the discussion"
        description="External data stays visibly separate from uploaded and synthetic experiment outcomes."
      />
      <div className="panel-content">
        <div className="external-source-actions">
          <div>
            <strong>Adobe Analytics</strong>
            <p>
              {adobe?.configured
                ? "Fetch an actual report for the selected date window."
                : "Disconnected. Configure your authorized Adobe account in Data & connections."}
            </p>
          </div>
          <button
            className="button subtle"
            disabled={!adobe?.configured || Boolean(busy)}
            onClick={() => fetchEvidence("adobe")}
          >
            {busy === "adobe" ? (
              <LoaderCircle size={13} className="spin" />
            ) : (
              <Database size={13} />
            )}
            Fetch Adobe report
          </button>
        </div>
        <div className="external-source-actions">
          <div>
            <strong>Read-only MCP enrichment</strong>
            <p>
              {mcp?.configured
                ? `Configured tool: ${String(mcp.settings.tool_name || "none selected")}`
                : "Connect a real public MCP server and select a read-only tool."}
            </p>
          </div>
          <button
            className="button subtle"
            disabled={
              !mcp?.configured || !mcp.settings.tool_name || Boolean(busy)
            }
            onClick={() => fetchEvidence("mcp")}
          >
            {busy === "mcp" ? (
              <LoaderCircle size={13} className="spin" />
            ) : (
              <Plug size={13} />
            )}
            Fetch MCP evidence
          </button>
        </div>
        {error ? (
          <div className="inline-error" role="alert">
            <Info size={14} />
            {error}
          </div>
        ) : null}
        {adobeData ? (
          <div className="adobe-evidence-result">
            <div className="section-label">
              <h2>Adobe report evidence</h2>
              <Pill
                tone={
                  adobeData.status === "success" ||
                  adobeData.status === "verified"
                    ? "green"
                    : "amber"
                }
              >
                {adobeData.status}
              </Pill>
            </div>
            {adobeData.detail ? <p>{adobeData.detail}</p> : null}
            {adobeData.rows?.length ? (
              <>
                <div className="evidence-strip">
                  {Object.entries(adobeData.totals || {}).map(
                    ([metric, value]) => (
                      <div key={metric}>
                        <span>{metric}</span>
                        <strong>{formatNumber(value, 2)}</strong>
                      </div>
                    ),
                  )}
                </div>
                {chart ? <AnalystChart chart={chart} /> : null}
                <div className="table-wrap">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Dimension value</th>
                        {Object.keys(adobeData.rows[0].values).map((metric) => (
                          <th key={metric}>{metric}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {adobeData.rows.slice(0, 20).map((row) => (
                        <tr key={row.item_id}>
                          <td>{row.label}</td>
                          {Object.values(row.values).map((value, index) => (
                            <td key={index}>{formatNumber(value, 2)}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : (
              <EmptyState
                title="No Adobe rows returned"
                description={
                  adobeData.detail ||
                  "Review report permissions, date range, and configured dimensions."
                }
              />
            )}
            {adobeData.provenance ? (
              <p className="control-caption">
                Actual Adobe API · fetched{" "}
                {new Date(adobeData.provenance.fetched_at).toLocaleString()} ·{" "}
                {adobeData.provenance.endpoint}
              </p>
            ) : null}
            {adobeData.limitations?.map((limitation) => (
              <p className="control-caption" key={limitation}>
                {limitation}
              </p>
            ))}
          </div>
        ) : null}
        {adobeMcpData ? (
          <details className="remote-evidence" open>
            <summary>
              Actual Adobe MCP report response · source-linked evidence
            </summary>
            <div className="code-box">
              {JSON.stringify(adobeMcpData, null, 2)}
            </div>
            <p className="control-caption">
              Remote tool content is shown as returned. A chart is only
              available when the adapter returns validated numeric data.
            </p>
          </details>
        ) : null}
        {remoteData ? (
          <details className="remote-evidence" open>
            <summary>Actual MCP response · unmerged reference evidence</summary>
            <div className="code-box">
              {JSON.stringify(remoteData, null, 2)}
            </div>
          </details>
        ) : null}
      </div>
    </Panel>
  );
}
