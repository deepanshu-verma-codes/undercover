import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { Claim } from "../types";
import { UploadCsvModal } from "./UploadCsvModal";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const sampleClaim: Claim = {
  claim_id: "CLM-7777",
  policy_id: "POL-2001",
  customer_id: "CUS-3001",
  claim_type: "trip_delay",
  submitted_on: "2026-06-25",
  incident_date: "2026-06-20",
  incident_location: "London, UK",
  summary: "Train delay",
  story: "Train broke down.",
  amount_claimed: 150.0,
  items: [
    {
      description: "Train delay",
      category: "trip_delay",
      amount: 150.0,
    },
  ],
  documents: [],
  status: "decided",
  decision: "approve",
  payout: 150.0,
  reason: "Covered.",
  policy_section: "3. Trip Delay",
  paid: true,
  signed_off: false,
};

it("downloads template and uploads csv successfully", async () => {
  const onClose = vi.fn();
  const onClaimsUploaded = vi.fn();
  let uploadedPayload: unknown = null;

  const createUrlSpy = vi.fn(() => "mock-url");
  global.URL.createObjectURL = createUrlSpy;
  global.URL.revokeObjectURL = vi.fn();

  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string, options?: RequestInit) => {
      if (url.includes("/api/claims/csv-template")) {
        return Promise.resolve(
          new Response(JSON.stringify({ template: "policy_id,customer_id\n" })),
        );
      }
      if (url.includes("/api/claims/upload-csv")) {
        uploadedPayload = JSON.parse(options?.body as string);
        return Promise.resolve(
          new Response(
            JSON.stringify({
              imported_count: 1,
              claims: [sampleClaim],
              decided_count: 1,
            }),
            { status: 201 },
          ),
        );
      }
      return Promise.resolve(new Response(JSON.stringify({})));
    }),
  );

  render(
    <UploadCsvModal
      isOpen={true}
      onClose={onClose}
      onClaimsUploaded={onClaimsUploaded}
    />,
  );

  expect(screen.getByText("Bulk Claims CSV Upload")).toBeDefined();

  // Test Download Template
  const downloadBtn = screen.getByRole("button", {
    name: "Download Template",
  });
  fireEvent.click(downloadBtn);
  await waitFor(() => {
    expect(createUrlSpy).toHaveBeenCalled();
  });

  // Test file input with preview
  const fileContent =
    'policy_id,customer_id,claim_type,amount_claimed\nPOL-2001,CUS-3001,trip_delay,"150.00"';
  const file = new File([fileContent], "test_claims.csv", {
    type: "text/csv",
  });
  Object.defineProperty(file, "text", {
    value: () => Promise.resolve(fileContent),
  });

  const fileInput = screen.getByLabelText("Select CSV File");
  fireEvent.change(fileInput, { target: { files: [file] } });

  expect(await screen.findByText("CSV Preview")).toBeDefined();
  expect(await screen.findByText("POL-2001")).toBeDefined();

  // Toggle checkbox
  const checkbox = screen.getByLabelText(
    "Run UnderCover Agent on all imported claims",
  );
  fireEvent.click(checkbox);
  fireEvent.click(checkbox);

  // Submit upload
  const uploadBtn = screen.getByRole("button", { name: "Upload and Ingest" });
  fireEvent.click(uploadBtn);

  await waitFor(() => {
    expect(uploadedPayload).toBeDefined();
    expect(onClaimsUploaded).toHaveBeenCalledWith([sampleClaim]);
    expect(
      screen.getByText("Successfully imported 1 claim(s). 1 audited."),
    ).toBeDefined();
  });

  // Test Done button
  const doneBtn = screen.getByRole("button", { name: "Done" });
  fireEvent.click(doneBtn);
  expect(onClose).toHaveBeenCalled();
});

it("handles upload errors and empty content", async () => {
  const onClose = vi.fn();
  const onClaimsUploaded = vi.fn();

  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string) => {
      if (url.includes("/api/claims/upload-csv")) {
        return Promise.resolve(
          new Response(JSON.stringify({ detail: "Invalid CSV headers" }), {
            status: 400,
          }),
        );
      }
      return Promise.resolve(new Response(JSON.stringify({})));
    }),
  );

  render(
    <UploadCsvModal
      isOpen={true}
      onClose={onClose}
      onClaimsUploaded={onClaimsUploaded}
    />,
  );

  const fileContent = "bad_header\nval";
  const file = new File([fileContent], "bad.csv", { type: "text/csv" });
  Object.defineProperty(file, "text", {
    value: () => Promise.resolve(fileContent),
  });

  const fileInput = screen.getByLabelText("Select CSV File");
  fireEvent.change(fileInput, { target: { files: [file] } });

  const uploadBtn = await screen.findByRole("button", {
    name: "Upload and Ingest",
  });
  fireEvent.click(uploadBtn);

  expect(await screen.findByText("Invalid CSV headers")).toBeDefined();
});

it("returns null when closed", () => {
  const { container } = render(
    <UploadCsvModal
      isOpen={false}
      onClose={vi.fn()}
      onClaimsUploaded={vi.fn()}
    />,
  );
  expect(container.firstChild).toBeNull();
});
