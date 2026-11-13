import { expect, test } from "@playwright/test";

test.beforeEach(async ({ request }) => {
  await request.post("http://127.0.0.1:8000/api/reset");
});

test("queue page displays claims and allows filtering and search", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "UnderCover" })).toBeVisible();
  await expect(page.getByText("Backend: up")).toBeVisible();

  // All 25 claims should be listed
  const rows = page.locator("tbody tr");
  await expect(rows).toHaveCount(25);

  // Search by claim ID
  const searchInput = page.getByPlaceholder("Search claims...");
  await searchInput.fill("CLM-1001");
  await expect(rows).toHaveCount(1);
  await expect(page.getByText("CLM-1001")).toBeVisible();

  // Clear search
  await searchInput.fill("");
  await expect(rows).toHaveCount(25);

  // Filter by Decided (initially 0)
  await page.getByRole("button", { name: "Decided" }).click();
  await expect(
    page.getByText("No claims match the filter criteria."),
  ).toBeVisible();

  // Reset to All Claims
  await page.getByRole("button", { name: "All Claims" }).click();
  await expect(rows).toHaveCount(25);

  // Clicking a claim navigates to details
  await page.getByText("CLM-1001").click();
  await expect(
    page.getByRole("heading", { name: "Claim CLM-1001" }),
  ).toBeVisible();
});
