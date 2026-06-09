// Typed API client for the SimLifecycle backend. All calls go through the Vite
// /api proxy to the FastAPI server.

export type Tier = "hot" | "warm" | "cold";
export type RestoreStatus = "none" | "restoring" | "restored";

export interface Dataset {
  id: string;
  name: string;
  project: string;
  owner: string;
  model_ref: string;
  run_config: Record<string, unknown>;
  size_bytes: number;
  tier: Tier;
  physical_path: string;
  created_at: string;
  last_accessed_at: string;
  access_count: number;
  is_critical: boolean;
  restore_status: RestoreStatus;
  is_exempt: boolean;
  exempt_reasons: string[];
}

export interface Policy {
  id: number;
  name: string;
  source_tier: Tier;
  target_tier: Tier;
  inactivity_threshold_days: number;
  enabled: boolean;
  priority: number;
}

export interface ExceptionRule {
  id: number;
  dataset_id: string | null;
  project: string | null;
  reason: string;
  created_at: string;
}

export interface Candidate {
  dataset_id: string;
  name: string;
  current_tier: Tier;
  target_tier: Tier;
  inactive_days: number;
  policy_name: string;
}

export interface ScanSummary {
  scanned: number;
  moved: number;
  skipped_exception: number;
  bytes_reclaimed_from_hot: number;
  moves: Array<Record<string, unknown>>;
}

export interface TierStats {
  tier: Tier;
  dataset_count: number;
  total_bytes: number;
  monthly_cost_usd: number;
}

export interface DashboardMetrics {
  tiers: TierStats[];
  total_datasets: number;
  total_bytes: number;
  hot_bytes_reclaimed: number;
  monthly_cost_usd: number;
  baseline_all_hot_cost_usd: number;
  monthly_savings_usd: number;
  savings_pct: number;
  compliance_pct: number;
  noncompliant_count: number;
}

export interface LifecycleEvent {
  id: number;
  dataset_id: string;
  event_type: "create" | "access" | "move" | "restore";
  from_tier: Tier | null;
  to_tier: Tier | null;
  timestamp: string;
  details: string;
}

async function req<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { "content-type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  // Datasets / catalog
  listDatasets: (params: { tier?: Tier; search?: string } = {}) => {
    const q = new URLSearchParams();
    if (params.tier) q.set("tier", params.tier);
    if (params.search) q.set("search", params.search);
    const qs = q.toString();
    return req<Dataset[]>(`/datasets${qs ? `?${qs}` : ""}`);
  },
  createDataset: (body: {
    name: string;
    project: string;
    owner: string;
    size_bytes: number;
  }) => req<Dataset>("/datasets", { method: "POST", body: JSON.stringify(body) }),
  accessDataset: (id: string, op_type: "read" | "write") =>
    req<{ dataset: Dataset; latency_ms: number; note: string }>(
      `/datasets/${id}/access`,
      { method: "POST", body: JSON.stringify({ op_type, user: "engineer" }) }
    ),
  restoreDataset: (id: string) =>
    req<{ dataset: Dataset; restored_from: Tier | null; note: string }>(
      `/datasets/${id}/restore`,
      { method: "POST" }
    ),
  setCritical: (id: string, is_critical: boolean) =>
    req<Dataset>(`/datasets/${id}/critical?is_critical=${is_critical}`, {
      method: "POST",
    }),

  // Policies & exceptions
  listPolicies: () => req<Policy[]>("/policies"),
  createPolicy: (body: Omit<Policy, "id">) =>
    req<Policy>("/policies", { method: "POST", body: JSON.stringify(body) }),
  updatePolicy: (id: number, body: Partial<Policy>) =>
    req<Policy>(`/policies/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  deletePolicy: (id: number) => req<void>(`/policies/${id}`, { method: "DELETE" }),
  listExceptions: () => req<ExceptionRule[]>("/exceptions"),
  createException: (body: { dataset_id?: string; project?: string; reason: string }) =>
    req<ExceptionRule>("/exceptions", { method: "POST", body: JSON.stringify(body) }),
  deleteException: (id: number) => req<void>(`/exceptions/${id}`, { method: "DELETE" }),

  // Lifecycle
  candidates: () => req<Candidate[]>("/lifecycle/candidates"),
  runScan: () => req<ScanSummary>("/lifecycle/run", { method: "POST" }),

  // Dashboard
  metrics: () => req<DashboardMetrics>("/dashboard/metrics"),
  events: (limit = 50) => req<LifecycleEvent[]>(`/dashboard/events?limit=${limit}`),
};
