import { expect, test } from "@playwright/test";
import { addToBag, ADMIN, login, payInMockSheet } from "./helpers";

test.describe("browsing", () => {
  test("home, category filters, sorting and search", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await page.goto("/category/earrings?sort=price_asc");
    await expect(page.getByRole("heading", { name: "Earrings", level: 1 })).toBeVisible();
    const prices = await page.locator("article .tabular > span:first-child").allInnerTexts();
    const nums = prices.map((p) => Number(p.replace(/[^\d.]/g, "")));
    expect(nums).toEqual([...nums].sort((a, b) => a - b));
    await page.getByRole("button", { name: /In stock only/ }).or(page.getByLabel("In stock only")).first().click();
    await expect(page).toHaveURL(/in_stock=true/);

    await page.goto("/search?q=jhumki");
    await expect(page.getByText(/Jhumka/).first()).toBeVisible();
    await page.goto("/search?q=neckalce");
    await expect(page.getByText("Did you mean")).toBeVisible();
  });

  test("product page shows MRP, discount, variants and delivery estimate", async ({ page }) => {
    await page.goto("/product/gold-plated-traditional-earrings");
    await expect(page.getByText("₹499").first()).toBeVisible();
    await expect(page.getByText("50% off").first()).toBeVisible();
    await expect(page.getByText(/SKU/).first()).toBeVisible();
    await page.getByPlaceholder("Enter PIN code").fill("560038");
    await page.getByRole("button", { name: "Check" }).click();
    await expect(page.getByText(/Delivery by/)).toBeVisible();
  });
});

test.describe("purchase", () => {
  test("logged-in customer pays online, then cancels for a refund", async ({ page }) => {
    await login(page);
    await addToBag(page, "emerald-block-print-cotton-kurti");
    await page.goto("/cart");
    await expect(page.getByRole("heading", { name: /Your bag/ })).toBeVisible();
    const remove = page.getByRole("button", { name: /Remove coupon/ });
    if (await remove.isVisible()) await remove.click();
    await page.locator("#coupon").fill("SUMMER25");
    await page.getByRole("button", { name: "Apply" }).click();
    await expect(page.getByText(/has expired/)).toBeVisible();
    await page.getByRole("button", { name: "Checkout securely" }).click();
    await expect(page.getByText("Standard Delivery")).toBeVisible();
    await page.locator("form").getByRole("button", { name: /^Pay ₹/ }).click();
    await payInMockSheet(page);
    await expect(page.getByRole("heading", { name: /payment received/i })).toBeVisible();
    await page.getByRole("link", { name: "View order details" }).click();
    await page.getByRole("button", { name: "Cancel order" }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Cancel order" }).click();
    await expect(page.getByText("Refunded").first()).toBeVisible();
  });

  test("cash on delivery order is placed without online payment", async ({ page }) => {
    await login(page);
    await addToBag(page, "pearl-drop-studs");
    await page.goto("/checkout");
    await expect(page.getByText("Standard Delivery")).toBeVisible();
    await page.getByLabel(/Cash on Delivery/).check();
    await page.getByRole("button", { name: "Place order" }).click();
    await expect(page.getByRole("heading", { name: "Order placed" })).toBeVisible();
  });
});

test.describe("admin", () => {
  test("admin sees dashboard and can open an order", async ({ page }) => {
    await login(page, ADMIN);
    await page.goto("/admin");
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
    await page.goto("/admin/orders");
    await page.locator("table tbody tr").first().click();
    await expect(page.getByText("Status history")).toBeVisible();
  });
});
