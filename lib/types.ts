export type Meta = {
  synthetic: boolean | null;
  start_date: string;
  end_date: string;
  source?: string;
  events?: number;
  sessions?: number;
  generated_at?: string;
};
export type Insight = { title: string; detail: string; severity: string };
export type Kpi = {
  key: string;
  label: string;
  value: number | null;
  unit: string;
  delta: number | null;
  description?: string;
};
export type TrendPoint = {
  date: string;
  searches: number;
  sessions: number;
  applications: number;
  conversion_rate: number;
  completion_rate: number;
  latency_ms: number;
};
export type Market = {
  market: string;
  name?: string;
  searches: number;
  sessions: number;
  applications: number;
  application_rate: number;
  completion_rate?: number;
  share: number;
};
export type OverviewData = {
  meta: Meta;
  kpis: Kpi[];
  trend: TrendPoint[];
  markets: Market[];
  insights: Insight[];
  product_metrics?: {
    dau: number;
    wau: number;
    searches: number;
    job_views: number;
    application_starts: number;
    application_submits: number;
    search_conversion_rate: number;
    application_completion_rate: number;
    search_success_rate: number;
    definitions: Record<string, string>;
  };
};
export type ExperimentArm = {
  arm: string;
  label: string;
  provider: string;
  model: string | null;
  assigned_users: number;
  exposed_users: number;
  users: number;
  applications: number;
  sessions: number;
  conversion_rate: number | null;
  exposure_rate: number | null;
  lift_pct: number | null;
  absolute_lift_pp: number | null;
  ci_low: number | null;
  ci_high: number | null;
  p_value: number | null;
  significant: boolean;
  latency_ms: number;
  cost_usd: number;
  decision: string;
};
export type ExperimentsData = {
  experiment_id?: string;
  name?: string;
  primary_metric?: string;
  analysis_unit?: string;
  available?: boolean;
  reason?: string;
  status?: string;
  arms: ExperimentArm[];
  srm: { p_value: number | null; mismatch: boolean; status: string };
  guardrails: {
    variant: string;
    application_error_rate: number | null;
    avg_load_time_ms: number;
    latency_delta_ms: number;
    model_cost_usd: number;
    cost_per_search_usd: number;
  }[];
  filter_note: string;
  limitations?: string[];
  decision?: string;
  methodology?: Record<string, unknown>;
};
export type FunnelData = {
  meta: Meta;
  steps: {
    key: string;
    label: string;
    count: number;
    conversion_rate: number;
    step_conversion_rate: number;
    drop_off: number;
    drop_off_rate: number;
  }[];
  overall_conversion_rate: number;
  biggest_drop: { from: string; to: string; count: number; rate: number };
  insights: Insight[];
};
export type SegmentData = {
  meta: Meta;
  dimension: string;
  metric: string;
  rows: {
    name: string;
    label: string;
    sessions: number;
    applications: number;
    completion_rate: number;
    job_view_rate: number;
    error_rate: number;
    avg_load_time_ms: number;
    metric_value: number;
    share: number;
  }[];
  dimensions: string[];
  metrics: string[];
};
export type Release = {
  id: string;
  name: string;
  feature: string;
  release_date: string;
  market: string;
  platform: string;
  before: {
    sessions: number;
    applications: number;
    conversion_rate: number;
    completion_rate: number;
    error_rate: number;
    latency_ms: number;
  };
  after: {
    sessions: number;
    applications: number;
    conversion_rate: number;
    completion_rate: number;
    error_rate: number;
    latency_ms: number;
  };
  impact_pp: number | null;
  relative_lift_pct: number | null;
  latency_change_ms: number | null;
  error_change_pp?: number | null;
  before_window: { start_date: string; end_date: string };
  after_window: { start_date: string; end_date: string };
  confidence: string;
  interpretation: string;
};
export type ReleaseData = {
  meta: Meta;
  releases: Release[];
  disclaimer: string;
};
export type Job = {
  job_id: string;
  job_title: string;
  job_category: string;
  market: string;
  location: string;
  salary_min: number;
  salary_max: number;
  remote_type: string;
  experience_level: string;
  posted_date: string;
};
export type SearchResult = {
  query: string;
  synthetic_catalog: boolean;
  catalog_size: number;
  arms: {
    id: string;
    label: string;
    provider: string;
    model: string | null;
    status: string;
    latency_ms: number | null;
    retrieval_latency_ms?: number | null;
    inference_latency_ms?: number | null;
    jobs: Job[];
    explanation: string;
    cost_usd: number | null;
    error?: string;
  }[];
  measurement_note: string;
};
export type ModelsData = {
  providers: {
    id: string;
    label: string;
    model: string;
    configured: boolean;
    status: string;
    description: string;
  }[];
  policy: {
    per_ip_daily_limit: number;
    global_daily_limit: number;
    max_query_length: number;
  };
  synthetic_catalog: boolean;
  catalog?: {
    provider: string;
    id: string;
    label: string;
    source: string;
    available: boolean;
    capabilities: string[];
  }[];
  catalog_status?: string | Record<string, unknown>;
  defaults?: {
    search: { openrouter: string; ollama: string };
    analyst: { provider: string; model: string };
    ingestion: { provider: string; model: string };
  };
};

export type WorkspaceConnector = {
  id: string;
  name: string;
  configured: boolean;
  status: string;
  settings: Record<string, unknown>;
  secrets_present: string[];
  last_tested_at?: string | null;
  last_result?: {
    verified?: boolean;
    status?: string;
    detail?: string;
    capabilities?: string[];
  } | null;
};
export type UploadDataset = {
  dataset_id: string;
  id?: string;
  name: string;
  kind: string;
  row_count: number;
  column_count: number;
  columns: string[];
  mapping: Record<string, string>;
  created_at: string;
  readiness: Record<string, boolean>;
  reasons?: Record<string, string>;
  date_range?: { start_date: string; end_date: string } | null;
  preview?: Record<string, unknown>[];
  profile?: Record<string, unknown>;
  semantic_metadata?: Record<string, unknown>;
  warnings?: string[];
  filter_options?: FilterOptions;
};
export type AnalystAnswer = {
  answer: string;
  mode: "provider" | "evidence";
  provider: string;
  model: string | null;
  synthetic: boolean | null;
  evidence: { label: string; value: number; unit: string }[];
  chart: {
    type: "line" | "bar";
    title: string;
    x_key: string;
    y_key: string;
    data: Record<string, string | number | null>[];
  } | null;
  suggested_questions: string[];
  limitations: string[];
};
export type Integration = {
  id: string;
  name: string;
  type: string;
  status: string;
  configured: boolean;
  description: string;
  required_env: string[];
  capabilities: string[];
  setup_url?: string;
  details?: Record<string, unknown>;
};
export type IntegrationData = {
  integrations: Integration[];
  exports: { id: string; label: string; url: string }[];
  mcp: { endpoint: string; transport: string; tools: string[] };
  synthetic: boolean | null;
};
export type QualityData = {
  meta: Meta;
  score: number;
  checks: {
    key: string;
    label: string;
    status: string;
    observed: number;
    threshold: number;
    unit: string;
    detail: string;
  }[];
  daily: {
    date: string;
    events: number;
    sessions: number;
    missing_required: number;
    orphan_events: number;
  }[];
  event_volume: number;
  session_volume: number;
};
export type TrackingData = {
  events: {
    name: string;
    description: string;
    trigger: string;
    required_properties: string[];
    owner: string;
    status: string;
    volume: number;
  }[];
  common_properties: string[];
  synthetic: boolean | null;
};
export type FilterOptions = {
  markets: string[];
  devices: string[];
  user_types: string[];
  job_categories: string[];
  date_range: { start_date: string; end_date: string };
  synthetic: boolean | null;
};
