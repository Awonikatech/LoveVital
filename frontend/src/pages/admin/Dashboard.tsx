import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { AlertTriangle, ArrowDownRight, ArrowUpRight, Clock, PackageCheck, RotateCcw, Truck, XCircle } from "lucide-react";
import { adminApi, type Dashboard as DashboardData, type DashboardSummary } from "@/services/admin";
import { PageHeader, Panel, QueryState, Table, Td, Th, Tr, Thumb, EmptyRow } from "@/components/admin/kit";
import { DateRangeFilter, Definitions, HBarChart, ShareList, TrendChart, presetRange, type Range } from "@/components/admin/charts";
import { Skeleton, StatusBadge } from "@/components/ui";
import { date, rupees } from "@/utils/format";
import { cn } from "@/utils/cn";

function delta(cur?: string | number, prev?: string | number): number | null {
  const c = Number(cur ?? 0), p = Number(prev ?? 0);
  if (!p) return c ? null : 0;
  return ((c - p) / p) * 100;
}

function StatCard({ label, value, d, sub, invert, to }: { label: string; value: ReactNode; d?: number | null; sub?: ReactNode; invert?: boolean; to?: string }) {
  const good = d === null || d === undefined ? null : invert ? d <= 0 : d >= 0;
  const body = (
    <>
      <p className="text-[13px] text-kajal-500">{label}</p>
      <p className="mt-1.5 font-display text-[26px] leading-none text-kajal tabular">{value}</p>
      <div className="mt-2 flex min-h-[20px] flex-wrap items-center gap-x-2 text-[13px]">
        {d !== undefined && (
          d === null ? <span className="text-kajal-400">New this period</span> : (
            <span className={cn("inline-flex items-center gap-0.5 tabular", good ? "text-leaf" : "text-kumkum")}>
              {d >= 0 ? <ArrowUpRight className="h-3.5 w-3.5" aria-hidden /> : <ArrowDownRight className="h-3.5 w-3.5" aria-hidden />}
              {Math.abs(d).toFixed(1)}%<span className="sr-only"> {d >= 0 ? "up" : "down"}</span>
              <span className="text-kajal-400">&nbsp;vs previous</span>
            </span>
          )
        )}
        {sub && <span className="text-kajal-400">{sub}</span>}
      </div>
    </>
  );
  return to ? <Link to={to} className="card block p-4 transition-shadow hover:shadow-hair">{body}</Link> : <div className="card p-4">{body}</div>;
}

function Queue({ to, icon, label, count, tone }: { to: string; icon: ReactNode; label: string; count: number; tone?: "warn" }) {
  return (
    <Link to={to} className="group flex items-center gap-2.5 rounded-xl border border-gold-200/50 bg-white px-3 py-3 sm:gap-3 sm:px-4 transition-colors hover:border-gold-300">
      <span className={cn("flex h-9 w-9 shrink-0 items-center justify-center rounded-full", tone === "warn" && count ? "bg-[#FCF1DD] text-[#8A5A00]" : "bg-gold-50 text-gold-700")}>{icon}</span>
      <span className="min-w-0 flex-1 text-[14px] leading-tight text-kajal-700">{label}</span>
      <span className="font-display text-2xl tabular text-kajal">{count}</span>
    </Link>
  );
}

export default function Dashboard() {
  const [range, setRange] = useState<Range>(presetRange(30));
  const q = useQuery({ queryKey: ["admin", "dashboard", range], queryFn: () => adminApi.dashboard(range), placeholderData: keepPreviousData });

  return (
    <>
      <PageHeader title="Dashboard" sub={q.data ? `${date(q.data.range.start)} – ${date(q.data.range.end)}` : "Store performance at a glance"}
        actions={<DateRangeFilter value={range} onChange={setRange} />} />
      <QueryState q={q} what="The dashboard" skeleton={<DashSkeleton />}>
        {(d) => <DashboardBody d={d} fetching={q.isFetching} />}
      </QueryState>
    </>
  );
}

function DashSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">{Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-[108px] rounded-2xl" />)}</div>
      <Skeleton className="h-[320px] rounded-2xl" />
    </div>
  );
}

function DashboardBody({ d, fetching }: { d: DashboardData; fetching: boolean }) {
  const s = d.summary as DashboardSummary, p = d.previous as DashboardSummary;
  const fin = d.finance_visible;
  const [metric, setMetric] = useState<"net_sales" | "revenue" | "orders">(fin ? "net_sales" : "orders");
  const m = fin ? metric : "orders";
  return (
    <div className={cn("space-y-6 transition-opacity", fetching && "opacity-70")}>
      {!fin && (
        <p className="rounded-xl border border-gold-200/60 bg-gold-50 px-4 py-2.5 text-sm text-kajal-700">
          Sales and finance figures are visible to administrators only. You're seeing order and operations metrics.
        </p>
      )}
      <div className={cn("grid grid-cols-2 gap-3 lg:grid-cols-4", fin && "2xl:grid-cols-5")}>
        {fin && <StatCard label="Net sales" value={rupees(s.net_sales)} d={delta(s.net_sales, p.net_sales)} />}
        {fin && <StatCard label="Revenue" value={rupees(s.revenue)} d={delta(s.revenue, p.revenue)} />}
        <StatCard label="Orders" value={s.orders.toLocaleString("en-IN")} d={delta(s.orders, p.orders)} to="/admin/orders" />
        {fin && <StatCard label="Average order value" value={rupees(s.aov)} d={delta(s.aov, p.aov)} />}
        {fin && <StatCard label="Discounts" value={rupees(s.discounts)} d={delta(s.discounts, p.discounts)} invert sub={`Markdowns ${rupees(s.markdowns)}`} />}
        {fin && <StatCard label="Refunds" value={rupees(s.refunds)} d={delta(s.refunds, p.refunds)} invert />}
        <StatCard label="Customers" value={d.totals.customers.toLocaleString("en-IN")} sub={`${d.totals.new_customers} new in range`} to="/admin/customers" />
        <StatCard label="Active products" value={d.totals.products.toLocaleString("en-IN")} to="/admin/products?status=active" />
        {fin && s.gross_margin !== undefined && <StatCard label="Gross margin" value={rupees(s.gross_margin)} sub="Lines with cost data" />}
        {fin && <StatCard label="GST collected" value={rupees(s.tax_collected)} d={delta(s.tax_collected, p.tax_collected)} />}
      </div>

      <section aria-label="Work queues" className="grid grid-cols-2 gap-2 sm:gap-3 xl:grid-cols-5">
        <Queue to="/admin/orders?status=order_placed,payment_confirmed" icon={<Clock className="h-4 w-4" />} label="Pending orders" count={d.queues.pending_orders} />
        <Queue to="/admin/orders?status=processing,packed" icon={<Truck className="h-4 w-4" />} label="Awaiting dispatch" count={d.queues.awaiting_dispatch} />
        <Queue to="/admin/orders?status=cancellation_requested" icon={<XCircle className="h-4 w-4" />} label="Cancellation requests" count={d.queues.cancellation_requests} tone="warn" />
        <Queue to="/admin/returns?status=requested,approved" icon={<RotateCcw className="h-4 w-4" />} label="Open returns" count={d.queues.open_returns} tone="warn" />
        <Queue to="/admin/inventory?stock=low" icon={<AlertTriangle className="h-4 w-4" />} label="Low or out of stock" count={d.queues.low_stock} tone="warn" />
      </section>

      <Panel title="Sales trend" action={fin ? (
        <div role="group" aria-label="Chart metric" className="inline-flex rounded-full bg-ivory-200 p-0.5 text-[13px]">
          {(["net_sales", "revenue", "orders"] as const).map((k) => (
            <button key={k} type="button" aria-pressed={metric === k} onClick={() => setMetric(k)}
              className={cn("rounded-full px-3 py-1", metric === k ? "bg-white text-kajal shadow-sm" : "text-kajal-500 hover:text-kajal")}>
              {k === "net_sales" ? "Net sales" : k === "revenue" ? "Revenue" : "Orders"}
            </button>
          ))}
        </div>
      ) : <span className="text-[13px] text-kajal-500">Orders per day</span>}>
        <TrendChart data={d.sales_trend} metric={m} money={m !== "orders"} />
      </Panel>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Panel title={fin ? "Net sales by category" : "Units sold by category"}>
          {d.sales_by_category.length ? <HBarChart data={d.sales_by_category} labelKey="category" valueKey={fin ? "net_sales" : "units"} money={fin} />
            : <p className="py-10 text-center text-sm text-kajal-500">No sales in this range.</p>}
        </Panel>
        <Panel title="Payment methods">
          {d.payment_methods.length ? (
            <ShareList rows={[...d.payment_methods].sort((a, b) => Number(fin ? b.amount : b.orders) - Number(fin ? a.amount : a.orders)).map((r) => ({
              label: r.method, value: fin ? Number(r.amount) : r.orders, display: fin ? rupees(r.amount) : `${r.orders} orders`, sub: fin ? `${r.orders} orders` : undefined,
            }))} />
          ) : <p className="py-10 text-center text-sm text-kajal-500">No payments in this range.</p>}
        </Panel>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Panel title="Best sellers" bodyClass="p-0">
          <ul className="divide-y divide-gold-200/40">
            {d.best_sellers.map((b, i) => (
              <li key={b.sku} className="flex items-center gap-3 px-5 py-3">
                <span className="w-5 text-sm tabular text-kajal-400">{i + 1}</span>
                <Thumb src={b.image} />
                <div className="min-w-0 flex-1">
                  {b.product_id ? <Link to={`/admin/products/${b.product_id}`} className="block truncate text-[14px] text-kajal hover:underline">{b.name}</Link> : <p className="truncate text-[14px]">{b.name}</p>}
                  <p className="text-xs text-kajal-400">{b.sku}</p>
                </div>
                <div className="text-right text-[14px] tabular">
                  <p className="text-kajal">{b.units} sold</p>
                  {fin && <p className="text-xs text-kajal-500">{rupees(b.net_sales)}</p>}
                </div>
              </li>
            ))}
            {!d.best_sellers.length && <li className="px-5 py-10 text-center text-sm text-kajal-500">No sales in this range.</li>}
          </ul>
        </Panel>
        <Panel title="Low stock" action={<Link to="/admin/inventory?stock=low" className="text-sm text-gold-700 hover:underline">View inventory</Link>} bodyClass="p-0">
          <ul className="divide-y divide-gold-200/40">
            {d.low_stock.map((r) => (
              <li key={r.variant_id} className="flex items-center gap-3 px-5 py-3">
                <PackageCheck className="h-4 w-4 shrink-0 text-kajal-400" aria-hidden />
                <div className="min-w-0 flex-1">
                  <Link to={`/admin/products/${r.product_id}`} className="block truncate text-[14px] text-kajal hover:underline">{r.product_name}</Link>
                  <p className="truncate text-xs text-kajal-400">{r.variant_name} · {r.sku}</p>
                </div>
                <span className={cn("rounded-full px-2.5 py-0.5 text-xs tabular", r.available <= 0 ? "bg-kumkum-50 text-kumkum" : "bg-[#FCF1DD] text-[#8A5A00]")}>
                  {r.available <= 0 ? "Out of stock" : `${r.available} left`}
                </span>
              </li>
            ))}
            {!d.low_stock.length && <li className="px-5 py-10 text-center text-sm text-kajal-500">Everything is well stocked.</li>}
          </ul>
        </Panel>
      </div>

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-sans text-[15px] font-medium">Recent orders</h2>
          <Link to="/admin/orders" className="text-sm text-gold-700 hover:underline">All orders</Link>
        </div>
        <Table minWidth={720}>
          <thead><tr><Th>Order</Th><Th>Customer</Th><Th>Placed</Th><Th>Status</Th><Th>Payment</Th><Th align="right">Total</Th></tr></thead>
          <tbody>
            {d.recent_orders.map((o) => (
              <Tr key={o.id}>
                <Td><Link className="font-medium text-kajal hover:underline" to={`/admin/orders/${o.id}`}>{o.order_number}</Link></Td>
                <Td><span className="block max-w-[220px] truncate">{o.customer_name ?? o.email}</span></Td>
                <Td className="whitespace-nowrap">{date(o.placed_at, "long")}</Td>
                <Td><StatusBadge status={o.status} /></Td>
                <Td><span className="text-xs uppercase tracking-wide text-kajal-500">{o.payment_method === "cod" ? "COD" : "Online"}</span> <StatusBadge status={o.payment_status} /></Td>
                <Td align="right">{fin ? rupees(o.grand_total) : rupees(o.grand_total)}</Td>
              </Tr>
            ))}
            {!d.recent_orders.length && <EmptyRow cols={6}>No orders yet.</EmptyRow>}
          </tbody>
        </Table>
      </section>

      <Definitions text={d.definitions} />
    </div>
  );
}
