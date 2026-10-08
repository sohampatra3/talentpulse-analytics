"use client";

import {
  AlertCircle,
  ArrowDown,
  ArrowUp,
  ArrowUpRight,
  Check,
  Download,
  LoaderCircle,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import { useState, type CSSProperties, type ReactNode } from "react";
import { downloadApi, formatNumber } from "@/lib/api";

export function Pill({
  children,
  tone = "neutral",
  dot = false,
}: {
  children: ReactNode;
  tone?: "neutral" | "green" | "amber" | "blue" | "purple";
  dot?: boolean;
}) {
  return (
    <span className={`pill pill-${tone}`}>
      {dot ? <span className="status-dot" /> : null}
      {children}
    </span>
  );
}

export function Panel({
  children,
  className = "",
  style,
}: {
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <section className={`panel ${className}`} style={style}>
      {children}
    </section>
  );
}

export function PanelHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="panel-heading">
      <div>
        {eyebrow ? <div className="eyebrow">{eyebrow}</div> : null}
        <h2>{title}</h2>
        {description ? <p>{description}</p> : null}
      </div>
      {action}
    </div>
  );
}

export function Metric({
  label,
  value,
  unit,
  delta,
  note,
  icon,
  lowerIsBetter = false,
}: {
  label: string;
  value: number | string | null | undefined;
  unit?: string;
  delta?: number | null;
  note?: string;
  icon?: ReactNode;
  lowerIsBetter?: boolean;
}) {
  const display =
    typeof value === "number"
      ? unit === "%"
        ? value.toFixed(1)
        : formatNumber(value, unit === "$" || unit === "€" ? 2 : 0)
      : (value ?? "—");
  return (
    <Panel className="metric-card">
      <div className="metric-top">
        <span>{label}</span>
        <span className="metric-icon">
          {icon || <ArrowUpRight size={16} />}
        </span>
      </div>
      <div className="metric-value">
        {unit === "$" || unit === "€" ? (
          <span className="metric-unit">{unit}</span>
        ) : null}
        {display}
        {unit && unit !== "$" && unit !== "€" ? (
          <span className="metric-unit">{unit}</span>
        ) : null}
      </div>
      <div className="metric-bottom">
        {delta !== null && delta !== undefined ? (
          <span
            className={`metric-change ${(lowerIsBetter ? delta <= 0 : delta >= 0) ? "positive" : "negative"}`}
          >
            {delta >= 0 ? <ArrowUp size={12} /> : <ArrowDown size={12} />}
            {Math.abs(delta).toFixed(1)}
            {unit === "%" ? " pp" : unit === "ms" ? " ms" : "%"}
          </span>
        ) : null}
        <span>
          {note ??
            (delta === null || delta === undefined
              ? "Comparison unavailable"
              : "vs. previous period")}
        </span>
      </div>
    </Panel>
  );
}

export function LoadingState() {
  return (
    <div className="loading-state" aria-live="polite">
      <div className="skeleton hero-skeleton" />
      <div className="metrics-grid">
        {Array.from({ length: 4 }, (_, index) => (
          <div className="skeleton metric-skeleton" key={index} />
        ))}
      </div>
      <div className="skeleton chart-skeleton" />
      <span className="loading-copy">
        <LoaderCircle className="spin" size={16} /> Loading your analytics
        workspace…
      </span>
    </div>
  );
}

export function ErrorState({
  message,
  retry,
}: {
  message: string;
  retry: () => void;
}) {
  return (
    <Panel className="error-state">
      <div className="error-icon">
        <AlertCircle size={26} />
      </div>
      <h2>We couldn’t load this view</h2>
      <p>{message}</p>
      <button className="button primary" onClick={retry}>
        <RefreshCw size={15} /> Try again
      </button>
      <span className="small muted">Your filters are preserved.</span>
    </Panel>
  );
}

export function EmptyState({
  title = "No data in this selection",
  description = "Try a wider date range or another segment.",
}: {
  title?: string;
  description?: string;
}) {
  return (
    <div className="empty-state">
      <div className="empty-icon">
        <Sparkles size={22} />
      </div>
      <h3>{title}</h3>
      <p>{description}</p>
    </div>
  );
}

export function ExportButton({
  url,
  label = "Export data",
  authenticated = false,
}: {
  url: string;
  label?: string;
  authenticated?: boolean;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function download() {
    setBusy(true);
    setError(null);
    try {
      await downloadApi(url, "talentpulse-upload.csv");
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Export failed.");
    } finally {
      setBusy(false);
    }
  }
  if (authenticated)
    return (
      <span className="export-button-wrap">
        <button className="button subtle" onClick={download} disabled={busy}>
          {busy ? (
            <LoaderCircle size={15} className="spin" />
          ) : (
            <Download size={15} />
          )}
          <span>{label}</span>
        </button>
        {error ? (
          <span className="small muted" role="alert">
            {error}
          </span>
        ) : null}
      </span>
    );
  return (
    <a href={url} className="button subtle" download>
      <Download size={15} />
      <span>{label}</span>
    </a>
  );
}

export function ActionFeedback({ children }: { children: ReactNode }) {
  return (
    <div className="action-feedback" role="status">
      <Check size={14} />
      {children}
    </div>
  );
}

export function Note({ children }: { children: ReactNode }) {
  return (
    <div className="data-note">
      <span className="note-dot" />
      {children}
    </div>
  );
}

export function RequestStatus({
  refreshing,
  error,
  retry,
  lastUpdated,
}: {
  refreshing: boolean;
  error: string | null;
  retry: () => void;
  lastUpdated?: number | null;
}) {
  if (!refreshing && !error) return null;
  return (
    <div
      className={`request-status ${error ? "request-stale" : ""}`}
      role="status"
    >
      {refreshing ? (
        <LoaderCircle size={14} className="spin" />
      ) : (
        <AlertCircle size={14} />
      )}
      <span>
        {error
          ? `Showing the last available evidence${lastUpdated ? ` from ${new Date(lastUpdated).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}` : ""}. ${error}`
          : "Refreshing the saved evidence for this selection…"}
      </span>
      {error ? (
        <button className="text-link" onClick={retry}>
          <RefreshCw size={12} />
          Retry now
        </button>
      ) : null}
    </div>
  );
}
