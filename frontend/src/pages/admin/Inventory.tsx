import { useState } from "react";
import { Link } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { adminApi, type InventoryRow } from "@/services/admin";
import {
  EmptyRow, FilterBar, FilterSelect, PageHeader, QueryState, SearchBox, Table, TableFooter, TableSkeleton, Td, Th, Thumb, Tr, Chip,
} from "@/components/admin/kit";
import { useAdminMutation, useUrlFilters } from "@/components/admin/hooks";
import { Badge, Button, Input, Modal, Select, StatusBadge, Tabs, Textarea } from "@/components/ui";
import { useAuth } from "@/features/auth";
import { date } from "@/utils/format";
import { cn } from "@/utils/cn";

const DEFAULTS = { tab: "stock", q: "", stock: "", page: "1", type: "" };

export default function Inventory() {
  const [f, set] = useUrlFilters(DEFAULTS);
  const { can } = useAuth();
  const write = can("inventory:write");
  const sweep = useAdminMutation(() => adminApi.sweepReservations(), {
    invalidate: [["admin", "inventory"], ["admin", "reservations"]],
    success: (r) => {
      const n = Array.isArray(r.released_orders) ? r.released_orders.length : Number(r.released_orders) || 0;
      return n ? `Released holds for ${n} expired order${n === 1 ? "" : "s"}` : "No expired holds to release";
    },
  });
  return (
    <>
      <PageHeader title="Inventory" sub="Stock on hand, reservations held by unpaid orders, and every movement."
        actions={write && <Button variant="outline" size="sm" onClick={() => sweep.mutate(undefined)} loading={sweep.isPending}><RefreshCw className="h-4 w-4" aria-hidden />Release expired holds</Button>} />
      <Tabs className="mb-5" value={f.tab as "stock" | "movements" | "reservations"} onChange={(t) => set({ tab: t, q: "", stock: "", type: "" })}
        tabs={[{ value: "stock", label: "Stock levels" }, { value: "movements", label: "Movement history" }, { value: "reservations", label: "Active reservations" }]} />
      {f.tab === "stock" && <StockTab f={f} set={set} write={write} />}
      {f.tab === "movements" && <MovementsTab f={f} set={set} />}
      {f.tab === "reservations" && <ReservationsTab />}
    </>
  );
}

type TabProps = { f: typeof DEFAULTS; set: (p: Partial<typeof DEFAULTS>, resetPage?: boolean) => void };

function StockTab({ f, set, write }: TabProps & { write: boolean }) {
  const q = useQuery({ queryKey: ["admin", "inventory", f.q, f.stock, f.page], queryFn: () => adminApi.inventory({ q: f.q, stock: f.stock, page: f.page, page_size: 25 }), placeholderData: keepPreviousData });
  const [adjust, setAdjust] = useState<InventoryRow | null>(null);
  return (
    <>
      <FilterBar>
        <SearchBox className="w-full sm:w-72" value={f.q} onChange={(v) => set({ q: v })} placeholder="Search SKU or product" label="Search inventory" />
        {[["", "All"], ["low", "Low stock"], ["out", "Out of stock"], ["in", "Healthy"]].map(([v, l]) => (
          <Chip key={v} active={f.stock === v} onClick={() => set({ stock: v })}>{l}</Chip>
        ))}
      </FilterBar>
      <QueryState q={q} what="Inventory" skeleton={<Table><tbody><TableSkeleton cols={7} /></tbody></Table>}>
        {(d) => (
          <>
            <Table minWidth={860} className={cn(q.isFetching && "opacity-70")}>
              <thead><tr><Th>Variant</Th><Th>Status</Th><Th align="right">On hand</Th><Th align="right">Reserved</Th><Th align="right">Available</Th><Th align="right">Alert at</Th><Th align="right"><span className="sr-only">Actions</span></Th></tr></thead>
              <tbody>
                {d.items.map((r) => (
                  <Tr key={r.variant_id}>
                    <Td>
                      <div className="flex items-center gap-3">
                        <Thumb src={r.image} size={36} />
                        <div className="min-w-0">
                          <Link to={`/admin/products/${r.product_id}`} className="block max-w-[320px] truncate text-kajal hover:underline">{r.product_name}</Link>
                          <p className="text-xs text-kajal-400">{r.variant_name} · {r.sku}{!r.is_active && " · inactive"}</p>
                        </div>
                      </div>
                    </Td>
                    <Td><Badge className={r.status === "out_of_stock" ? "!bg-kumkum-50 !text-kumkum" : ""} tone={r.status === "out_of_stock" ? "sale" : r.status === "low_stock" ? "warning" : "success"}>{r.status === "out_of_stock" ? "Out of stock" : r.status === "low_stock" ? "Low" : "In stock"}</Badge></Td>
                    <Td align="right">{r.on_hand}</Td>
                    <Td align="right">{r.reserved || <span className="text-kajal-300">0</span>}</Td>
                    <Td align="right"><span className={cn("font-medium", r.available <= 0 ? "text-kumkum" : r.available <= r.low_stock_threshold ? "text-[#8A5A00]" : "text-kajal")}>{r.available}</span></Td>
                    <Td align="right" className="text-kajal-500">{r.low_stock_threshold}</Td>
                    <Td align="right">{write && <Button variant="ghost" size="sm" className="h-8 text-gold-700 hover:bg-gold-50" onClick={() => setAdjust(r)}>Adjust stock</Button>}</Td>
                  </Tr>
                ))}
                {!d.items.length && <EmptyRow cols={7}>No variants match.</EmptyRow>}
              </tbody>
            </Table>
            <TableFooter total={d.total} page={d.page} pages={d.pages} onPage={(p) => set({ page: String(p) }, false)} noun="variant" />
          </>
        )}
      </QueryState>
      {adjust && <AdjustModal row={adjust} onClose={() => setAdjust(null)} />}
    </>
  );
}

function AdjustModal({ row, onClose }: { row: InventoryRow; onClose: () => void }) {
  const [dir, setDir] = useState<"add" | "remove">("add");
  const [qty, setQty] = useState("");
  const [type, setType] = useState("restock");
  const [note, setNote] = useState("");
  const [threshold, setThreshold] = useState(String(row.low_stock_threshold));
  const [err, setErr] = useState<string | null>(null);
  const n = Number(qty || 0);
  const delta = dir === "add" ? n : -n;
  const after = row.on_hand + delta;
  const m = useAdminMutation(() => adminApi.adjustStock({
    variant_id: row.variant_id, delta, movement_type: type, note: note || null,
    low_stock_threshold: threshold !== String(row.low_stock_threshold) ? Number(threshold) : null,
  }), { invalidate: [["admin", "inventory"], ["admin", "movements"], ["admin", "dashboard"]], success: (r) => `${row.sku}: ${r.on_hand} on hand, ${r.available} available`, onSuccess: onClose });
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (qty && (!/^\d+$/.test(qty))) return setErr("Enter a whole number");
    if (!/^\d+$/.test(threshold)) return setErr("Alert threshold must be a whole number");
    if (!n && threshold === String(row.low_stock_threshold)) return setErr("Enter a quantity or change the alert threshold");
    if (after < row.reserved) return setErr(`On hand can't drop below the ${row.reserved} units reserved by open orders`);
    setErr(null);
    m.mutate(undefined);
  };
  return (
    <Modal open onClose={onClose} title="Adjust stock" size="md"
      footer={<><Button variant="ghost" size="sm" onClick={onClose}>Cancel</Button><Button size="sm" type="submit" form="adjust-form" loading={m.isPending}>Save adjustment</Button></>}>
      <form id="adjust-form" onSubmit={submit} className="space-y-4">
        <div className="rounded-xl bg-ivory-200/60 px-4 py-3 text-sm">
          <p className="font-medium text-kajal">{row.product_name}</p>
          <p className="text-kajal-500">{row.variant_name} · {row.sku}</p>
          <p className="mt-1 tabular text-kajal-700">On hand {row.on_hand} · reserved {row.reserved} · available {row.available}</p>
        </div>
        <div role="radiogroup" aria-label="Direction" className="inline-flex rounded-full border border-kajal-300/50 bg-white p-0.5">
          {(["add", "remove"] as const).map((d) => (
            <button key={d} type="button" role="radio" aria-checked={dir === d}
              onClick={() => { setDir(d); setType(d === "add" ? "restock" : "damage"); }}
              className={cn("rounded-full px-4 py-1.5 text-sm", dir === d ? "bg-kajal text-ivory" : "text-kajal-700 hover:bg-ivory-200")}>
              {d === "add" ? "Add stock (+)" : "Remove stock (−)"}
            </button>
          ))}
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Input label="Quantity" inputMode="numeric" value={qty} onChange={(e) => setQty(e.target.value.replace(/[^\d]/g, ""))} placeholder="0" />
          <Select label="Reason" value={type} onChange={(e) => setType(e.target.value)} options={[
            { value: "restock", label: "Restock" }, { value: "adjustment", label: "Count adjustment" }, { value: "damage", label: "Damaged / lost" }, { value: "return", label: "Customer return" }]} />
        </div>
        {n > 0 && <p className="text-sm tabular text-kajal-700">On hand will be <strong>{after}</strong> ({delta > 0 ? "+" : ""}{delta}).</p>}
        <Textarea label="Note" rows={2} value={note} onChange={(e) => setNote(e.target.value)} maxLength={255} placeholder="e.g. PO #1043 received" />
        <Input label="Low-stock alert threshold" inputMode="numeric" value={threshold} onChange={(e) => setThreshold(e.target.value.replace(/[^\d]/g, ""))} />
        {err && <p role="alert" className="text-sm text-kumkum">{err}</p>}
      </form>
    </Modal>
  );
}

const TYPES = ["", "initial", "restock", "adjustment", "damage", "return", "sale", "cancellation"];
function MovementsTab({ f, set }: TabProps) {
  const q = useQuery({ queryKey: ["admin", "movements", f.type, f.page], queryFn: () => adminApi.movements({ movement_type: f.type, page: f.page, page_size: 30 }), placeholderData: keepPreviousData });
  return (
    <>
      <FilterBar>
        <FilterSelect label="Movement type" value={f.type} onChange={(v) => set({ type: v })} options={TYPES.map((t) => ({ value: t, label: t ? t[0].toUpperCase() + t.slice(1) : "All movement types" }))} />
      </FilterBar>
      <QueryState q={q} what="Inventory" skeleton={<Table><tbody><TableSkeleton cols={7} /></tbody></Table>}>
        {(d) => (
          <>
            <Table minWidth={900}>
              <thead><tr><Th>When</Th><Th>Variant</Th><Th>Type</Th><Th align="right">Change</Th><Th align="right">Balance</Th><Th>Reference / note</Th><Th>By</Th></tr></thead>
              <tbody>
                {d.items.map((m) => (
                  <Tr key={m.id}>
                    <Td className="whitespace-nowrap">{date(m.at, "long")}</Td>
                    <Td><span className="block max-w-[260px] truncate text-kajal">{m.product_name}</span><span className="text-xs text-kajal-400">{m.variant_name} · {m.sku}</span></Td>
                    <Td><Badge>{m.movement_type}</Badge></Td>
                    <Td align="right"><span className={m.quantity < 0 ? "text-kumkum" : "text-leaf"}>{m.quantity > 0 ? "+" : ""}{m.quantity}</span></Td>
                    <Td align="right">{m.balance_after}</Td>
                    <Td><span className="block max-w-[240px] truncate text-kajal-500">{[m.reference, m.note].filter(Boolean).join(" · ") || "—"}</span></Td>
                    <Td className="whitespace-nowrap text-kajal-500">{m.by}</Td>
                  </Tr>
                ))}
                {!d.items.length && <EmptyRow cols={7}>No movements.</EmptyRow>}
              </tbody>
            </Table>
            <TableFooter total={d.total} page={d.page} pages={d.pages} onPage={(p) => set({ page: String(p) }, false)} noun="movement" />
          </>
        )}
      </QueryState>
    </>
  );
}

function ReservationsTab() {
  const q = useQuery({ queryKey: ["admin", "reservations"], queryFn: () => adminApi.reservations("active") });
  return (
    <QueryState q={q} what="Inventory" skeleton={<Table><tbody><TableSkeleton cols={5} /></tbody></Table>}>
      {(rows) => (
        <>
          <p className="mb-3 text-sm text-kajal-500">Units held for orders awaiting payment. Holds past their expiry are released automatically, or immediately with “Release expired holds”.</p>
          <Table minWidth={640}>
            <thead><tr><Th>Order</Th><Th>SKU</Th><Th align="right">Qty</Th><Th>Expires</Th><Th>Status</Th></tr></thead>
            <tbody>
              {rows.map((r) => {
                const expired = new Date(r.expires_at + "Z").getTime() < Date.now();
                return (
                  <Tr key={r.id}>
                    <Td>{r.order_number ? <Link className="text-kajal hover:underline" to={`/admin/orders/${r.order_id}`}>{r.order_number}</Link> : "—"}</Td>
                    <Td>{r.sku}</Td>
                    <Td align="right">{r.quantity}</Td>
                    <Td className={cn("whitespace-nowrap", expired && "text-kumkum")}>{date(r.expires_at, "long")}{expired && " · expired"}</Td>
                    <Td><StatusBadge status={r.status} /></Td>
                  </Tr>
                );
              })}
              {!rows.length && <EmptyRow cols={5}>No active reservations.</EmptyRow>}
            </tbody>
          </Table>
        </>
      )}
    </QueryState>
  );
}
