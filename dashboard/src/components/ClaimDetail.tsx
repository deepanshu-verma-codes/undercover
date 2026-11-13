import { useEffect, useState } from "react";
import type { Claim, ClaimActivity, Customer, Policy } from "../types";
import {
  ActivitySection,
  CustomerSection,
  DecisionSection,
  DocumentsListSection,
  ItemsClaimedSection,
  PolicySection,
} from "./ClaimDetailSections";

interface Props {
  readonly claim: Claim;
  readonly onBack: () => void;
  readonly onRefreshClaim: (claimId: string) => Promise<void>;
  readonly handlerRole?: "handler" | "supervisor";
}

export function ClaimDetail({
  claim,
  onBack,
  onRefreshClaim,
  handlerRole = "handler",
}: Props) {
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [activities, setActivities] = useState<ClaimActivity[]>([]);
  const [running, setRunning] = useState<boolean>(false);
  const [signingOff, setSigningOff] = useState<boolean>(false);
  const [signOffError, setSignOffError] = useState<string | null>(null);

  useEffect(() => {
    const loadDetails = async () => {
      try {
        const polRes = await fetch(`/api/policies/${claim.policy_id}`);
        if (polRes.ok) setPolicy((await polRes.json()) as Policy);

        const custRes = await fetch(`/api/customers/${claim.customer_id}`);
        if (custRes.ok) setCustomer((await custRes.json()) as Customer);

        const actRes = await fetch(`/api/claims/${claim.claim_id}/activity`);
        if (actRes.ok) {
          const actData = (await actRes.json()) as unknown;
          if (Array.isArray(actData)) setActivities(actData as ClaimActivity[]);
        }
      } catch {
        // Ignore network errors
      }
    };
    void loadDetails();
  }, [claim.claim_id, claim.policy_id, claim.customer_id]);

  const refreshActivities = async () => {
    try {
      const actRes = await fetch(`/api/claims/${claim.claim_id}/activity`);
      if (actRes.ok) {
        const actData = (await actRes.json()) as unknown;
        if (Array.isArray(actData)) setActivities(actData as ClaimActivity[]);
      }
    } catch {
      // Ignore network errors
    }
  };

  useEffect(() => {
    let isMounted = true;
    const interval = setInterval(() => {
      if (isMounted && !running) {
        void onRefreshClaim(claim.claim_id);
        void (async () => {
          try {
            const actRes = await fetch(
              `/api/claims/${claim.claim_id}/activity`,
            );
            if (actRes.ok) {
              const actData = (await actRes.json()) as unknown;
              if (Array.isArray(actData)) {
                setActivities(actData as ClaimActivity[]);
              }
            }
          } catch {
            // Ignore network errors
          }
        })();
      }
    }, 2000);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [claim.claim_id, running, onRefreshClaim]);

  const handleRunAgent = async () => {
    setRunning(true);
    try {
      await fetch(`/api/claims/${claim.claim_id}/run`, { method: "POST" });
      await onRefreshClaim(claim.claim_id);
      await refreshActivities();
    } finally {
      setRunning(false);
    }
  };

  const handleSignOff = async () => {
    setSigningOff(true);
    setSignOffError(null);
    try {
      const res = await fetch(`/api/claims/${claim.claim_id}/sign-off`, {
        method: "POST",
        headers: { "X-Handler-Role": handlerRole },
      });
      if (!res.ok) {
        const err = (await res.json().catch(() => ({}))) as {
          detail?: string;
        };
        setSignOffError(err.detail ?? "Sign-off failed");
        return;
      }
      if (claim.payout) {
        await fetch(`/api/claims/${claim.claim_id}/pay`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ amount: claim.payout }),
        });
      }
      await onRefreshClaim(claim.claim_id);
      await refreshActivities();
    } finally {
      setSigningOff(false);
    }
  };

  return (
    <div>
      <div className="detail-header">
        <button className="back-btn" onClick={onBack}>
          &larr; Back to queue
        </button>
        <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
          <span className={`status-badge ${claim.status}`}>
            {claim.status.replace(/_/g, " ")}
          </span>
          <button
            className="btn btn-action"
            onClick={() => {
              void handleRunAgent();
            }}
            disabled={running || claim.status === "decided"}
          >
            {running ? "Running agent..." : "Run Agent"}
          </button>
        </div>
      </div>

      <div className="detail-grid">
        <div className="detail-main">
          <div className="panel">
            <h2>Claim {claim.claim_id}</h2>
            <p style={{ fontWeight: 600, marginBottom: "12px" }}>
              {claim.summary}
            </p>
            <div className="info-row">
              <span className="info-label">Incident Date</span>
              <span className="mono">{claim.incident_date}</span>
            </div>
            <div className="info-row">
              <span className="info-label">Location</span>
              <span>{claim.incident_location}</span>
            </div>
            <div className="info-row">
              <span className="info-label">Claim Type</span>
              <span style={{ textTransform: "capitalize" }}>
                {claim.claim_type.replace(/_/g, " ")}
              </span>
            </div>
            <div style={{ marginTop: "16px" }}>
              <span className="info-label">Customer Story</span>
              <p style={{ marginTop: "6px", lineHeight: "1.6" }}>
                {claim.story}
              </p>
            </div>
          </div>

          <ItemsClaimedSection
            items={claim.items}
            totalAmount={claim.amount_claimed}
          />
          <DocumentsListSection documents={claim.documents} />
        </div>

        <div className="detail-sidebar">
          {signOffError && (
            <div
              style={{
                backgroundColor: "#fee2e2",
                color: "#991b1b",
                padding: "10px 14px",
                borderRadius: "6px",
                marginBottom: "12px",
                fontSize: "13px",
              }}
            >
              {signOffError}
            </div>
          )}
          <DecisionSection
            claim={claim}
            signingOff={signingOff}
            handlerRole={handlerRole}
            onSignOff={() => {
              void handleSignOff();
            }}
          />
          <PolicySection policy={policy} />
          <CustomerSection customer={customer} />
          <ActivitySection activities={activities} />
        </div>
      </div>
    </div>
  );
}
