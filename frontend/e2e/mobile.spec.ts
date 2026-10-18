import { expect, test } from "@playwright/test";
import { addToBag, payInMockSheet } from "./helpers";

test("guest on mobile: declined payment, retry, then success", async ({ page }) => {
  await addToBag(page, "pearl-drop-studs");
  await page.goto("/checkout");
  await page.getByLabel("Email for order updates").fill(`guest+${Date.now()}@example.com`);
  await page.locator("[name='ship.full_name']").fill("Asha Guest");
  await page.locator("[name='ship.phone']").fill("9876512345");
  await page.locator("[name='ship.line1']").fill("22 Park Street");
  await page.locator("[name='ship.pin_code']").fill("700016");
  await page.locator("[name='ship.city']").fill("Kolkata");
  await page.locator("[name='ship.state']").selectOption("West Bengal");
  await expect(page.getByText("Standard Delivery")).toBeVisible();
  await page.locator("form").getByRole("button", { name: /^Pay ₹/ }).click();
  await payInMockSheet(page, "failure");
  await expect(page.getByRole("heading", { name: "Payment not completed" })).toBeVisible();
  await page.getByRole("button", { name: /Retry payment/ }).click();
  await payInMockSheet(page, "success");
  await expect(page.getByRole("heading", { name: /payment received/i })).toBeVisible();
  const width = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(width).toBeLessThanOrEqual(page.viewportSize()!.width);
});
