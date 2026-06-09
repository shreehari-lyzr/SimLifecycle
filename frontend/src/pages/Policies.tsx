import { useEffect, useState } from "react";
import {
  api,
  type Candidate,
  type ExceptionRule,
  type Policy,
  type Tier,
} from "../api/client";
import { TierBadge } from "../components/common";

export default function Policies() {
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [exceptions, setExceptions] = useState<ExceptionRule[]>([]);
  const [candidates, setCandidates] = useState<Candidate[]>([]);

  const load = () => {
    api.listPolicies().then(setPolicies);
    api.listExceptions().then(setExceptions);
    api.candidates().then(setCandidates);
  };
  useEffect(load, []);

  const toggle = async (p: Policy) => {
    await api.updatePolicy(p.id, { enabled: !p.enabled });
    load();
  };
  const updateThreshold = async (p: Policy, days: number) => {
    await api.updatePolicy(p.id, { inactivity_threshold_days: days });
    load();
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Lifecycle Policies</h2>
          <p>Governance rules the agent enforces — plus exceptions & overrides</p>
        </div>
      </div>

      <div className="banner">
        {candidates.length > 0
          ? `${candidates.length} dataset(s) currently match a policy and will move on the next scan.`
          : "All datasets are compliant with current policies."}
      </div>

      <div className="card" style={{ marginBottom: 16, padding: 0 }}>
        <div style={{ padding: 18 }}>
          <h3>Tier Transition Policies</h3>
        </div>
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Transition</th>
              <th>Inactivity Threshold (days)</th>
              <th>Priority</th>
              <th>Enabled</th>
            </tr>
          </thead>
          <tbody>
            {policies.map((p) => (
              <tr key={p.id}>
                <td>{p.name}</td>
                <td>
                  <TierBadge tier={p.source_tier} /> → <TierBadge tier={p.target_tier} />
                </td>
                <td>
                  <input
                    type="number"
                    min={0}
                    defaultValue={p.inactivity_threshold_days}
                    style={{ width: 80 }}
                    onBlur={(e) => updateThreshold(p, Number(e.target.value))}
                  />
                </td>
                <td>{p.priority}</td>
                <td>
                  <button className={`btn small ${p.enabled ? "primary" : ""}`} onClick={() => toggle(p)}>
                    {p.enabled ? "Enabled" : "Disabled"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <NewPolicyForm onCreated={load} />

      <div className="card" style={{ padding: 0, marginTop: 16 }}>
        <div style={{ padding: 18 }}>
          <h3>Exceptions & Overrides</h3>
        </div>
        <table>
          <thead>
            <tr>
              <th>Scope</th>
              <th>Reason</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {exceptions.length === 0 && (
              <tr><td colSpan={3} className="muted" style={{ padding: 18 }}>No exceptions configured.</td></tr>
            )}
            {exceptions.map((e) => (
              <tr key={e.id}>
                <td>
                  {e.project ? `Project: ${e.project}` : `Dataset: ${e.dataset_id}`}
                </td>
                <td className="muted">{e.reason}</td>
                <td>
                  <button className="btn small danger" onClick={() => api.deleteException(e.id).then(load)}>
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <NewExceptionForm onCreated={load} />
      </div>
    </div>
  );
}

function NewPolicyForm({ onCreated }: { onCreated: () => void }) {
  const [name, setName] = useState("");
  const [source, setSource] = useState<Tier>("hot");
  const [target, setTarget] = useState<Tier>("warm");
  const [days, setDays] = useState(30);

  const submit = async () => {
    if (!name) return;
    await api.createPolicy({
      name,
      source_tier: source,
      target_tier: target,
      inactivity_threshold_days: days,
      enabled: true,
      priority: 100,
    });
    setName("");
    onCreated();
  };

  return (
    <div className="card">
      <h3>Add Policy</h3>
      <div className="row">
        <input placeholder="Policy name" value={name} onChange={(e) => setName(e.target.value)} />
        <select value={source} onChange={(e) => setSource(e.target.value as Tier)}>
          <option value="hot">hot</option>
          <option value="warm">warm</option>
          <option value="cold">cold</option>
        </select>
        <span>→</span>
        <select value={target} onChange={(e) => setTarget(e.target.value as Tier)}>
          <option value="warm">warm</option>
          <option value="cold">cold</option>
          <option value="hot">hot</option>
        </select>
        <input type="number" min={0} value={days} onChange={(e) => setDays(Number(e.target.value))} style={{ width: 80 }} />
        <span className="muted">days inactive</span>
        <button className="btn primary" onClick={submit}>Add</button>
      </div>
    </div>
  );
}

function NewExceptionForm({ onCreated }: { onCreated: () => void }) {
  const [project, setProject] = useState("");
  const [reason, setReason] = useState("");
  const submit = async () => {
    if (!project) return;
    await api.createException({ project, reason });
    setProject("");
    setReason("");
    onCreated();
  };
  return (
    <div style={{ padding: 18 }}>
      <div className="row">
        <input placeholder="Project to exempt" value={project} onChange={(e) => setProject(e.target.value)} />
        <input placeholder="Reason" value={reason} onChange={(e) => setReason(e.target.value)} style={{ flex: 1 }} />
        <button className="btn" onClick={submit}>Add Exception</button>
      </div>
    </div>
  );
}
