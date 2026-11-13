import type { Claim, ClaimActivity, Customer, Policy } from "../types";

interface DecisionProps {
  readonly claim: Claim;
  readonly signingOff: boolean;
  readonly onSignOff: () => void;
}

export function DecisionSection({
  claim,
  signingOff,
  onSignOff,
}: DecisionProps) {
  if (!claim.decision) return null;

  return (
    <div className={`decision-card ${claim.decision}`}>
      <div className={`decision-badge ${claim.decision}`}>{claim.decision}</div>
      {claim.payout !== null && (
        <div className="payout-amount">${claim.payout.toFixed(2)}</div>
      )}
      {claim.reason && <p style={{ fontSize: "14px" }}>{claim.reason}</p>}
      {claim.policy_section && (
        <div className="policy-section-ref">Ref: {claim.policy_section}</div>
      )}

      {claim.status === "waiting_for_sign_off" && (
        <div style={{ marginTop: "16px" }}>
          <p
            style={{
              fontSize: "13px",
              fontWeight: 600,
              color: "var(--midnight)",
              marginBottom: "10px",
            }}
          >
            Payout exceeds $1,000 threshold. Handler sign-off required.
          </p>
          <button
            className="btn btn-signoff"
            onClick={onSignOff}
            disabled={signingOff}
            style={{ width: "100%" }}
          >
            {signingOff ? "Signing off..." : "Sign off & Pay"}
          </button>
        </div>
      )}
    </div>
  );
}

interface PolicyProps {
  readonly policy: Policy | null;
}

export function PolicySection({ policy }: PolicyProps) {
  if (!policy?.policy_id) return null;

  return (
    <div className="panel">
      <h2>Policy Details</h2>
      <div className="info-row">
        <span className="info-label">Policy ID</span>
        <span className="mono">{policy.policy_id}</span>
      </div>
      <div className="info-row">
        <span className="info-label">Plan</span>
        <span style={{ textTransform: "capitalize", fontWeight: 600 }}>
          {policy.plan}
        </span>
      </div>
      <div className="info-row">
        <span className="info-label">Destination</span>
        <span>{policy.trip.destination}</span>
      </div>
      <div className="info-row">
        <span className="info-label">Trip Cost</span>
        <span className="mono">${policy.trip.trip_cost.toFixed(2)}</span>
      </div>
      <div className="info-row">
        <span className="info-label">Travelers</span>
        <span>{policy.travelers.join(", ")}</span>
      </div>
    </div>
  );
}

interface CustomerProps {
  readonly customer: Customer | null;
}

export function CustomerSection({ customer }: CustomerProps) {
  if (!customer?.customer_id) return null;

  return (
    <div className="panel">
      <h2>Customer History</h2>
      <div className="info-row">
        <span className="info-label">Name</span>
        <span>{customer.name}</span>
      </div>
      <div className="info-row">
        <span className="info-label">Member Since</span>
        <span className="mono">{customer.customer_since}</span>
      </div>
      <div className="info-row">
        <span className="info-label">Past Claims</span>
        <span className="mono">{customer.previous_claims.length}</span>
      </div>
      {customer.previous_claims.length > 0 && (
        <div style={{ marginTop: "10px" }}>
          {customer.previous_claims.map((pc, idx) => (
            <div
              key={idx}
              style={{
                fontSize: "12px",
                padding: "6px 0",
                borderBottom: "1px solid var(--bg-light)",
              }}
            >
              <span className="mono" style={{ fontWeight: 600 }}>
                {pc.claim_id}
              </span>
              : {pc.summary} ({pc.outcome})
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

interface ActivityProps {
  readonly activities: readonly ClaimActivity[];
}

export function ActivitySection({ activities }: ActivityProps) {
  return (
    <div className="panel">
      <h2>Agent Activity</h2>
      {activities.length === 0 ? (
        <p style={{ fontSize: "13px", opacity: 0.6 }}>
          No activities recorded yet.
        </p>
      ) : (
        <ul className="activity-stream">
          {activities.map((act) => (
            <li key={act.id} className="activity-item">
              <span>{act.action}</span>
              <span className="activity-time">
                {new Date(act.timestamp).toLocaleTimeString()}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
