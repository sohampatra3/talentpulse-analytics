"use client";

import { useEffect, useRef, useState } from "react";
import {
  ArrowUpRight,
  Check,
  Database,
  Download,
  FileSpreadsheet,
  Info,
  LoaderCircle,
  Search,
  Trash2,
  UploadCloud,
  X,
} from "lucide-react";
import {
  apiFetch,
  downloadApi,
  formatNumber,
  invalidateApiCache,
  useApi,
} from "@/lib/api";
import type { UploadDataset } from "@/lib/types";
import { EmptyState, Pill } from "./ui";
import { ModelPicker, useWorkspace } from "./workspace";

type UploadSchema = {
  mapping_fields: string[];
  kinds: string[];
  model_choices: string[];
};
const displayValue = (value: unknown) =>
  value === null || value === undefined
    ? "—"
    : typeof value === "object"
      ? JSON.stringify(value)
      : String(value);

export function UploadsDialog() {
  const workspace = useWorkspace();
  const schema = useApi<UploadSchema>(
    "/uploads/schema",
    undefined,
    workspace.uploadOpen && workspace.ready,
  );
  const [file, setFile] = useState<File | null>(null);
  const [kind, setKind] = useState("auto");
  const [model, setModel] = useState("");
  const [search, setSearch] = useState("");
  const [detail, setDetail] = useState<UploadDataset | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [rowQuery, setRowQuery] = useState("");
  const [rowTotal, setRowTotal] = useState<number | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (!workspace.uploadOpen) return;
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") workspace.closeUploads();
    };
    document.addEventListener("keydown", close);
    return () => document.removeEventListener("keydown", close);
  }, [workspace.uploadOpen, workspace.closeUploads]);
  async function openDataset(dataset: UploadDataset) {
    setBusy("preview");
    setError(null);
    setFeedback("");
    try {
      const result = await apiFetch<UploadDataset>(
        `/uploads/${dataset.dataset_id}`,
      );
      setDetail(result);
      setMapping(result.mapping || {});
      setRows(result.preview || []);
      setRowQuery("");
      setRowTotal(null);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Preview failed.");
    } finally {
      setBusy(null);
    }
  }
  async function upload(event: React.FormEvent) {
    event.preventDefault();
    if (!file || busy) return;
    setBusy("upload");
    setError(null);
    setFeedback("");
    try {
      if (file.size > 3 * 1024 * 1024)
        throw new Error("Choose a CSV or XLSX file smaller than 3 MB.");
      if (!/\.(csv|xlsx)$/i.test(file.name))
        throw new Error(
          "Use a CSV or XLSX workbook. Older XLS files should be saved as XLSX first.",
        );
      const form = new FormData();
      form.append("file", file);
      form.append("kind", kind);
      form.append(
        "ingestion_model",
        model || workspace.models?.defaults?.ingestion.model || "gemma4:31b",
      );
      const result = await apiFetch<UploadDataset>(
        "/uploads",
        { method: "POST", body: form },
        45_000,
      );
      setDetail(result);
      setMapping(result.mapping || {});
      setRows(result.preview || []);
      setRowQuery("");
      setRowTotal(null);
      setFeedback(
        "Uploaded to your private workspace. Review the mapping before analyzing.",
      );
      workspace.refreshDatasets();
      setFile(null);
      if (inputRef.current) inputRef.current.value = "";
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Upload failed.");
    } finally {
      setBusy(null);
    }
  }
  async function saveMapping() {
    if (!detail) return;
    setBusy("mapping");
    setError(null);
    setFeedback("");
    try {
      const result = await apiFetch<UploadDataset>(
        `/uploads/${detail.dataset_id}/mapping`,
        {
          method: "PATCH",
          body: JSON.stringify({
            kind: detail.kind,
            mapping: Object.fromEntries(
              Object.entries(mapping).filter(([, value]) => value),
            ),
          }),
        },
      );
      setDetail(result);
      setMapping(result.mapping);
      setRows(result.preview || []);
      workspace.refreshDatasets();
      invalidateApiCache();
      setFeedback(
        "Mapping saved. Readiness has been recalculated from your actual columns.",
      );
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Mapping failed.");
    } finally {
      setBusy(null);
    }
  }
  async function searchRows(event: React.FormEvent) {
    event.preventDefault();
    if (!detail) return;
    setBusy("search");
    setError(null);
    try {
      const result = await apiFetch<{
        rows: { row_number: number; data: Record<string, unknown> }[];
        total: number;
      }>(
        `/uploads/${detail.dataset_id}/search?q=${encodeURIComponent(rowQuery)}`,
      );
      setRows(result.rows.map((item) => item.data));
      setRowTotal(result.total);
    } catch (failure) {
      setError(
        failure instanceof Error ? failure.message : "Row search failed.",
      );
    } finally {
      setBusy(null);
    }
  }
  async function removeDataset() {
    if (!detail) return;
    setBusy("delete");
    setError(null);
    try {
      await apiFetch(`/uploads/${detail.dataset_id}`, { method: "DELETE" });
      if (workspace.datasetId === detail.dataset_id)
        workspace.selectDataset(null);
      setDetail(null);
      workspace.refreshDatasets();
      setFeedback("Dataset removed from this workspace.");
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Delete failed.");
    } finally {
      setBusy(null);
    }
  }
  async function exportDataset() {
    if (!detail) return;
    try {
      await downloadApi(
        `/uploads/${detail.dataset_id}/export`,
        `${detail.name.replace(/\.[^.]+$/, "")}.csv`,
      );
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Export failed.");
    }
  }
  if (!workspace.uploadOpen) return null;
  const matching = workspace.datasets.filter((dataset) =>
    dataset.name.toLowerCase().includes(search.toLowerCase()),
  );
  const fields = schema.data?.mapping_fields || Object.keys(mapping);
  return (
    <div className="modal-backdrop" onClick={workspace.closeUploads}>
      <section
        className="modal upload-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="upload-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="upload-modal-heading">
          <div>
            <div className="eyebrow">Browser-private workspace</div>
            <h2 id="upload-title">Bring your own evidence</h2>
            <p>
              Upload CSV or Excel data, review its meaning, and choose which
              dataset powers your analysis.
            </p>
          </div>
          <button
            className="icon-button"
            aria-label="Close uploads"
            onClick={workspace.closeUploads}
            autoFocus
          >
            <X size={16} />
          </button>
        </div>
        <div className="upload-workspace">
          <aside className="upload-library">
            <div className="upload-library-heading">
              <h3>Your datasets</h3>
              <Pill>{workspace.datasets.length}</Pill>
            </div>
            <label className="search-field">
              <Search size={14} />
              <input
                aria-label="Search uploaded datasets"
                placeholder="Search uploads…"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
            </label>
            <button
              className={`dataset-list-item ${!workspace.datasetId ? "selected" : ""}`}
              onClick={() => {
                workspace.selectDataset(null);
                workspace.closeUploads();
              }}
            >
              <Database size={18} />
              <span>
                <strong>Synthetic product telemetry</strong>
                <small>Reproducible portfolio dataset</small>
              </span>
            </button>
            {workspace.datasetsLoading ? (
              <div className="small muted">
                <LoaderCircle size={13} className="spin" /> Loading uploads…
              </div>
            ) : null}
            {workspace.datasetsError ? (
              <div className="inline-error">
                {workspace.datasetsError}
                <button
                  className="text-link"
                  onClick={workspace.refreshDatasets}
                >
                  Retry
                </button>
              </div>
            ) : null}
            {matching.map((dataset) => (
              <button
                className={`dataset-list-item ${detail?.dataset_id === dataset.dataset_id ? "selected" : ""}`}
                key={dataset.dataset_id}
                onClick={() => openDataset(dataset)}
                disabled={busy === "preview"}
              >
                <FileSpreadsheet size={18} />
                <span>
                  <strong>{dataset.name}</strong>
                  <small>
                    {formatNumber(dataset.row_count)} rows ·{" "}
                    {dataset.kind.replaceAll("_", " ")}
                  </small>
                </span>
                {workspace.datasetId === dataset.dataset_id ? (
                  <Check size={14} />
                ) : null}
              </button>
            ))}
            {!matching.length && !workspace.datasetsLoading ? (
              <p className="control-caption">
                {search
                  ? "No uploads match this name."
                  : "Your private uploads will appear here."}
              </p>
            ) : null}
          </aside>
          <div className="upload-detail">
            <form className="upload-form" onSubmit={upload}>
              <label className="upload-dropzone" htmlFor="workspace-file">
                <UploadCloud size={25} />
                <strong>
                  {file ? file.name : "Choose a CSV or Excel workbook"}
                </strong>
                <span>
                  CSV / XLSX · 3 MB · up to 10,000 rows and 20 columns
                </span>
                <input
                  id="workspace-file"
                  ref={inputRef}
                  type="file"
                  accept=".csv,.xlsx"
                  onChange={(event) => {
                    setFile(event.target.files?.[0] || null);
                    setError(null);
                  }}
                />
              </label>
              <div className="upload-form-options">
                <label className="model-picker">
                  <span>Dataset structure</span>
                  <select
                    aria-label="Dataset structure"
                    value={kind}
                    onChange={(event) => setKind(event.target.value)}
                  >
                    {(
                      schema.data?.kinds || [
                        "auto",
                        "jobs",
                        "sessions",
                        "events",
                        "experiment_summary",
                      ]
                    ).map((value) => (
                      <option key={value} value={value}>
                        {value === "auto"
                          ? "Detect from columns"
                          : value.replaceAll("_", " ")}
                      </option>
                    ))}
                  </select>
                </label>
                <ModelPicker
                  provider="ollama"
                  purpose="ingestion"
                  value={model}
                  onChange={setModel}
                  label="Meaning-layer model"
                />
                <button
                  className="button primary"
                  disabled={!file || Boolean(busy) || !workspace.ready}
                >
                  {busy === "upload" ? (
                    <LoaderCircle size={14} className="spin" />
                  ) : (
                    <UploadCloud size={14} />
                  )}
                  {busy === "upload"
                    ? "Reading your data…"
                    : "Upload & inspect"}
                </button>
              </div>
              <p className="control-caption">
                Column mapping and numeric summaries come from the file. The
                selected cloud model receives column names and up to three
                preview rows to describe meaning; it cannot invent missing
                outcomes.
              </p>
            </form>
            {workspace.error ? (
              <div className="inline-error">
                {workspace.error}
                <button
                  className="text-link"
                  onClick={workspace.retryWorkspace}
                >
                  Retry workspace
                </button>
              </div>
            ) : null}
            {error ? (
              <div className="inline-error" role="alert">
                <Info size={14} />
                {error}
              </div>
            ) : null}
            {feedback ? (
              <div className="action-feedback" role="status">
                <Check size={14} />
                {feedback}
              </div>
            ) : null}
            {busy === "preview" ? (
              <div className="empty-state">
                <LoaderCircle className="spin" size={22} />
              </div>
            ) : detail ? (
              <>
                <div className="dataset-detail-heading">
                  <div>
                    <h3>{detail.name}</h3>
                    <p>
                      {formatNumber(detail.row_count)} rows ·{" "}
                      {detail.column_count} columns ·{" "}
                      {detail.kind.replaceAll("_", " ")}
                    </p>
                  </div>
                  <div className="button-row">
                    <button
                      className="button subtle small-button"
                      onClick={exportDataset}
                    >
                      <Download size={12} /> Export
                    </button>
                    <button
                      className="button subtle small-button"
                      onClick={removeDataset}
                      disabled={Boolean(busy)}
                      aria-label={`Delete ${detail.name}`}
                    >
                      <Trash2 size={12} />
                    </button>
                    <button
                      className="button primary small-button"
                      onClick={() => {
                        workspace.selectDataset(detail.dataset_id);
                        workspace.closeUploads();
                      }}
                    >
                      Use dataset <ArrowUpRight size={12} />
                    </button>
                  </div>
                </div>
                <div className="dataset-readiness">
                  <h4>What this data can support</h4>
                  <div className="readiness-pills">
                    {Object.entries(detail.readiness || {}).map(
                      ([capability, ready]) => (
                        <Pill
                          tone={ready ? "green" : "neutral"}
                          key={capability}
                        >
                          {ready ? <Check size={10} /> : <Info size={10} />}
                          {capability.replaceAll("_", " ")}
                        </Pill>
                      ),
                    )}
                  </div>
                  {Object.entries(detail.reasons || {}).map(([key, reason]) => (
                    <p key={key}>
                      <strong>{key.replaceAll("_", " ")}:</strong> {reason}
                    </p>
                  ))}
                </div>
                {detail.warnings?.length ? (
                  <div className="inline-error">
                    <Info size={14} />
                    <div>
                      {detail.warnings.map((warning) => (
                        <p key={warning}>{warning}</p>
                      ))}
                    </div>
                  </div>
                ) : null}
                <details className="mapping-editor" open>
                  <summary>
                    Review the column mapping{" "}
                    <span className="muted">
                      {Object.values(mapping).filter(Boolean).length} mapped
                      fields
                    </span>
                  </summary>
                  <div className="mapping-grid">
                    {fields.map((field) => (
                      <label key={field}>
                        <span>{field.replaceAll("_", " ")}</span>
                        <select
                          aria-label={`Map ${field}`}
                          value={mapping[field] || ""}
                          onChange={(event) =>
                            setMapping((previous) => ({
                              ...previous,
                              [field]: event.target.value,
                            }))
                          }
                        >
                          <option value="">Not supplied</option>
                          {detail.columns.map((column) => (
                            <option key={column} value={column}>
                              {column}
                            </option>
                          ))}
                        </select>
                      </label>
                    ))}
                  </div>
                  <button
                    className="button subtle small-button"
                    onClick={saveMapping}
                    disabled={Boolean(busy)}
                  >
                    {busy === "mapping" ? (
                      <LoaderCircle size={12} className="spin" />
                    ) : (
                      <Check size={12} />
                    )}
                    Save mapping & recheck
                  </button>
                </details>
                {detail.semantic_metadata &&
                Object.keys(detail.semantic_metadata).length ? (
                  <details className="meaning-layer">
                    <summary>Meaning layer & provenance</summary>
                    <div className="code-box">
                      {JSON.stringify(detail.semantic_metadata, null, 2)}
                    </div>
                  </details>
                ) : null}
                <div className="preview-heading">
                  <h4>Preview the actual rows</h4>
                  <span>
                    {rowTotal === null
                      ? "First 50 rows"
                      : `${formatNumber(rowTotal)} matching rows`}
                  </span>
                </div>
                <form className="row-search" onSubmit={searchRows}>
                  <input
                    className="field-input"
                    aria-label="Search within this dataset"
                    value={rowQuery}
                    onChange={(event) => setRowQuery(event.target.value)}
                    placeholder="Search roles, markets, values…"
                  />
                  <button
                    className="button subtle small-button"
                    disabled={Boolean(busy)}
                  >
                    <Search size={13} />
                    Search rows
                  </button>
                </form>
                {rows.length ? (
                  <div className="table-wrap upload-preview">
                    <table className="data-table">
                      <thead>
                        <tr>
                          {detail.columns.map((column) => (
                            <th key={column}>{column}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {rows.slice(0, 50).map((row, index) => (
                          <tr key={index}>
                            {detail.columns.map((column) => (
                              <td key={column}>{displayValue(row[column])}</td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <EmptyState
                    title="No matching rows"
                    description="Try a different search, or review the uploaded columns."
                  />
                )}
              </>
            ) : (
              <EmptyState
                title="Your evidence, your workspace"
                description="Upload a file or select one from your library to inspect its actual rows and measurement readiness."
              />
            )}
          </div>
        </div>
      </section>
    </div>
  );
}

export function DatasetReadiness({
  view,
  onOpen,
}: {
  view: string;
  onOpen: () => void;
}) {
  const { dataset } = useWorkspace();
  return (
    <section className="panel readiness-empty">
      <FileSpreadsheet size={28} />
      <h2>This dataset needs more evidence for {view}</h2>
      <p>
        {dataset?.reasons?.[view] ||
          "The mapped columns do not support this analysis. Explore the available views or review the column mapping."}
      </p>
      <div className="readiness-pills">
        {Object.entries(dataset?.readiness || {})
          .filter(([, ready]) => ready)
          .map(([key]) => (
            <Pill key={key} tone="green">
              <Check size={11} />
              {key.replaceAll("_", " ")}
            </Pill>
          ))}
      </div>
      <button className="button primary" onClick={onOpen}>
        Review uploaded data <ArrowUpRight size={13} />
      </button>
      <span className="control-caption">
        Missing metrics remain unavailable. Job catalog rows do not imply
        candidate conversions.
      </span>
    </section>
  );
}
