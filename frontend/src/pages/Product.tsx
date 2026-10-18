import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Heart, MapPin, Ruler, ShieldCheck, Truck, RotateCcw, Banknote, Check } from "lucide-react";
import { storeApi } from "@/services/store";
import { errorMessage } from "@/services/api";
import {
  Alert, Breadcrumbs, Button, EmptyState, ErrorState, Modal, PageSpinner, Price, QuantityStepper, Stars, Tabs, Textarea, Input,
} from "@/components/ui";
import { ProductCard, ProductRail } from "@/components/product/ProductCard";
import { useCart } from "@/features/cart";
import { useWishlist } from "@/features/wishlist";
import { useAuth } from "@/features/auth";
import { useToast } from "@/features/toast";
import { useSeo } from "@/hooks/useSeo";
import { date, plural, rupees } from "@/utils/format";
import { cn } from "@/utils/cn";
import type { DeliveryEstimate, ProductDetail, Variant } from "@/types";

const PIN_KEY = "swk_pin";

function Gallery({ p, variant }: { p: ProductDetail; variant?: Variant }) {
  const images = useMemo(() => {
    const vImgs = variant ? p.images.filter((i) => i.variant_id === variant.id) : [];
    const rest = p.images.filter((i) => !vImgs.includes(i) && (i.variant_id === null || !variant || p.options.length === 0));
    return [...vImgs, ...rest];
  }, [p, variant]);
  const [idx, setIdx] = useState(0);
  useEffect(() => setIdx(0), [variant?.id]);
  const cur = images[idx] ?? images[0];
  return (
    <div className="flex flex-col-reverse gap-4 md:flex-row">
      <div className="flex gap-3 overflow-x-auto scrollbar-none md:w-20 md:flex-col" role="tablist" aria-label="Product images">
        {images.map((im, i) => (
          <button key={im.id} role="tab" aria-selected={i === idx} onClick={() => setIdx(i)} aria-label={`Show image ${i + 1}`}
            className={cn("w-16 shrink-0 overflow-hidden rounded-xl border-2 bg-ivory-200 md:w-20", i === idx ? "border-gold-500" : "border-transparent opacity-80 hover:opacity-100")}>
            <img src={im.url} alt="" className="aspect-[4/5] w-full object-cover" />
          </button>
        ))}
      </div>
      <div className="relative flex-1 overflow-hidden rounded-3xl bg-ivory-200">
        {cur && <img src={cur.url} alt={cur.alt} className="aspect-[4/5] w-full object-cover" />}
        {p.discount_pct > 0 && <span className="absolute left-4 top-4 rounded-full bg-kumkum px-3 py-1 text-sm font-medium text-white">{p.discount_pct}% off</span>}
      </div>
    </div>
  );
}

function DeliveryChecker({ p, price }: { p: ProductDetail; price: string }) {
  const [pin, setPin] = useState(() => localStorage.getItem(PIN_KEY) ?? "");
  const [res, setRes] = useState<DeliveryEstimate | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const check = async (value = pin) => {
    if (!/^[1-9][0-9]{5}$/.test(value)) { setErr("Enter a valid 6-digit PIN code"); setRes(null); return; }
    setLoading(true); setErr(null);
    try {
      const r = await storeApi.estimate(value, p.slug, price);
      setRes(r);
      try { localStorage.setItem(PIN_KEY, value); } catch { /* ignore */ }
    } catch (e) { setErr(errorMessage(e)); } finally { setLoading(false); }
  };
  useEffect(() => { if (pin.length === 6) check(pin); }, [p.slug]); // eslint-disable-line react-hooks/exhaustive-deps
  const threshold = Number(p.free_shipping_threshold);
  return (
    <div className="rounded-2xl border border-gold-200/60 bg-white p-5">
      <p className="flex items-center gap-2 text-[15px] font-medium"><MapPin className="h-4 w-4 text-gold-600" />Check delivery</p>
      <form className="mt-3 flex gap-2" onSubmit={(e) => { e.preventDefault(); check(); }}>
        <label htmlFor="pin" className="sr-only">PIN code</label>
        <input id="pin" inputMode="numeric" maxLength={6} value={pin} onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))} placeholder="Enter PIN code" className="input h-10" />
        <Button type="submit" variant="outline" size="sm" className="h-10" loading={loading}>Check</Button>
      </form>
      {err && <p className="field-error">{err}</p>}
      {res && (
        <div className="mt-3 space-y-1.5 text-sm">
          {res.serviceable ? (
            <>
              <p className="flex items-start gap-2 text-leaf"><Check className="mt-0.5 h-4 w-4 shrink-0" /><span><strong className="font-medium">{res.message}</strong>{res.city ? ` to ${res.city}` : ""}</span></p>
              {res.methods.slice(1).map((m) => <p key={m.id} className="pl-6 text-kajal-500">{m.name}: by {date(m.delivery_to, "day")} ({Number(m.charge) ? rupees(m.charge) : "free"})</p>)}
              <p className="pl-6 text-kajal-500">{res.cod_available && p.is_cod_available ? "Cash on Delivery available" : "Cash on Delivery not available for this PIN"}</p>
            </>
          ) : <p className="text-kumkum">{res.message}</p>}
        </div>
      )}
      <ul className="mt-4 space-y-2 border-t border-gold-200/50 pt-4 text-sm text-kajal-700">
        <li className="flex gap-2"><Truck className="h-4 w-4 shrink-0 text-gold-600" />{Number(price) >= threshold ? "Free shipping on this item" : `Free shipping on orders above ${rupees(threshold)}; otherwise ₹79`}</li>
        <li className="flex gap-2"><RotateCcw className="h-4 w-4 shrink-0 text-gold-600" />{p.is_returnable ? `${p.return_window_days}-day easy returns & replacement` : "Not eligible for return (hygiene / made to order)"}</li>
        {p.is_cod_available && <li className="flex gap-2"><Banknote className="h-4 w-4 shrink-0 text-gold-600" />Cash on Delivery available (₹49 fee)</li>}
        <li className="flex gap-2"><ShieldCheck className="h-4 w-4 shrink-0 text-gold-600" />Secure payments via Razorpay — UPI, cards, net banking, wallets</li>
      </ul>
    </div>
  );
}

function Reviews({ p }: { p: ProductDetail }) {
  const { user } = useAuth();
  const toast = useToast();
  const qc = useQueryClient();
  const [sort, setSort] = useState("recent");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ rating: 5, title: "", body: "" });
  const { data } = useQuery({ queryKey: ["reviews", p.slug, sort], queryFn: () => storeApi.reviews(p.slug, 1, sort) });
  const submit = useMutation({
    mutationFn: () => storeApi.addReview(p.slug, form),
    onSuccess: () => { toast("Thanks — your review is live."); setOpen(false); qc.invalidateQueries({ queryKey: ["reviews", p.slug] }); qc.invalidateQueries({ queryKey: ["product", p.slug] }); },
    onError: (e) => toast(errorMessage(e), "error"),
  });
  return (
    <section id="reviews" className="border-t border-gold-200/50 pt-14" aria-labelledby="reviews-h">
      <div className="grid gap-10 lg:grid-cols-[300px_1fr]">
        <div>
          <h2 id="reviews-h" className="text-[30px]">Customer reviews</h2>
          {data && data.count > 0 ? (
            <>
              <div className="mt-4 flex items-end gap-3"><span className="font-display text-5xl leading-none">{data.average.toFixed(1)}</span><div><Stars value={data.average} size={16} /><p className="text-sm text-kajal-500">{plural(data.count, "review")}</p></div></div>
              <div className="mt-5 space-y-1.5">
                {Object.entries(data.distribution).map(([star, n]) => (
                  <div key={star} className="flex items-center gap-3 text-sm">
                    <span className="w-6 tabular text-kajal-500">{star}★</span>
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-ivory-300"><div className="h-full rounded-full bg-gold-500" style={{ width: `${data.count ? (n / data.count) * 100 : 0}%` }} /></div>
                    <span className="w-6 text-right tabular text-kajal-400">{n}</span>
                  </div>
                ))}
              </div>
            </>
          ) : <p className="mt-3 text-kajal-500">No reviews yet. Be the first to share how it looks on you.</p>}
          <Button variant="outline" className="mt-6" onClick={() => (user ? setOpen(true) : toast("Log in to write a review", "info"))}>Write a review</Button>
        </div>
        <div>
          {data && data.items.length > 0 && (
            <>
              <div className="mb-4 flex justify-end">
                <select aria-label="Sort reviews" value={sort} onChange={(e) => setSort(e.target.value)} className="input h-9 w-44 py-1 text-sm">
                  <option value="recent">Most recent</option><option value="highest">Highest rated</option><option value="lowest">Lowest rated</option>
                </select>
              </div>
              <ul className="divide-y divide-gold-200/50">
                {data.items.map((r) => (
                  <li key={r.id} className="py-5">
                    <div className="flex items-center gap-3"><Stars value={r.rating} /><span className="text-[15px] font-medium">{r.title}</span></div>
                    {r.body && <p className="mt-2 max-w-2xl leading-7 text-kajal-700">{r.body}</p>}
                    <p className="mt-2 text-sm text-kajal-400">{r.author} · {date(r.created_at)}{r.verified && <span className="ml-2 text-leaf">Verified purchase</span>}</p>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      </div>
      <Modal open={open} onClose={() => setOpen(false)} title="Write a review"
        footer={<><Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button><Button loading={submit.isPending} onClick={() => submit.mutate()}>Post review</Button></>}>
        <fieldset>
          <legend className="label">Your rating</legend>
          <div className="flex gap-1">
            {[1, 2, 3, 4, 5].map((n) => (
              <button key={n} type="button" onClick={() => setForm({ ...form, rating: n })} aria-label={`${n} star${n > 1 ? "s" : ""}`} aria-pressed={form.rating === n}
                className={cn("text-3xl", n <= form.rating ? "text-gold-500" : "text-gold-200")}>★</button>
            ))}
          </div>
        </fieldset>
        <Input className="mt-4" label="Headline" value={form.title} maxLength={150} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="e.g. Looks stunning in person" />
        <Textarea className="mt-4" label="Your review" value={form.body} maxLength={3000} onChange={(e) => setForm({ ...form, body: e.target.value })} placeholder="How did it look, feel and fit?" />
      </Modal>
    </section>
  );
}

export default function ProductPage() {
  const { slug = "" } = useParams();
  const nav = useNavigate();
  const { data: p, isLoading, isError, error, refetch } = useQuery({ queryKey: ["product", slug], queryFn: () => storeApi.product(slug) });
  const { add } = useCart();
  const { ids, toggle } = useWishlist();
  const [sel, setSel] = useState<Record<string, string>>({});
  const [qty, setQty] = useState(1);
  const [tab, setTab] = useState<"details" | "specs" | "care" | "returns">("details");
  const [chart, setChart] = useState(false);
  const [needOption, setNeedOption] = useState<string | null>(null);

  useEffect(() => {
    if (!p) return;
    const def = p.variants.find((v) => v.is_default && v.available > 0) ?? p.variants.find((v) => v.available > 0) ?? p.variants[0];
    const init: Record<string, string> = {};
    p.options.forEach((o) => {
      if (o.values.length === 1 || o.code === "color") init[o.code] = def?.attributes[o.code] ?? o.values[0].value;
    });
    setSel(init);
    setQty(p.min_order_qty);
  }, [p?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const variant = useMemo(() => {
    if (!p) return undefined;
    if (p.options.length === 0) return p.variants[0];
    if (p.options.some((o) => !sel[o.code])) return undefined;
    return p.variants.find((v) => p.options.every((o) => v.attributes[o.code] === sel[o.code]));
  }, [p, sel]);
  const displayVariant = variant ?? p?.variants.find((v) => Object.entries(sel).every(([k, val]) => v.attributes[k] === val)) ?? p?.variants[0];

  const ld = p ? {
    "@context": "https://schema.org/", "@type": "Product", name: p.name, sku: p.sku, brand: { "@type": "Brand", name: p.brand },
    description: p.short_description, image: p.images.map((i) => window.location.origin + i.url), category: p.category.name,
    ...(p.rating_count ? { aggregateRating: { "@type": "AggregateRating", ratingValue: p.rating_avg, reviewCount: p.rating_count } } : {}),
    offers: { "@type": "AggregateOffer", priceCurrency: "INR", lowPrice: Math.min(...p.variants.map((v) => Number(v.price))), highPrice: Math.max(...p.variants.map((v) => Number(v.price))),
      offerCount: p.variants.length, availability: p.in_stock ? "https://schema.org/InStock" : "https://schema.org/OutOfStock" },
  } : null;
  useSeo({ title: p?.seo_title, description: p?.seo_description, jsonLd: ld });

  if (isLoading) return <PageSpinner />;
  if (isError || !p) {
    const status = (error as any)?.response?.status;
    return status === 404
      ? <EmptyState title="This piece isn't available" body="It may have sold out or been retired." action={<Link to="/new-arrivals" className="link-underline">See new arrivals</Link>} />
      : <div className="container-site py-24"><ErrorState message="We couldn't load this product." onRetry={() => refetch()} /></div>;
  }

  const isAvailable = (code: string, value: string) =>
    p.variants.some((v) => v.attributes[code] === value && v.available > 0 && Object.entries(sel).every(([k, sv]) => k === code || v.attributes[k] === sv));
  const maxQty = variant ? Math.min(p.max_order_qty, variant.available) : p.max_order_qty;

  const doAdd = async (buyNow = false) => {
    const missing = p.options.find((o) => !sel[o.code]);
    if (missing) { setNeedOption(missing.code); return; }
    if (!variant) return;
    await add.mutateAsync({ variantId: variant.id, qty, silent: buyNow });
    if (buyNow) nav("/checkout");
  };
  const saved = ids.has(p.id);
  const crumbs = [{ label: "Home", to: "/" }, ...p.breadcrumbs.map((b) => ({ label: b.name, to: `/category/${b.slug}` })), { label: p.name }];
  const spec = p.specifications;

  return (
    <div className="container-site pb-10 pt-6">
      <Breadcrumbs items={crumbs} />
      <div className="mt-6 grid gap-10 lg:grid-cols-[1.1fr_1fr] lg:gap-14">
        <div className="lg:sticky lg:top-36 lg:self-start"><Gallery p={p} variant={displayVariant} /></div>
        <div>
          <p className="text-sm text-gold-700">{p.brand} · {p.category.name}</p>
          <h1 className="mt-2 text-[32px] leading-tight sm:text-[40px]">{p.name}</h1>
          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-kajal-500">
            {p.rating_count > 0 && <a href="#reviews" className="flex items-center gap-1.5 hover:text-kajal"><Stars value={p.rating_avg} /><span className="tabular">{p.rating_avg.toFixed(1)} · {plural(p.rating_count, "review")}</span></a>}
            <span>SKU <span className="tabular text-kajal-700">{displayVariant?.sku ?? p.sku}</span></span>
          </div>

          <div className="mt-6 border-t border-gold-200/50 pt-6">
            {displayVariant && <Price price={displayVariant.price} mrp={displayVariant.mrp} discount={displayVariant.discount_pct} size="lg" />}
            {displayVariant && Number(displayVariant.savings) > 0 && <p className="mt-2 text-[15px] text-kumkum">You save {rupees(displayVariant.savings)}</p>}
            <p className="mt-1 text-sm text-kajal-500">MRP inclusive of all taxes (GST {Number(p.tax_rate)}%{p.hsn_code ? `, HSN ${p.hsn_code}` : ""})</p>
            {p.badges.length > 0 && <div className="mt-3 flex flex-wrap gap-2">{p.badges.map((b) => <span key={b} className="rounded-full bg-kajal px-3 py-1 text-xs text-gold-200">{b}</span>)}</div>}
          </div>

          {p.short_description && <p className="mt-5 max-w-xl leading-7 text-kajal-700">{p.short_description}</p>}

          <div className="mt-6 space-y-6">
            {p.options.map((o) => (
              <fieldset key={o.code} aria-describedby={needOption === o.code ? `need-${o.code}` : undefined}>
                <div className="mb-2.5 flex items-center justify-between">
                  <legend className="text-[15px]"><span className="text-kajal-500">{o.name}:</span> <span className="font-medium">{sel[o.code] ?? "Select"}</span></legend>
                  {o.code === "size" && p.size_chart && (
                    <button type="button" onClick={() => setChart(true)} className="flex items-center gap-1.5 text-sm link-underline"><Ruler className="h-4 w-4" />Size guide</button>
                  )}
                </div>
                <div className="flex flex-wrap gap-2.5">
                  {o.values.map((v) => {
                    const on = sel[o.code] === v.value;
                    const avail = isAvailable(o.code, v.value);
                    return o.display_type === "swatch" ? (
                      <button key={v.slug} type="button" aria-pressed={on} title={v.value + (avail ? "" : " — sold out")}
                        onClick={() => { setSel({ ...sel, [o.code]: v.value }); setNeedOption(null); }}
                        className={cn("relative flex h-11 items-center gap-2 rounded-full border py-1 pl-1 pr-4 text-sm transition", on ? "border-kajal ring-1 ring-kajal" : "border-kajal-300/60 hover:border-gold-500", !avail && "opacity-50")}>
                        <span className="h-8 w-8 rounded-full border border-kajal/10" style={{ background: v.hex ?? "#ddd" }} />{v.value}
                      </button>
                    ) : (
                      <button key={v.slug} type="button" aria-pressed={on} disabled={!avail}
                        onClick={() => { setSel({ ...sel, [o.code]: v.value }); setNeedOption(null); }}
                        className={cn("h-11 min-w-12 rounded-full border px-4 text-sm transition", on ? "border-kajal bg-kajal text-ivory" : "border-kajal-300/60 hover:border-gold-500",
                          !avail && "cursor-not-allowed text-kajal-300 line-through hover:border-kajal-300/60")}>
                        {v.value}
                      </button>
                    );
                  })}
                </div>
                {needOption === o.code && <p id={`need-${o.code}`} className="field-error">Please select a {o.name.toLowerCase()}</p>}
              </fieldset>
            ))}
          </div>

          <div className="mt-6 text-sm">
            {variant ? (
              variant.available <= 0 ? <p className="text-kumkum">Sold out in this option</p>
                : variant.stock_status === "low_stock" ? <p className="text-[#8A5A00]">Hurry — only {variant.available} left</p>
                : <p className="text-leaf">In stock, ready to dispatch in {plural(Math.max(1, p.processing_days), "business day")}</p>
            ) : !p.in_stock ? <p className="text-kumkum">Currently sold out</p> : null}
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <QuantityStepper value={qty} min={p.min_order_qty} max={Math.max(p.min_order_qty, maxQty)} onChange={setQty} disabled={!!variant && variant.available <= 0} />
            <Button size="lg" className="min-w-[180px] flex-1" onClick={() => doAdd(false)} loading={add.isPending && !add.variables?.silent}
              disabled={(!!variant && variant.available <= 0) || !p.in_stock}>Add to bag</Button>
            <button onClick={() => toggle(p.id)} aria-pressed={saved} aria-label={saved ? "Remove from wishlist" : "Save to wishlist"}
              className="flex h-[52px] w-[52px] items-center justify-center rounded-full border border-kajal-300/60 hover:border-kumkum"><Heart className={cn("h-5 w-5", saved && "fill-kumkum text-kumkum")} /></button>
          </div>
          <Button size="lg" variant="gold" block className="mt-3" onClick={() => doAdd(true)} disabled={(!!variant && variant.available <= 0) || !p.in_stock}>Buy now</Button>
          {p.max_order_qty < 10 && <p className="mt-2 text-xs text-kajal-400">Limit {p.max_order_qty} per order.</p>}

          <div className="mt-8"><DeliveryChecker p={p} price={displayVariant?.price ?? p.price} /></div>

          <div className="mt-10">
            <Tabs value={tab} onChange={setTab} tabs={[{ value: "details", label: "Details" }, { value: "specs", label: "Specifications" }, { value: "care", label: "Care" }, { value: "returns", label: "Returns & refunds" }]} />
            <div className="pt-5 text-[15px] leading-7 text-kajal-700">
              {tab === "details" && <div className="space-y-3 whitespace-pre-line">{p.description}</div>}
              {tab === "specs" && (
                <dl className="divide-y divide-gold-200/50">
                  {Object.entries(spec).map(([k, v]) => (<div key={k} className="grid grid-cols-[150px_1fr] gap-4 py-2.5"><dt className="text-kajal-500">{k}</dt><dd>{v}</dd></div>))}
                  {displayVariant?.weight_grams && <div className="grid grid-cols-[150px_1fr] gap-4 py-2.5"><dt className="text-kajal-500">Weight</dt><dd>{Number(displayVariant.weight_grams)} g</dd></div>}
                  <div className="grid grid-cols-[150px_1fr] gap-4 py-2.5"><dt className="text-kajal-500">SKU</dt><dd className="tabular">{displayVariant?.sku}</dd></div>
                </dl>
              )}
              {tab === "care" && <p>{p.care_instructions}</p>}
              {tab === "returns" && (
                <div className="space-y-2">
                  {p.is_returnable ? <p>Return or exchange within <strong className="font-medium">{p.return_window_days} days</strong> of delivery from <Link to="/account/orders" className="link-underline">My orders</Link>. Items must be unused with tags and packaging intact.</p>
                    : <p>This item can't be returned for hygiene reasons or because it's made to order. Damaged or incorrect items are always replaced.</p>}
                  <p>Refunds go back to your original payment method within 5–7 business days of the return being received. COD orders are refunded by bank transfer or UPI.</p>
                  <Link to="/pages/return-policy" className="link-underline">Read the full policy</Link>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {p.frequently_bought_together.length > 0 && (
        <section className="mt-20 rounded-3xl border border-gold-200/60 bg-white p-6 sm:p-10">
          <h2 className="text-[28px]">Complete the look</h2>
          <p className="mt-1 text-kajal-500">Pieces customers often buy together with this one.</p>
          <div className="mt-6 grid grid-cols-2 gap-6 md:grid-cols-4">
            <div className="hidden md:block"><ProductCard p={p} /></div>
            {p.frequently_bought_together.slice(0, 3).map((x) => <ProductCard key={x.id} p={x} />)}
          </div>
        </section>
      )}

      {p.related.length > 0 && (
        <section className="mt-20">
          <h2 className="mb-6 text-[28px]">You may also like</h2>
          <ProductRail products={p.related.slice(0, 4)} />
        </section>
      )}

      <div className="mt-20"><Reviews p={p} /></div>

      <Modal open={chart} onClose={() => setChart(false)} title="Size guide" size="lg">
        {p.size_chart && (
          <div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm tabular">
                <thead><tr className="border-b border-gold-200">{p.size_chart.columns.map((c) => <th key={c} className="px-3 py-2 font-medium">{c}{c !== p.size_chart!.columns[0] ? ` (${p.size_chart!.unit})` : ""}</th>)}</tr></thead>
                <tbody>{p.size_chart.rows.map((r) => <tr key={r[0]} className="border-b border-gold-200/40">{r.map((c, i) => <td key={i} className={cn("px-3 py-2", i === 0 && "font-medium")}>{c}</td>)}</tr>)}</tbody>
              </table>
            </div>
            {p.size_chart.note && <Alert className="mt-4">{p.size_chart.note}</Alert>}
          </div>
        )}
      </Modal>
    </div>
  );
}
