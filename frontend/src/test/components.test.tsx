import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Price, QuantityStepper, StatusBadge, Pagination } from "@/components/ui";
import { FreeShippingMeter } from "@/components/product/FreeShippingMeter";
import { TotalsBreakdown } from "@/components/product/TotalsBreakdown";
import type { Totals } from "@/types";

const totals = (over: Partial<Totals> = {}): Totals => ({
  subtotal_mrp: "1998.00", subtotal: "998.00", item_discount: "1000.00", promotion_discount: "0.00", coupon_discount: "100.00",
  shipping_charge: "79.00", cod_charge: "0.00", tax_total: "28.15", grand_total: "977.00", total_savings: "1100.00",
  free_shipping: false, free_shipping_threshold: "999.00", amount_to_free_shipping: "101.00", applied_promotions: [],
  coupon: { code: "EARRING100", applied: true, message: "EARRING100 applied." }, messages: [], tax_inclusive: true, ...over,
});

describe("<Price>", () => {
  it("shows sale price, struck MRP and discount", () => {
    render(<Price price="499.00" mrp="999.00" discount={50} />);
    expect(screen.getByText("₹499")).toBeInTheDocument();
    expect(screen.getByText("₹999")).toHaveClass("line-through", { exact: false });
    expect(screen.getByText("50% off")).toBeInTheDocument();
  });
  it("hides MRP when there is no discount", () => {
    render(<Price price="499.00" mrp="499.00" />);
    expect(screen.queryByText(/MRP/)).not.toBeInTheDocument();
  });
});

describe("<QuantityStepper>", () => {
  it("respects min and max", async () => {
    const onChange = vi.fn();
    render(<QuantityStepper value={1} min={1} max={2} onChange={onChange} />);
    expect(screen.getByLabelText("Decrease quantity")).toBeDisabled();
    await userEvent.click(screen.getByLabelText("Increase quantity"));
    expect(onChange).toHaveBeenCalledWith(2);
  });
});

describe("<StatusBadge>", () => {
  it("humanises statuses", () => {
    render(<StatusBadge status="out_for_delivery" />);
    expect(screen.getByText("Out for delivery")).toBeInTheDocument();
  });
});

describe("<Pagination>", () => {
  it("marks the current page and moves forward", async () => {
    const onChange = vi.fn();
    render(<Pagination page={2} pages={5} onChange={onChange} />);
    expect(screen.getByRole("button", { name: "2" })).toHaveAttribute("aria-current", "page");
    await userEvent.click(screen.getByLabelText("Next page"));
    expect(onChange).toHaveBeenCalledWith(3);
  });
});

describe("<FreeShippingMeter>", () => {
  it("tells the shopper how much more to add", () => {
    render(<FreeShippingMeter totals={totals()} />);
    expect(screen.getByText(/more for free shipping/)).toBeInTheDocument();
    expect(screen.getByText("₹101")).toBeInTheDocument();
  });
  it("celebrates once unlocked", () => {
    render(<FreeShippingMeter totals={totals({ free_shipping: true, amount_to_free_shipping: "0.00" })} />);
    expect(screen.getByText(/unlocked/)).toBeInTheDocument();
  });
});

describe("<TotalsBreakdown>", () => {
  it("lists every server-computed charge and the payable total", () => {
    render(<TotalsBreakdown totals={totals()} />);
    expect(screen.getByText("Total MRP")).toBeInTheDocument();
    expect(screen.getByText("Coupon EARRING100")).toBeInTheDocument();
    expect(screen.getByText("₹79")).toBeInTheDocument();
    expect(screen.getByText("₹977")).toBeInTheDocument();
    expect(screen.getByText(/saving/)).toBeInTheDocument();
  });
  it("shows the COD fee when cash on delivery is chosen", () => {
    render(<TotalsBreakdown totals={totals({ cod_charge: "49.00", grand_total: "1026.00" })} codSelected />);
    expect(screen.getByText("Cash on Delivery fee")).toBeInTheDocument();
    expect(screen.getByText("₹49")).toBeInTheDocument();
  });
});
