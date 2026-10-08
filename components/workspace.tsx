"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { ensureWorkspace, invalidateApiCache, useApi } from "@/lib/api";
import type {
  ModelsData,
  UploadDataset,
  WorkspaceConnector,
} from "@/lib/types";

type WorkspaceContextValue = {
  ready: boolean;
  error: string | null;
  retryWorkspace: () => void;
  datasets: UploadDataset[];
  datasetsLoading: boolean;
  datasetsError: string | null;
  datasetId: string | null;
  dataset: UploadDataset | null;
  selectDataset: (id: string | null) => void;
  connectors: WorkspaceConnector[];
  connectorsLoading: boolean;
  connectorsError: string | null;
  models: ModelsData | null;
  modelsLoading: boolean;
  modelsError: string | null;
  refreshDatasets: () => void;
  refreshConnectors: () => void;
  refreshModels: () => void;
  uploadOpen: boolean;
  openUploads: () => void;
  closeUploads: () => void;
};
const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const [datasetId, setDatasetId] = useState<string | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  useEffect(() => {
    let mounted = true;
    setError(null);
    ensureWorkspace()
      .then(() => {
        if (mounted) setReady(true);
      })
      .catch((failure) => {
        if (mounted) setError(failure.message);
      });
    return () => {
      mounted = false;
    };
  }, [revision]);
  const uploads = useApi<{ datasets: UploadDataset[] }>(
    "/uploads",
    undefined,
    ready,
  );
  const connections = useApi<{ connectors: WorkspaceConnector[] }>(
    "/workspace/connectors",
    undefined,
    ready,
  );
  const modelCatalog = useApi<ModelsData>("/ai/models", undefined, ready);
  const datasets = uploads.data?.datasets || [];
  const dataset =
    datasets.find((item) => item.dataset_id === datasetId) || null;
  return (
    <WorkspaceContext.Provider
      value={{
        ready,
        error,
        retryWorkspace: () => setRevision((value) => value + 1),
        datasets,
        datasetsLoading: uploads.loading,
        datasetsError: uploads.error,
        datasetId,
        dataset,
        selectDataset: setDatasetId,
        connectors: connections.data?.connectors || [],
        connectorsLoading: connections.loading,
        connectorsError: connections.error,
        models: modelCatalog.data,
        modelsLoading: modelCatalog.loading,
        modelsError: modelCatalog.error,
        refreshDatasets: () => {
          invalidateApiCache("/uploads");
          uploads.retry();
        },
        refreshConnectors: () => {
          invalidateApiCache("/workspace/connectors");
          connections.retry();
          modelCatalog.retry();
        },
        refreshModels: modelCatalog.retry,
        uploadOpen,
        openUploads: () => setUploadOpen(true),
        closeUploads: () => setUploadOpen(false),
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspace() {
  const context = useContext(WorkspaceContext);
  if (!context)
    throw new Error(
      "Workspace controls must be inside the workspace provider.",
    );
  return context;
}

export function ModelPicker({
  provider,
  purpose,
  value,
  onChange,
  label,
}: {
  provider: string;
  purpose: "search" | "analyst" | "ingestion";
  value: string;
  onChange: (value: string) => void;
  label?: string;
}) {
  const workspace = useWorkspace();
  const catalog =
    workspace.models?.catalog?.filter(
      (item) =>
        item.provider === provider &&
        (purpose !== "ingestion" ||
          item.id.startsWith("gemma4:31b") ||
          item.id.startsWith("gpt-oss:120b")),
    ) || [];
  const configuredDefault =
    purpose === "search"
      ? workspace.models?.defaults?.search[provider as "openrouter" | "ollama"]
      : purpose === "ingestion"
        ? workspace.models?.defaults?.ingestion.model
        : workspace.models?.providers.find((item) => item.id === provider)
            ?.model;
  const selected = value || configuredDefault || "";
  return (
    <label className="model-picker">
      <span>
        {label ||
          (provider === "ollama" ? "Ollama Cloud model" : "OpenRouter model")}
      </span>
      <select
        aria-label={label || `${provider} ${purpose} model`}
        value={selected}
        onChange={(event) => onChange(event.target.value)}
        disabled={workspace.modelsLoading && !workspace.models}
      >
        {!selected && !catalog.length ? (
          <option value="">Loading model catalog…</option>
        ) : null}
        {selected && !catalog.some((item) => item.id === selected) ? (
          <option value={selected}>{selected} · configured default</option>
        ) : null}
        {catalog.map((item) => (
          <option key={item.id} value={item.id}>
            {item.label || item.id}
            {item.available ? "" : " · availability unverified"}
          </option>
        ))}
      </select>
      {workspace.modelsError ? (
        <small>
          Catalog unavailable. Configured defaults remain selectable.
        </small>
      ) : null}
    </label>
  );
}
