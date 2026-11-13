import { useEffect, useState } from "react";

interface Props {
  readonly isOpen: boolean;
  readonly onClose: () => void;
}

export function AgentInstructionsModal({ isOpen, onClose }: Props) {
  const [instructions, setInstructions] = useState<string>("");

  useEffect(() => {
    if (!isOpen) return;
    const fetchInstructions = async () => {
      try {
        const res = await fetch("/api/instructions");
        if (res.ok) {
          const data = (await res.json()) as { instructions: string };
          setInstructions(data.instructions);
        } else {
          setInstructions("Failed to load instructions.");
        }
      } catch {
        setInstructions("Failed to load instructions.");
      }
    };
    void fetchInstructions();
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true">
      <div className="modal-card">
        <div className="modal-header">
          <h2>Agent Instructions</h2>
          <button className="btn" onClick={onClose}>
            Close
          </button>
        </div>
        <div className="modal-body mono">
          {instructions || "Loading instructions..."}
        </div>
      </div>
    </div>
  );
}
