import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { adminApi, type CustomerDetail as CD } from "@/services/admin";
import { KeyVal, PageHeader, Panel, QueryState, Table, Td, Th, Tr, EmptyRow, useConfirm } from "@/components/admin/kit";
import { useAdminMutation } from "@/components/admin/hooks";
import { Alert, Badge, Button, StatusBadge, Textarea } from "@/components/ui";
import { useAuth } from "@/features/auth";
import { date, rupees } from "@/utils/format";

export default function CustomerDetail() {
  const { id } = useParams();
  const cid = Number(id);
  const q = useQuery({ queryKey: ["admin", "customer", cid], queryFn: () => adminApi.customer(cid) });
  return (
    <>
      <QueryState q={q} what="Customers">{(c) => <View c={c} />}</QueryState>
    </>
  );
}

function View({ c }: { c: CD }) {
  const { can, user } = useAuth();
  const confirm = useConfirm();
  const [notes, setNotes] = useState(c.support_notes ?? "");
  const inv = [["admin", "customer", c.id], ["admin", "customers"]];
  const saveNotes = useAdminMutation(() => adminApi.patchCustomer(c.id, { support_notes: notes }), { invalidate: inv, success: "Support notes saved" });
  const toggle = useAdminMutation((v: { is_active: boolean; reason?: string }) => adminApi.patchCustomer(c.id, { is_active: v.is_active, disabled_reason: v.reason ?? null }), {
    invalidate: inv, success: (r) => (r.is_active ? "Account enabled" : "Account disabled and signed out everywhere"),
  });
  const onToggle = async () => {
    if (c.is_active) {
      const r = await confirm({
        title: `Disable ${c.full_name}'s account?`, confirmLabel: "Disable account", danger: true,
        body: "They'll be signed out on all devices and won't be able to log in. Their orders are kept.",
        reason: { label: "Reason", required: true, minLength: 3, placeholder: "e.g. Repeated fraudulent COD refusals" },
      });
      if (r.ok) toggle.mutate({ is_active: false, reason: r.reason });
    } else {
      const r = await confirm({ title: `Enable ${c.full_name}'s account?`, body: "They'll be able to log in again.", confirmLabel: "Enable account" });
      if (r.ok) toggle.mutate({ is_active: true });
    }
  };
  const isSelf = user?.id === c.id;
  return (
    <>
      <PageHeader
        back={<Link to="/admin/customers" className="inline-flex items-center gap-1 text-sm text-kajal-500 hover:text-kajal"><ArrowLeft className="h-4 w-4" aria-hidden />Customers</Link>}
        title={c.full_name}
        sub={<span className="flex flex-wrap items-center gap-2">{c.email} <Badge tone={c.is_active ? "success" : "sale"} className={c.is_active ? "" : "!bg-kumkum-50 !text-kumkum"}>{c.is_active ? "Active" : "Disabled"}</Badge>{c.email_verified_at ? <Badge>Email verified</Badge> : <Badge tone="warning">Unverified</Badge>}</span>}
        actions={can("customers:write") && !isSelf && (
          <Button variant={c.is_active ? "ghost" : "outline"} size="sm" className={c.is_active ? "text-kumkum" : ""} onClick={onToggle} loading={toggle.isPending}>
            {c.is_active ? "Disable account" : "Enable account"}
          </Button>
        )} />
      {!c.is_active && c.disabled_reason && <Alert tone="warning" className="mb-6">Disabled: {c.disabled_reason}</Alert>}

      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[["Orders", String(c.stats.orders)], ["Lifetime value", rupees(c.stats.lifetime_value)], ["Average order", rupees(c.stats.aov)], ["Refunded", rupees(c.stats.refunded)]].map(([k, v]) => (
          <div key={k} className="card p-4"><p className="text-[13px] text-kajal-500">{k}</p><p className="mt-1 font-display text-2xl tabular">{v}</p></div>
        ))}
      </div>

      <div className="grid gap-6 xl:grid-cols-[1fr_360px]">
        <section className="min-w-0">
          <h2 className="mb-3 font-sans text-[15px] font-medium">Order history</h2>
          <Table minWidth={620}>
            <thead><tr><Th>Order</Th><Th>Placed</Th><Th>Status</Th><Th>Payment</Th><Th align="right">Total</Th></tr></thead>
            <tbody>
              {c.orders.map((o) => (
                <Tr key={o.id}>
                  <Td><Link to={`/admin/orders/${o.id}`} className="font-medium text-kajal hover:underline">{o.order_number}</Link><span className="block max-w-[220px] truncate text-xs text-kajal-400">{o.first_item}{o.item_count > 1 ? ` + ${o.item_count - 1} more` : ""}</span></Td>
                  <Td className="whitespace-nowrap">{date(o.placed_at)}</Td>
                  <Td><StatusBadge status={o.status} /></Td>
                  <Td><StatusBadge status={o.payment_status} /></Td>
                  <Td align="right">{rupees(o.grand_total)}</Td>
                </Tr>
              ))}
              {!c.orders.length && <EmptyRow cols={5}>No orders yet.</EmptyRow>}
            </tbody>
          </Table>
        </section>
        <aside className="space-y-6">
          <Panel title="Profile">
            <dl>
              <KeyVal k="Phone" v={c.phone ?? "—"} />
              <KeyVal k="Joined" v={date(c.created_at)} />
              <KeyVal k="Last login" v={date(c.last_login_at, "long")} />
              <KeyVal k="Roles" v={c.roles.join(", ")} />
            </dl>
          </Panel>
          <Panel title={`Addresses (${c.addresses.length})`}>
            {c.addresses.length ? (
              <ul className="space-y-3">
                {c.addresses.map((a) => (
                  <li key={a.id} className="text-sm leading-6 text-kajal-700">
                    <p className="text-kajal">{a.label ?? a.full_name} {a.is_default_shipping && <Badge tone="gold" className="ml-1">Default</Badge>}</p>
                    {a.line1}{a.line2 ? `, ${a.line2}` : ""}, {a.city}, {a.state} {a.pin_code} · {a.phone}
                  </li>
                ))}
              </ul>
            ) : <p className="text-sm text-kajal-500">No saved addresses.</p>}
          </Panel>
          <Panel title="Support notes">
            <form onSubmit={(e) => { e.preventDefault(); saveNotes.mutate(undefined); }}>
              <Textarea label="Notes" rows={5} value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={5000} hint="Visible to staff only." />
              <Button type="submit" size="sm" className="mt-2" disabled={notes === (c.support_notes ?? "")} loading={saveNotes.isPending}>Save notes</Button>
            </form>
          </Panel>
        </aside>
      </div>
    </>
  );
}
