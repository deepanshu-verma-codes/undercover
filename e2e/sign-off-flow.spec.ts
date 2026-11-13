import { expect, test } from "@playwright/test";

test.beforeEach(async ({ request }) => {
  await request.post("http://127.0.0.1:8000/api/reset");
});

test("high-value claim requires handler sign-off before payout completes", async ({
  page,
  request,
}) => {
  // Pre-set claim CLM-1003 with approval over $1,000 threshold
  await request.post("http://127.0.0.1:8000/api/claims/CLM-1003/decision", {
    data: {
      decision: "approve",
      payout: 1500.0,
      reason:
        "Emergency hospital stay covered under First plan emergency medical.",
      policy_section: "7. Emergency Medical",
    },
  });

  await page.goto("/");
  await page.getByText("CLM-1003").click();

  // Verify status is waiting for sign-off
  await expect(page.getByText("waiting for sign off").first()).toBeVisible();
  await expect(page.getByText("$1500.00", { exact: true })).toBeVisible();
  await expect(
    page.getByText(
      "Payout exceeds $1,000 threshold. Handler sign-off required.",
    ),
  ).toBeVisible();

  // Sign off and pay
  const signoffBtn = page.getByRole("button", { name: "Sign off & Pay" });
  await expect(signoffBtn).toBeVisible();
  await signoffBtn.click();

  // Verify claim transitions to decided
  await expect(page.getByText("decided").first()).toBeVisible();
  await expect(
    page.getByText(
      "Payout exceeds $1,000 threshold. Handler sign-off required.",
    ),
  ).toBeHidden();
});
