import { useEffect, useState } from "react";
import { api, type Dataset, type Tier } from "../api/client";
import { TierBadge, formatBytes, timeAgo } from "../components/common";

export default function Catalog() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [search, setSearch] = useState("");
  const [tierFilter, setTierFilter] = useState<Tier | "">("");
  const [toast, setToast] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  const load = () =>
    api
      .listDatasets({ search: search || undefined, tier: tierFilter || undefined })
      .then(setDatasets);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, tierFilter]);

  const flash = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 4000);
  };

  const access = async (d: Dataset) => {
    const r = await api.accessDataset(d.id, "read");
    flash(`${d.name}: ${r.note} (latency ${r.latency_ms}ms)`);
    load();
  };
  const restore = async (d: Dataset) => {
    const r = await api.restoreDataset(d.id);
    flash(`${d.name}: ${r.note}`);
    load();
  };
  const toggleCritical = async (d: Dataset) => {
    await api.setCritical(d.id, !d.is_critical);
    flash(`${d.name} ${!d.is_critical ? "marked critical (exempt)" : "no longer critical"}`);
    load();
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Data Catalog</h2>
          <p>Find, access and restore any dataset — physical tier is transparent</p>
        </div>
        <button className="btn primary" onClick={() => setShowCreate((s) => !s)}>
          {showCreate ? "Close" : "Create Dataset"}
        </button>
      </div>

      {showCreate && <CreateForm onCreated={() => { setShowCreate(false); load(); flash("Dataset created in hot storage"); }} />}

      <div className="row" style={{ marginBottom: 16 }}>
        <input
          placeholder="Search by name…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ width: 240 }}
        />
        <select value={tierFilter} onChange={(e) => setTierFilter(e.target.value as Tier | "")}>
          <option value="">All tiers</option>
          <option value="hot">Hot</option>
          <option value="warm">Warm</option>
          <option value="cold">Cold</option>
        </select>
        <div className="spacer" />
        <span className="muted">{datasets.length} dataset(s)</span>
      </div>

      <div className="card" style={{ padding: 0 }}>
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Project</th>
              <th>Tier</th>
              <th>Size</th>
              <th>Last Access</th>
              <th>Accesses</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {datasets.map((d) => (
              <tr key={d.id}>
                <td>
                  {d.name}{" "}
                  {d.is_exempt && (
                    <span
                      className="pill"
                      style={{ color: "#ffb84a", cursor: "help" }}
                      title={`Exempt from automated movement:\n• ${d.exempt_reasons.join("\n• ")}`}
                    >
                      exempt ({d.exempt_reasons.length})
                    </span>
                  )}
                </td>
                <td className="muted">{d.project}</td>
                <td><TierBadge tier={d.tier} /></td>
                <td>{formatBytes(d.size_bytes)}</td>
                <td className="muted">{timeAgo(d.last_accessed_at)}</td>
                <td>{d.access_count}</td>
                <td>
                  <div className="row">
                    <button className="btn small" onClick={() => access(d)}>Access</button>
                    {d.tier !== "hot" && (
                      <button className="btn small primary" onClick={() => restore(d)}>Restore</button>
                    )}
                    <button className="btn small" onClick={() => toggleCritical(d)}>
                      {d.is_critical ? "Unflag" : "Mark critical"}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}

function CreateForm({ onCreated }: { onCreated: () => void }) {
  const [name, setName] = useState("");
  const [project, setProject] = useState("");
  const [owner, setOwner] = useState("");
  const [sizeGb, setSizeGb] = useState(2);

  const submit = async () => {
    if (!name || !project || !owner) return;
    await api.createDataset({ name, project, owner, size_bytes: sizeGb * 1_000_000_000 });
    onCreated();
  };

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <h3>New Simulation Dataset</h3>
      <div className="row">
        <input placeholder="Dataset name" value={name} onChange={(e) => setName(e.target.value)} />
        <input placeholder="Project" value={project} onChange={(e) => setProject(e.target.value)} />
        <input placeholder="Owner" value={owner} onChange={(e) => setOwner(e.target.value)} />
        <input
          type="number"
          min={1}
          value={sizeGb}
          onChange={(e) => setSizeGb(Number(e.target.value))}
          style={{ width: 90 }}
        />
        <span className="muted">GB</span>
        <button className="btn primary" onClick={submit}>Create in Hot</button>
      </div>
    </div>
  );
}
