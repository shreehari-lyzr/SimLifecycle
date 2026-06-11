import { useState } from "react";
import Dashboard from "./pages/Dashboard";
import Catalog from "./pages/Catalog";
import Policies from "./pages/Policies";
import Events from "./pages/Events";
import AIAdvisor from "./pages/AIAdvisor";

type Page = "dashboard" | "advisor" | "catalog" | "policies" | "events";

const NAV: { key: Page; label: string }[] = [
  { key: "dashboard", label: "Dashboard" },
  { key: "advisor", label: "AI Advisor" },
  { key: "catalog", label: "Data Catalog" },
  { key: "policies", label: "Policies" },
  { key: "events", label: "Lifecycle Events" },
];

export default function App() {
  const [page, setPage] = useState<Page>("dashboard");

  return (
    <div className="app">
      <aside className="sidebar">
        <h1>SimLifecycle</h1>
        <p className="tagline">Storage Lifecycle Agent</p>
        {NAV.map((n) => (
          <button
            key={n.key}
            className={`nav-item ${page === n.key ? "active" : ""}`}
            onClick={() => setPage(n.key)}
          >
            {n.label}
          </button>
        ))}
      </aside>
      <main className="main">
        {page === "dashboard" && <Dashboard />}
        {page === "advisor" && <AIAdvisor />}
        {page === "catalog" && <Catalog />}
        {page === "policies" && <Policies />}
        {page === "events" && <Events />}
      </main>
    </div>
  );
}
