import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Clock, XCircle } from "lucide-react";
import { storeApi } from "@/services/store";
import { Alert, Button, ButtonLink, ErrorState, Money, PageSpinner } from "@/components/ui";
import { usePayment } from "@/features/payments";
import { useAuth } from "@/features/auth";
import { useSeo } from "@/hooks/useSeo";
import { date } from "@/utils/format";
import { errorMessage as errorMessageSafe } from "@/services/api";

export default function PaymentResult() {
  useSeo({ title: "Order status", noindex: true });
  const { orderNumber = "" } = useParams();
  const [sp] = useSearchParams();
  const key = sp.get("key") ?? undefined;
  const hinted = sp.get("status");
  const { user } = useAuth();
  const nav = useNavigate();
  const qc = useQueryClient();
  const { pay, modal } = usePayment();
  const [retrying, setRetrying] = useState(false);
  const [retryErr, setRetryErr] = useState<string | null>(null);
  const [polls, setPolls] = useState(0);

  const order = useQuery({ queryKey: ["order", orderNumber, key], queryFn: () => storeApi.order(orderNumber, key) });
  const o = order.data;
  const paid = o?.payment_status === "paid";
  const pendingVerification = !!o && hinted === "paid" && !paid && o.status === "payment_pending";

  // If the browser was told "paid" but the server hasn't confirmed yet (webhook in flight), poll briefly.
  useEffect(() => {
    if (!pendingVerification || polls > 10) return;
    const t = setTimeout(() => { setPolls((n) => n + 1); order.refetch(); }, 3000);
    return () => clearTimeout(t);
  }, [pendingVerification, polls]); // eslint-disable-line react-hooks/exhaustive-deps

  const retry = async () => {
    setRetrying(true); setRetryErr(null);
    try {
      const r = await pay(orderNumber, key ?? o?.order_key);
      const k = r.orderKey ?? key;
      nav(`/payment/${orderNumber}?status=${r.status}${k ? `&key=${k}` : ""}${r.status === "failed" ? `&msg=${encodeURIComponent(r.message)}` : ""}`, { replace: true });
      qc.invalidateQueries({ queryKey: ["order", orderNumber] });
    } catch (e) {
      setRetryErr(errorMessageSafe(e));
    } finally { setRetrying(false); }
  };

  if (order.isLoading) return <PageSpinner />;
  if (order.isError || !o) return <div className="container-site py-24"><ErrorState message="We couldn't find that order." onRetry={() => order.refetch()} /></div>;

  const placedCod = o.payment_method === "cod" && o.status !== "cancelled";
  const success = paid || placedCod;
  const detailsLink = user ? `/account/orders/${o.order_number}` : `/track?order=${o.order_number}`;

  return (
    <div className="container-site max-w-3xl py-14">
      {modal}
      <div className="text-center">
        {success ? <CheckCircle2 className="mx-auto h-14 w-14 text-leaf" strokeWidth={1.4} aria-hidden />
          : pendingVerification ? <Clock className="mx-auto h-14 w-14 text-gold-500" strokeWidth={1.4} aria-hidden />
          : <XCircle className="mx-auto h-14 w-14 text-kumkum" strokeWidth={1.4} aria-hidden />}
        <h1 className="mt-5 text-[34px] leading-tight sm:text-[42px]">
          {success ? (placedCod && !paid ? "Order placed" : "Thank you — payment received") : pendingVerification ? "Confirming your payment" : o.status === "cancelled" ? "This order was cancelled" : "Payment not completed"}
        </h1>
        <p className="mx-auto mt-3 max-w-lg text-kajal-500">
          {success ? <>Order <strong className="font-medium text-kajal">{o.order_number}</strong> is confirmed. A confirmation has been sent to {o.email}.</>
            : pendingVerification ? "Your bank has responded and we're verifying the payment with Razorpay. This usually takes a few seconds — please don't pay again."
            : o.status === "cancelled" ? (o.cancellation_reason ?? "") + " Any amount debited will be refunded automatically."
            : <>Your order <strong className="font-medium text-kajal">{o.order_number}</strong> is saved and your items are held for a short while. {sp.get("msg") ? `Reason: ${sp.get("msg")!.replace(/\.$/, "")}.` : ""} If money was debited, it will be refunded automatically.</>}
        </p>
      </div>

      {!success && o.status === "payment_pending" && !pendingVerification && (
        <div className="mx-auto mt-8 flex max-w-sm flex-col gap-3">
          {retryErr && <Alert tone="error">{retryErr}</Alert>}
          <Button size="lg" onClick={retry} loading={retrying}>Retry payment of <Money value={o.grand_total} /></Button>
          <ButtonLink to="/cart" variant="ghost">Back to bag</ButtonLink>
        </div>
      )}

      <div className="card mt-10 p-6 sm:p-8">
        <div className="flex flex-wrap justify-between gap-4 border-b border-gold-200/50 pb-5 text-sm">
          <div><p className="text-kajal-500">Order number</p><p className="mt-0.5 font-medium tabular">{o.order_number}</p></div>
          <div><p className="text-kajal-500">Placed on</p><p className="mt-0.5">{date(o.placed_at)}</p></div>
          <div><p className="text-kajal-500">Payment</p><p className="mt-0.5">{o.payment_method === "cod" ? "Cash on Delivery" : "Online"} · {o.payment_status.replace(/_/g, " ")}</p></div>
          {o.estimated_delivery_date && success && <div><p className="text-kajal-500">Estimated delivery</p><p className="mt-0.5">{date(o.estimated_delivery_date)}</p></div>}
        </div>
        <ul className="divide-y divide-gold-200/40">
          {o.items.map((it) => (
            <li key={it.id} className="flex gap-4 py-4">
              <img src={it.image_url ?? ""} alt="" className="h-20 w-16 rounded-xl bg-ivory-200 object-cover" />
              <div className="flex-1 text-sm"><p className="text-[15px]">{it.product_name}</p><p className="text-kajal-500">{it.variant_name} · Qty {it.quantity}</p></div>
              <Money value={it.line_total} className="text-[15px]" />
            </li>
          ))}
        </ul>
        <div className="flex items-baseline justify-between border-t border-gold-200/50 pt-4">
          <span>Total</span><Money value={o.grand_total} className="font-display text-2xl" />
        </div>
        {o.shipping_address && (
          <p className="mt-4 text-sm leading-6 text-kajal-500">Delivering to {o.shipping_address.full_name}, {o.shipping_address.line1}, {o.shipping_address.city}, {o.shipping_address.state} {o.shipping_address.pin_code}</p>
        )}
      </div>

      <div className="mt-8 flex flex-wrap justify-center gap-3">
        <ButtonLink to={detailsLink} variant="outline">{user ? "View order details" : "Track this order"}</ButtonLink>
        <ButtonLink to="/new-arrivals">Continue shopping</ButtonLink>
      </div>
      {!user && success && <p className="mt-6 text-center text-sm text-kajal-500"><Link to="/register" className="link-underline">Create an account</Link> with {o.email} to track orders and save addresses.</p>}
    </div>
  );
}
