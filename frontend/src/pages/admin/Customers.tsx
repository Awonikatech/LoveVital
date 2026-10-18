import { Link, useNavigate } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { adminApi } from "@/services/admin";
import {
  EmptyRow, FilterBar, FilterSelect, PageHeader, QueryState, SearchBox, Table, TableFooter, TableSkeleton, Td, Th, Tr,
} from "@/components/admin/kit";
import { useUrlFilters } from "@/components/admin/hooks";
import { Badge } from "@/components/ui";
import { date, rupees } from "@/utils/format";
import { cn } from "@/utils/cn";

const DEFAULTS = { q: "", status: "", sort: "newest", page: "1" };

export default function Customers() {
  const [f, set] = useUrlFilters(DEFAULTS);
  const nav = useNavigate();
  const q = useQuery({ queryKey: ["admin", "customers", f], queryFn: () => adminApi.customers({ ...f, page_size: 20 }), placeholderData: keepPreviousData });
  return (
    <>
      <PageHeader title="Customers" sub="Registered shoppers, their orders and lifetime value." />
      <FilterBar>
        <SearchBox className="w-full sm:w-80" value={f.q} onChange={(v) => set({ q: v })} placeholder="Name, email or phone" label="Search customers" />
        <FilterSelect label="Account status" value={f.status} onChange={(v) => set({ status: v })} options={[{ value: "", label: "All accounts" }, { value: "active", label: "Active" }, { value: "disabled", label: "Disabled" }]} />
        <FilterSelect label="Sort by" value={f.sort} onChange={(v) => set({ sort: v })} options={[
          { value: "newest", label: "Newest first" }, { value: "spend", label: "Highest spend" }, { value: "orders", label: "Most orders" }, { value: "name", label: "Name (A–Z)" }]} />
      </FilterBar>
      <QueryState q={q} what="Customers" skeleton={<Table><tbody><TableSkeleton cols={6} /></tbody></Table>}>
        {(d) => (
          <>
            <Table minWidth={820} className={cn(q.isFetching && "opacity-70")}>
              <thead><tr><Th>Customer</Th><Th>Phone</Th><Th>Joined</Th><Th>Last order</Th><Th align="right">Orders</Th><Th align="right">Total spend</Th></tr></thead>
              <tbody>
                {d.items.map((c) => (
                  <Tr key={c.id} onClick={() => nav(`/admin/customers/${c.id}`)}>
                    <Td>
                      <Link to={`/admin/customers/${c.id}`} onClick={(e) => e.stopPropagation()} className="font-medium text-kajal hover:underline">{c.full_name}</Link>
                      {!c.is_active && <Badge tone="sale" className="ml-2 !bg-kumkum-50 !text-kumkum">Disabled</Badge>}
                      <span className="block text-xs text-kajal-400">{c.email}{!c.email_verified && " · unverified"}</span>
                    </Td>
                    <Td className="whitespace-nowrap">{c.phone ?? "—"}</Td>
                    <Td className="whitespace-nowrap">{date(c.created_at)}</Td>
                    <Td className="whitespace-nowrap">{date(c.last_order_at)}</Td>
                    <Td align="right">{c.orders}</Td>
                    <Td align="right" className="font-medium text-kajal">{rupees(c.total_spend)}</Td>
                  </Tr>
                ))}
                {!d.items.length && <EmptyRow cols={6}>No customers match.</EmptyRow>}
              </tbody>
            </Table>
            <TableFooter total={d.total} page={d.page} pages={d.pages} onPage={(p) => set({ page: String(p) }, false)} noun="customer" />
          </>
        )}
      </QueryState>
    </>
  );
}
