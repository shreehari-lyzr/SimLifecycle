import { useEffect, useState } from "react";
import {
  api,
  type AIStatus,
  type RecommendationReport,
  type ScanSummary,
} from "../api/client";
import { Criticality, TierBadge, formatBytes } from "../components/common";

export default function AIAdvisor() {
  const [status, setStatus] = useState<AIStatus | null>(null);
  const [report, setReport] = useState<RecommendationReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const loadStatus = () => api.aiStatus().then(setStatus);

  const loadRecs = async () => {
    setLoading(true);
    try {
      setReport(await api.recommendations());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStatus();
    loadRecs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const runScan = async () => {
    setBusy(true);
    try {
      const s: ScanSummary = await api.runScan();
      setToast(
        `${s.engine === "ai" ? "AI" : "Heuristic"} scan: ${s.moved} moved, ` +
          `${formatBytes(s.bytes_reclaimed_from_hot)} reclaimed from hot, ${s.skipped_exception} exempt.`
      );
      await loadRecs();
    } finally {
      setBusy(false);
      setTimeout(() => setToast(null), 6000);
    }
  };

  const live = status?.engine === "ai";
  const recs = report?.recommendations ?? [];
  const moves = recs.filter((r) => r.action === "move");

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>AI Storage Manager</h2>
          <p>Tiering decisions weighing policy + data criticality + cost/GB</p>
        </div>
        <button className="btn primary" onClick={runScan} disabled={busy}>
          {busy ? "Applying…" : "Run AI Scan"}
        </button>
      </div>

      <div className="banner" style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span
          className="pill"
          style={{
            background: live ? "rgba(62,207,142,0.18)" : "rgba(255,184,74,0.18)",
            color: live ? "var(--good)" : "var(--warm)",
            fontWeight: 700,
          }}
        >
          {live ? "● LIVE AI" : "● HEURISTIC"}
        </span>
        <span className="muted">
          {live
            ? `Decisions made by ${status?.model}.`
            : "No ANTHROPIC_API_KEY configured — using the deterministic fallback. Decisions follow the same policy + criticality + cost reasoning. Set the key to enable live Claude."}
        </span>
        <div className="spacer" />
        <span className="muted">
          {moves.length} move{moves.length === 1 ? "" : "s"} recommended of {recs.length} movable
        </span>
      </div>

      {loading ? (
        <div className="muted">Asking the advisor…</div>
      ) : (
        <div className="card" style={{ padding: 0 }}>
          <table>
            <thead>
              <tr>
                <th>Decision</th>
                <th>Dataset</th>
                <th>Tier</th>
                <th>Criticality</th>
                <th>Value</th>
                <th>Inactive</th>
                <th>Savings/mo</th>
                <th>Conf.</th>
                <th>Rationale</th>
              </tr>
            </thead>
            <tbody>
              {recs.map((r) => (
                <tr key={r.dataset_id}>
                  <td>
                    <span
                      className="pill"
                      style={{
                        fontWeight: 700,
                        color: r.action === "move" ? "var(--warm)" : "var(--good)",
                        background:
                          r.action === "move"
                            ? "rgba(255,184,74,0.15)"
                            : "rgba(62,207,142,0.15)",
                      }}
                    >
                      {r.action === "move" ? "MOVE" : "KEEP"}
                    </span>
                  </td>
                  <td>
                    {r.name}
                    <div className="muted" style={{ fontSize: 11 }}>{r.project}</div>
                  </td>
                  <td>
                    <TierBadge tier={r.current_tier} />
                    {r.target_tier && r.target_tier !== r.current_tier && (
                      <>
                        {" → "}
                        <TierBadge tier={r.target_tier} />
                      </>
                    )}
                  </td>
                  <td><Criticality score={r.criticality_score} /></td>
                  <td className="muted">{r.business_value}</td>
                  <td className="muted">{r.inactive_days.toFixed(0)}d</td>
                  <td style={{ color: r.monthly_savings_usd > 0 ? "var(--good)" : "var(--muted)" }}>
                    ${r.monthly_savings_usd.toFixed(2)}
                  </td>
                  <td className="muted">{(r.confidence * 100).toFixed(0)}%</td>
                  <td className="muted" style={{ maxWidth: 360, fontSize: 12 }}>{r.rationale}</td>
                </tr>
              ))}
              {recs.length === 0 && (
                <tr><td colSpan={9} className="muted" style={{ padding: 18 }}>No movable datasets.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}
