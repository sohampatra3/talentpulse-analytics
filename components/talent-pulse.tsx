"use client";

import { useEffect, useState } from "react";
import {
  BarChart3,
  CalendarDays,
  ChevronDown,
  ChevronRight,
  Database,
  Download,
  FlaskConical,
  Globe2,
  LayoutDashboard,
  Menu,
  Moon,
  MonitorSmartphone,
  Plug,
  Rocket,
  ShieldCheck,
  Sparkles,
  Sun,
  Users,
} from "lucide-react";
import {
  apiFilters,
  DEFAULT_FILTERS,
  filterQuery,
  formatDate,
  useApi,
  type Filters,
} from "@/lib/api";
import type { FilterOptions } from "@/lib/types";
import {
  AnalystView,
  ConnectionsView,
  ExperimentsView,
  FunnelView,
  OverviewView,
  ReleasesView,
  type ViewName,
} from "./views";
import { Pill } from "./ui";

const NAVIGATION = [
  {
    id: "overview" as const,
    label: "Overview",
    icon: LayoutDashboard,
    title: "Product overview",
    description:
      "A clearer picture of the candidate experience. Every signal, in one place.",
  },
  {
    id: "experiments" as const,
    label: "Search experiments",
    icon: FlaskConical,
    title: "Search experiments",
    description: "Turn AI search hypotheses into measurable product decisions.",
  },
  {
    id: "funnel" as const,
    label: "Funnel & segments",
    icon: BarChart3,
    title: "Funnel & segments",
    description: "Find the moments that matter in the candidate journey.",
  },
  {
    id: "releases" as const,
    label: "Release impact",
    icon: Rocket,
    title: "Release impact",
    description:
      "Follow changes in the experience, and investigate what happens next.",
  },
  {
    id: "analyst" as const,
    label: "AI analyst",
    icon: Sparkles,
    title: "Your AI analyst",
    description: "From a good question to a clear, visual explanation.",
  },
  {
    id: "connections" as const,
    label: "Data & connections",
    icon: Plug,
    title: "Data & connections",
    description:
      "The foundation for trustworthy analytics. Ready for your workflow.",
  },
];

function Brand() {
  return (
    <div className="brand">
      <span className="brand-symbol" aria-hidden="true">
        {Array.from({ length: 9 }, (_, index) => (
          <i key={index} />
        ))}
      </span>
      <div className="brand-name">
        TalentPulse<span>LAB</span>
      </div>
    </div>
  );
}

export default function TalentPulse() {
  const [view, setView] = useState<ViewName>("overview");
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [theme, setTheme] = useState("light");
  const [mobileOpen, setMobileOpen] = useState(false);
  const { data: options } = useApi<FilterOptions>("/filters");
  const { data: health } = useApi<{
    status: string;
    database: string;
    synthetic: boolean;
  }>("/health");
  useEffect(() => {
    setTheme(document.documentElement.dataset.theme || "light");
    const readHash = () => {
      const hash = window.location.hash.slice(1);
      if (NAVIGATION.some((item) => item.id === hash))
        setView(hash as ViewName);
    };
    readHash();
    window.addEventListener("hashchange", readHash);
    return () => window.removeEventListener("hashchange", readHash);
  }, []);
  function navigate(next: ViewName) {
    setView(next);
    setMobileOpen(false);
    window.location.hash = next;
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
  function toggleTheme(next: string) {
    setTheme(next);
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem("talentpulse.theme.v1", next);
    } catch {}
  }
  function filter(key: keyof Filters, value: string) {
    setFilters((previous) => ({ ...previous, [key]: value }));
  }
  const current = NAVIGATION.find((item) => item.id === view)!;
  const dates = apiFilters(filters);
  const segmented =
    filters.market !== "all" ||
    filters.device !== "all" ||
    filters.user_type !== "all";
  const props = { filters, navigate };
  return (
    <div className="app-shell">
      <button
        className={`mobile-backdrop ${mobileOpen ? "open" : ""}`}
        aria-label="Close navigation"
        onClick={() => setMobileOpen(false)}
      />
      <aside className={`sidebar ${mobileOpen ? "open" : ""}`}>
        <Brand />
        <div className="workspace-switch">
          <div className="workspace-logo">
            <LayersIcon />
          </div>
          <div>
            <strong>Job discovery</strong>
            <small>Product analytics workspace</small>
          </div>
          <ChevronDown size={12} />
        </div>
        <div className="nav-label">Workspace</div>
        <nav aria-label="Analytics workspaces">
          {NAVIGATION.map((item) => (
            <button
              className={`nav-item ${view === item.id ? "active" : ""}`}
              key={item.id}
              onClick={() => navigate(item.id)}
              aria-current={view === item.id ? "page" : undefined}
            >
              <item.icon size={16} strokeWidth={1.7} />
              {item.label}
              {item.id === "analyst" ? (
                <span className="nav-tag">AI</span>
              ) : null}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="lab-note">
            <FlaskConical size={16} />
            <strong>A lab for better decisions</strong>
            <p>
              Real analytics infrastructure.
              <br />
              Synthetic candidate telemetry.
              <br />
              Built to explore what comes next.
            </p>
          </div>
          <div className="profile">
            <span className="avatar">PA</span>
            <div>
              <strong>Product Analyst</strong>
              <small>Research workspace</small>
            </div>
            <ShieldCheck size={14} />
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="icon-button mobile-menu"
              aria-label="Open navigation"
              onClick={() => setMobileOpen(true)}
            >
              <Menu size={17} />
            </button>
            <span>Workspace</span>
            <ChevronRight size={11} />
            <strong>{current.label}</strong>
          </div>
          <div className="topbar-actions">
            <Pill tone="green" dot>
              Synthetic dataset
            </Pill>
            <div className="theme-button" aria-label="Appearance">
              <button
                className={theme === "light" ? "selected" : ""}
                onClick={() => toggleTheme("light")}
                aria-label="Light mode"
                aria-pressed={theme === "light"}
              >
                <Sun size={13} />
              </button>
              <button
                className={theme === "dark" ? "selected" : ""}
                onClick={() => toggleTheme("dark")}
                aria-label="Dark mode"
                aria-pressed={theme === "dark"}
              >
                <Moon size={12} />
              </button>
            </div>
          </div>
        </header>
        <main className="main-content">
          <div className="page-titlebar">
            <div>
              <div className="eyebrow">Product intelligence</div>
              <h1>{current.title}</h1>
              <p className="page-description">{current.description}</p>
            </div>
            <div className="title-actions">
              <a
                className="button subtle"
                href={`/api/export/daily?${filterQuery(filters)}`}
                download
                aria-label="Export daily analytics CSV"
              >
                <Download size={14} />
                <span>Export data</span>
              </a>
              {view !== "analyst" ? (
                <button
                  className="button primary"
                  aria-label="Ask AI"
                  onClick={() => navigate("analyst")}
                >
                  <Sparkles size={13} />
                  <span>Ask AI</span>
                </button>
              ) : null}
            </div>
          </div>
          <div className="filter-bar" aria-label="Shared analytics filters">
            <div className="filter-control">
              <CalendarDays />
              <select
                aria-label="Date range"
                value={filters.days}
                onChange={(event) => filter("days", event.target.value)}
              >
                <option value="7">Last 7 days</option>
                <option value="28">Last 28 days</option>
                <option value="56">Full 56 days</option>
              </select>
            </div>
            <div className="filter-control">
              <Globe2 />
              <select
                aria-label="Market"
                value={filters.market}
                onChange={(event) => filter("market", event.target.value)}
              >
                <option value="all">All markets</option>
                {options?.markets.map((market) => (
                  <option key={market} value={market}>
                    {market}
                  </option>
                ))}
              </select>
            </div>
            <div className="filter-control">
              <MonitorSmartphone />
              <select
                aria-label="Device"
                value={filters.device}
                onChange={(event) => filter("device", event.target.value)}
              >
                <option value="all">All devices</option>
                {options?.devices.map((device) => (
                  <option key={device} value={device}>
                    {device.replaceAll("_", " ")}
                  </option>
                ))}
              </select>
            </div>
            <div className="filter-control">
              <Users />
              <select
                aria-label="User type"
                value={filters.user_type}
                onChange={(event) => filter("user_type", event.target.value)}
              >
                <option value="all">All candidates</option>
                {options?.user_types.map((type) => (
                  <option key={type} value={type}>
                    {type.replaceAll("_", " ")}
                  </option>
                ))}
              </select>
            </div>
            {segmented ? (
              <button
                className="filters-active"
                onClick={() =>
                  setFilters((previous) => ({
                    ...previous,
                    market: "all",
                    device: "all",
                    user_type: "all",
                  }))
                }
              >
                Reset segments
              </button>
            ) : null}
            <span className="filter-date">
              {formatDate(dates.start_date, true)} —{" "}
              {formatDate(dates.end_date, true)} 2026
            </span>
          </div>
          {view === "overview" ? (
            <OverviewView {...props} />
          ) : view === "experiments" ? (
            <ExperimentsView {...props} />
          ) : view === "funnel" ? (
            <FunnelView {...props} />
          ) : view === "releases" ? (
            <ReleasesView {...props} />
          ) : view === "analyst" ? (
            <AnalystView {...props} />
          ) : (
            <ConnectionsView {...props} />
          )}
          <div className="workspace-footer">
            <span>
              TalentPulse Lab · An independent product analytics portfolio
            </span>
            <span className="data-source">
              <Database size={11} />
              {health?.status === "ok" || health?.status === "healthy"
                ? "Neon connected"
                : "Database-backed analytics"}
            </span>
          </div>
        </main>
      </div>
    </div>
  );
}

function LayersIcon() {
  return (
    <svg
      width="17"
      height="17"
      viewBox="0 0 20 20"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="m10 3 7 4-7 4-7-4 7-4Z"
        stroke="currentColor"
        strokeWidth="1.25"
        strokeLinejoin="round"
      />
      <path
        d="m3 10 7 4 7-4M3 13l7 4 7-4"
        stroke="currentColor"
        strokeWidth="1.25"
        strokeLinejoin="round"
      />
    </svg>
  );
}
