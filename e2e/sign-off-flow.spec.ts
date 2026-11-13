import { expect, test } from "@playwright/test";

const API_KEY =
  process.env.UNDERCOVER_API_KEY ??
  "iz5mGyn3Gvb-79aenJfV1eifk_oQ9pp8nuVNpgl_MEQ";

test.beforeEach(async ({ request }) => {
  await request.post("http://127.0.0.1:8000/api/reset");
});

test("high-value claim requires handler sign-off before payout completes", async ({
  page,
  request,
}) => {
  // Pre-set claim CLM-1003 with approval over $1,000 threshold
  await request.post("http://127.0.0.1:8000/api/claims/CLM-1003/decision", {
    headers: { "x-api-key": API_KEY },
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

  // Verify regular handler cannot sign off
  const signoffBtn = page.getByRole("button", { name: "Sign off & Pay" });
  await expect(signoffBtn).toBeVisible();
  await expect(signoffBtn).toBeDisabled();

  // Switch to supervisor role to authorize sign-off
  await page.getByRole("combobox", { name: "Role" }).selectOption("supervisor");
  await expect(signoffBtn).toBeEnabled();
  await signoffBtn.click();

  // Verify claim transitions to decided
  await expect(page.getByText("decided").first()).toBeVisible();
  await expect(
    page.getByText(
      "Payout exceeds $1,000 threshold. Handler sign-off required.",
    ),
  ).toBeHidden();
});
