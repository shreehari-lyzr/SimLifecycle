import { useEffect, useState } from "react";
import {
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  Bar,
  BarChart,
  XAxis,
  YAxis,
} from "recharts";
import { api, type DashboardMetrics } from "../api/client";
import { MetricCard, formatBytes } from "../components/common";

const TIER_COLORS: Record<string, string> = {
  hot: "#ff6b4a",
  warm: "#ffb84a",
  cold: "#4a9eff",
};

export default function Dashboard() {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const load = () => api.metrics().then(setMetrics);

  useEffect(() => {
    load();
    const t = setInterval(load, 5000); // live refresh shows the agent working
    return () => clearInterval(t);
  }, []);

  const runScan = async () => {
    setBusy(true);
    try {
      const s = await api.runScan();
      setToast(
        `Scan complete — ${s.moved} dataset(s) moved, ${formatBytes(
          s.bytes_reclaimed_from_hot
        )} reclaimed from hot, ${s.skipped_exception} exempt.`
      );
      await load();
    } finally {
      setBusy(false);
      setTimeout(() => setToast(null), 5000);
    }
  };

  if (!metrics) return <div className="muted">Loading metrics…</div>;

  const pieData = metrics.tiers.map((t) => ({
    name: t.tier,
    value: t.total_bytes,
    count: t.dataset_count,
  }));
  const costData = metrics.tiers.map((t) => ({
    name: t.tier,
    cost: t.monthly_cost_usd,
  }));

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Operational Dashboard</h2>
          <p>Tier distribution, reclaimed capacity, cost savings & policy compliance</p>
        </div>
        <button className="btn primary" onClick={runScan} disabled={busy}>
          {busy ? "Scanning…" : "Run Lifecycle Scan"}
        </button>
      </div>

      <div className="grid grid-4" style={{ marginBottom: 16 }}>
        <MetricCard
          label="Total Datasets"
          value={String(metrics.total_datasets)}
          sub={formatBytes(metrics.total_bytes) + " managed"}
        />
        <MetricCard
          label="Hot Capacity Reclaimed"
          value={formatBytes(metrics.hot_bytes_reclaimed)}
          sub="moved to warm / cold"
        />
        <MetricCard
          label="Monthly Savings"
          value={`$${metrics.monthly_savings_usd.toFixed(2)}`}
          sub={`${metrics.savings_pct}% vs all-hot baseline`}
        />
        <MetricCard
          label="Policy Compliance"
          value={`${metrics.compliance_pct}%`}
          sub={`${metrics.noncompliant_count} pending move(s)`}
        />
      </div>

      <div className="grid grid-2">
        <div className="card">
          <h3>Tier Distribution (by size)</h3>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie
                data={pieData}
                dataKey="value"
                nameKey="name"
                outerRadius={90}
                label={(e) => `${e.name} (${e.count})`}
              >
                {pieData.map((d) => (
                  <Cell key={d.name} fill={TIER_COLORS[d.name]} />
                ))}
              </Pie>
              <Tooltip formatter={(v: number) => formatBytes(v)} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <h3>Monthly Cost by Tier (USD)</h3>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={costData}>
              <XAxis dataKey="name" stroke="#8b95ad" />
              <YAxis stroke="#8b95ad" />
              <Tooltip formatter={(v: number) => `$${v.toFixed(2)}`} />
              <Bar dataKey="cost">
                {costData.map((d) => (
                  <Cell key={d.name} fill={TIER_COLORS[d.name]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div className="muted" style={{ marginTop: 8 }}>
            All-hot baseline: ${metrics.baseline_all_hot_cost_usd.toFixed(2)}/mo · Current: $
            {metrics.monthly_cost_usd.toFixed(2)}/mo
          </div>
        </div>
      </div>

      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}
