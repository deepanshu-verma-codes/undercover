import { expect, test } from "@playwright/test";

test.beforeEach(async ({ request }) => {
  await request.post("http://127.0.0.1:8000/api/reset");
});

test("claim detail view displays full claim information and instructions modal", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByText("CLM-1001").click();

  // Verify claim details
  await expect(
    page.getByRole("heading", { name: "Claim CLM-1001" }),
  ).toBeVisible();
  await expect(
    page.getByText("Flight home canceled by the airline"),
  ).toBeVisible();
  await expect(page.getByText("Customer Story")).toBeVisible();
  await expect(
    page.getByText("My flight home from Rome on June 18 was canceled"),
  ).toBeVisible();

  // Verify items and documents
  await expect(
    page.getByRole("heading", { name: "Items Claimed" }),
  ).toBeVisible();
  await expect(page.getByText("Airport hotel, one night")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Supporting Documents" }),
  ).toBeVisible();
  await expect(
    page.getByText("Meridian Air cancellation notice"),
  ).toBeVisible();

  // Verify policy details and customer history
  await expect(
    page.getByRole("heading", { name: "Policy Details" }),
  ).toBeVisible();
  await expect(page.getByText("Rome, Italy").first()).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Customer History" }),
  ).toBeVisible();
  await expect(page.getByText("Maya Patel").first()).toBeVisible();

  // Instructions modal
  await page.getByRole("button", { name: "Agent Instructions" }).click();
  await expect(
    page.getByRole("heading", { name: "Agent Instructions" }),
  ).toBeVisible();
  await expect(page.getByText("UnderCover Agent")).toBeVisible();
  await page.getByRole("button", { name: "Close" }).click();
  await expect(
    page.getByRole("heading", { name: "Agent Instructions" }),
  ).toBeHidden();

  // Navigate back
  await page.getByRole("button", { name: "← Back to queue" }).click();
  await expect(page.getByPlaceholder("Search claims...")).toBeVisible();
});
