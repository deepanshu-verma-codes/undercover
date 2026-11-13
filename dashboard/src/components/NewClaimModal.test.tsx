import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { Claim } from "../types";
import { NewClaimModal } from "./NewClaimModal";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const sampleClaim: Claim = {
  claim_id: "CLM-9999",
  policy_id: "POL-2001",
  customer_id: "CUS-3001",
  claim_type: "trip_delay",
  submitted_on: "2026-06-25",
  incident_date: "2026-06-20",
  incident_location: "Madrid, Spain",
  summary: "Missed connection in Madrid",
  story: "Flight was delayed causing a missed connecting flight.",
  amount_claimed: 300.0,
  items: [
    {
      description: "Missed connection in Madrid",
      category: "trip_delay",
      amount: 300.0,
    },
  ],
  documents: [],
  status: "decided",
  decision: "approve",
  payout: 300.0,
  reason: "Covered under trip delay.",
  policy_section: "3. Trip Delay",
  paid: true,
  signed_off: false,
};

it("validates input and submits claim successfully", async () => {
  let createdPayload: unknown = null;
  const onClaimCreated = vi.fn();
  const onClose = vi.fn();

  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((_url: string, options?: RequestInit) => {
      createdPayload = JSON.parse(options?.body as string);
      return Promise.resolve(
        new Response(JSON.stringify(sampleClaim), { status: 201 }),
      );
    }),
  );

  render(
    <NewClaimModal
      isOpen={true}
      onClose={onClose}
      onClaimCreated={onClaimCreated}
    />,
  );

  expect(screen.getByText("Submit New Claim")).toBeDefined();

  const form = screen.getByRole("dialog").querySelector("form");
  if (form) {
    fireEvent.submit(form);
  }

  expect(
    await screen.findByText(
      "Please enter a valid claimed amount greater than $0.",
    ),
  ).toBeDefined();

  fireEvent.change(screen.getByLabelText("Incident Location *"), {
    target: { value: "Madrid, Spain" },
  });
  fireEvent.change(screen.getByLabelText("Amount Claimed ($ USD) *"), {
    target: { value: "300" },
  });
  fireEvent.change(screen.getByLabelText("Summary *"), {
    target: { value: "Missed connection in Madrid" },
  });
  fireEvent.change(screen.getByLabelText("Customer Story *"), {
    target: { value: "Flight was delayed causing a missed connecting flight." },
  });

  if (form) {
    fireEvent.submit(form);
  }

  await waitFor(() => {
    expect(createdPayload).toBeDefined();
    expect(onClaimCreated).toHaveBeenCalledWith(sampleClaim);
    expect(onClose).toHaveBeenCalled();
  });
});

it("handles validation and API errors", async () => {
  const onClaimCreated = vi.fn();
  const onClose = vi.fn();

  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation(() =>
      Promise.resolve(
        new Response(JSON.stringify({ detail: "Invalid policy" }), {
          status: 400,
        }),
      ),
    ),
  );

  render(
    <NewClaimModal
      isOpen={true}
      onClose={onClose}
      onClaimCreated={onClaimCreated}
    />,
  );

  const cancelBtn = screen.getByRole("button", { name: "Cancel" });
  fireEvent.click(cancelBtn);
  expect(onClose).toHaveBeenCalled();

  fireEvent.change(screen.getByLabelText("Policy ID *"), {
    target: { value: "POL-9999" },
  });
  fireEvent.change(screen.getByLabelText("Customer ID *"), {
    target: { value: "CUS-9999" },
  });
  fireEvent.change(screen.getByLabelText("Claim Type *"), {
    target: { value: "medical" },
  });
  fireEvent.change(screen.getByLabelText("Incident Date *"), {
    target: { value: "2026-06-21" },
  });
  fireEvent.change(screen.getByLabelText("Incident Location *"), {
    target: { value: "Paris" },
  });
  fireEvent.change(screen.getByLabelText("Amount Claimed ($ USD) *"), {
    target: { value: "500" },
  });
  fireEvent.change(screen.getByLabelText("Summary *"), {
    target: { value: "Medical visit" },
  });
  fireEvent.change(screen.getByLabelText("Customer Story *"), {
    target: { value: "Needed clinic visit" },
  });
  const checkbox = screen.getByLabelText(
    "Run UnderCover Agent immediately for audit",
  );
  fireEvent.click(checkbox);

  const form = screen.getByRole("dialog").querySelector("form");
  if (form) {
    fireEvent.submit(form);
  }

  expect(await screen.findByText("Invalid policy")).toBeDefined();
});

it("returns null when not open", () => {
  const { container } = render(
    <NewClaimModal isOpen={false} onClose={vi.fn()} onClaimCreated={vi.fn()} />,
  );
  expect(container.firstChild).toBeNull();
});
