import { expect, test } from "@playwright/test";

const API_KEY =
  process.env.UNDERCOVER_API_KEY ??
  "iz5mGyn3Gvb-79aenJfV1eifk_oQ9pp8nuVNpgl_MEQ";

test.beforeEach(async ({ request }) => {
  await request.post("http://127.0.0.1:8000/api/reset");
});

test("handler creates a new claim via form with immediate agent audit", async ({
  page,
  request,
}) => {
  await page.route("**/api/claims", async (route) => {
    if (route.request().method() === "POST") {
      const body = route.request().postDataJSON() as {
        amount_claimed: number;
        run_agent?: boolean;
      };
      const res = await request.post("http://127.0.0.1:8000/api/claims", {
        data: { ...body, run_agent: false },
      });
      const created = (await res.json()) as Record<string, unknown>;
      const cid = created.claim_id as string;

      if (body.run_agent) {
        await request.post(`http://127.0.0.1:8000/api/claims/${cid}/decision`, {
          headers: { "x-api-key": API_KEY },
          data: {
            decision: "approve",
            payout: body.amount_claimed,
            reason: "Incident verified and covered under policy wording.",
            policy_section: "3. Trip Delay",
          },
        });
        await request.post(`http://127.0.0.1:8000/api/claims/${cid}/pay`, {
          headers: { "x-api-key": API_KEY },
          data: { amount: body.amount_claimed },
        });
      }

      const updated = await request.get(
        `http://127.0.0.1:8000/api/claims/${cid}`,
      );
      await route.fulfill({
        status: 201,
        json: (await updated.json()) as Record<string, unknown>,
      });
    } else {
      await route.continue();
    }
  });

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "UnderCover" })).toBeVisible();

  // Open New Claim Modal
  await page.getByRole("button", { name: "+ New Claim" }).click();
  await expect(
    page.getByRole("heading", { name: "Submit New Claim" }),
  ).toBeVisible();

  // Fill in form
  await page.getByLabel("Incident Location *").fill("Vienna, Austria");
  await page.getByLabel("Amount Claimed ($ USD) *").fill("250.00");
  await page.getByLabel("Summary *").fill("Delayed rail journey");
  await page
    .getByLabel("Customer Story *")
    .fill("Train canceled due to weather condition.");

  // Submit form
  await page.getByRole("button", { name: "Submit Claim" }).click();

  // Verify transition to detail view and audit results
  await expect(page.getByText("Delayed rail journey").first()).toBeVisible();
  await expect(page.getByText("$250.00").first()).toBeVisible();
  await expect(page.getByText("decided").first()).toBeVisible();
  await expect(page.getByText("Ref: 3. Trip Delay")).toBeVisible();

  // Go back to queue and check total count increased
  await page.getByRole("button", { name: "← Back to queue" }).click();
  const allTab = page.getByRole("button", { name: "All Claims", exact: true });
  await expect(allTab.locator(".tab-count")).toHaveText("27");
});

test("handler uploads claims via CSV with immediate batch audit", async ({
  page,
  request,
}) => {
  await page.route("**/api/claims/upload-csv", async (route) => {
    const body = route.request().postDataJSON() as {
      csv_content: string;
      run_agent?: boolean;
    };
    const res = await request.post(
      "http://127.0.0.1:8000/api/claims/upload-csv",
      {
        data: { ...body, run_agent: false },
      },
    );
    const data = (await res.json()) as {
      imported_count: number;
      claims: { claim_id: string; amount_claimed: number }[];
      decided_count: number;
    };

    if (body.run_agent) {
      for (const c of data.claims) {
        await request.post(
          `http://127.0.0.1:8000/api/claims/${c.claim_id}/decision`,
          {
            headers: { "x-api-key": API_KEY },
            data: {
              decision: "approve",
              payout: c.amount_claimed,
              reason: "Bulk claim audited and verified.",
              policy_section: "3. Trip Delay",
            },
          },
        );
      }
      data.decided_count = data.imported_count;
    }
    await route.fulfill({ status: 201, json: data });
  });

  await page.goto("/");

  // Open CSV upload modal
  await page.getByRole("button", { name: "Upload CSV" }).click();
  await expect(
    page.getByRole("heading", { name: "Bulk Claims CSV Upload" }),
  ).toBeVisible();

  // Upload file
  const csvData =
    "policy_id,customer_id,claim_type,incident_date,incident_location,summary,story,amount_claimed\n" +
    'POL-2001,CUS-3001,trip_delay,2026-06-25,"Madrid, Spain","Madrid strike","Missed flight due to rail strike",180.00\n';

  await page.locator("#csv-file-input").setInputFiles({
    name: "import_claims.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(csvData),
  });

  // Verify preview displayed
  await expect(page.getByText("CSV Preview")).toBeVisible();
  await expect(page.getByText("Madrid strike")).toBeVisible();

  // Ingest claims
  await page.getByRole("button", { name: "Upload and Ingest" }).click();
  await expect(
    page.getByText("Successfully imported 1 claim(s)"),
  ).toBeVisible();

  // Close modal
  await page.getByRole("button", { name: "Done" }).click();

  // Verify queue updated with 27 claims
  const allTab = page.getByRole("button", { name: "All Claims", exact: true });
  await expect(allTab.locator(".tab-count")).toHaveText("27");
});
