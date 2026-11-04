import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { adminApi, ORDER_STATUSES, qs } from "@/services/admin";
import { downloadFile, errorMessage } from "@/services/api";
import {
  Chip, EmptyRow, FilterBar, FilterSelect, PageHeader, QueryState, SearchBox, Table, TableFooter, TableSkeleton, Td, Th, Thumb, Tr,
} from "@/components/admin/kit";
import { useUrlFilters } from "@/components/admin/hooks";
import { Button, StatusBadge } from "@/components/ui";
import { useToast } from "@/features/toast";
import { date, rupees } from "@/utils/format";
import { cn } from "@/utils/cn";

const DEFAULTS = { q: "", status: "", payment_status: "", payment_method: "", date_from: "", date_to: "", page: "1" };

export default function Orders() {
  const [f, set] = useUrlFilters(DEFAULTS);
  const nav = useNavigate();
  const toast = useToast();
  const [exporting, setExporting] = useState(false);
  const q = useQuery({ queryKey: ["admin", "orders", f], queryFn: () => adminApi.orders({ ...f, page_size: 20 }), placeholderData: keepPreviousData });
  const counts = q.data?.status_counts ?? {};
  const totalAll = Object.values(counts).reduce((a, b) => a + b, 0);
  const selected = f.status ? f.status.split(",") : [];
  const filterParams = { q: f.q, status: f.status, payment_status: f.payment_status, payment_method: f.payment_method, date_from: f.date_from, date_to: f.date_to };

  const exportCsv = async () => {
    setExporting(true);
    try { await downloadFile(`/admin/orders-export.csv${qs(filterParams)}`, `orders-${new Date().toISOString().slice(0, 10)}.csv`); }
    catch (e) { toast(errorMessage(e), "error"); }
    finally { setExporting(false); }
  };
  const toggleStatus = (s: string) => {
    const next = selected.includes(s) ? selected.filter((x) => x !== s) : [s];
    set({ status: next.join(",") });
  };

  return (
    <>
      <PageHeader title="Orders" sub="Search, filter and fulfil customer orders."
        actions={<Button variant="outline" size="sm" onClick={exportCsv} loading={exporting}><Download className="h-4 w-4" aria-hidden />Export CSV</Button>} />

      <div className="-mx-4 mb-3 overflow-x-auto px-4 pb-1 scrollbar-none sm:mx-0 sm:px-0">
        <div className="flex gap-1.5" role="group" aria-label="Filter by status">
          <Chip active={!selected.length} onClick={() => set({ status: "" })} count={totalAll}>All</Chip>
          {selected.length > 1 && <Chip active onClick={() => set({ status: "" })}>{selected.length} statuses</Chip>}
          {ORDER_STATUSES.filter((s) => counts[s.value]).map((s) => (
            <Chip key={s.value} active={selected.length === 1 && selected[0] === s.value} onClick={() => toggleStatus(s.value)} count={counts[s.value]}>{s.label}</Chip>
          ))}
        </div>
      </div>

      <FilterBar>
        <SearchBox className="w-full sm:w-80" value={f.q} onChange={(v) => set({ q: v })} placeholder="Order number, email, name or phone" label="Search orders" />
        <FilterSelect label="Payment status" value={f.payment_status} onChange={(v) => set({ payment_status: v })} options={[
          { value: "", label: "Any payment status" }, { value: "paid", label: "Paid" }, { value: "pending", label: "Pending" }, { value: "failed", label: "Failed" },
          { value: "partially_refunded", label: "Partially refunded" }, { value: "refunded", label: "Refunded" }, { value: "cancelled", label: "Cancelled" }]} />
        <FilterSelect label="Payment method" value={f.payment_method} onChange={(v) => set({ payment_method: v })} options={[
          { value: "", label: "Any method" }, { value: "razorpay", label: "Online (Razorpay)" }, { value: "cod", label: "Cash on delivery" }]} />
        <div className="flex items-center gap-1.5">
          <label className="sr-only" htmlFor="o-from">Placed from</label>
          <input id="o-from" type="date" className="input h-10 w-[150px] py-0 text-sm" value={f.date_from} max={f.date_to || undefined} onChange={(e) => set({ date_from: e.target.value })} />
          <span className="text-kajal-400" aria-hidden>–</span>
          <label className="sr-only" htmlFor="o-to">Placed to</label>
          <input id="o-to" type="date" className="input h-10 w-[150px] py-0 text-sm" value={f.date_to} min={f.date_from || undefined} onChange={(e) => set({ date_to: e.target.value })} />
        </div>
        {(f.q || f.status || f.payment_status || f.payment_method || f.date_from || f.date_to) && (
          <Button variant="link" size="sm" onClick={() => set({ q: "", status: "", payment_status: "", payment_method: "", date_from: "", date_to: "" })}>Clear filters</Button>
        )}
      </FilterBar>

      <QueryState q={q} what="Orders" skeleton={<Table><tbody><TableSkeleton cols={7} /></tbody></Table>}>
        {(d) => (
          <>
            <Table minWidth={960} className={cn(q.isFetching && "opacity-70")}>
              <thead><tr><Th>Order</Th><Th>Customer</Th><Th>Placed</Th><Th>Status</Th><Th>Payment</Th><Th align="right">Items</Th><Th align="right">Total</Th></tr></thead>
              <tbody>
                {d.items.map((o) => (
                  <Tr key={o.id} onClick={() => nav(`/admin/orders/${o.id}`)}>
                    <Td>
                      <div className="flex items-center gap-3">
                        <Thumb src={o.thumbnails[0]} size={36} />
                        <div>
                          <Link to={`/admin/orders/${o.id}`} onClick={(e) => e.stopPropagation()} className="font-medium text-kajal hover:underline">{o.order_number}</Link>
                          <p className="max-w-[200px] truncate text-xs text-kajal-400">{o.first_item}</p>
                        </div>
                      </div>
                    </Td>
                    <Td><span className="block max-w-[200px] truncate text-kajal">{o.customer_name ?? "—"}</span><span className="block max-w-[200px] truncate text-xs text-kajal-400">{o.email}</span></Td>
                    <Td className="whitespace-nowrap">{date(o.placed_at, "long")}</Td>
                    <Td><StatusBadge status={o.status} /></Td>
                    <Td className="whitespace-nowrap"><span className="mr-1.5 text-xs text-kajal-500">{o.payment_method === "cod" ? "COD" : "Online"}</span><StatusBadge status={o.payment_status} /></Td>
                    <Td align="right">{o.item_count}</Td>
                    <Td align="right" className="font-medium text-kajal">{rupees(o.grand_total)}</Td>
                  </Tr>
                ))}
                {!d.items.length && <EmptyRow cols={7}>No orders match these filters.</EmptyRow>}
              </tbody>
            </Table>
            <TableFooter total={d.total} page={d.page} pages={d.pages} onPage={(p) => set({ page: String(p) }, false)} noun="order" />
          </>
        )}
      </QueryState>
    </>
  );
}
