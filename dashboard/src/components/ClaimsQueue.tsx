import { useState } from "react";
import type { Claim } from "../types";

interface Props {
  readonly claims: readonly Claim[];
  readonly onSelectClaim: (claim: Claim) => void;
}

export function ClaimsQueue({ claims, onSelectClaim }: Props) {
  const [filter, setFilter] = useState<string>("all");
  const [search, setSearch] = useState<string>("");

  const filtered = claims.filter((c) => {
    const matchesFilter = filter === "all" || c.status === filter;
    const q = search.toLowerCase();
    const matchesSearch =
      c.claim_id.toLowerCase().includes(q) ||
      c.customer_id.toLowerCase().includes(q) ||
      c.claim_type.toLowerCase().includes(q) ||
      c.summary.toLowerCase().includes(q);
    return matchesFilter && matchesSearch;
  });

  const getStatusLabel = (status: string) => {
    switch (status) {
      case "waiting":
        return "Waiting";
      case "in_progress":
        return "In Progress";
      case "waiting_for_sign_off":
        return "Waiting for Sign-Off";
      case "decided":
        return "Decided";
      default:
        return status;
    }
  };

  return (
    <div className="panel">
      <div className="queue-controls">
        <div className="filter-tabs">
          {[
            "all",
            "waiting",
            "in_progress",
            "waiting_for_sign_off",
            "decided",
          ].map((st) => (
            <button
              key={st}
              className={`filter-tab ${filter === st ? "active" : ""}`}
              onClick={() => {
                setFilter(st);
              }}
            >
              {st === "all" ? "All Claims" : getStatusLabel(st)}
            </button>
          ))}
        </div>
        <input
          type="text"
          placeholder="Search claims..."
          className="search-input"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
          }}
        />
      </div>

      <table className="claims-table">
        <thead>
          <tr>
            <th>Claim ID</th>
            <th>Type</th>
            <th>Summary</th>
            <th>Amount Claimed</th>
            <th>Submitted</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map((c) => (
            <tr
              key={c.claim_id}
              className="clickable"
              onClick={() => {
                onSelectClaim(c);
              }}
              role="row"
            >
              <td className="mono">{c.claim_id}</td>
              <td style={{ textTransform: "capitalize" }}>
                {c.claim_type.replace(/_/g, " ")}
              </td>
              <td>{c.summary}</td>
              <td className="mono">${c.amount_claimed.toFixed(2)}</td>
              <td className="mono">{c.submitted_on}</td>
              <td>
                <span className={`status-badge ${c.status}`}>
                  {getStatusLabel(c.status)}
                </span>
              </td>
            </tr>
          ))}
          {filtered.length === 0 && (
            <tr>
              <td
                colSpan={6}
                style={{
                  textAlign: "center",
                  padding: "32px",
                  opacity: 0.6,
                }}
              >
                No claims match the filter criteria.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
