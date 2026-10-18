import { Link, useNavigate } from "react-router-dom";
import { ShoppingBag, Trash2 } from "lucide-react";
import { Button, Drawer, Money, QuantityStepper, Spinner } from "@/components/ui";
import { useCart, useCartUi } from "@/features/cart";
import { FreeShippingMeter } from "@/components/product/FreeShippingMeter";

export function CartDrawer() {
  const { open, setOpen } = useCartUi();
  const { cart, isLoading, update, remove } = useCart();
  const nav = useNavigate();
  const items = cart?.items ?? [];
  const close = () => setOpen(false);

  return (
    <Drawer open={open} onClose={close} title={<>Your bag{cart?.item_count ? <span className="ml-2 text-base text-kajal-400">({cart.item_count})</span> : null}</>}
      footer={items.length > 0 && cart ? (
        <div className="space-y-3">
          <div className="flex items-baseline justify-between">
            <span className="text-kajal-500">Subtotal</span>
            <Money value={cart.totals.grand_total} className="text-xl font-medium" />
          </div>
          {Number(cart.totals.total_savings) > 0 && (
            <p className="text-sm text-kumkum">You save <Money value={cart.totals.total_savings} /> on this order</p>
          )}
          <p className="text-xs text-kajal-400">Inclusive of all taxes. Shipping and coupons are finalised at checkout.</p>
          <div className="grid grid-cols-2 gap-2">
            <Button variant="outline" onClick={() => { close(); nav("/cart"); }}>View bag</Button>
            <Button onClick={() => { close(); nav("/checkout"); }} disabled={!cart.can_checkout}>Checkout</Button>
          </div>
        </div>
      ) : undefined}>
      {isLoading ? (
        <div className="flex justify-center py-16"><Spinner /></div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center px-6 py-16 text-center">
          <div className="arch arch-frame mb-5 flex h-28 w-20 items-end justify-center bg-gradient-to-b from-gold-50 to-blush pb-5 text-gold-600"><ShoppingBag className="h-6 w-6" /></div>
          <p className="font-display text-xl">Your bag is empty</p>
          <p className="mt-1 text-kajal-500">Find something you'll love wearing.</p>
          <Button className="mt-6" onClick={() => { close(); nav("/new-arrivals"); }}>Shop new arrivals</Button>
        </div>
      ) : (
        <div>
          {cart && <div className="border-b border-gold-200/50 px-5 py-4"><FreeShippingMeter totals={cart.totals} /></div>}
          <ul className="divide-y divide-gold-200/40">
            {items.map((it) => {
              const issue = cart?.issues.find((i) => i.item_id === it.id && i.code !== "price_changed");
              return (
                <li key={it.id} className="flex gap-4 px-5 py-4">
                  <Link to={`/product/${it.product_slug}`} onClick={close} className="shrink-0">
                    <img src={it.image ?? ""} alt={it.product_name} className="h-28 w-[88px] rounded-xl bg-ivory-200 object-cover" />
                  </Link>
                  <div className="min-w-0 flex-1">
                    <Link to={`/product/${it.product_slug}`} onClick={close} className="line-clamp-2 text-[15px] leading-snug text-kajal hover:text-gold-700">{it.product_name}</Link>
                    <p className="mt-0.5 text-sm text-kajal-500">{Object.values(it.attributes).join(" · ") || it.variant_name}</p>
                    <div className="mt-1 flex items-baseline gap-2 tabular">
                      <Money value={it.line_subtotal} className="font-medium" />
                      {Number(it.line_mrp) > Number(it.line_subtotal) && <span className="text-sm text-kajal-400 line-through"><Money value={it.line_mrp} /></span>}
                    </div>
                    {issue && <p className="mt-1 text-sm text-kumkum">{issue.message}</p>}
                    <div className="mt-3 flex items-center justify-between">
                      <QuantityStepper size="sm" value={it.quantity} min={it.min_qty} max={Math.max(it.quantity, it.max_qty)} disabled={update.isPending}
                        onChange={(q) => update.mutate({ id: it.id, qty: q })} />
                      <button onClick={() => remove.mutate(it.id)} className="rounded-full p-2 text-kajal-400 hover:bg-ivory-200 hover:text-kumkum" aria-label={`Remove ${it.product_name}`}>
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </Drawer>
  );
}
