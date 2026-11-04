import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, CheckCircle2, Circle, FileText, Package, Printer, Truck, XCircle } from "lucide-react";
import { adminApi, isForbidden, isNotFound, type AdminOrderDetail } from "@/services/admin";
import { downloadFile, errorMessage } from "@/services/api";
import { KeyVal, NoAccess, PageHeader, Panel, Thumb, useConfirm, Switch } from "@/components/admin/kit";
import { useAdminMutation } from "@/components/admin/hooks";
import { Alert, Badge, Button, ErrorState, Input, Modal, PageSpinner, Select, StatusBadge, Textarea } from "@/components/ui";
import { useAuth } from "@/features/auth";
import { useToast } from "@/features/toast";
import { date, rupees, titleCase } from "@/utils/format";
import type { OrderAddress } from "@/types";
import { cn } from "@/utils/cn";

export default function OrderDetail() {
  const { id } = useParams();
  const oid = Number(id);
  const q = useQuery({ queryKey: ["admin", "order", oid], queryFn: () => adminApi.order(oid) });
  if (q.isPending) return <PageSpinner />;
  if (q.isError) {
    if (isForbidden(q.error)) return <NoAccess what="Orders" />;
    return <ErrorState message={isNotFound(q.error) ? "This order doesn't exist." : errorMessage(q.error)} onRetry={() => q.refetch()} />;
  }
  return <OrderView o={q.data} />;
}

function useOrderMutation<V>(oid: number, fn: (v: V) => Promise<unknown>, success: string, after?: () => void) {
  const qc = useQueryClient();
  return useAdminMutation(fn, {
    success,
    onSuccess: (d) => {
      if (d && typeof d === "object" && "order_number" in (d as object)) qc.setQueryData(["admin", "order", oid], d);
      qc.invalidateQueries({ queryKey: ["admin", "order", oid] });
      qc.invalidateQueries({ queryKey: ["admin", "orders"] });
      qc.invalidateQueries({ queryKey: ["admin", "dashboard"] });
      after?.();
    },
  });
}

function OrderView({ o }: { o: AdminOrderDetail }) {
  const { can } = useAuth();
  const write = can("orders:write");
  const toast = useToast();
  const confirm = useConfirm();
  const [modal, setModal] = useState<null | "ship" | "refund" | "status">(null);
  const [dl, setDl] = useState<string | null>(null);
  const t = o.totals;
  const remaining = Number(t.grand_total) - Number(t.refunded_total);
  const canCancel = write && (o.allowed_transitions ?? []).some((x) => x.value === "cancelled") && o.status !== "cancellation_requested";
  const cancelReq = write && o.status === "cancellation_requested";
  const hasCost = o.items.some((i) => i.unit_cost !== undefined);

  const cancel = useOrderMutation(o.id, (reason: string) => adminApi.cancelOrder(o.id, reason), "Order cancelled");
  const resolve = useOrderMutation(o.id, (v: { approve: boolean; note?: string }) => adminApi.resolveCancellation(o.id, v.approve, v.note), "Cancellation request resolved");

  const download = async (kind: "invoice" | "packing-slip") => {
    setDl(kind);
    try { await downloadFile(`/admin/orders/${o.id}/${kind}`, `${kind === "invoice" ? "Invoice" : "PackingSlip"}-${o.order_number}.pdf`); }
    catch (e) { toast(errorMessage(e), "error"); }
    finally { setDl(null); }
  };
  const doCancel = async () => {
    const paid = o.payment_status === "paid";
    const r = await confirm({
      title: `Cancel order ${o.order_number}?`, confirmLabel: "Cancel order", danger: true,
      body: <>Stock is released back to inventory{paid ? <> and the paid amount (<strong>{rupees(remaining)}</strong>) is refunded automatically</> : ""}. The customer is emailed.
        {paid && !can("refunds:write") && <Alert tone="warning" className="mt-3">This order is paid, so cancelling it issues a refund — only an administrator can do this.</Alert>}</>,
      reason: { label: "Reason", required: true, minLength: 3, placeholder: "e.g. Customer asked by phone" },
    });
    if (r.ok) cancel.mutate(r.reason);
  };
  const doResolve = async (approve: boolean) => {
    const r = await confirm({
      title: approve ? "Approve the cancellation?" : "Decline the cancellation?", confirmLabel: approve ? "Approve and cancel" : "Decline request", danger: approve,
      body: approve ? "The order is cancelled, stock is released and any payment is refunded." : `The order returns to its previous status. Customer's reason: “${o.cancellation_reason ?? "—"}”`,
      reason: { label: "Note", placeholder: "Optional note for the history" },
    });
    if (r.ok) resolve.mutate({ approve, note: r.reason });
  };

  return (
    <>
      <PageHeader
        back={<Link to="/admin/orders" className="inline-flex items-center gap-1 text-sm text-kajal-500 hover:text-kajal"><ArrowLeft className="h-4 w-4" aria-hidden />Orders</Link>}
        title={<span className="tabular">{o.order_number}</span>}
        sub={<span className="flex flex-wrap items-center gap-2">
          <StatusBadge status={o.status} />
          <StatusBadge status={o.payment_status} label={`Payment ${o.payment_status.replace(/_/g, " ")}`} />
          <span>Placed {date(o.placed_at, "long")} · {o.payment_method === "cod" ? "Cash on delivery" : "Online payment"}</span>
        </span>}
        actions={<>
          <Button variant="ghost" size="sm" onClick={() => download("packing-slip")} loading={dl === "packing-slip"}><Printer className="h-4 w-4" aria-hidden />Packing slip</Button>
          {o.invoice_available && <Button variant="ghost" size="sm" onClick={() => download("invoice")} loading={dl === "invoice"}><FileText className="h-4 w-4" aria-hidden />Invoice</Button>}
        </>} />

      {/* actions bar */}
      {write && (o.manual_transitions?.length || o.can_ship || canCancel || cancelReq || o.can_refund) ? (
        <div className="card mb-6 flex flex-wrap items-center gap-2 p-3">
          <span className="px-2 text-sm text-kajal-500">Actions</span>
          {o.can_ship && <Button size="sm" onClick={() => setModal("ship")}><Truck className="h-4 w-4" aria-hidden />Create shipment</Button>}
          {!!o.manual_transitions?.length && <Button variant="outline" size="sm" onClick={() => setModal("status")}>Change status</Button>}
          {cancelReq && <>
            <Button variant="danger" size="sm" onClick={() => doResolve(true)} loading={resolve.isPending && resolve.variables?.approve}>Approve cancellation</Button>
            <Button variant="outline" size="sm" onClick={() => doResolve(false)} loading={resolve.isPending && !resolve.variables?.approve}>Decline cancellation</Button>
          </>}
          {o.can_refund && <Button variant="outline" size="sm" onClick={() => setModal("refund")}>Issue refund</Button>}
          {canCancel && <Button variant="ghost" size="sm" className="text-kumkum" onClick={doCancel} loading={cancel.isPending}><XCircle className="h-4 w-4" aria-hidden />Cancel order</Button>}
        </div>
      ) : null}

      {o.status === "cancellation_requested" && <Alert tone="warning" className="mb-6">The customer asked to cancel: “{o.cancellation_reason ?? "no reason given"}”.</Alert>}
      {o.cancellation_reason && o.status !== "cancellation_requested" && o.cancelled_at && <Alert className="mb-6">Cancelled {date(o.cancelled_at, "long")}: {o.cancellation_reason}</Alert>}

      <div className="grid gap-6 xl:grid-cols-[1fr_360px]">
        <div className="min-w-0 space-y-6">
          <Panel title={`Items (${o.item_count})`} bodyClass="p-0">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[560px] text-[14px]">
                <thead><tr className="border-b border-gold-200/60 text-left text-[13px] text-kajal-500">
                  <th className="px-5 py-2 font-medium">Product</th><th className="px-3 py-2 text-right font-medium">Price</th><th className="px-3 py-2 text-right font-medium">Qty</th>
                  {hasCost && <th className="px-3 py-2 text-right font-medium">Unit cost</th>}<th className="px-5 py-2 text-right font-medium">Total</th>
                </tr></thead>
                <tbody>
                  {o.items.map((i) => (
                    <tr key={i.id} className="border-b border-gold-200/30 last:border-0">
                      <td className="px-5 py-3">
                        <div className="flex gap-3">
                          <Thumb src={i.image_url} size={48} />
                          <div className="min-w-0">
                            {i.product_id ? <Link to={`/admin/products/${i.product_id}`} className="text-kajal hover:underline">{i.product_name}</Link> : <span>{i.product_name}</span>}
                            <p className="text-xs text-kajal-500">{[i.variant_name, i.sku].filter(Boolean).join(" · ")}</p>
                            {i.attributes && Object.keys(i.attributes).length > 0 && <p className="text-xs text-kajal-400">{Object.entries(i.attributes).map(([k, v]) => `${titleCase(k)}: ${v}`).join(" · ")}</p>}
                            {i.returned_quantity > 0 && <Badge tone="warning" className="mt-1">{i.returned_quantity} returned</Badge>}
                          </div>
                        </div>
                      </td>
                      <td className="px-3 py-3 text-right tabular">
                        {rupees(i.unit_price)}
                        {Number(i.unit_mrp) > Number(i.unit_price) && <span className="block text-xs text-kajal-400 line-through">{rupees(i.unit_mrp)}</span>}
                      </td>
                      <td className="px-3 py-3 text-right tabular">{i.quantity}</td>
                      {hasCost && <td className="px-3 py-3 text-right tabular text-kajal-500">{rupees(i.unit_cost)}</td>}
                      <td className="px-5 py-3 text-right tabular">
                        {rupees(i.line_total)}
                        {Number(i.discount_amount) > 0 && <span className="block text-xs text-kumkum">−{rupees(i.discount_amount)} off</span>}
                        <span className="block text-xs text-kajal-400">GST {Number(i.tax_rate)}% · {rupees(i.tax_amount)}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <dl className="border-t border-gold-200/50 px-5 py-4 sm:ml-auto sm:max-w-sm">
              <KeyVal k="Subtotal (MRP)" v={rupees(t.subtotal_mrp)} />
              {Number(t.item_discount) > 0 && <KeyVal k="Item discounts" v={<span className="text-kumkum">−{rupees(t.item_discount)}</span>} />}
              {Number(t.promotion_discount) > 0 && <KeyVal k={<>Promotions{o.applied_promotions.length ? <span className="block text-xs">{o.applied_promotions.map((p) => p.name).join(", ")}</span> : null}</>} v={<span className="text-kumkum">−{rupees(t.promotion_discount)}</span>} />}
              {Number(t.coupon_discount) > 0 && <KeyVal k={`Coupon ${t.coupon_code ?? ""}`} v={<span className="text-kumkum">−{rupees(t.coupon_discount)}</span>} />}
              <KeyVal k={`Shipping${o.shipping_method_name ? ` · ${o.shipping_method_name}` : ""}`} v={Number(t.shipping_charge) ? rupees(t.shipping_charge) : "Free"} />
              {Number(t.cod_charge) > 0 && <KeyVal k="COD fee" v={rupees(t.cod_charge)} />}
              <KeyVal k="GST included" v={rupees(t.tax_total)} className="text-kajal-400" />
              <div className="mt-2 flex items-baseline justify-between border-t border-gold-200/50 pt-2">
                <span className="font-medium">Grand total</span><span className="font-display text-2xl tabular">{rupees(t.grand_total)}</span>
              </div>
              {Number(t.refunded_total) > 0 && <KeyVal k="Refunded" v={<span className="text-kumkum">−{rupees(t.refunded_total)}</span>} />}
            </dl>
          </Panel>

          <ShipmentsPanel o={o} write={write} />
          <PaymentsPanel o={o} />
          <HistoryPanel o={o} />
        </div>

        <aside className="space-y-6">
          <Panel title="Customer">
            <p className="text-kajal">{o.shipping_address?.full_name ?? o.customer_name ?? "Guest"}</p>
            <p className="text-sm text-kajal-500">{o.email}</p>
            {o.phone && <p className="text-sm text-kajal-500">{o.phone}</p>}
            {o.user_id ? (can("customers:read") && <Link to={`/admin/customers/${o.user_id}`} className="mt-2 inline-block text-sm text-gold-700 hover:underline">View customer profile</Link>)
              : <p className="mt-2 text-xs text-kajal-400">Guest checkout</p>}
            {o.customer_note && <p className="mt-3 rounded-lg bg-ivory-200/60 px-3 py-2 text-sm text-kajal-700">“{o.customer_note}”</p>}
          </Panel>
          <Panel title="Shipping address"><Address a={o.shipping_address} /></Panel>
          <Panel title="Billing address"><Address a={o.billing_address} same={JSON.stringify(o.billing_address) === JSON.stringify(o.shipping_address)} /></Panel>
          <Panel title="Delivery">
            <dl>
              <KeyVal k="Method" v={o.shipping_method_name ?? "—"} />
              <KeyVal k="Dispatch by" v={date(o.estimated_dispatch_date)} />
              <KeyVal k="Estimated delivery" v={date(o.estimated_delivery_date)} />
              {o.delivered_at && <KeyVal k="Delivered" v={date(o.delivered_at, "long")} />}
            </dl>
          </Panel>
          <NotesPanel o={o} write={write} />
        </aside>
      </div>

      {modal === "ship" && <ShipmentModal o={o} onClose={() => setModal(null)} />}
      {modal === "refund" && <RefundModal o={o} remaining={remaining} onClose={() => setModal(null)} />}
      {modal === "status" && <StatusModal o={o} onClose={() => setModal(null)} />}
    </>
  );
}

function Address({ a, same }: { a: OrderAddress | null; same?: boolean }) {
  if (!a) return <p className="text-sm text-kajal-500">—</p>;
  if (same) return <p className="text-sm text-kajal-500">Same as shipping address{a.gstin ? ` · GSTIN ${a.gstin}` : ""}</p>;
  return (
    <address className="text-sm not-italic leading-6 text-kajal-700">
      <span className="text-kajal">{a.full_name}</span><br />
      {a.line1}{a.line2 ? <>, {a.line2}</> : null}<br />
      {a.landmark && <>{a.landmark}<br /></>}
      {a.city}, {a.state} {a.pin_code}<br />
      {a.phone}{a.gstin && <><br />GSTIN {a.gstin}</>}
    </address>
  );
}

function ShipmentsPanel({ o, write }: { o: AdminOrderDetail; write: boolean }) {
  const [upd, setUpd] = useState<number | null>(null);
  if (!o.shipments.length) return null;
  return (
    <Panel title="Shipments">
      <div className="space-y-6">
        {o.shipments.map((s) => {
          const open = !["delivered", "cancelled", "returned"].includes(s.status);
          return (
            <div key={s.id}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="flex items-center gap-2 text-kajal"><Package className="h-4 w-4 text-gold-600" aria-hidden />{s.courier_name ?? "Courier"} <StatusBadge status={s.status} /></p>
                  <p className="mt-0.5 text-sm text-kajal-500 tabular">
                    AWB {s.tracking_url ? <a href={s.tracking_url} target="_blank" rel="noreferrer" className="underline decoration-gold-300 underline-offset-2">{s.tracking_number}</a> : s.tracking_number ?? "—"}
                    {s.shipped_at && <> · shipped {date(s.shipped_at, "long")}</>}
                  </p>
                </div>
                {write && open && <Button variant="outline" size="sm" onClick={() => setUpd(s.id)}>Update tracking</Button>}
              </div>
              {s.events.length > 0 && (
                <ol className="ml-2 mt-4 border-l border-gold-200 pl-5">
                  {s.events.map((e, i) => (
                    <li key={i} className="relative pb-4 last:pb-0">
                      <span className={cn("absolute -left-[26px] top-1 h-2.5 w-2.5 rounded-full border-2 border-white", i === 0 ? "bg-gold-500" : "bg-gold-200")} aria-hidden />
                      <p className="text-sm text-kajal">{e.description}</p>
                      <p className="text-xs text-kajal-400">{date(e.occurred_at, "long")}{e.location ? ` · ${e.location}` : ""}</p>
                    </li>
                  ))}
                </ol>
              )}
              {upd === s.id && <ShipmentStatusModal o={o} sid={s.id} current={s.status} onClose={() => setUpd(null)} />}
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

function PaymentsPanel({ o }: { o: AdminOrderDetail }) {
  if (!o.payments.length && !o.refunds.length) return null;
  return (
    <Panel title="Payments & refunds" bodyClass="p-0">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] text-[14px]">
          <thead><tr className="border-b border-gold-200/60 text-left text-[13px] text-kajal-500">
            <th className="px-5 py-2 font-medium">Payment</th><th className="px-3 py-2 font-medium">Status</th><th className="px-3 py-2 font-medium">Date</th><th className="px-5 py-2 text-right font-medium">Amount</th>
          </tr></thead>
          <tbody>
            {o.payments.map((p) => (
              <tr key={`p${p.id}`} className="border-b border-gold-200/30">
                <td className="px-5 py-2.5">
                  <span className="text-kajal">{p.provider === "cod" ? "Cash on delivery" : `${titleCase(p.provider)}${p.method ? ` · ${p.method.toUpperCase()}` : ""}`}</span>
                  <span className="block text-xs text-kajal-400">{p.razorpay_payment_id ?? p.razorpay_order_id ?? ""}{p.mode !== "live" ? ` · ${p.mode} mode` : ""} · {p.attempts} attempt{p.attempts === 1 ? "" : "s"}</span>
                  {p.error_description && <span className="block text-xs text-kumkum">{p.error_description}</span>}
                </td>
                <td className="px-3 py-2.5"><StatusBadge status={p.status} /></td>
                <td className="whitespace-nowrap px-3 py-2.5 text-kajal-500">{date(p.captured_at ?? p.created_at, "long")}</td>
                <td className="px-5 py-2.5 text-right tabular">{rupees(p.amount)}{Number(p.amount_refunded) > 0 && <span className="block text-xs text-kumkum">−{rupees(p.amount_refunded)} refunded</span>}</td>
              </tr>
            ))}
            {o.refunds.map((r) => (
              <tr key={`r${r.id}`} className="border-b border-gold-200/30 bg-kumkum-50/30">
                <td className="px-5 py-2.5"><span className="text-kajal">Refund</span><span className="block text-xs text-kajal-400">{r.reason}{r.razorpay_refund_id ? ` · ${r.razorpay_refund_id}` : ""}</span></td>
                <td className="px-3 py-2.5"><StatusBadge status={r.status} /></td>
                <td className="whitespace-nowrap px-3 py-2.5 text-kajal-500">{date(r.processed_at ?? r.created_at, "long")}</td>
                <td className="px-5 py-2.5 text-right tabular text-kumkum">−{rupees(r.amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function HistoryPanel({ o }: { o: AdminOrderDetail }) {
  const items = [...o.history].reverse();
  return (
    <Panel title="Status history">
      <ol className="space-y-4">
        {items.map((h, i) => (
          <li key={i} className="flex gap-3">
            {i === 0 ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-gold-600" aria-hidden /> : <Circle className="mt-0.5 h-4 w-4 shrink-0 text-gold-200" aria-hidden />}
            <div>
              <p className="text-[14px] text-kajal">{h.label}{h.from && <span className="text-kajal-400"> · from {titleCase(h.from).toLowerCase()}</span>}</p>
              <p className="text-xs text-kajal-400">{date(h.at, "long")} · by {h.actor_type}</p>
              {h.note && <p className="mt-0.5 text-sm text-kajal-500">{h.note}</p>}
            </div>
          </li>
        ))}
      </ol>
    </Panel>
  );
}

function NotesPanel({ o, write }: { o: AdminOrderDetail; write: boolean }) {
  const [body, setBody] = useState("");
  const add = useOrderMutation(o.id, (b: string) => adminApi.addOrderNote(o.id, b), "Note added", () => setBody(""));
  return (
    <Panel title="Internal notes">
      {o.notes?.length ? (
        <ul className="mb-4 space-y-3">
          {o.notes.map((n) => (
            <li key={n.id} className="rounded-lg bg-ivory-200/50 px-3 py-2">
              <p className="whitespace-pre-wrap text-sm text-kajal-700">{n.body}</p>
              <p className="mt-1 text-xs text-kajal-400">{n.author ?? "Staff"} · {date(n.at, "long")}</p>
            </li>
          ))}
        </ul>
      ) : <p className="mb-3 text-sm text-kajal-500">No notes yet. Notes are never shown to the customer.</p>}
      {write && (
        <form onSubmit={(e) => { e.preventDefault(); if (body.trim()) add.mutate(body.trim()); }}>
          <Textarea label="Add a note" rows={3} value={body} onChange={(e) => setBody(e.target.value)} maxLength={2000} />
          <Button type="submit" size="sm" className="mt-2" disabled={!body.trim()} loading={add.isPending}>Add note</Button>
        </form>
      )}
    </Panel>
  );
}

function ShipmentModal({ o, onClose }: { o: AdminOrderDetail; onClose: () => void }) {
  const [f, setF] = useState({ courier_name: "", tracking_number: "", tracking_url: "", weight_grams: "", mark_shipped: true });
  const [err, setErr] = useState<string | null>(null);
  const m = useOrderMutation(o.id, () => adminApi.createShipment(o.id, {
    courier_name: f.courier_name || null, tracking_number: f.tracking_number || null, tracking_url: f.tracking_url || null,
    weight_grams: f.weight_grams ? Number(f.weight_grams) : null, mark_shipped: f.mark_shipped,
  }), f.mark_shipped ? "Shipment created and marked shipped" : "Shipment created", onClose);
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (f.weight_grams && !(/^\d+$/.test(f.weight_grams) && Number(f.weight_grams) > 0)) return setErr("Weight must be a whole number of grams");
    if (f.tracking_url && !/^https?:\/\//.test(f.tracking_url)) return setErr("Tracking URL must start with https://");
    setErr(null);
    m.mutate(undefined);
  };
  return (
    <Modal open onClose={onClose} title="Create shipment"
      footer={<><Button variant="ghost" size="sm" onClick={onClose}>Cancel</Button><Button size="sm" type="submit" form="ship-form" loading={m.isPending}>Create shipment</Button></>}>
      <form id="ship-form" onSubmit={submit} className="space-y-4">
        <p className="text-sm text-kajal-500">Leave the AWB blank to book with the store's courier integration (mock), which generates the AWB and tracking link.</p>
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="Courier" value={f.courier_name} onChange={(e) => setF({ ...f, courier_name: e.target.value })} placeholder="e.g. Delhivery" />
          <Input label="AWB / tracking number" value={f.tracking_number} onChange={(e) => setF({ ...f, tracking_number: e.target.value })} placeholder="Auto-generate" />
          <Input label="Tracking URL" value={f.tracking_url} onChange={(e) => setF({ ...f, tracking_url: e.target.value })} placeholder="https://…" className="sm:col-span-2" />
          <Input label="Parcel weight (g)" inputMode="numeric" value={f.weight_grams} onChange={(e) => setF({ ...f, weight_grams: e.target.value })} placeholder="250" />
        </div>
        <Switch label="Mark the order as shipped now (emails the customer)" checked={f.mark_shipped} onChange={(v) => setF({ ...f, mark_shipped: v })} />
        {err && <p role="alert" className="text-sm text-kumkum">{err}</p>}
      </form>
    </Modal>
  );
}

const SHIP_STATUSES = [
  { value: "shipped", label: "Shipped" }, { value: "in_transit", label: "In transit" }, { value: "out_for_delivery", label: "Out for delivery" },
  { value: "delivered", label: "Delivered" }, { value: "delivery_failed", label: "Delivery failed" },
];
function ShipmentStatusModal({ o, sid, current, onClose }: { o: AdminOrderDetail; sid: number; current: string; onClose: () => void }) {
  const opts = SHIP_STATUSES.filter((s) => s.value !== current && !(current !== "created" && s.value === "shipped"));
  const [f, setF] = useState({ status: opts[0]?.value ?? "in_transit", location: "", description: "" });
  const m = useOrderMutation(o.id, () => adminApi.shipmentStatus(sid, { status: f.status, location: f.location || null, description: f.description || null }), "Tracking updated", onClose);
  return (
    <Modal open onClose={onClose} title="Update shipment status"
      footer={<><Button variant="ghost" size="sm" onClick={onClose}>Cancel</Button><Button size="sm" type="submit" form="ss-form" loading={m.isPending}>Update status</Button></>}>
      <form id="ss-form" onSubmit={(e) => { e.preventDefault(); m.mutate(undefined); }} className="space-y-4">
        <Select label="New status" value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })} options={opts} />
        <Input label="Location" value={f.location} onChange={(e) => setF({ ...f, location: e.target.value })} placeholder="e.g. Noida hub" />
        <Input label="Description" value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} placeholder="Shown in the tracking timeline" />
      </form>
    </Modal>
  );
}

function StatusModal({ o, onClose }: { o: AdminOrderDetail; onClose: () => void }) {
  const opts = o.manual_transitions ?? [];
  const [status, setStatus] = useState(opts[0]?.value ?? "");
  const [note, setNote] = useState("");
  const m = useOrderMutation(o.id, () => adminApi.setOrderStatus(o.id, status, note), "Order status updated", onClose);
  return (
    <Modal open onClose={onClose} title="Change order status"
      footer={<><Button variant="ghost" size="sm" onClick={onClose}>Cancel</Button><Button size="sm" type="submit" form="st-form" disabled={!status} loading={m.isPending}>Update status</Button></>}>
      <form id="st-form" onSubmit={(e) => { e.preventDefault(); m.mutate(undefined); }} className="space-y-4">
        <p className="text-sm text-kajal-500">Currently <strong className="text-kajal">{o.status_label}</strong>. Shipping, cancelling, returns and refunds have their own actions.</p>
        <Select label="New status" value={status} onChange={(e) => setStatus(e.target.value)} options={opts} />
        <Textarea label="Note (optional)" rows={2} value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} />
      </form>
    </Modal>
  );
}

function RefundModal({ o, remaining, onClose }: { o: AdminOrderDetail; remaining: number; onClose: () => void }) {
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const m = useOrderMutation(o.id, () => adminApi.refund(o.id, { amount: amount || null, reason: reason.trim() }), "Refund issued", onClose);
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (amount && !(/^\d+(\.\d{1,2})?$/.test(amount) && Number(amount) > 0)) return setErr("Enter a valid amount");
    if (amount && Number(amount) > remaining + 0.001) return setErr(`You can refund at most ${rupees(remaining)}`);
    if (reason.trim().length < 3) return setErr("Give a reason (at least 3 characters)");
    setErr(null);
    m.mutate(undefined);
  };
  return (
    <Modal open onClose={onClose} title="Issue refund"
      footer={<><Button variant="ghost" size="sm" onClick={onClose}>Cancel</Button><Button variant="danger" size="sm" type="submit" form="rf-form" loading={m.isPending}>Issue refund{amount ? ` of ${rupees(amount)}` : ` of ${rupees(remaining)}`}</Button></>}>
      <form id="rf-form" onSubmit={submit} className="space-y-4">
        <p className="text-sm text-kajal-700">Paid {rupees(o.totals.grand_total)} · already refunded {rupees(o.totals.refunded_total)} · <strong>refundable {rupees(remaining)}</strong></p>
        <Input label="Amount (₹)" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder={`${remaining.toFixed(2)} (full remaining)`} hint="Leave blank to refund the full remaining amount." />
        <Textarea label="Reason" required rows={2} value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} placeholder="e.g. Item damaged in transit" />
        <p className="text-xs text-kajal-500">The refund goes back to the original payment method via Razorpay. This can't be undone.</p>
        {err && <p role="alert" className="text-sm text-kumkum">{err}</p>}
      </form>
    </Modal>
  );
}

