import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { adminApi, REPORT_NAMES, type ReportName } from "@/services/admin";
import { downloadFile, errorMessage } from "@/services/api";
import { EmptyRow, FilterSelect, PageHeader, Panel, QueryState, Table, Td, Th, Tr } from "@/components/admin/kit";
import { useUrlFilters } from "@/components/admin/hooks";
import { DateRangeFilter, Definitions, HBarChart, METRIC_DEFINITIONS, TrendChart, VBarChart, presetRange, shortDay } from "@/components/admin/charts";
import { Badge, Button, Skeleton, StatusBadge, Tabs } from "@/components/ui";
import { useToast } from "@/features/toast";
import { rupees, titleCase } from "@/utils/format";
import { cn } from "@/utils/cn";

const LABELS: Record<ReportName, string> = {
  sales: "Sales", order_status: "Order status", products: "Products", categories: "Categories", inventory: "Inventory",
  coupons: "Coupons", customers: "Customers", refunds: "Refunds & returns",
};

export default function Reports() {
  const def = presetRange(30);
  const [f, set] = useUrlFilters({ report: "sales", start: def.start, end: def.end, granularity: "day" });
  const name = (REPORT_NAMES as readonly string[]).includes(f.report) ? (f.report as ReportName) : "sales";
  const params = { start: f.start, end: f.end, granularity: name === "sales" ? f.granularity : undefined };
  const q = useQuery({ queryKey: ["admin", "report", name, params], queryFn: () => adminApi.report(name, params), placeholderData: keepPreviousData });
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const exportCsv = async () => {
    setBusy(true);
    const p = new URLSearchParams({ start: f.start, end: f.end, format: "csv", ...(name === "sales" ? { granularity: f.granularity } : {}) });
    try { await downloadFile(`/admin/reports/${name}?${p}`, `${name}-report-${f.start}-${f.end}.csv`); }
    catch (e) { toast(errorMessage(e), "error"); }
    finally { setBusy(false); }
  };
  return (
    <>
      <PageHeader title="Reports" sub="Analyse sales, products, customers and refunds over any period."
        actions={<Button variant="outline" size="sm" onClick={exportCsv} loading={busy}><Download className="h-4 w-4" aria-hidden />Export CSV</Button>} />
      <Tabs className="mb-4" value={name} onChange={(t) => set({ report: t })} tabs={REPORT_NAMES.map((r) => ({ value: r, label: LABELS[r] }))} />
      <div className="mb-5 flex flex-wrap items-center gap-2">
        {name !== "inventory" && <DateRangeFilter value={{ start: f.start, end: f.end }} onChange={(r) => set({ start: r.start, end: r.end })} presets={[7, 30, 90, 365]} />}
        {name === "sales" && (
          <FilterSelect label="Group by" value={f.granularity} onChange={(v) => set({ granularity: v })}
            options={[{ value: "day", label: "By day" }, { value: "week", label: "By week" }, { value: "month", label: "By month" }, { value: "year", label: "By year" }]} />
        )}
        {name === "inventory" && <p className="text-sm text-kajal-500">Inventory is a live snapshot; the date range doesn't apply.</p>}
      </div>
      <QueryState q={q} what="Reports" skeleton={<div className="space-y-4"><Skeleton className="h-28 rounded-2xl" /><Skeleton className="h-72 rounded-2xl" /></div>}>
        {(r) => <div className={cn("space-y-6 transition-opacity", q.isFetching && "opacity-70")}><ReportBody name={r.report} data={r.data} /></div>}
      </QueryState>
      <div className="mt-8"><Definitions text={METRIC_DEFINITIONS} /></div>
    </>
  );
}

function Stat({ label, value, sub }: { label: string; value: ReactNode; sub?: ReactNode }) {
  return <div className="card p-4"><p className="text-[13px] text-kajal-500">{label}</p><p className="mt-1 font-display text-2xl tabular">{value}</p>{sub && <p className="mt-1 text-xs text-kajal-400">{sub}</p>}</div>;
}
function Stats({ children }: { children: ReactNode }) { return <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">{children}</div>; }

type Col<T> = { key: string; label: string; align?: "right"; render?: (r: T) => ReactNode };
function DataTable<T extends Record<string, any>>({ rows, cols, empty = "No data for this period." }: { rows: T[]; cols: Col<T>[]; empty?: string }) {
  return (
    <Table minWidth={Math.max(560, cols.length * 130)}>
      <thead><tr>{cols.map((c) => <Th key={c.key} align={c.align}>{c.label}</Th>)}</tr></thead>
      <tbody>
        {rows.map((r, i) => <Tr key={i}>{cols.map((c) => <Td key={c.key} align={c.align}>{c.render ? c.render(r) : String(r[c.key] ?? "—")}</Td>)}</Tr>)}
        {!rows.length && <EmptyRow cols={cols.length}>{empty}</EmptyRow>}
      </tbody>
    </Table>
  );
}
const money = (k: string) => (r: Record<string, any>) => rupees(r[k]);

function ReportBody({ name, data }: { name: ReportName; data: any }) {
  switch (name) {
    case "sales": {
      const s = data.summary, series = data.series as any[];
      const daily = series.length && /^\d{4}-\d{2}-\d{2}$/.test(series[0].period);
      return (
        <>
          <Stats>
            <Stat label="Net sales" value={rupees(s.net_sales)} sub={`Gross ${rupees(s.gross_sales)}`} />
            <Stat label="Revenue" value={rupees(s.revenue)} sub={`Shipping ${rupees(s.shipping_collected)}`} />
            <Stat label="Orders" value={s.orders} sub={`AOV ${rupees(s.aov)}`} />
            <Stat label="Discounts" value={rupees(s.discounts)} sub={`Markdowns ${rupees(s.markdowns)}`} />
            <Stat label="Refunds" value={rupees(s.refunds)} />
            <Stat label="GST collected" value={rupees(s.tax_collected)} />
            {s.gross_margin !== undefined && <Stat label="Gross margin" value={rupees(s.gross_margin)} sub="Lines with cost data" />}
          </Stats>
          <Panel title="Net sales over time">
            {series.length ? (daily ? <TrendChart data={series} metric="net_sales" money /> : <VBarChart data={series} labelKey="period" valueKey="net_sales" money />)
              : <p className="py-10 text-center text-sm text-kajal-500">No sales in this period.</p>}
          </Panel>
          <DataTable rows={series} cols={[
            { key: "period", label: "Period", render: (r) => shortDay(r.period) },
            { key: "orders", label: "Orders", align: "right" }, { key: "net_sales", label: "Net sales", align: "right", render: money("net_sales") },
            { key: "revenue", label: "Revenue", align: "right", render: money("revenue") }]} />
        </>
      );
    }
    case "order_status": {
      const rows = data as any[];
      return (
        <>
          <Panel title="Orders by status">{rows.length ? <HBarChart data={rows} labelKey="label" valueKey="orders" money={false} /> : <p className="py-8 text-center text-sm text-kajal-500">No orders in this period.</p>}</Panel>
          <DataTable rows={rows} cols={[
            { key: "label", label: "Status", render: (r) => <StatusBadge status={r.status} label={r.label} /> },
            { key: "orders", label: "Orders", align: "right" }, { key: "value", label: "Order value", align: "right", render: money("value") }]} />
        </>
      );
    }
    case "products": {
      const rows = data as any[];
      const hasMargin = rows.some((r) => r.gross_margin !== undefined);
      return (
        <>
          <Panel title="Top 10 by units sold">{rows.length ? <HBarChart data={rows.slice(0, 10)} labelKey="name" valueKey="units" money={false} /> : <p className="py-8 text-center text-sm text-kajal-500">No sales in this period.</p>}</Panel>
          <DataTable rows={rows} cols={[
            { key: "name", label: "Product", render: (r) => r.product_id ? <Link className="text-kajal hover:underline" to={`/admin/products/${r.product_id}`}>{r.name}</Link> : r.name },
            { key: "sku", label: "SKU" }, { key: "units", label: "Units", align: "right" }, { key: "returned_units", label: "Returned", align: "right" },
            { key: "net_sales", label: "Net sales", align: "right", render: money("net_sales") },
            ...(hasMargin ? [{ key: "gross_margin", label: "Gross margin", align: "right" as const, render: money("gross_margin") }] : [])]} />
        </>
      );
    }
    case "categories": {
      const rows = data as any[];
      return (
        <>
          <Panel title="Net sales by category">{rows.length ? <HBarChart data={rows} labelKey="category" valueKey="net_sales" money /> : <p className="py-8 text-center text-sm text-kajal-500">No sales in this period.</p>}</Panel>
          <DataTable rows={rows} cols={[{ key: "category", label: "Category" }, { key: "orders", label: "Orders", align: "right" }, { key: "units", label: "Units", align: "right" }, { key: "net_sales", label: "Net sales", align: "right", render: money("net_sales") }]} />
        </>
      );
    }
    case "inventory": {
      return (
        <>
          <Stats>
            <Stat label="Active variants" value={data.variants} />
            <Stat label="Units on hand" value={data.units_on_hand.toLocaleString("en-IN")} sub={`${data.units_reserved} reserved`} />
            <Stat label="Retail value" value={rupees(data.retail_value)} sub={data.cost_value ? `Cost ${rupees(data.cost_value)}` : undefined} />
            <Stat label="Low / out of stock" value={`${data.low_stock} / ${data.out_of_stock}`} />
          </Stats>
          <h2 className="font-sans text-[15px] font-medium">Variants needing attention</h2>
          <DataTable rows={data.items} empty="Everything is well stocked." cols={[
            { key: "product_name", label: "Product", render: (r) => <Link className="text-kajal hover:underline" to={`/admin/products/${r.product_id}`}>{r.product_name}</Link> },
            { key: "variant_name", label: "Variant" }, { key: "sku", label: "SKU" }, { key: "on_hand", label: "On hand", align: "right" },
            { key: "reserved", label: "Reserved", align: "right" }, { key: "available", label: "Available", align: "right" },
            { key: "status", label: "Status", render: (r) => <Badge className={r.status === "out_of_stock" ? "!bg-kumkum-50 !text-kumkum" : ""} tone={r.status === "out_of_stock" ? "sale" : "warning"}>{r.status === "out_of_stock" ? "Out of stock" : "Low"}</Badge> }]} />
        </>
      );
    }
    case "coupons": {
      const rows = data as any[];
      const used = rows.filter((r) => r.redemptions > 0);
      return (
        <>
          <Panel title="Discount given by coupon">{used.length ? <HBarChart data={used} labelKey="code" valueKey="discount_given" money /> : <p className="py-8 text-center text-sm text-kajal-500">No coupons were used in this period.</p>}</Panel>
          <DataTable rows={rows} cols={[
            { key: "code", label: "Code", render: (r) => <span className="font-mono text-[13px]">{r.code}</span> },
            { key: "type", label: "Type", render: (r) => titleCase(r.type) }, { key: "redemptions", label: "Redemptions", align: "right" },
            { key: "times_used_all_time", label: "All-time uses", align: "right", render: (r) => `${r.times_used_all_time}${r.usage_limit ? ` / ${r.usage_limit}` : ""}` },
            { key: "discount_given", label: "Discount given", align: "right", render: money("discount_given") },
            { key: "order_value", label: "Order value", align: "right", render: money("order_value") }]} />
        </>
      );
    }
    case "customers": {
      return (
        <>
          <Stats>
            <Stat label="Buyers (all time)" value={data.buyers} />
            <Stat label="Repeat buyers" value={data.repeat_buyers} />
            <Stat label="Repeat rate" value={`${data.repeat_rate}%`} />
            <Stat label="New sign-ups in range" value={(data.acquisition as any[]).reduce((a, r) => a + r.new_customers, 0)} />
          </Stats>
          <Panel title="New customers by month">{data.acquisition.length ? <VBarChart data={data.acquisition} labelKey="month" valueKey="new_customers" money={false} /> : <p className="py-8 text-center text-sm text-kajal-500">No sign-ups in this period.</p>}</Panel>
          <h2 className="font-sans text-[15px] font-medium">Top customers by lifetime value</h2>
          <DataTable rows={data.top_customers} cols={[{ key: "email", label: "Email" }, { key: "orders", label: "Orders", align: "right" }, { key: "lifetime_value", label: "Lifetime value", align: "right", render: money("lifetime_value") }]} />
        </>
      );
    }
    case "refunds": {
      const refunded = (data.refunds as any[]).reduce((a, r) => a + Number(r.amount), 0);
      return (
        <>
          <Stats>
            <Stat label="Cancelled orders" value={data.cancelled_orders} sub={`Value ${rupees(data.cancelled_value)}`} />
            <Stat label="Refunds" value={(data.refunds as any[]).reduce((a, r) => a + r.count, 0)} sub={`Amount ${rupees(refunded)}`} />
            <Stat label="Return requests" value={(data.returns as any[]).reduce((a, r) => a + r.count, 0)} />
          </Stats>
          <div className="grid gap-6 xl:grid-cols-2">
            <div><h2 className="mb-3 font-sans text-[15px] font-medium">Cancellation reasons</h2>
              <DataTable rows={data.cancellation_reasons} cols={[{ key: "reason", label: "Reason" }, { key: "count", label: "Orders", align: "right" }]} /></div>
            <div><h2 className="mb-3 font-sans text-[15px] font-medium">Refunds by status</h2>
              <DataTable rows={data.refunds} cols={[{ key: "status", label: "Status", render: (r) => <StatusBadge status={r.status} /> }, { key: "count", label: "Count", align: "right" }, { key: "amount", label: "Amount", align: "right", render: money("amount") }]} /></div>
          </div>
          <div><h2 className="mb-3 font-sans text-[15px] font-medium">Returns by reason</h2>
            <DataTable rows={data.returns} cols={[{ key: "reason", label: "Reason", render: (r) => titleCase(r.reason) }, { key: "status", label: "Status", render: (r) => <StatusBadge status={r.status} /> }, { key: "count", label: "Count", align: "right" }]} /></div>
        </>
      );
    }
  }
}
