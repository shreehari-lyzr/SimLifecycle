import type { Tier } from "../api/client";

export function TierBadge({ tier }: { tier: Tier }) {
  return <span className={`tier-badge tier-${tier}`}>{tier}</span>;
}

export function MetricCard({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="card metric">
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {sub && <div className="sub">{sub}</div>}
    </div>
  );
}

export function Criticality({ score }: { score: number }) {
  const color = score >= 75 ? "#ff6b4a" : score >= 50 ? "#ffb84a" : "#3ecf8e";
  return (
    <span title={`Criticality ${score}/100`} className="row" style={{ gap: 6 }}>
      <span
        style={{
          display: "inline-block",
          width: 44,
          height: 6,
          borderRadius: 4,
          background: "var(--panel-2)",
          position: "relative",
          overflow: "hidden",
        }}
      >
        <span
          style={{
            position: "absolute",
            inset: 0,
            width: `${score}%`,
            background: color,
          }}
        />
      </span>
      <span style={{ fontSize: 12, color: "var(--muted)" }}>{score}</span>
    </span>
  );
}

export function formatBytes(bytes: number): string {
  if (bytes >= 1e9) return `${(bytes / 1e9).toFixed(1)} GB`;
  if (bytes >= 1e6) return `${(bytes / 1e6).toFixed(0)} MB`;
  if (bytes >= 1e3) return `${(bytes / 1e3).toFixed(0)} KB`;
  return `${bytes} B`;
}

export function timeAgo(iso: string): string {
  const then = new Date(iso).getTime();
  const secs = Math.max(0, (Date.now() - then) / 1000);
  if (secs < 60) return `${secs.toFixed(0)}s ago`;
  if (secs < 3600) return `${(secs / 60).toFixed(0)}m ago`;
  if (secs < 86400) return `${(secs / 3600).toFixed(0)}h ago`;
  return `${(secs / 86400).toFixed(0)}d ago`;
}
