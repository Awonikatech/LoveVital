import { useState } from "react";
import { Link } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { adminApi, type ReturnRequest } from "@/services/admin";
import { Chip, EmptyRow, FilterBar, KeyVal, PageHeader, QueryState, Table, TableFooter, TableSkeleton, Td, Th, Thumb, Tr } from "@/components/admin/kit";
import { useAdminMutation, useUrlFilters } from "@/components/admin/hooks";
import { Alert, Button, Drawer, StatusBadge, Textarea } from "@/components/ui";
import { useAuth } from "@/features/auth";
import { date, rupees, titleCase } from "@/utils/format";
import { cn } from "@/utils/cn";

const FILTERS: [string, string][] = [["", "All"], ["requested", "Requested"], ["approved", "Approved"], ["received", "Received"], ["rejected", "Rejected"], ["requested,approved", "Open"]];

export default function Returns() {
  const [f, set] = useUrlFilters({ status: "", page: "1" });
  const q = useQuery({ queryKey: ["admin", "returns", f], queryFn: () => adminApi.returns({ ...f, page_size: 20 }), placeholderData: keepPreviousData });
  const [openId, setOpenId] = useState<number | null>(null);
  const open = q.data?.items.find((r) => r.id === openId) ?? null;
  return (
    <>
      <PageHeader title="Returns" sub="Review return requests, confirm receipt and refund customers." />
      <FilterBar>
        {FILTERS.map(([v, l]) => <Chip key={v} active={f.status === v} onClick={() => set({ status: v })}>{l}</Chip>)}
      </FilterBar>
      <QueryState q={q} what="Returns" skeleton={<Table><tbody><TableSkeleton cols={6} /></tbody></Table>}>
        {(d) => (
          <>
            <Table minWidth={860} className={cn(q.isFetching && "opacity-70")}>
              <thead><tr><Th>Request</Th><Th>Order</Th><Th>Reason</Th><Th>Items</Th><Th>Status</Th><Th align="right">Refund</Th></tr></thead>
              <tbody>
                {d.items.map((r) => (
                  <Tr key={r.id} onClick={() => setOpenId(r.id)}>
                    <Td><button type="button" className="font-medium text-kajal hover:underline" onClick={(e) => { e.stopPropagation(); setOpenId(r.id); }}>#{r.id} · {titleCase(r.return_type)}</button><span className="block text-xs text-kajal-400">{date(r.created_at, "long")}</span></Td>
                    <Td><Link to={`/admin/orders/${r.order_id}`} onClick={(e) => e.stopPropagation()} className="text-kajal hover:underline">{r.order_number}</Link><span className="block max-w-[200px] truncate text-xs text-kajal-400">{r.customer_email}</span></Td>
                    <Td>{titleCase(r.reason)}</Td>
                    <Td>{r.items.reduce((a, i) => a + i.quantity, 0)} item{r.items.reduce((a, i) => a + i.quantity, 0) === 1 ? "" : "s"}</Td>
                    <Td><StatusBadge status={r.status} /></Td>
                    <Td align="right">{rupees(r.refund_amount)}</Td>
                  </Tr>
                ))}
                {!d.items.length && <EmptyRow cols={6}>No return requests.</EmptyRow>}
              </tbody>
            </Table>
            <TableFooter total={d.total} page={d.page} pages={d.pages} onPage={(p) => set({ page: String(p) }, false)} noun="request" />
          </>
        )}
      </QueryState>
      <Drawer open={!!open} onClose={() => setOpenId(null)} title={open ? `Return #${open.id}` : ""}>
        {open && <ReturnDetail r={open} />}
      </Drawer>
    </>
  );
}

function ReturnDetail({ r }: { r: ReturnRequest }) {
  const { can } = useAuth();
  const write = can("returns:write");
  const [note, setNote] = useState(r.admin_note ?? "");
  const act = useAdminMutation((a: "approve" | "reject" | "receive") => adminApi.returnAction(r.id, a, note), {
    invalidate: [["admin", "returns"], ["admin", "order", r.order_id], ["admin", "orders"], ["admin", "dashboard"]],
    success: (_, a) => ({ approve: "Return approved — ask the customer to send the item", reject: "Return rejected", receive: "Return received, stock restocked and refund issued" }[a]),
  });
  const prepaid = r.payment_method !== "cod";
  const needsRefundPerm = r.return_type === "return" && prepaid && !can("refunds:write");
  return (
    <div className="space-y-5 p-5">
      <div className="flex flex-wrap items-center gap-2"><StatusBadge status={r.status} /><span className="text-sm text-kajal-500">Order <Link to={`/admin/orders/${r.order_id}`} className="text-kajal underline decoration-gold-300 underline-offset-2">{r.order_number}</Link> · <StatusBadge status={r.order_status} /></span></div>
      <dl className="rounded-xl border border-gold-200/60 bg-white px-4 py-2">
        <KeyVal k="Type" v={titleCase(r.return_type)} />
        <KeyVal k="Customer" v={r.customer_email} />
        <KeyVal k="Reason" v={titleCase(r.reason)} />
        <KeyVal k="Requested" v={date(r.created_at, "long")} />
        {r.resolved_at && <KeyVal k="Resolved" v={date(r.resolved_at, "long")} />}
        <KeyVal k="Payment" v={prepaid ? "Prepaid (online)" : "Cash on delivery"} />
        <KeyVal k="Refund amount" v={<span className="font-medium">{rupees(r.refund_amount)}</span>} />
      </dl>
      {r.details && <p className="rounded-xl bg-ivory-200/60 px-4 py-3 text-sm text-kajal-700">“{r.details}”</p>}
      <div>
        <h3 className="mb-2 font-sans text-sm font-medium text-kajal">Items</h3>
        <ul className="space-y-2">
          {r.items.map((i) => (
            <li key={i.order_item_id} className="flex items-center gap-3">
              <Thumb src={i.image_url} size={44} />
              <div className="min-w-0 flex-1"><p className="truncate text-sm text-kajal">{i.product_name}</p><p className="text-xs text-kajal-400">{i.sku}</p></div>
              <span className="text-sm tabular">× {i.quantity}</span>
            </li>
          ))}
        </ul>
      </div>
      {write && (r.status === "requested" || r.status === "approved") && (
        <div className="space-y-3 border-t border-gold-200/50 pt-5">
          <Textarea label="Note for the record" rows={2} value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} />
          {r.status === "approved" && (
            <Alert tone={needsRefundPerm ? "warning" : "info"}>
              Marking it received restocks the items{r.return_type === "return" ? <> and refunds <strong>{rupees(r.refund_amount)}</strong>{prepaid ? " to the original payment method" : ""}</> : ""}.
              {needsRefundPerm && " This is a prepaid order, so an administrator with refund permission must complete this step."}
            </Alert>
          )}
          <div className="flex flex-wrap gap-2">
            {r.status === "requested" && <Button size="sm" onClick={() => act.mutate("approve")} loading={act.isPending && act.variables === "approve"}>Approve return</Button>}
            {r.status === "approved" && <Button size="sm" disabled={needsRefundPerm} onClick={() => act.mutate("receive")} loading={act.isPending && act.variables === "receive"}>Mark received{r.return_type === "return" ? " & refund" : ""}</Button>}
            <Button variant="ghost" size="sm" className="text-kumkum" onClick={() => act.mutate("reject")} loading={act.isPending && act.variables === "reject"}>Reject return</Button>
          </div>
        </div>
      )}
      {r.admin_note && !(write && (r.status === "requested" || r.status === "approved")) && <p className="text-sm text-kajal-500">Note: {r.admin_note}</p>}
    </div>
  );
}
