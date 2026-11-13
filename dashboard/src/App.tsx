import { useEffect, useState } from "react";
import "./styles.css";
import { AgentInstructionsModal } from "./components/AgentInstructionsModal";
import { ClaimDetail } from "./components/ClaimDetail";
import { ClaimsQueue } from "./components/ClaimsQueue";
import { NewClaimModal } from "./components/NewClaimModal";
import { UploadCsvModal } from "./components/UploadCsvModal";
import type { Claim } from "./types";

export function App() {
  const [status, setStatus] = useState<string>("checking");
  const [claims, setClaims] = useState<Claim[]>([]);
  const [selectedClaimId, setSelectedClaimId] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [isNewClaimOpen, setIsNewClaimOpen] = useState<boolean>(false);
  const [isUploadCsvOpen, setIsUploadCsvOpen] = useState<boolean>(false);
  const [isRunningAll, setIsRunningAll] = useState<boolean>(false);

  const fetchClaimsList = async () => {
    try {
      const claimsRes = await fetch("/api/claims");
      if (claimsRes.ok) {
        const data = (await claimsRes.json()) as Claim[];
        if (Array.isArray(data)) {
          setClaims(data);
        }
      }
    } catch {
      // Ignore network errors
    }
  };

  useEffect(() => {
    let isMounted = true;

    const fetchClaims = async () => {
      try {
        const claimsRes = await fetch("/api/claims");
        if (claimsRes.ok && isMounted) {
          const data = (await claimsRes.json()) as Claim[];
          if (Array.isArray(data)) {
            setClaims(data);
          }
        }
      } catch {
        if (isMounted) {
          setClaims([]);
        }
      }
    };

    const fetchHealth = async () => {
      try {
        const healthRes = await fetch("/api/health");
        if (isMounted) {
          setStatus(healthRes.ok ? "up" : "down");
        }
      } catch {
        if (isMounted) {
          setStatus("down");
        }
      }
    };

    void fetchHealth();
    void fetchClaims();

    const interval = setInterval(() => {
      void fetchClaims();
    }, 2000);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
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

  const handleRunAll = async () => {
    setIsRunningAll(true);
    try {
      const waiting = claims.filter((c) => c.status === "waiting");
      for (const c of waiting) {
        await fetch(`/api/claims/${c.claim_id}/run`, { method: "POST" });
        await fetchClaimsList();
      }
    } finally {
      setIsRunningAll(false);
      await fetchClaimsList();
    }
  };

  const handleClaimCreated = (newClaim: Claim) => {
    setClaims((prev) => [newClaim, ...prev]);
    setSelectedClaimId(newClaim.claim_id);
  };

  const handleClaimsUploaded = (uploadedClaims: Claim[]) => {
    setClaims((prev) => [...uploadedClaims, ...prev]);
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
            onRunAll={() => {
              void handleRunAll();
            }}
            isRunningAll={isRunningAll}
            onOpenNewClaim={() => {
              setIsNewClaimOpen(true);
            }}
            onOpenUploadCsv={() => {
              setIsUploadCsvOpen(true);
            }}
          />
        )}
      </main>

      <NewClaimModal
        isOpen={isNewClaimOpen}
        onClose={() => {
          setIsNewClaimOpen(false);
        }}
        onClaimCreated={handleClaimCreated}
      />

      <UploadCsvModal
        isOpen={isUploadCsvOpen}
        onClose={() => {
          setIsUploadCsvOpen(false);
        }}
        onClaimsUploaded={handleClaimsUploaded}
      />

      <AgentInstructionsModal
        isOpen={isModalOpen}
        onClose={() => {
          setIsModalOpen(false);
        }}
      />
    </div>
  );
}
