import { useEffect, useState } from "react";
import { api, type LifecycleEvent } from "../api/client";
import { TierBadge, timeAgo } from "../components/common";

export default function Events() {
  const [events, setEvents] = useState<LifecycleEvent[]>([]);
  const [busy, setBusy] = useState(false);

  const load = () => api.events(100).then(setEvents);
  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);

  const runScan = async () => {
    setBusy(true);
    try {
      await api.runScan();
      await load();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Lifecycle Events</h2>
          <p>Append-only audit trail of every create, access, move & restore</p>
        </div>
        <button className="btn primary" onClick={runScan} disabled={busy}>
          {busy ? "Scanning…" : "Run Lifecycle Scan"}
        </button>
      </div>

      <div className="card" style={{ padding: 0 }}>
        <table>
          <thead>
            <tr>
              <th>When</th>
              <th>Event</th>
              <th>Transition</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            {events.map((e) => (
              <tr key={e.id}>
                <td className="muted">{timeAgo(e.timestamp)}</td>
                <td>
                  <span className={`event-type event-${e.event_type}`}>{e.event_type}</span>
                </td>
                <td>
                  {e.from_tier || e.to_tier ? (
                    <>
                      {e.from_tier ? <TierBadge tier={e.from_tier} /> : <span className="muted">—</span>}
                      {" → "}
                      {e.to_tier ? <TierBadge tier={e.to_tier} /> : <span className="muted">—</span>}
                    </>
                  ) : (
                    <span className="muted">—</span>
                  )}
                </td>
                <td className="muted">{e.details}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
