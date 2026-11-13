import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "./App";
import type { Claim } from "./types";

const mockClaims: Claim[] = [
  {
    claim_id: "CLM-1001",
    policy_id: "POL-2001",
    customer_id: "CUS-3001",
    claim_type: "trip_delay",
    submitted_on: "2026-06-24",
    incident_date: "2026-06-18",
    incident_location: "Rome, Italy",
    summary: "Flight canceled by airline",
    story: "My flight home from Rome was canceled.",
    amount_claimed: 420.0,
    items: [{ description: "Hotel", category: "accommodation", amount: 245.0 }],
    documents: [
      {
        name: "Notice",
        type: "carrier_report",
        content: "Flight canceled",
      },
    ],
    status: "waiting",
    decision: null,
    payout: null,
    reason: null,
    policy_section: null,
    paid: false,
    signed_off: false,
  },
  {
    claim_id: "CLM-1003",
    policy_id: "POL-2003",
    customer_id: "CUS-3003",
    claim_type: "emergency_medical",
    submitted_on: "2026-06-25",
    incident_date: "2026-06-20",
    incident_location: "Lisbon, Portugal",
    summary: "Emergency hospital visit",
    story: "Fell ill and required emergency medical care.",
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
        name: "Hospital invoice",
        type: "medical_report",
        content: "Treated for food poisoning",
      },
    ],
    status: "waiting_for_sign_off",
    decision: "approved",
    payout: 1500.0,
    reason: "Covered emergency hospital stay.",
    policy_section: "7. Emergency Medical",
    paid: false,
    signed_off: false,
  },
  {
    claim_id: "CLM-1004",
    policy_id: "POL-2004",
    customer_id: "CUS-3004",
    claim_type: "baggage_delay",
    submitted_on: "2026-06-26",
    incident_date: "2026-06-22",
    incident_location: "Tokyo, Japan",
    summary: "Baggage delayed by 18 hours",
    story: "Bag did not arrive on carousel.",
    amount_claimed: 120.0,
    items: [{ description: "Clothes", category: "clothing", amount: 120.0 }],
    documents: [
      {
        name: "PIR report",
        type: "pir",
        content: "Bag delivered next day",
      },
    ],
    status: "decided",
    decision: "approved",
    payout: 120.0,
    reason: "Delayed over 12 hours.",
    policy_section: "4. Baggage Delay",
    paid: true,
    signed_off: false,
  },
];

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("shows that the backend is up", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string) => {
      if (url.includes("/api/health")) {
        return Promise.resolve(new Response(JSON.stringify({ status: "ok" })));
      }
      if (url.includes("/api/claims")) {
        return Promise.resolve(new Response(JSON.stringify(mockClaims)));
      }
      return Promise.resolve(new Response(JSON.stringify({})));
    }),
  );

  render(<App />);
  expect(await screen.findByText("Backend: up")).toBeDefined();
  expect(await screen.findByText("CLM-1001")).toBeDefined();
  expect(await screen.findByText("CLM-1003")).toBeDefined();
  expect(screen.getByText("Payout")).toBeDefined();
  expect(screen.getAllByText("$120.00")).toHaveLength(2);
});

it("shows that the backend is down", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
  render(<App />);
  expect(await screen.findByText("Backend: down")).toBeDefined();
});

it("filters and searches claims in the queue", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string) => {
      if (url.includes("/api/health")) {
        return Promise.resolve(new Response(JSON.stringify({ status: "ok" })));
      }
      if (url.includes("/api/claims")) {
        return Promise.resolve(new Response(JSON.stringify(mockClaims)));
      }
      return Promise.resolve(new Response(JSON.stringify({})));
    }),
  );

  render(<App />);
  await screen.findByText("CLM-1001");

  // Filter by waiting
  const waitingTab = screen.getByRole("button", { name: "Waiting" });
  expect(waitingTab.textContent).toContain("Waiting");
  expect(waitingTab.textContent).toContain("1");
  fireEvent.click(waitingTab);
  expect(screen.getByText("CLM-1001")).toBeDefined();
  expect(screen.queryByText("CLM-1003")).toBeNull();

  // Search input
  const searchInput = screen.getByPlaceholderText("Search claims...");
  fireEvent.change(searchInput, { target: { value: "nonexistent" } });
  expect(
    screen.getByText("No claims match the filter criteria."),
  ).toBeDefined();

  // Clear search and reset filter
  fireEvent.change(searchInput, { target: { value: "" } });
  fireEvent.click(screen.getByRole("button", { name: "All Claims" }));
  expect(screen.getByText("CLM-1001")).toBeDefined();
});

it("opens claim detail view and returns back to queue", async () => {
  const mockPolicy = {
    policy_id: "POL-2001",
    customer_id: "CUS-3001",
    plan: "premium",
    add_ons: [],
    purchased_on: "2026-04-22",
    sold_through: "Online",
    trip: {
      destination: "Rome, Italy",
      departs_on: "2026-06-10",
      returns_on: "2026-06-18",
      trip_cost: 3100.0,
    },
    travelers: ["Maya Patel"],
    status: "active",
  };
  const mockCustomer = {
    customer_id: "CUS-3001",
    name: "Maya Patel",
    email: "maya@example.com",
    phone: "555-0143",
    date_of_birth: "1988-03-14",
    address: {
      street: "123 St",
      city: "Jersey City",
      state: "NJ",
      zip: "07302",
    },
    customer_since: "2023-04-11",
    previous_claims: [
      {
        claim_id: "CLM-01",
        filed_on: "2024",
        incident_date: "2024",
        claim_type: "delay",
        summary: "Late bag",
        outcome: "approved",
        amount_paid: 100,
      },
    ],
  };
  const mockActivities = [
    {
      id: 1,
      claim_id: "CLM-1001",
      timestamp: "2026-06-24T10:00:00Z",
      action: "Claim filed",
    },
  ];

  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string) => {
      if (url.includes("/api/health")) {
        return Promise.resolve(new Response(JSON.stringify({ status: "ok" })));
      }
      if (url === "/api/claims") {
        return Promise.resolve(new Response(JSON.stringify(mockClaims)));
      }
      if (url.includes("/api/policies/POL-2001")) {
        return Promise.resolve(new Response(JSON.stringify(mockPolicy)));
      }
      if (url.includes("/api/customers/CUS-3001")) {
        return Promise.resolve(new Response(JSON.stringify(mockCustomer)));
      }
      if (url.includes("/api/claims/CLM-1001/activity")) {
        return Promise.resolve(new Response(JSON.stringify(mockActivities)));
      }
      return Promise.resolve(new Response(JSON.stringify({})));
    }),
  );

  render(<App />);
  await screen.findByText("CLM-1001");

  // Click row to navigate to details
  const claimRow = screen.getByText("CLM-1001");
  fireEvent.click(claimRow);

  expect(await screen.findByText("Customer Story")).toBeDefined();
  expect(
    screen.getByText("My flight home from Rome was canceled."),
  ).toBeDefined();
  expect(screen.getAllByText("Maya Patel").length).toBeGreaterThan(0);
  expect(screen.getByText("Claim filed")).toBeDefined();

  // Click back button
  fireEvent.click(screen.getByText("← Back to queue"));
  expect(await screen.findByPlaceholderText("Search claims...")).toBeDefined();
});

it("runs the agent from the claim detail view", async () => {
  const fetchMock = vi.fn().mockImplementation((url: string) => {
    if (url.includes("/api/health")) {
      return Promise.resolve(new Response(JSON.stringify({ status: "ok" })));
    }
    if (url === "/api/claims") {
      return Promise.resolve(new Response(JSON.stringify(mockClaims)));
    }
    if (url.includes("/api/claims/CLM-1001/run")) {
      return Promise.resolve(new Response(JSON.stringify({ status: "ok" })));
    }
    if (url.includes("/api/claims/CLM-1001/activity")) {
      return Promise.resolve(
        new Response(
          JSON.stringify([
            {
              id: 1,
              claim_id: "CLM-1001",
              timestamp: "2026-06-24T10:00:00Z",
              action: "Evaluating",
            },
          ]),
        ),
      );
    }
    if (url.includes("/api/claims/CLM-1001")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            ...mockClaims[0],
            status: "decided",
            decision: "approved",
            payout: 420.0,
          }),
        ),
      );
    }
    return Promise.resolve(new Response(JSON.stringify({})));
  });
  vi.stubGlobal("fetch", fetchMock);

  render(<App />);
  await screen.findByText("CLM-1001");
  fireEvent.click(screen.getByText("CLM-1001"));

  const runBtn = await screen.findByRole("button", { name: "Run Agent" });
  fireEvent.click(runBtn);

  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith("/api/claims/CLM-1001/run", {
      method: "POST",
    });
  });
});

it("handles handler sign-off for high-value claims", async () => {
  const fetchMock = vi.fn().mockImplementation((url: string) => {
    if (url.includes("/api/health")) {
      return Promise.resolve(new Response(JSON.stringify({ status: "ok" })));
    }
    if (url === "/api/claims") {
      return Promise.resolve(new Response(JSON.stringify(mockClaims)));
    }
    if (url.includes("/api/claims/CLM-1003/sign-off")) {
      return Promise.resolve(
        new Response(JSON.stringify({ signed_off: true })),
      );
    }
    if (url.includes("/api/claims/CLM-1003/pay")) {
      return Promise.resolve(new Response(JSON.stringify({ paid: true })));
    }
    if (url.includes("/api/claims/CLM-1003/activity")) {
      return Promise.resolve(
        new Response(
          JSON.stringify([
            {
              id: 1,
              claim_id: "CLM-1003",
              timestamp: "2026-06-25T10:00:00Z",
              action: "Signed off",
            },
          ]),
        ),
      );
    }
    if (url.includes("/api/claims/CLM-1003")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            ...mockClaims[1],
            status: "decided",
            signed_off: true,
            paid: true,
          }),
        ),
      );
    }
    return Promise.resolve(new Response(JSON.stringify({})));
  });
  vi.stubGlobal("fetch", fetchMock);

  render(<App />);
  await screen.findByText("CLM-1003");
  fireEvent.click(screen.getByText("CLM-1003"));

  // Switch to supervisor role to enable sign-off
  const roleSelect = screen.getByRole("combobox", { name: "Role" });
  fireEvent.change(roleSelect, { target: { value: "supervisor" } });

  const signoffBtn = await screen.findByRole("button", {
    name: "Sign off & Pay",
  });
  fireEvent.click(signoffBtn);

  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith("/api/claims/CLM-1003/sign-off", {
      method: "POST",
      headers: { "X-Handler-Role": "supervisor" },
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/claims/CLM-1003/pay",
      expect.any(Object),
    );
  });
});

it("opens and closes the agent instructions modal", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string) => {
      if (url.includes("/api/health")) {
        return Promise.resolve(new Response(JSON.stringify({ status: "ok" })));
      }
      if (url === "/api/claims") {
        return Promise.resolve(new Response(JSON.stringify([])));
      }
      if (url.includes("/api/instructions")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({ instructions: "Special instructions text" }),
          ),
        );
      }
      return Promise.resolve(new Response(JSON.stringify({})));
    }),
  );

  render(<App />);
  const instructionsBtn = screen.getByRole("button", {
    name: "Agent Instructions",
  });
  fireEvent.click(instructionsBtn);

  expect(await screen.findByText("Special instructions text")).toBeDefined();

  const closeBtn = screen.getByRole("button", { name: "Close" });
  fireEvent.click(closeBtn);

  await waitFor(() => {
    expect(screen.queryByText("Special instructions text")).toBeNull();
  });
});

it("runs the agent on all claims from the queue view", async () => {
  let runCalled = false;
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string) => {
      if (url.includes("/api/health")) {
        return Promise.resolve(new Response(JSON.stringify({ status: "ok" })));
      }
      if (url.includes("/api/claims/CLM-1001/run")) {
        runCalled = true;
        return Promise.resolve(new Response(JSON.stringify({})));
      }
      if (url.includes("/api/claims")) {
        return Promise.resolve(new Response(JSON.stringify(mockClaims)));
      }
      return Promise.resolve(new Response(JSON.stringify({})));
    }),
  );

  render(<App />);
  const runAllBtn = await screen.findByRole("button", {
    name: "Run Agent on All Claims",
  });
  fireEvent.click(runAllBtn);
  await waitFor(() => {
    expect(runCalled).toBe(true);
  });
});

it("opens and closes new claim modal from queue view", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string) => {
      if (url.includes("/api/health")) {
        return Promise.resolve(new Response(JSON.stringify({ status: "ok" })));
      }
      if (url.includes("/api/claims")) {
        return Promise.resolve(new Response(JSON.stringify(mockClaims)));
      }
      return Promise.resolve(new Response(JSON.stringify({})));
    }),
  );

  render(<App />);
  const newClaimBtn = await screen.findByRole("button", {
    name: "+ New Claim",
  });
  fireEvent.click(newClaimBtn);
  expect(await screen.findByText("Submit New Claim")).toBeDefined();

  const cancelBtn = screen.getByRole("button", { name: "Cancel" });
  fireEvent.click(cancelBtn);
  await waitFor(() => {
    expect(screen.queryByText("Submit New Claim")).toBeNull();
  });
});

it("opens and closes upload csv modal from queue view", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string) => {
      if (url.includes("/api/health")) {
        return Promise.resolve(new Response(JSON.stringify({ status: "ok" })));
      }
      if (url.includes("/api/claims")) {
        return Promise.resolve(new Response(JSON.stringify(mockClaims)));
      }
      return Promise.resolve(new Response(JSON.stringify({})));
    }),
  );

  render(<App />);
  const uploadCsvBtn = await screen.findByRole("button", {
    name: "Upload CSV",
  });
  fireEvent.click(uploadCsvBtn);
  expect(await screen.findByText("Bulk Claims CSV Upload")).toBeDefined();

  const doneBtn = screen.getByRole("button", { name: "Done" });
  fireEvent.click(doneBtn);
  await waitFor(() => {
    expect(screen.queryByText("Bulk Claims CSV Upload")).toBeNull();
  });
});
