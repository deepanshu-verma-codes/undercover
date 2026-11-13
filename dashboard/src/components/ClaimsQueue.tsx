import { useState } from "react";
import type { Claim } from "../types";

interface Props {
  readonly claims: readonly Claim[];
  readonly onSelectClaim: (claim: Claim) => void;
  readonly onRunAll?: () => void;
  readonly isRunningAll?: boolean;
}

export function ClaimsQueue({
  claims,
  onSelectClaim,
  onRunAll,
  isRunningAll = false,
}: Props) {
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

  const counts: Record<string, number> = {
    all: claims.length,
    waiting: claims.filter((c) => c.status === "waiting").length,
    in_progress: claims.filter((c) => c.status === "in_progress").length,
    waiting_for_sign_off: claims.filter(
      (c) => c.status === "waiting_for_sign_off",
    ).length,
    decided: claims.filter((c) => c.status === "decided").length,
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
          ].map((st) => {
            const label = st === "all" ? "All Claims" : getStatusLabel(st);
            const count = counts[st] ?? 0;
            return (
              <button
                key={st}
                aria-label={label}
                className={`filter-tab ${filter === st ? "active" : ""}`}
                onClick={() => {
                  setFilter(st);
                }}
              >
                <span className="tab-label">{label}</span>
                <span className="tab-count">{count}</span>
              </button>
            );
          })}
        </div>
        <div className="queue-actions">
          <input
            type="text"
            placeholder="Search claims..."
            className="search-input"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
            }}
          />
          {onRunAll && (
            <button
              className="btn btn-primary"
              onClick={onRunAll}
              disabled={isRunningAll || counts.waiting === 0}
            >
              {isRunningAll ? "Running Agent..." : "Run Agent on All Claims"}
            </button>
          )}
        </div>
      </div>

      <table className="claims-table">
        <thead>
          <tr>
            <th>Claim ID</th>
            <th>Type</th>
            <th>Summary</th>
            <th>Amount Claimed</th>
            <th>Payout</th>
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
              <td className="mono">
                {c.payout !== null ? `$${c.payout.toFixed(2)}` : "—"}
              </td>
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
                colSpan={7}
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
