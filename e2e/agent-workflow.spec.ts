import { expect, test } from "@playwright/test";

test.beforeEach(async ({ request }) => {
  await request.post("http://127.0.0.1:8000/api/reset");
});

test("agent workflow assesses and decides a standard claim", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await page.getByText("CLM-1001").click();

  // Intercept agent run endpoint to simulate deterministic agent evaluation
  await page.route("**/api/claims/CLM-1001/run", async (route) => {
    await request.post("http://127.0.0.1:8000/api/claims/CLM-1001/activity", {
      data: { action: "Reviewing policy wording Section 3" },
    });
    await request.post("http://127.0.0.1:8000/api/claims/CLM-1001/decision", {
      data: {
        decision: "approve",
        payout: 420.0,
        reason:
          "Delay of 19 hours exceeds 6 hour waiting period under Premium plan.",
        policy_section: "3. Trip Delay",
      },
    });
    await request.post("http://127.0.0.1:8000/api/claims/CLM-1001/pay", {
      data: { amount: 420.0 },
    });
    const updated = await request.get(
      "http://127.0.0.1:8000/api/claims/CLM-1001",
    );
    const json = (await updated.json()) as Record<string, unknown>;
    json.agent_reply = "Claim CLM-1001 approved and paid.";
    await route.fulfill({ json });
  });

  await page.getByRole("button", { name: "Run Agent" }).click();

  // Verify Decision Card appears with payout, explanation, and section
  await expect(page.getByText("$420.00")).toBeVisible();
  await expect(
    page.getByText("Delay of 19 hours exceeds 6 hour waiting period"),
  ).toBeVisible();
  await expect(page.getByText("Ref: 3. Trip Delay")).toBeVisible();
  await expect(page.getByText("decided").first()).toBeVisible();
  await expect(
    page.getByText("Reviewing policy wording Section 3"),
  ).toBeVisible();
});
