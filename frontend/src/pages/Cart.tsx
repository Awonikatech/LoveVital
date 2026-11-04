import { Link, useNavigate } from "react-router-dom";
import { ShoppingBag, Trash2, Heart, Lock } from "lucide-react";
import { Alert, Button, EmptyState, Money, PageSpinner, QuantityStepper, Breadcrumbs } from "@/components/ui";
import { useCart } from "@/features/cart";
import { useWishlist } from "@/features/wishlist";
import { useAuth } from "@/features/auth";
import { TotalsBreakdown } from "@/components/product/TotalsBreakdown";
import { CouponBox } from "@/components/product/CouponBox";
import { FreeShippingMeter } from "@/components/product/FreeShippingMeter";
import { useSeo } from "@/hooks/useSeo";
import { plural } from "@/utils/format";

export default function CartPage() {
  useSeo({ title: "Your bag", noindex: true });
  const { cart, isLoading, update, remove } = useCart();
  const { toggle, ids } = useWishlist();
  const { user } = useAuth();
  const nav = useNavigate();
  if (isLoading) return <PageSpinner />;
  if (!cart || cart.items.length === 0) {
    return <EmptyState icon={<ShoppingBag className="h-6 w-6" />} title="Your bag is empty" body="Pieces you add will wait for you here." action={<Button onClick={() => nav("/best-sellers")}>Shop best sellers</Button>} />;
  }
  const blocking = cart.issues.filter((i) => i.code !== "price_changed");
  const priceNotes = cart.issues.filter((i) => i.code === "price_changed");
  return (
    <div className="container-site pb-10 pt-6">
      <Breadcrumbs items={[{ label: "Home", to: "/" }, { label: "Bag" }]} />
      <h1 className="mt-5 text-[36px] sm:text-[44px]">Your bag <span className="text-2xl text-kajal-400">({plural(cart.item_count, "item")})</span></h1>
      <div className="mt-8 grid gap-10 lg:grid-cols-[1fr_380px]">
        <div>
          <div className="mb-5 rounded-2xl border border-gold-200/60 bg-white px-5 py-4"><FreeShippingMeter totals={cart.totals} /></div>
          {blocking.length > 0 && <Alert tone="error" className="mb-4">{blocking.map((i) => <p key={i.item_id + i.code}>{i.message}</p>)}<p className="mt-1">Update these items to continue to checkout.</p></Alert>}
          {priceNotes.length > 0 && <Alert tone="info" className="mb-4">{priceNotes.map((i) => <p key={i.item_id}>{i.message}</p>)}</Alert>}
          <ul className="divide-y divide-gold-200/50 border-y border-gold-200/50">
            {cart.items.map((it) => (
              <li key={it.id} className="flex gap-4 py-6 sm:gap-6">
                <Link to={`/product/${it.product_slug}`} className="shrink-0"><img src={it.image ?? ""} alt={it.product_name} className="h-36 w-28 rounded-2xl bg-ivory-200 object-cover sm:h-44 sm:w-36" /></Link>
                <div className="flex min-w-0 flex-1 flex-col">
                  <div className="flex justify-between gap-4">
                    <div className="min-w-0">
                      <Link to={`/product/${it.product_slug}`} className="text-[17px] leading-snug hover:text-gold-700">{it.product_name}</Link>
                      <p className="mt-1 text-sm text-kajal-500">{Object.entries(it.attributes).map(([k, v]) => `${k}: ${v}`).join(" · ") || it.variant_name}</p>
                      <p className="mt-0.5 text-xs text-kajal-400">SKU {it.sku}</p>
                    </div>
                    <div className="shrink-0 text-right tabular">
                      <Money value={it.line_total} className="text-[17px] font-medium" />
                      {Number(it.line_mrp) > Number(it.line_total) && <p className="text-sm text-kajal-400 line-through"><Money value={it.line_mrp} /></p>}
                      {(Number(it.promo_discount) > 0 || Number(it.coupon_discount) > 0) && <p className="text-xs text-kumkum">incl. offers</p>}
                    </div>
                  </div>
                  {it.available > 0 && it.available <= 5 && <p className="mt-2 text-sm text-[#8A5A00]">Only {it.available} left</p>}
                  <div className="mt-auto flex flex-wrap items-center gap-4 pt-4">
                    <QuantityStepper value={it.quantity} min={it.min_qty} max={Math.max(it.quantity, it.max_qty)} disabled={update.isPending} onChange={(q) => update.mutate({ id: it.id, qty: q })} />
                    <button onClick={() => remove.mutate(it.id)} className="flex items-center gap-1.5 text-sm text-kajal-500 hover:text-kumkum"><Trash2 className="h-4 w-4" />Remove</button>
                    {user && !ids.has(it.product_id) && (
                      <button onClick={() => { toggle(it.product_id); remove.mutate(it.id); }} className="flex items-center gap-1.5 text-sm text-kajal-500 hover:text-kajal"><Heart className="h-4 w-4" />Move to wishlist</button>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
          <Link to="/shop" className="mt-6 inline-block link-underline text-[15px]">Continue shopping</Link>
        </div>
        <aside className="lg:sticky lg:top-36 lg:self-start">
          <div className="card p-6">
            <h2 className="text-2xl">Order summary</h2>
            <div className="mt-5"><CouponBox totals={cart.totals} /></div>
            <div className="mt-6"><TotalsBreakdown totals={cart.totals} /></div>
            <Button size="lg" block className="mt-6" disabled={!cart.can_checkout} onClick={() => nav("/checkout")}><Lock className="h-4 w-4" />Checkout securely</Button>
            {!user && <p className="mt-3 text-center text-sm text-kajal-500"><Link to="/login?next=/checkout" className="link-underline">Log in</Link> for faster checkout, or continue as a guest.</p>}
          </div>
          <p className="mt-4 text-center text-xs text-kajal-400">Final shipping and COD charges are confirmed at checkout for your PIN code.</p>
        </aside>
      </div>
    </div>
  );
}
