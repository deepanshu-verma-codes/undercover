import { useState, type SyntheticEvent } from "react";
import type { Claim } from "../types";
import { ClaimFormFields } from "./ClaimFormFields";

interface Props {
  readonly isOpen: boolean;
  readonly onClose: () => void;
  readonly onClaimCreated: (claim: Claim) => void;
}

export function NewClaimModal({ isOpen, onClose, onClaimCreated }: Props) {
  const [policyId, setPolicyId] = useState<string>("POL-2001");
  const [customerId, setCustomerId] = useState<string>("CUS-3001");
  const [claimType, setClaimType] = useState<string>("trip_delay");
  const [incidentDate, setIncidentDate] = useState<string>(
    new Date().toISOString().split("T")[0],
  );
  const [incidentLocation, setIncidentLocation] = useState<string>("");
  const [amountClaimed, setAmountClaimed] = useState<string>("");
  const [summary, setSummary] = useState<string>("");
  const [story, setStory] = useState<string>("");
  const [runAgent, setRunAgent] = useState<boolean>(true);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string>("");

  if (!isOpen) return null;

  const handleSubmit = async (e: SyntheticEvent) => {
    e.preventDefault();
    setError("");

    const parsedAmount = parseFloat(amountClaimed);
    if (isNaN(parsedAmount) || parsedAmount <= 0) {
      setError("Please enter a valid claimed amount greater than $0.");
      return;
    }

    if (!summary.trim() || !story.trim() || !incidentLocation.trim()) {
      setError("Please fill out all required fields.");
      return;
    }

    setIsSubmitting(true);
    try {
      const res = await fetch("/api/claims", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          policy_id: policyId.trim(),
          customer_id: customerId.trim(),
          claim_type: claimType,
          incident_date: incidentDate,
          incident_location: incidentLocation.trim(),
          amount_claimed: parsedAmount,
          summary: summary.trim(),
          story: story.trim(),
          run_agent: runAgent,
        }),
      });

      if (!res.ok) {
        const errData = (await res.json().catch(() => ({}))) as {
          detail?: string;
        };
        throw new Error(errData.detail ?? "Failed to create claim");
      }

      const createdClaim = (await res.json()) as Claim;
      onClaimCreated(createdClaim);
      onClose();
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Error creating claim";
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  let submitButtonText = "Submit Claim";
  if (isSubmitting) {
    submitButtonText = runAgent ? "Auditing Claim..." : "Submitting...";
  }

  return (
    <div
      className="modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="new-claim-title"
    >
      <div className="modal-card">
        <div className="modal-header">
          <h2 id="new-claim-title">Submit New Claim</h2>
          <button
            className="btn btn-secondary"
            onClick={onClose}
            disabled={isSubmitting}
            aria-label="Close modal"
          >
            Close
          </button>
        </div>

        <form onSubmit={(e) => void handleSubmit(e)} className="claim-form">
          <ClaimFormFields
            policyId={policyId}
            setPolicyId={setPolicyId}
            customerId={customerId}
            setCustomerId={setCustomerId}
            claimType={claimType}
            setClaimType={setClaimType}
            incidentDate={incidentDate}
            setIncidentDate={setIncidentDate}
            incidentLocation={incidentLocation}
            setIncidentLocation={setIncidentLocation}
            amountClaimed={amountClaimed}
            setAmountClaimed={setAmountClaimed}
            summary={summary}
            setSummary={setSummary}
            story={story}
            setStory={setStory}
          />

          <div className="form-checkbox-group" style={{ marginTop: "16px" }}>
            <label className="form-checkbox-label">
              <input
                type="checkbox"
                checked={runAgent}
                onChange={(e) => {
                  setRunAgent(e.target.checked);
                }}
              />
              <span>Run UnderCover Agent immediately for audit</span>
            </label>
          </div>

          {error && <div className="form-error">{error}</div>}

          <div className="form-actions">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={isSubmitting}
            >
              {submitButtonText}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
