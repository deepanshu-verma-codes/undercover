import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Claim } from "../types";
import { ClaimDetail } from "./ClaimDetail";

const mockHighValueClaim: Claim = {
  claim_id: "CLM-1003",
  policy_id: "POL-2003",
  customer_id: "CUS-3003",
  claim_type: "medical",
  submitted_on: "2026-06-25",
  incident_date: "2026-06-20",
  incident_location: "Bangkok, Thailand",
  summary: "Emergency hospital stay",
  story: "Hospital admission after illness.",
  amount_claimed: 1500.0,
  items: [
    {
      description: "Hospital bill",
      category: "medical",
      amount: 1500.0,
    },
  ],
  documents: [
    {
      name: "Bill.pdf",
      type: "medical_report",
      content: "Invoice",
    },
  ],
  status: "waiting_for_sign_off",
  decision: "approve",
  payout: 1500.0,
  reason: "Medical coverage applied.",
  policy_section: "7. Emergency Medical",
  paid: false,
  signed_off: false,
};

describe("ClaimDetail Role-Based Access Control", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("disables sign-off button and displays warning for handler role", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string) => {
        if (url.includes("/activity")) {
          return Promise.resolve(new Response(JSON.stringify([])));
        }
        return Promise.resolve(new Response(JSON.stringify({})));
      }),
    );

    render(
      <ClaimDetail
        claim={mockHighValueClaim}
        handlerRole="handler"
        onBack={vi.fn()}
        onRefreshClaim={vi.fn()}
      />,
    );

    const button = screen.getByRole("button", { name: "Sign off & Pay" });
    expect(button.hasAttribute("disabled")).toBe(true);
    expect(
      screen.getByText("Supervisor role required to sign off payouts."),
    ).toBeDefined();
  });

  it("enables sign-off button and executes sign-off with header for supervisor role", async () => {
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url.includes("/sign-off")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({ ...mockHighValueClaim, signed_off: true }),
          ),
        );
      }
      if (url.includes("/pay")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              ...mockHighValueClaim,
              status: "decided",
              paid: true,
            }),
          ),
        );
      }
      if (url.includes("/activity")) {
        return Promise.resolve(new Response(JSON.stringify([])));
      }
      return Promise.resolve(new Response(JSON.stringify({})));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <ClaimDetail
        claim={mockHighValueClaim}
        handlerRole="supervisor"
        onBack={vi.fn()}
        onRefreshClaim={vi.fn()}
      />,
    );

    const button = screen.getByRole("button", { name: "Sign off & Pay" });
    expect(button.hasAttribute("disabled")).toBe(false);

    fireEvent.click(button);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/claims/CLM-1003/sign-off",
        expect.objectContaining({
          method: "POST",
          headers: { "X-Handler-Role": "supervisor" },
        }),
      );
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/claims/CLM-1003/pay",
        expect.objectContaining({
          method: "POST",
        }),
      );
    });
  });

  it("handles HTTP 403 error gracefully in UI", async () => {
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url.includes("/sign-off")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              detail: "Supervisor role required to sign off payouts",
            }),
            { status: 403 },
          ),
        );
      }
      if (url.includes("/activity")) {
        return Promise.resolve(new Response(JSON.stringify([])));
      }
      return Promise.resolve(new Response(JSON.stringify({})));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <ClaimDetail
        claim={mockHighValueClaim}
        handlerRole="supervisor"
        onBack={vi.fn()}
        onRefreshClaim={vi.fn()}
      />,
    );

    const button = screen.getByRole("button", { name: "Sign off & Pay" });
    fireEvent.click(button);

    await waitFor(() => {
      expect(
        screen.getByText("Supervisor role required to sign off payouts"),
      ).toBeDefined();
    });
  });
});
