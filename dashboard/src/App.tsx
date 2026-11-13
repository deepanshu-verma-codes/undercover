import { useEffect, useState } from "react";
import "./styles.css";
import { AgentInstructionsModal } from "./components/AgentInstructionsModal";
import { ClaimDetail } from "./components/ClaimDetail";
import { ClaimsQueue } from "./components/ClaimsQueue";
import type { Claim } from "./types";

export function App() {
  const [status, setStatus] = useState<string>("checking");
  const [claims, setClaims] = useState<Claim[]>([]);
  const [selectedClaimId, setSelectedClaimId] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);

  useEffect(() => {
    const init = async () => {
      try {
        const healthRes = await fetch("/api/health");
        setStatus(healthRes.ok ? "up" : "down");
      } catch {
        setStatus("down");
      }

      try {
        const claimsRes = await fetch("/api/claims");
        if (claimsRes.ok) {
          const data = (await claimsRes.json()) as Claim[];
          if (Array.isArray(data)) {
            setClaims(data);
          }
        }
      } catch {
        setClaims([]);
      }
    };
    void init();
  }, []);

  const handleRefreshClaim = async (claimId: string) => {
    try {
      const res = await fetch(`/api/claims/${claimId}`);
      if (res.ok) {
        const updated = (await res.json()) as Claim;
        setClaims((prev) =>
          prev.map((c) => (c.claim_id === claimId ? updated : c)),
        );
      }
    } catch {
      // Ignore network errors
    }
  };

  const selectedClaim = claims.find((c) => c.claim_id === selectedClaimId);

  return (
    <div className="app-container">
      <header className="app-header">
        <div className="brand-section">
          <h1>UnderCover</h1>
          <span className={`backend-badge ${status}`}>Backend: {status}</span>
        </div>
        <div className="header-actions">
          <button
            className="btn btn-secondary"
            onClick={() => {
              setIsModalOpen(true);
            }}
          >
            Agent Instructions
          </button>
        </div>
      </header>

      <main>
        {selectedClaim ? (
          <ClaimDetail
            claim={selectedClaim}
            onBack={() => {
              setSelectedClaimId(null);
            }}
            onRefreshClaim={handleRefreshClaim}
          />
        ) : (
          <ClaimsQueue
            claims={claims}
            onSelectClaim={(c) => {
              setSelectedClaimId(c.claim_id);
            }}
          />
        )}
      </main>

      <AgentInstructionsModal
        isOpen={isModalOpen}
        onClose={() => {
          setIsModalOpen(false);
        }}
      />
    </div>
  );
}
