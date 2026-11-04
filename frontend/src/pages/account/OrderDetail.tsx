import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Truck, ExternalLink } from "lucide-react";
import { storeApi } from "@/services/store";
import { downloadFile, errorMessage } from "@/services/api";
import { Alert, Breadcrumbs, Button, ErrorState, Modal, Money, PageSpinner, Select, StatusBadge, Textarea } from "@/components/ui";
import { OrderTimeline, ShipmentEvents } from "@/components/product/OrderTimeline";
import { usePayment } from "@/features/payments";
import { useToast } from "@/features/toast";
import { date, isPositive } from "@/utils/format";
import { useSeo } from "@/hooks/useSeo";
import type { OrderDetail as OD } from "@/types";

const CANCEL_REASONS = ["Ordered by mistake", "Found a better price", "Delivery is taking too long", "Want to change size or colour", "Other"];
const RETURN_REASONS: [string, string][] = [["size_issue", "Size or fit issue"], ["damaged", "Item arrived damaged"], ["wrong_item", "Received the wrong item"], ["quality_issue", "Quality not as expected"], ["not_as_described", "Looks different from photos"], ["changed_mind", "Changed my mind"], ["other", "Other"]];

export function OrderBody({ o, onChanged, guestKey }: { o: OD; onChanged: (o: OD) => void; guestKey?: string }) {
  const toast = useToast();
  const { pay, modal } = usePayment();
  const [cancelOpen, setCancelOpen] = useState(false);
  const [reason, setReason] = useState(CANCEL_REASONS[0]);
  const [returnOpen, setReturnOpen] = useState(false);
  const [ret, setRet] = useState<{ type: string; reason: string; details: string; qty: Record<number, number> }>({ type: "return", reason: "size_issue", details: "", qty: {} });
  const [paying, setPaying] = useState(false);

  const cancel = useMutation({
    mutationFn: () => storeApi.cancelOrder(o.order_number, reason, guestKey),
    onSuccess: (r) => { toast(r.message); setCancelOpen(false); onChanged(r.order); },
    onError: (e) => toast(errorMessage(e), "error"),
  });
  const doReturn = useMutation({
    mutationFn: () => storeApi.requestReturn(o.order_number, {
      return_type: ret.type, reason: ret.reason, details: ret.details || undefined,
      items: Object.entries(ret.qty).filter(([, q]) => q > 0).map(([id, q]) => ({ order_item_id: Number(id), quantity: q })),
    }),
    onSuccess: (r) => { toast(r.message); setReturnOpen(false); onChanged(r.order); },
    onError: (e) => toast(errorMessage(e), "error"),
  });
  const retryPay = async () => {
    setPaying(true);
    try {
      const r = await pay(o.order_number, guestKey ?? o.order_key);
      if (r.status === "paid") toast("Payment received — thank you!");
      else if (r.status === "failed") toast(r.message, "error");
      onChanged(await storeApi.order(o.order_number, guestKey ?? o.order_key));
    } catch (e) { toast(errorMessage(e), "error"); } finally { setPaying(false); }
  };

  const t = o.totals;
  const returnable = o.items.filter((i) => i.quantity - i.returned_quantity > 0);
  return (
    <div className="space-y-6">
      {modal}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-3"><h2 className="text-[28px] tabular">{o.order_number}</h2><StatusBadge status={o.status} label={o.status_label} /></div>
          <p className="mt-1 text-sm text-kajal-500">Placed {date(o.placed_at, "long")} · {o.payment_method === "cod" ? "Cash on Delivery" : "Paid online"} · payment {o.payment_status.replace(/_/g, " ")}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {o.can_pay && <Button onClick={retryPay} loading={paying}>Pay <Money value={o.grand_total} /></Button>}
          {o.invoice_available && (
            <Button variant="outline" size="sm" onClick={() => downloadFile(`/orders/${o.order_number}/invoice${guestKey ? `?key=${guestKey}` : ""}`, `LoveVital-Invoice-${o.order_number}.pdf`).catch((e) => toast(errorMessage(e), "error"))}>
              <Download className="h-4 w-4" />Invoice
            </Button>
          )}
          {(o.can_cancel || o.can_request_cancel) && <Button variant="outline" size="sm" onClick={() => setCancelOpen(true)}>{o.can_cancel ? "Cancel order" : "Request cancellation"}</Button>}
          {o.can_return && !guestKey && <Button variant="outline" size="sm" onClick={() => setReturnOpen(true)}>Return or replace</Button>}
        </div>
      </div>

      {o.status === "payment_pending" && <Alert tone="warning">Payment hasn't been completed for this order yet{o.payments.at(-1)?.error_description ? ` (${o.payments.at(-1)!.error_description})` : ""}. Your items are held for you — complete payment to confirm.</Alert>}
      {o.cancellation_reason && ["cancelled", "cancellation_requested", "refund_initiated", "refunded"].includes(o.status) && <Alert tone="info">Cancellation reason: {o.cancellation_reason}</Alert>}

      {!["payment_pending"].includes(o.status) && <div className="card p-6"><OrderTimeline order={o} /></div>}

      {o.shipments.map((s) => (
        <div key={s.id} className="card p-6">
          <div className="mb-5 flex flex-wrap items-center gap-3">
            <Truck className="h-5 w-5 text-gold-600" />
            <p className="flex-1 text-[15px]"><span className="font-medium">{s.courier_name}</span> · AWB <span className="tabular">{s.tracking_number}</span></p>
            {s.tracking_number && <Link to={`/track/${s.tracking_number}`} className="flex items-center gap-1 text-sm link-underline">Track shipment<ExternalLink className="h-3.5 w-3.5" /></Link>}
          </div>
          <ShipmentEvents events={s.events} />
        </div>
      ))}

      <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
        <div className="card p-6">
          <h3 className="text-xl">Items</h3>
          <ul className="mt-3 divide-y divide-gold-200/40">
            {o.items.map((it) => (
              <li key={it.id} className="flex gap-4 py-4">
                <img src={it.image_url ?? ""} alt="" className="h-24 w-20 rounded-xl bg-ivory-200 object-cover" />
                <div className="flex-1 text-sm">
                  {it.product_slug ? <Link to={`/product/${it.product_slug}`} className="text-[15px] hover:text-gold-700">{it.product_name}</Link> : <p className="text-[15px]">{it.product_name}</p>}
                  <p className="text-kajal-500">{it.variant_name} · SKU {it.sku}</p>
                  <p className="text-kajal-500">Qty {it.quantity}{it.returned_quantity ? ` · ${it.returned_quantity} returned` : ""}</p>
                  {o.can_review && it.product_slug && <Link to={`/product/${it.product_slug}#reviews`} className="mt-1 inline-block link-underline">Write a review</Link>}
                </div>
                <div className="text-right text-sm tabular"><Money value={it.line_total} className="text-[15px]" />{Number(it.unit_mrp) > Number(it.unit_price) && <p className="text-kajal-400 line-through"><Money value={String(Number(it.unit_mrp) * it.quantity)} /></p>}</div>
              </li>
            ))}
          </ul>
        </div>
        <div className="space-y-6">
          <div className="card p-6 text-[15px]">
            <h3 className="text-xl">Payment summary</h3>
            <dl className="mt-3 space-y-1.5">
              <div className="flex justify-between"><dt className="text-kajal-500">Total MRP</dt><dd><Money value={t.subtotal_mrp} /></dd></div>
              {isPositive(t.item_discount) && <div className="flex justify-between text-kumkum"><dt>Discount</dt><dd><Money value={t.item_discount} negative /></dd></div>}
              {isPositive(t.promotion_discount) && <div className="flex justify-between text-kumkum"><dt>Offers</dt><dd><Money value={t.promotion_discount} negative /></dd></div>}
              {isPositive(t.coupon_discount) && <div className="flex justify-between text-kumkum"><dt>Coupon {t.coupon_code}</dt><dd><Money value={t.coupon_discount} negative /></dd></div>}
              <div className="flex justify-between"><dt className="text-kajal-500">Shipping</dt><dd>{isPositive(t.shipping_charge) ? <Money value={t.shipping_charge} /> : "Free"}</dd></div>
              {isPositive(t.cod_charge) && <div className="flex justify-between"><dt className="text-kajal-500">COD fee</dt><dd><Money value={t.cod_charge} /></dd></div>}
              <div className="flex justify-between border-t border-gold-200/60 pt-2 text-lg"><dt>Total</dt><dd><Money value={t.grand_total} /></dd></div>
              <p className="text-right text-xs text-kajal-400">Includes GST <Money value={t.tax_total} /></p>
              {isPositive(t.refunded_total) && <div className="flex justify-between text-leaf"><dt>Refunded</dt><dd><Money value={t.refunded_total} /></dd></div>}
            </dl>
            {o.refunds.length > 0 && (
              <ul className="mt-4 space-y-1 border-t border-gold-200/50 pt-3 text-sm">
                {o.refunds.map((r) => <li key={r.id} className="flex justify-between"><span>Refund · {date(r.created_at)}</span><span className="flex items-center gap-2"><Money value={r.amount} /><StatusBadge status={r.status} /></span></li>)}
              </ul>
            )}
          </div>
          {o.shipping_address && (
            <div className="card p-6 text-[15px] leading-6">
              <h3 className="text-xl">Delivery address</h3>
              <p className="mt-2">{o.shipping_address.full_name}<br />{o.shipping_address.line1}{o.shipping_address.line2 && `, ${o.shipping_address.line2}`}<br />{o.shipping_address.city}, {o.shipping_address.state} {o.shipping_address.pin_code}<br />{o.shipping_address.phone}</p>
              <p className="mt-3 text-sm text-kajal-500">{o.shipping_method_name}{o.estimated_delivery_date && !o.delivered_at ? ` · Estimated by ${date(o.estimated_delivery_date)}` : ""}{o.delivered_at ? ` · Delivered ${date(o.delivered_at)}` : ""}</p>
            </div>
          )}
        </div>
      </div>

      <Modal open={cancelOpen} onClose={() => setCancelOpen(false)} title={o.can_cancel ? "Cancel this order?" : "Request cancellation"} size="sm"
        footer={<><Button variant="ghost" onClick={() => setCancelOpen(false)}>Keep order</Button><Button variant="danger" loading={cancel.isPending} onClick={() => cancel.mutate()}>{o.can_cancel ? "Cancel order" : "Send request"}</Button></>}>
        <Select label="Reason" value={reason} onChange={(e) => setReason(e.target.value)} options={CANCEL_REASONS.map((r) => ({ value: r, label: r }))} />
        <p className="mt-4 text-sm text-kajal-500">{o.payment_status === "paid" ? "A full refund will go back to your original payment method within 5–7 business days." : "No payment has been taken for this order."}{!o.can_cancel && " Your order is already packed, so our team will confirm the cancellation."}</p>
      </Modal>

      <Modal open={returnOpen} onClose={() => setReturnOpen(false)} title="Return or replace items" size="lg"
        footer={<><Button variant="ghost" onClick={() => setReturnOpen(false)}>Close</Button><Button loading={doReturn.isPending} disabled={!Object.values(ret.qty).some((q) => q > 0)} onClick={() => doReturn.mutate()}>Submit request</Button></>}>
        <div className="flex gap-2">
          {[["return", "Refund"], ["replacement", "Replacement"]].map(([v, l]) => (
            <button key={v} className={`chip ${ret.type === v ? "chip-active" : ""}`} onClick={() => setRet({ ...ret, type: v })}>{l}</button>
          ))}
        </div>
        <ul className="mt-4 divide-y divide-gold-200/40">
          {returnable.map((it) => (
            <li key={it.id} className="flex items-center gap-3 py-3">
              <img src={it.image_url ?? ""} alt="" className="h-14 w-11 rounded-lg object-cover" />
              <span className="flex-1 text-sm">{it.product_name}<span className="block text-kajal-400">{it.variant_name}</span></span>
              <label className="sr-only" htmlFor={`rq-${it.id}`}>Quantity to return</label>
              <select id={`rq-${it.id}`} className="input h-9 w-20 py-1" value={ret.qty[it.id] ?? 0} onChange={(e) => setRet({ ...ret, qty: { ...ret.qty, [it.id]: Number(e.target.value) } })}>
                {Array.from({ length: it.quantity - it.returned_quantity + 1 }).map((_, n) => <option key={n} value={n}>{n}</option>)}
              </select>
            </li>
          ))}
        </ul>
        <Select className="mt-4" label="Reason" value={ret.reason} onChange={(e) => setRet({ ...ret, reason: e.target.value })} options={RETURN_REASONS.map(([v, l]) => ({ value: v, label: l }))} />
        <Textarea className="mt-4" label="Tell us more (optional)" rows={3} value={ret.details} onChange={(e) => setRet({ ...ret, details: e.target.value })} />
        <p className="mt-3 text-sm text-kajal-500">We'll schedule a free pickup. Refunds are issued once the item reaches our warehouse and passes a quick check.</p>
      </Modal>
    </div>
  );
}

export default function OrderDetail() {
  const { ref = "" } = useParams();
  useSeo({ title: `Order ${ref}`, noindex: true });
  const qc = useQueryClient();
  const { data, isLoading, isError, refetch } = useQuery({ queryKey: ["order", ref], queryFn: () => storeApi.order(ref) });
  if (isLoading) return <PageSpinner />;
  if (isError || !data) return <ErrorState message="We couldn't find this order." onRetry={() => refetch()} />;
  return (
    <div>
      <Breadcrumbs items={[{ label: "Orders", to: "/account/orders" }, { label: data.order_number }]} />
      <div className="mt-4"><OrderBody o={data} onChanged={(o) => { qc.setQueryData(["order", ref], o); qc.invalidateQueries({ queryKey: ["orders"] }); }} /></div>
    </div>
  );
}
