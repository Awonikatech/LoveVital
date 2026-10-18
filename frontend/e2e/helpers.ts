import { expect, type Page } from "@playwright/test";

export const CUSTOMER = { email: "priya@example.com", password: "Customer@123" };
export const ADMIN = { email: "admin@lovevital.example.com", password: "Admin@12345" };

export async function login(page: Page, who = CUSTOMER) {
  await page.goto("/login");
  await page.getByLabel("Email", { exact: true }).fill(who.email);
  await page.getByLabel("Password", { exact: true }).fill(who.password);
  await page.locator("form").getByRole("button", { name: "Log in" }).click();
  await expect(page).not.toHaveURL(/\/login/);
}

/** Adds an in-stock variant of a product to the bag (picks the first available size if needed). */
export async function addToBag(page: Page, slug: string) {
  await page.goto(`/product/${slug}`);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  const sizes = page.locator("fieldset:has(legend:has-text('Size')) button[aria-pressed]:not([disabled])");
  if (await sizes.count()) await sizes.first().click();
  const added = page.waitForResponse((r) => r.url().includes("/api/v1/cart/items") && r.request().method() === "POST");
  await page.getByRole("button", { name: "Add to bag", exact: true }).first().click();
  expect((await added).status()).toBe(201);
}

export async function payInMockSheet(page: Page, outcome: "success" | "failure" = "success") {
  const sheet = page.getByRole("dialog", { name: "Razorpay test checkout" });
  await expect(sheet).toBeVisible();
  if (outcome === "success") await sheet.getByRole("button", { name: /^Pay ₹/ }).click();
  else await sheet.getByRole("button", { name: "Simulate a declined payment" }).click();
}
