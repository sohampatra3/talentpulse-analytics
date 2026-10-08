"use client";

import { useEffect, useState } from "react";

export type Filters = {
  days: string;
  market: string;
  device: string;
  user_type: string;
  dataset_id?: string;
  range_start?: string;
  range_end?: string;
};
export const DEFAULT_FILTERS: Filters = {
  days: "28",
  market: "all",
  device: "all",
  user_type: "all",
};

export function filterQuery(filters: Filters) {
  return new URLSearchParams({
    ...apiFilters(filters),
    ...(filters.dataset_id ? { dataset_id: filters.dataset_id } : {}),
  }).toString();
}

export function apiFilters(filters: Filters) {
  const end = new Date(`${filters.range_end || "2026-10-04"}T12:00:00Z`);
  const start = new Date(end);
  start.setUTCDate(end.getUTCDate() - Number(filters.days) + 1);
  const startDate = start.toISOString().slice(0, 10);
  return {
    start_date:
      filters.range_start && startDate < filters.range_start
        ? filters.range_start
        : startDate,
    end_date: end.toISOString().slice(0, 10),
    market: filters.market === "all" ? "All" : filters.market,
    device_type: filters.device === "all" ? "All" : filters.device,
    user_type: filters.user_type === "all" ? "All" : filters.user_type,
  };
}

let workspaceMemory: string | null = null;
let workspaceCreation: Promise<string> | null = null;
export function workspaceToken() {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem("talentpulse.workspace.v1") || workspaceMemory;
  } catch {
    return workspaceMemory;
  }
}

export async function ensureWorkspace(): Promise<string> {
  const existing = workspaceToken();
  if (existing) return existing;
  if (!workspaceCreation) {
    workspaceCreation = apiFetch<{ workspace_token: string }>("/workspaces", {
      method: "POST",
      body: "{}",
    })
      .then(({ workspace_token }) => {
        workspaceMemory = workspace_token;
        try {
          localStorage.setItem("talentpulse.workspace.v1", workspace_token);
        } catch {}
        return workspace_token;
      })
      .finally(() => {
        workspaceCreation = null;
      });
  }
  return workspaceCreation;
}

export async function apiFetch<T>(
  path: string,
  options?: RequestInit,
  timeoutMs = 25_000,
): Promise<T> {
  if (
    (path.startsWith("/workspace/") || path.startsWith("/uploads")) &&
    !workspaceToken()
  )
    await ensureWorkspace();
  const controller = new AbortController();
  const abort = () => controller.abort();
  let timedOut = false;
  if (options?.signal?.aborted) controller.abort();
  options?.signal?.addEventListener("abort", abort, { once: true });
  const timer = window.setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  const headers = new Headers(options?.headers);
  if (!(options?.body instanceof FormData) && !headers.has("Content-Type"))
    headers.set("Content-Type", "application/json");
  const token = workspaceToken();
  if (token) headers.set("X-Workspace-Token", token);
  try {
    const response = await fetch(`/api${path}`, {
      ...options,
      signal: controller.signal,
      headers,
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      const detail = data?.detail;
      throw new Error(
        typeof detail === "string"
          ? detail
          : data?.error ||
              `The data service returned ${response.status}. Please try again.`,
      );
    }
    return data as T;
  } catch (error) {
    if (timedOut)
      throw new Error(
        `This request exceeded ${Math.round(timeoutMs / 1000)} seconds. Your workspace remains available; retry when ready.`,
      );
    throw error;
  } finally {
    window.clearTimeout(timer);
    options?.signal?.removeEventListener("abort", abort);
  }
}

const responseCache = new Map<string, { value: unknown; updatedAt: number }>();
export function invalidateApiCache(prefix = "") {
  for (const key of responseCache.keys())
    if (!prefix || key.includes(prefix)) responseCache.delete(key);
  if (typeof window !== "undefined")
    window.dispatchEvent(
      new CustomEvent("talentpulse:invalidate", { detail: { prefix } }),
    );
}

export function useApi<T>(path: string, filters?: Filters, enabled = true) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<number | null>(null);
  const [revision, setRevision] = useState(0);
  const query = filters ? filterQuery(filters) : "";
  useEffect(() => {
    const invalidate = (event: Event) => {
      const prefix = (event as CustomEvent<{ prefix: string }>).detail.prefix;
      if (!prefix || path.includes(prefix)) setRevision((value) => value + 1);
    };
    window.addEventListener("talentpulse:invalidate", invalidate);
    return () =>
      window.removeEventListener("talentpulse:invalidate", invalidate);
  }, [path]);
  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }
    const requestPath = `${path}${query ? `${path.includes("?") ? "&" : "?"}${query}` : ""}`;
    const key = `${workspaceToken() || "public"}:${requestPath}`;
    const cached = responseCache.get(key);
    const controller = new AbortController();
    setData(cached ? (cached.value as T) : null);
    setLastUpdated(cached?.updatedAt || null);
    setLoading(!cached);
    setRefreshing(Boolean(cached));
    setError(null);
    apiFetch<T>(requestPath, { signal: controller.signal })
      .then((result) => {
        if (controller.signal.aborted) return;
        const updatedAt = Date.now();
        responseCache.set(key, { value: result, updatedAt });
        if (responseCache.size > 64)
          responseCache.delete(responseCache.keys().next().value!);
        setData(result);
        setLastUpdated(updatedAt);
        setLoading(false);
        setRefreshing(false);
      })
      .catch((failure: Error) => {
        if (!controller.signal.aborted) {
          setError(failure.message);
          setLoading(false);
          setRefreshing(false);
        }
      });
    return () => controller.abort();
  }, [path, query, revision, enabled]);
  return {
    data,
    loading,
    refreshing,
    error,
    lastUpdated,
    retry: () => setRevision((value) => value + 1),
  };
}

export async function downloadApi(path: string, filename: string) {
  const token = await ensureWorkspace();
  const response = await fetch(path.startsWith("/api") ? path : `/api${path}`, {
    headers: { "X-Workspace-Token": token },
    signal: AbortSignal.timeout(45_000),
  });
  if (!response.ok)
    throw new Error(
      `The export returned ${response.status}. Please try again.`,
    );
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.style.display = "none";
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

export function downloadText(
  content: string,
  filename: string,
  mime = "text/plain",
) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.style.display = "none";
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

export function formatNumber(
  value: number | null | undefined,
  maximumFractionDigits = 0,
) {
  if (value === null || value === undefined || !Number.isFinite(value))
    return "—";
  return new Intl.NumberFormat("en-GB", { maximumFractionDigits }).format(
    value,
  );
}

export function formatPercent(value: number | null | undefined, decimals = 1) {
  return value === null || value === undefined
    ? "—"
    : `${value.toFixed(decimals)}%`;
}

export function formatDate(value: string, compact = false) {
  return new Date(`${value.slice(0, 10)}T12:00:00`).toLocaleDateString(
    "en-GB",
    { day: "numeric", month: compact ? "short" : "long" },
  );
}
