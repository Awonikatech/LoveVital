import { Fragment, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ChevronRight } from "lucide-react";
import { adminApi } from "@/services/admin";
import { EmptyRow, FilterBar, FilterSelect, PageHeader, QueryState, SearchBox, Table, TableFooter, TableSkeleton, Td, Th, Tr } from "@/components/admin/kit";
import { useUrlFilters } from "@/components/admin/hooks";
import { Badge } from "@/components/ui";
import { date } from "@/utils/format";
import { cn } from "@/utils/cn";

const ENTITIES = ["", "order", "product", "variant", "category", "collection", "coupon", "promotion", "shipping_method", "pincode", "banner", "page", "settings", "user", "return", "shipment", "tax_rate"];

export default function AuditLog() {
  const [f, set] = useUrlFilters({ entity_type: "", action: "", page: "1" });
  const q = useQuery({ queryKey: ["admin", "audit", f], queryFn: () => adminApi.audit({ ...f, page_size: 50 }), placeholderData: keepPreviousData });
  const [open, setOpen] = useState<Set<number>>(new Set());
  const toggle = (id: number) => setOpen((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  return (
    <>
      <PageHeader title="Audit log" sub="Every change made by staff, with who, when and what changed." />
      <FilterBar>
        <FilterSelect label="Entity" value={f.entity_type} onChange={(v) => set({ entity_type: v })} options={ENTITIES.map((e) => ({ value: e, label: e ? e.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase()) : "All entities" }))} />
        <SearchBox className="w-full sm:w-64" value={f.action} onChange={(v) => set({ action: v })} placeholder="Action starts with, e.g. order." label="Filter by action" />
      </FilterBar>
      <QueryState q={q} what="The audit log" skeleton={<Table><tbody><TableSkeleton cols={5} /></tbody></Table>}>
        {(d) => (
          <>
            <Table minWidth={820} className={cn(q.isFetching && "opacity-70")}>
              <thead><tr><Th className="w-8"><span className="sr-only">Expand</span></Th><Th>When</Th><Th>Who</Th><Th>Action</Th><Th>Entity</Th><Th>IP</Th></tr></thead>
              <tbody>
                {d.items.map((a) => {
                  const isOpen = open.has(a.id);
                  const has = a.changes !== null && a.changes !== undefined;
                  return (
                    <Fragment key={a.id}>
                      <Tr onClick={has ? () => toggle(a.id) : undefined}>
                        <Td>{has && (
                          <button type="button" aria-expanded={isOpen} aria-label={isOpen ? "Hide changes" : "Show changes"} onClick={(e) => { e.stopPropagation(); toggle(a.id); }} className="rounded p-0.5 text-kajal-400 hover:text-kajal">
                            <ChevronRight className={cn("h-4 w-4 transition-transform", isOpen && "rotate-90")} />
                          </button>
                        )}</Td>
                        <Td className="whitespace-nowrap">{date(a.at, "long")}</Td>
                        <Td className="max-w-[220px] truncate">{a.actor}</Td>
                        <Td><code className="text-[13px] text-kajal">{a.action}</code></Td>
                        <Td><Badge>{a.entity_type}</Badge>{a.entity_id && <span className="ml-1.5 text-kajal-500 tabular">#{a.entity_id}</span>}</Td>
                        <Td className="text-kajal-400 tabular">{a.ip ?? "—"}</Td>
                      </Tr>
                      {isOpen && (
                        <tr><td colSpan={6} className="border-b border-gold-200/30 bg-ivory-50 px-4 py-3">
                          <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-lg border border-gold-200/50 bg-white p-3 font-mono text-[12.5px] leading-5 text-kajal-700">{JSON.stringify(a.changes, null, 2)}</pre>
                        </td></tr>
                      )}
                    </Fragment>
                  );
                })}
                {!d.items.length && <EmptyRow cols={6}>No audit entries.</EmptyRow>}
              </tbody>
            </Table>
            <TableFooter total={d.total} page={d.page} pages={d.pages} onPage={(p) => set({ page: String(p) }, false)} noun="entry" />
          </>
        )}
      </QueryState>
    </>
  );
}
