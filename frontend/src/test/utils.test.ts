import { describe, expect, it } from "vitest";
import { rupees, plural, date } from "@/utils/format";
import { renderMarkdown } from "@/utils/markdown";

describe("rupees()", () => {
  it("formats whole rupees without paise in Indian grouping", () => {
    expect(rupees("499.00")).toBe("₹499");
    expect(rupees("123456.00")).toBe("₹1,23,456");
  });
  it("keeps paise when present and never uses float drift", () => {
    expect(rupees("1210.55")).toBe("₹1,210.55");
    expect(rupees("0.10")).toBe("₹0.10");
  });
  it("handles empty values", () => {
    expect(rupees(null)).toBe("—");
    expect(rupees("")).toBe("—");
  });
});

describe("helpers", () => {
  it("pluralises", () => {
    expect(plural(1, "item")).toBe("1 item");
    expect(plural(3, "item")).toBe("3 items");
  });
  it("formats ISO dates", () => {
    expect(date("2026-10-18")).toMatch(/18 Oct 2026/);
  });
});

describe("renderMarkdown()", () => {
  it("renders headings, lists and links", () => {
    const html = renderMarkdown("## Title\n- one\n- **two**\n[Policy](/pages/return-policy)");
    expect(html).toContain("<h2>Title</h2>");
    expect(html).toContain("<li><strong>two</strong></li>");
    expect(html).toContain('<a href="/pages/return-policy">Policy</a>');
  });
  it("escapes HTML and blocks javascript: links", () => {
    const html = renderMarkdown('<script>alert(1)</script>\n[x](javascript:alert(1))');
    expect(html).not.toContain("<script>");
    expect(html).toContain("&lt;script&gt;");
    expect(html).not.toContain('href="javascript');
  });
});
