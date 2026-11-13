import { useState, type ChangeEvent } from "react";
import type { Claim } from "../types";

interface Props {
  readonly isOpen: boolean;
  readonly onClose: () => void;
  readonly onClaimsUploaded: (claims: Claim[]) => void;
}

export function UploadCsvModal({ isOpen, onClose, onClaimsUploaded }: Props) {
  const [csvContent, setCsvContent] = useState<string>("");
  const [fileName, setFileName] = useState<string>("");
  const [previewRows, setPreviewRows] = useState<string[][]>([]);
  const [runAgent, setRunAgent] = useState<boolean>(true);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [error, setError] = useState<string>("");
  const [successMsg, setSuccessMsg] = useState<string>("");

  if (!isOpen) return null;

  const handleDownloadTemplate = async () => {
    try {
      const res = await fetch("/api/claims/csv-template");
      if (!res.ok) throw new Error("Failed to fetch template");
      const data = (await res.json()) as { template: string };
      const blob = new Blob([data.template], {
        type: "text/csv;charset=utf-8;",
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "claims_template.csv";
      link.click();
      URL.revokeObjectURL(url);
    } catch {
      setError("Unable to download CSV template");
    }
  };

  const handleFileChange = async (e: ChangeEvent<HTMLInputElement>) => {
    setError("");
    const file = e.target.files?.[0];
    if (!file) return;

    setFileName(file.name);
    try {
      const text = await file.text();
      setCsvContent(text);

      const lines = text
        .split("\n")
        .map((l) => l.trim())
        .filter((l) => l.length > 0)
        .slice(0, 6)
        .map((l) => l.split(",").map((c) => c.replace(/^"|"$/g, "")));
      setPreviewRows(lines);
    } catch {
      setError("Failed to read CSV file");
    }
  };

  const handleUpload = async () => {
    if (!csvContent.trim()) {
      setError("Please select a valid CSV file to upload.");
      return;
    }

    setIsUploading(true);
    setError("");
    try {
      const res = await fetch("/api/claims/upload-csv", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          csv_content: csvContent,
          run_agent: runAgent,
        }),
      });

      if (!res.ok) {
        const err = (await res.json().catch(() => ({}))) as {
          detail?: string;
        };
        throw new Error(err.detail ?? "CSV import failed");
      }

      const result = (await res.json()) as {
        imported_count: number;
        claims: Claim[];
        decided_count: number;
      };

      setSuccessMsg(
        `Successfully imported ${String(result.imported_count)} claim(s). ${String(result.decided_count)} audited.`,
      );
      onClaimsUploaded(result.claims);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Error uploading CSV";
      setError(message);
    } finally {
      setIsUploading(false);
    }
  };

  let submitButtonLabel = "Upload and Ingest";
  if (isUploading) {
    submitButtonLabel = runAgent
      ? "Importing & Auditing..."
      : "Importing Claims...";
  }

  return (
    <div
      className="modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="csv-modal-title"
    >
      <div className="modal-card">
        <div className="modal-header">
          <h2 id="csv-modal-title">Bulk Claims CSV Upload</h2>
          <button
            className="btn btn-secondary"
            onClick={onClose}
            disabled={isUploading}
            aria-label="Close modal"
          >
            Close
          </button>
        </div>

        <div className="csv-upload-content">
          <div className="template-download-row">
            <span>Need the standard CSV structure?</span>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => void handleDownloadTemplate()}
            >
              Download Template
            </button>
          </div>

          <div className="upload-dropzone">
            <label htmlFor="csv-file-input" className="form-label">
              Select CSV File
            </label>
            <input
              id="csv-file-input"
              type="file"
              accept=".csv"
              onChange={(e) => void handleFileChange(e)}
              disabled={isUploading}
            />
            {fileName && (
              <p className="selected-filename">Selected: {fileName}</p>
            )}
          </div>

          {previewRows.length > 0 && (
            <div className="preview-container">
              <h3>CSV Preview</h3>
              <div className="preview-table-wrapper">
                <table className="preview-table">
                  <thead>
                    <tr>
                      {previewRows[0]?.map((col, idx) => (
                        <th key={`head-${String(idx)}`}>{col}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {previewRows.slice(1).map((row, rIdx) => (
                      <tr key={`row-${String(rIdx)}`}>
                        {row.map((val, cIdx) => (
                          <td key={`cell-${String(rIdx)}-${String(cIdx)}`}>
                            {val}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div className="form-checkbox-group" style={{ marginTop: "16px" }}>
            <label className="form-checkbox-label">
              <input
                type="checkbox"
                checked={runAgent}
                onChange={(e) => {
                  setRunAgent(e.target.checked);
                }}
              />
              <span>Run UnderCover Agent on all imported claims</span>
            </label>
          </div>

          {error && <div className="form-error">{error}</div>}
          {successMsg && <div className="form-success">{successMsg}</div>}

          <div className="form-actions">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={onClose}
              disabled={isUploading}
            >
              Done
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => void handleUpload()}
              disabled={isUploading || !csvContent}
            >
              {submitButtonLabel}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
