import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ProductCard } from "@/components/product/ProductCard";
import type { ProductCard as P } from "@/types";

vi.mock("@/features/wishlist", () => ({ useWishlist: () => ({ ids: new Set<number>(), toggle: vi.fn() }) }));
vi.mock("@/features/cart", () => ({ useCart: () => ({ add: { mutate: vi.fn(), isPending: false } }) }));

const product: P = {
  id: 1, slug: "gold-plated-traditional-earrings", name: "Gold-Plated Traditional Earrings", sku: "JW-EAR-001", brand: "LoveVital",
  product_type: "jewellery", category: { id: 2, name: "Earrings", slug: "earrings" }, image: "/a.svg", hover_image: null,
  mrp: "999.00", price: "499.00", discount_pct: 50, rating_avg: 4.3, rating_count: 3, in_stock: true, stock_status: "in_stock",
  is_new_arrival: false, is_bestseller: true, is_featured: true, badges: [], variant_count: 1, default_variant_id: 10, colors: [],
};

function wrap(ui: React.ReactNode) {
  return render(<QueryClientProvider client={new QueryClient()}><MemoryRouter>{ui}</MemoryRouter></QueryClientProvider>);
}

describe("<ProductCard>", () => {
  it("shows name, SKU, MRP, sale price, discount and rating", () => {
    wrap(<ProductCard p={product} />);
    expect(screen.getByRole("heading", { name: product.name })).toBeInTheDocument();
    expect(screen.getByText("JW-EAR-001")).toBeInTheDocument();
    expect(screen.getByText("₹499")).toBeInTheDocument();
    expect(screen.getByText("₹999")).toBeInTheDocument();
    expect(screen.getByText("50% off")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /4.3 out of 5/ })).toBeInTheDocument();
    expect(screen.getByText("Bestseller")).toBeInTheDocument();
  });
  it("marks sold-out products and hides quick add", () => {
    wrap(<ProductCard p={{ ...product, in_stock: false, stock_status: "out_of_stock" }} />);
    expect(screen.getByText("Sold out")).toBeInTheDocument();
    expect(screen.queryByText("Add to bag")).not.toBeInTheDocument();
  });
  it("links to the product page and offers a wishlist toggle", () => {
    wrap(<ProductCard p={product} />);
    expect(screen.getAllByRole("link", { name: product.name })[0]).toHaveAttribute("href", "/product/gold-plated-traditional-earrings");
    expect(screen.getByLabelText(`Save ${product.name} to wishlist`)).toBeInTheDocument();
  });
});
