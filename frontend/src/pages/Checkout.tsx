import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Lock, Truck, Banknote, CreditCard, Check, Plus, ShieldCheck } from "lucide-react";
import { storeApi } from "@/services/store";
import { errorCode, errorMessage } from "@/services/api";
import { Alert, Button, Checkbox, EmptyState, Input, Money, PageSpinner, Spinner, Textarea } from "@/components/ui";
import { AddressFields, addressSchema, emptyAddress } from "@/components/forms/AddressForm";
import { TotalsBreakdown } from "@/components/product/TotalsBreakdown";
import { CouponBox } from "@/components/product/CouponBox";
import { useAuth } from "@/features/auth";
import { useCart } from "@/features/cart";
import { usePayment } from "@/features/payments";
import { useToast } from "@/features/toast";
import { useDebounce } from "@/hooks/useDebounce";
import { useSeo } from "@/hooks/useSeo";
import { date, uuid } from "@/utils/format";
import { PIN_RE } from "@/utils/india";
import { cn } from "@/utils/cn";
import { useQueryClient } from "@tanstack/react-query";

const buildSchema = (needShip: boolean, needBill: boolean) => z.object({
  email: z.string().email("Enter a valid email address").optional().or(z.literal("")),
  ship: needShip ? addressSchema : z.any(),
  billing_same: z.boolean(),
  bill: needBill ? addressSchema : z.any(),
  gstin: z.string().trim().toUpperCase().regex(/^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/, "Enter a valid 15-character GSTIN").optional().or(z.literal("")),
  save_address: z.boolean(),
  note: z.string().max(500).optional(),
});
type Values = z.infer<ReturnType<typeof buildSchema>>;

function Step({ n, title, done, children, aside }: { n: number; title: string; done?: boolean; children: React.ReactNode; aside?: React.ReactNode }) {
  return (
    <section className="card p-5 sm:p-7" aria-labelledby={`step-${n}`}>
      <div className="mb-5 flex items-center gap-3">
        <span className={cn("flex h-8 w-8 items-center justify-center rounded-full border text-sm tabular", done ? "border-leaf bg-leaf text-white" : "border-gold-300 text-gold-700")}>
          {done ? <Check className="h-4 w-4" /> : n}
        </span>
        <h2 id={`step-${n}`} className="flex-1 text-[22px]">{title}</h2>
        {aside}
      </div>
      {children}
    </section>
  );
}

export default function Checkout() {
  useSeo({ title: "Checkout", noindex: true });
  const { user, ready } = useAuth();
  const { cart, isLoading } = useCart();
  const nav = useNavigate();
  const toast = useToast();
  const qc = useQueryClient();
  const { pay, modal } = usePayment();
  const idemKey = useRef(uuid());
  const placedRef = useRef(false);
  const [addressId, setAddressId] = useState<number | "new" | null>(null);
  const [methodId, setMethodId] = useState<number | undefined>();
  const [payment, setPayment] = useState<"razorpay" | "cod">("razorpay");
  const [placing, setPlacing] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const addresses = useQuery({ queryKey: ["addresses"], queryFn: storeApi.addresses, enabled: !!user });
  useEffect(() => {
    if (addresses.data && addressId === null) {
      const def = addresses.data.find((a) => a.is_default_shipping) ?? addresses.data[0];
      setAddressId(def ? def.id : "new");
    }
    if (!user && ready) setAddressId("new");
  }, [addresses.data, user, ready]); // eslint-disable-line react-hooks/exhaustive-deps

  const needShipRef = useRef(true);
  const form = useForm<Values>({
    resolver: ((values: any, ctx: any, opts: any) => zodResolver(buildSchema(needShipRef.current, !values.billing_same))(values, ctx, opts)) as any,
    defaultValues: { email: "", ship: { ...emptyAddress, full_name: user?.full_name ?? "", phone: user?.phone ?? "" }, billing_same: true, bill: { ...emptyAddress }, gstin: "", save_address: true, note: "" },
  });
  needShipRef.current = addressId === "new";
  const billingSame = form.watch("billing_same");
  const typedPin = form.watch("ship.pin_code");
  const email = form.watch("email");
  const selected = typeof addressId === "number" ? addresses.data?.find((a) => a.id === addressId) : undefined;
  const pin = selected?.pin_code ?? (PIN_RE.test(typedPin ?? "") ? typedPin : undefined);
  const dPin = useDebounce(pin, 300);
  const dEmail = useDebounce(email, 500);

  const quote = useQuery({
    queryKey: ["quote", dPin, methodId, payment, cart?.totals.grand_total, cart?.totals.coupon?.code, cart?.item_count, user?.id, dEmail],
    queryFn: () => storeApi.validateCheckout({ pin_code: dPin, shipping_method_id: methodId, payment_method: payment, email: user ? undefined : dEmail || undefined }),
    enabled: !!cart && cart.items.length > 0,
    placeholderData: (p) => p,
  });
  const q = quote.data;
  const methods = q?.delivery?.methods ?? [];
  useEffect(() => {
    if (methods.length && !methods.some((m) => m.id === methodId)) setMethodId(methods[0].id);
  }, [methods, methodId]);
  useEffect(() => {
    if (q && payment === "cod" && !q.cod_available) setPayment("razorpay");
  }, [q?.cod_available]); // eslint-disable-line react-hooks/exhaustive-deps
  // A changed cart is a new purchase intent → new idempotency key.
  useEffect(() => { idemKey.current = uuid(); }, [cart?.item_count, cart?.totals.grand_total]);

  const totals = q?.totals ?? cart?.totals;
  const blocking = (q?.issues ?? cart?.issues ?? []).filter((i) => i.code !== "price_changed");
  const serviceable = q?.delivery ? q.delivery.serviceable : true;

  const placeOrder = form.handleSubmit(async (v) => {
    setServerError(null);
    if (!user && !v.email) { form.setError("email", { message: "Enter your email for order updates" }); return; }
    if (addressId !== "new" && !selected) { setServerError("Choose a delivery address"); return; }
    setPlacing(true);
    try {
      const body: Record<string, unknown> = {
        email: user ? undefined : v.email,
        payment_method: payment,
        shipping_method_id: methodId,
        billing_same_as_shipping: v.billing_same,
        customer_note: v.note || undefined,
        gstin: v.gstin || undefined,
        coupon_code: cart?.totals.coupon?.applied ? cart.totals.coupon.code : undefined,
      };
      if (addressId === "new") { body.shipping_address = v.ship; body.save_address = !!user && v.save_address; } else body.shipping_address_id = addressId;
      if (!v.billing_same) body.billing_address = v.bill;
      const { order } = await storeApi.checkout(body, idemKey.current);
      placedRef.current = true;
      const refreshCart = () => { qc.invalidateQueries({ queryKey: ["cart"] }); qc.invalidateQueries({ queryKey: ["addresses"] }); };
      const key = order.order_key;
      if (order.payment_method === "cod") {
        refreshCart();
        nav(`/payment/${order.order_number}?status=placed${key ? `&key=${key}` : ""}`, { replace: true });
        return;
      }
      const r = await pay(order.order_number, key);
      refreshCart();
      const k = r.orderKey ?? key;
      nav(`/payment/${r.orderNumber}?status=${r.status}${k ? `&key=${k}` : ""}${r.status === "failed" ? `&msg=${encodeURIComponent(r.message)}` : ""}`, { replace: true });
    } catch (e) {
      const code = errorCode(e);
      setServerError(errorMessage(e));
      if (code === "cart_invalid" || code === "insufficient_stock") qc.invalidateQueries({ queryKey: ["cart"] });
      toast(errorMessage(e), "error");
    } finally {
      setPlacing(false);
    }
  }, () => {
    setServerError("Please complete the highlighted fields.");
    window.scrollTo({ top: 0, behavior: "smooth" });
  });

  const contactDone = !!user || /.+@.+\..+/.test(email ?? "");
  const addressDone = addressId !== "new" ? !!selected : PIN_RE.test(typedPin ?? "");

  if (isLoading || !ready) return <>{modal}<PageSpinner /></>;
  if ((!cart || cart.items.length === 0) && !placedRef.current) return <EmptyState title="Your bag is empty" body="Add something you love, then come back to check out." action={<Button onClick={() => nav("/")}>Continue shopping</Button>} />;

  return (
    <div className="container-site pb-10 pt-8">
      {modal}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-[36px] sm:text-[44px]">Checkout</h1>
        <p className="flex items-center gap-2 text-sm text-kajal-500"><Lock className="h-4 w-4 text-gold-600" />Secure checkout — prices are recalculated on our server</p>
      </div>
      <form onSubmit={placeOrder} noValidate className="mt-8 grid gap-8 lg:grid-cols-[1fr_400px]">
        <div className="space-y-6">
          {serverError && <Alert tone="error">{serverError}</Alert>}
          {blocking.length > 0 && <Alert tone="error">{blocking.map((i) => <p key={i.item_id + i.code}>{i.message}</p>)}<Link to="/cart" className="mt-1 inline-block link-underline">Update your bag</Link></Alert>}

          <Step n={1} title="Contact" done={contactDone}>
            {user ? (
              <p className="text-[15px] text-kajal-700">Ordering as <strong className="font-medium">{user.full_name}</strong> ({user.email})</p>
            ) : (
              <div className="grid gap-4 sm:grid-cols-[1fr_auto] sm:items-end">
                <Input label="Email for order updates" type="email" autoComplete="email" {...form.register("email")} error={form.formState.errors.email?.message} required />
                <p className="pb-3 text-sm text-kajal-500">Have an account? <Link to="/login?next=/checkout" className="link-underline">Log in</Link></p>
              </div>
            )}
          </Step>

          <Step n={2} title="Delivery address" done={addressDone}>
            {user && (addresses.data?.length ?? 0) > 0 && (
              <div className="mb-5 grid gap-3 sm:grid-cols-2" role="radiogroup" aria-label="Saved addresses">
                {addresses.data!.map((a) => (
                  <label key={a.id} className={cn("cursor-pointer rounded-2xl border p-4 text-sm transition", addressId === a.id ? "border-kajal ring-1 ring-kajal" : "border-kajal-300/50 hover:border-gold-500")}>
                    <input type="radio" name="addr" className="sr-only" checked={addressId === a.id} onChange={() => setAddressId(a.id)} />
                    <span className="flex items-center justify-between"><span className="font-medium">{a.full_name}</span>{a.label && <span className="rounded-full bg-ivory-200 px-2 py-0.5 text-xs text-kajal-500">{a.label}</span>}</span>
                    <span className="mt-1 block leading-6 text-kajal-500">{a.line1}{a.line2 ? `, ${a.line2}` : ""}, {a.city}, {a.state} {a.pin_code}</span>
                    <span className="block text-kajal-500">{a.phone}</span>
                  </label>
                ))}
                <button type="button" onClick={() => setAddressId("new")}
                  className={cn("flex min-h-[110px] items-center justify-center gap-2 rounded-2xl border border-dashed text-sm", addressId === "new" ? "border-kajal text-kajal" : "border-kajal-300 text-kajal-500 hover:border-gold-500")}>
                  <Plus className="h-4 w-4" />Use a new address
                </button>
              </div>
            )}
            {addressId === "new" && (
              <>
                <AddressFields form={form as any} prefix="ship." />
                {user && <Checkbox className="mt-4" label="Save this address to my account" {...form.register("save_address")} />}
              </>
            )}
            {q?.delivery && !q.delivery.serviceable && <Alert tone="error" className="mt-4">{q.delivery.message} Try a different address.</Alert>}
            <div className="mt-5 border-t border-gold-200/50 pt-5">
              <Checkbox label="Billing address is the same as delivery" {...form.register("billing_same")} />
              {!billingSame && <div className="mt-4"><AddressFields form={form as any} prefix="bill." /></div>}
              <details className="mt-4 text-sm">
                <summary className="cursor-pointer text-kajal-500 hover:text-kajal">Need a GST invoice for your business?</summary>
                <Input className="mt-3 max-w-xs" label="GSTIN" placeholder="22AAAAA0000A1Z5" {...form.register("gstin")} error={form.formState.errors.gstin?.message} />
              </details>
            </div>
          </Step>

          <Step n={3} title="Delivery method" done={!!methodId && !!pin}>
            {!pin ? <p className="text-[15px] text-kajal-500">Enter your PIN code above to see delivery options and dates.</p>
              : quote.isFetching && !methods.length ? <Spinner />
              : (
                <div className="space-y-3" role="radiogroup" aria-label="Delivery method">
                  {methods.map((m) => (
                    <label key={m.id} className={cn("flex cursor-pointer items-start gap-4 rounded-2xl border p-4 transition", methodId === m.id ? "border-kajal ring-1 ring-kajal" : "border-kajal-300/50 hover:border-gold-500")}>
                      <input type="radio" name="method" className="mt-1 accent-[#2A1A1F]" checked={methodId === m.id} onChange={() => setMethodId(m.id)} />
                      <Truck className="mt-0.5 h-5 w-5 shrink-0 text-gold-600" aria-hidden />
                      <span className="flex-1">
                        <span className="flex justify-between gap-3"><span className="font-medium">{m.name}</span><span className="tabular">{Number(m.charge) ? <Money value={m.charge} /> : <span className="text-leaf">Free</span>}</span></span>
                        <span className="mt-0.5 block text-sm text-kajal-500">Arrives {date(m.delivery_from, "day")} – {date(m.delivery_to, "day")} · {m.carrier}</span>
                        <span className="block text-xs text-kajal-400">Dispatches by {date(m.dispatch_date, "day")}{m.free_shipping_threshold ? ` · free above ₹${Number(m.free_shipping_threshold).toLocaleString("en-IN")}` : ""}</span>
                      </span>
                    </label>
                  ))}
                </div>
              )}
          </Step>

          <Step n={4} title="Payment">
            <div className="space-y-3" role="radiogroup" aria-label="Payment method">
              <label className={cn("flex cursor-pointer items-start gap-4 rounded-2xl border p-4", payment === "razorpay" ? "border-kajal ring-1 ring-kajal" : "border-kajal-300/50 hover:border-gold-500")}>
                <input type="radio" name="pay" className="mt-1 accent-[#2A1A1F]" checked={payment === "razorpay"} onChange={() => setPayment("razorpay")} />
                <CreditCard className="mt-0.5 h-5 w-5 shrink-0 text-gold-600" aria-hidden />
                <span><span className="font-medium">Pay online</span><span className="mt-0.5 block text-sm text-kajal-500">UPI, cards, net banking and wallets via Razorpay</span></span>
              </label>
              <label className={cn("flex items-start gap-4 rounded-2xl border p-4", !q?.cod_available ? "cursor-not-allowed opacity-60" : "cursor-pointer", payment === "cod" ? "border-kajal ring-1 ring-kajal" : "border-kajal-300/50 hover:border-gold-500")}>
                <input type="radio" name="pay" className="mt-1 accent-[#2A1A1F]" disabled={!q?.cod_available} checked={payment === "cod"} onChange={() => setPayment("cod")} />
                <Banknote className="mt-0.5 h-5 w-5 shrink-0 text-gold-600" aria-hidden />
                <span><span className="font-medium">Cash on Delivery</span>
                  <span className="mt-0.5 block text-sm text-kajal-500">{q?.cod_available ? `Pay when it arrives · ₹${Number(q.cod_fee)} fee` : q?.cod_unavailable_reason ?? "Enter your PIN code to check availability"}</span></span>
              </label>
            </div>
            <Textarea className="mt-5" label="Order note (optional)" placeholder="Gift message or delivery instructions" rows={2} {...form.register("note")} />
          </Step>
        </div>

        <aside className="lg:sticky lg:top-36 lg:self-start">
          <div className="card p-6">
            <h2 className="text-2xl">Your order</h2>
            <ul className="mt-4 max-h-64 space-y-3 overflow-y-auto pr-1">
              {(cart?.items ?? []).map((it) => (
                <li key={it.id} className="flex gap-3">
                  <div className="relative shrink-0">
                    <img src={it.image ?? ""} alt="" className="h-16 w-12 rounded-lg bg-ivory-200 object-cover" />
                    <span className="absolute -right-1.5 -top-1.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-kajal px-1 text-[11px] tabular text-ivory">{it.quantity}</span>
                  </div>
                  <div className="min-w-0 flex-1 text-sm"><p className="line-clamp-1">{it.product_name}</p><p className="text-kajal-400">{it.variant_name}</p></div>
                  <Money value={it.line_subtotal} className="text-sm" />
                </li>
              ))}
            </ul>
            <div className="mt-5 border-t border-gold-200/50 pt-5"><CouponBox totals={totals!} onChange={() => quote.refetch()} /></div>
            <div className={cn("mt-5 transition-opacity", quote.isFetching && "opacity-60")}>{totals && <TotalsBreakdown totals={totals} codSelected={payment === "cod"} />}</div>
            <Button type="submit" size="lg" block className="mt-6" loading={placing} disabled={blocking.length > 0 || !serviceable || (!!q && !cart?.can_checkout)}>
              {payment === "cod" ? "Place order" : <>Pay <Money value={totals?.grand_total} /></>}
            </Button>
            <p className="mt-3 flex items-start gap-2 text-xs leading-5 text-kajal-400"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" /><span>By placing this order you agree to our <Link to="/pages/terms" className="underline">terms</Link> and <Link to="/pages/return-policy" className="underline">return policy</Link>. Card details are handled by Razorpay and never touch our servers.</span></p>
          </div>
        </aside>
      </form>
    </div>
  );
}
