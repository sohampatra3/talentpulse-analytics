"use client";

import { useEffect, useState } from "react";

export type Filters = {
  days: string;
  market: string;
  device: string;
  user_type: string;
};
export const DEFAULT_FILTERS: Filters = {
  days: "28",
  market: "all",
  device: "all",
  user_type: "all",
};

export function filterQuery(filters: Filters) {
  return new URLSearchParams(apiFilters(filters)).toString();
}

export function apiFilters(filters: Filters) {
  const end = new Date("2026-10-04T12:00:00Z");
  const start = new Date(end);
  start.setUTCDate(end.getUTCDate() - Number(filters.days) + 1);
  return {
    start_date: start.toISOString().slice(0, 10),
    end_date: "2026-10-04",
    market: filters.market === "all" ? "All" : filters.market,
    device_type: filters.device === "all" ? "All" : filters.device,
    user_type: filters.user_type === "all" ? "All" : filters.user_type,
  };
}

export async function apiFetch<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
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
}

export function useApi<T>(path: string, filters?: Filters) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const query = filters ? filterQuery(filters) : "";
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    apiFetch<T>(
      `${path}${query ? `${path.includes("?") ? "&" : "?"}${query}` : ""}`,
      { signal: controller.signal },
    )
      .then((result) => {
        setData(result);
        setLoading(false);
      })
      .catch((failure: Error) => {
        if (failure.name !== "AbortError") {
          setError(failure.message);
          setLoading(false);
        }
      });
    return () => controller.abort();
  }, [path, query, revision]);
  return {
    data,
    loading,
    error,
    retry: () => setRevision((value) => value + 1),
  };
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
