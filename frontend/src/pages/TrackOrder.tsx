import { useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { PackageSearch, Truck } from "lucide-react";
import { storeApi } from "@/services/store";
import { errorMessage } from "@/services/api";
import { Alert, Button, ErrorState, Input, PageSpinner, StatusBadge } from "@/components/ui";
import { ShipmentEvents } from "@/components/product/OrderTimeline";
import { OrderBody } from "@/pages/account/OrderDetail";
import { useSeo } from "@/hooks/useSeo";
import { date } from "@/utils/format";
import type { OrderDetail } from "@/types";

function AwbView({ awb }: { awb: string }) {
  const { data, isLoading, isError, error } = useQuery({ queryKey: ["track", awb], queryFn: () => storeApi.track(awb) });
  if (isLoading) return <PageSpinner />;
  if (isError || !data) return <ErrorState message={errorMessage(error, "No shipment found with that tracking number.")} />;
  return (
    <div className="card p-6 sm:p-8">
      <div className="flex flex-wrap items-center gap-3">
        <Truck className="h-6 w-6 text-gold-600" />
        <h2 className="flex-1 text-2xl">{data.courier_name} · <span className="tabular">{data.tracking_number}</span></h2>
        <StatusBadge status={data.order_status} label={data.order_status_label} />
      </div>
      <dl className="mt-5 grid gap-4 border-y border-gold-200/50 py-5 text-sm sm:grid-cols-3">
        <div><dt className="text-kajal-500">Order</dt><dd className="mt-0.5 tabular">{data.order_number}</dd></div>
        <div><dt className="text-kajal-500">Destination</dt><dd className="mt-0.5">{data.destination}</dd></div>
        <div><dt className="text-kajal-500">{data.delivered_at ? "Delivered" : "Expected by"}</dt><dd className="mt-0.5">{date(data.delivered_at ?? data.estimated_delivery_date)}</dd></div>
      </dl>
      <div className="mt-6">{data.events.length ? <ShipmentEvents events={data.events} /> : <p className="text-kajal-500">The courier hasn't scanned this parcel yet. Check back soon.</p>}</div>
    </div>
  );
}

export default function TrackOrder() {
  useSeo({ title: "Track your order", description: "Track your LoveVital order with your order number or AWB tracking number." });
  const { awb } = useParams();
  const [sp] = useSearchParams();
  const nav = useNavigate();
  const [orderNo, setOrderNo] = useState(sp.get("order") ?? "");
  const [email, setEmail] = useState("");
  const [awbIn, setAwbIn] = useState("");
  const [found, setFound] = useState<OrderDetail | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  return (
    <div className="container-site max-w-4xl py-12">
      <h1 className="text-[36px] sm:text-[44px]">Track your order</h1>
      <p className="mt-2 text-kajal-500">Logged in? Your orders are in <Link to="/account/orders" className="link-underline">My account</Link>.</p>
      {awb ? <div className="mt-8"><AwbView awb={awb} /></div> : found ? (
        <div className="mt-8"><OrderBody o={found} guestKey={found.order_key} onChanged={setFound} /></div>
      ) : (
        <div className="mt-8 grid gap-6 md:grid-cols-2">
          <form className="card space-y-4 p-6" onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true); setErr(null);
            try { setFound(await storeApi.lookupOrder(orderNo.trim(), email.trim())); } catch (ex) { setErr(errorMessage(ex)); } finally { setBusy(false); }
          }}>
            <h2 className="flex items-center gap-2 text-xl"><PackageSearch className="h-5 w-5 text-gold-600" />Order number & email</h2>
            {err && <Alert tone="error">{err}</Alert>}
            <Input label="Order number" placeholder="SWK…" value={orderNo} onChange={(e) => setOrderNo(e.target.value.toUpperCase())} required />
            <Input label="Email used at checkout" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            <Button type="submit" block loading={busy}>Find my order</Button>
          </form>
          <form className="card space-y-4 p-6" onSubmit={(e) => { e.preventDefault(); if (awbIn.trim()) nav(`/track/${awbIn.trim().toUpperCase()}`); }}>
            <h2 className="flex items-center gap-2 text-xl"><Truck className="h-5 w-5 text-gold-600" />Tracking number</h2>
            <Input label="AWB / tracking number" placeholder="SWK123456789IN" value={awbIn} onChange={(e) => setAwbIn(e.target.value)} required />
            <Button type="submit" variant="outline" block>Track shipment</Button>
          </form>
        </div>
      )}
    </div>
  );
}
