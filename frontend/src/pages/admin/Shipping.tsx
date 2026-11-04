import { useEffect, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { adminApi, type PinPayload, type PinRule, type ShippingMethod, type ShippingMethodPayload } from "@/services/admin";
import {
  EmptyRow, FieldGrid, PageHeader, Panel, QueryState, ReadOnlyNote, SearchBox, Switch, Table, TableFooter, TableSkeleton, Td, Th, Tr, useConfirm,
} from "@/components/admin/kit";
import { useAdminMutation, useUrlFilters } from "@/components/admin/hooks";
import { Alert, Badge, Button, Input, Modal, Select, Tabs, Textarea } from "@/components/ui";
import { useAuth } from "@/features/auth";
import { rupees } from "@/utils/format";

export default function Shipping() {
  const [f, set] = useUrlFilters({ tab: "methods", q: "", page: "1" });
  const { can } = useAuth();
  const write = can("shipping:write");
  return (
    <>
      <PageHeader title="Shipping" sub="Delivery methods, serviceable PIN codes and store-wide shipping rules." />
      <Tabs className="mb-5" value={f.tab as "methods" | "pins" | "settings"} onChange={(t) => set({ tab: t, q: "" })}
        tabs={[{ value: "methods", label: "Delivery methods" }, { value: "pins", label: "PIN code rules" }, { value: "settings", label: "Shipping settings" }]} />
      {!write && <ReadOnlyNote>View only — an administrator can change shipping.</ReadOnlyNote>}
      {f.tab === "methods" && <Methods write={write} />}
      {f.tab === "pins" && <Pins write={write} q={f.q} page={Number(f.page)} set={set} />}
      {f.tab === "settings" && <ShipSettings write={can("settings:write")} />}
    </>
  );
}

function Methods({ write }: { write: boolean }) {
  const q = useQuery({ queryKey: ["admin", "shipping-methods"], queryFn: adminApi.shippingMethods });
  const [edit, setEdit] = useState<ShippingMethod | "new" | null>(null);
  return (
    <>
      {write && <div className="mb-4 flex justify-end"><Button size="sm" onClick={() => setEdit("new")}><Plus className="h-4 w-4" aria-hidden />Add method</Button></div>}
      <QueryState q={q} what="Shipping" skeleton={<Table><tbody><TableSkeleton cols={6} /></tbody></Table>}>
        {(rows) => (
          <Table minWidth={820}>
            <thead><tr><Th>Method</Th><Th>Carrier</Th><Th align="right">Charge</Th><Th align="right">Free above</Th><Th>Delivery time</Th><Th>COD</Th><Th>Status</Th><Th align="right"><span className="sr-only">Actions</span></Th></tr></thead>
            <tbody>
              {rows.map((m) => (
                <Tr key={m.id}>
                  <Td><span className="text-kajal">{m.name}</span><span className="block text-xs text-kajal-400">{m.code} · order {m.display_order}</span></Td>
                  <Td className="text-kajal-500">{m.carrier}</Td>
                  <Td align="right">{Number(m.base_charge) ? rupees(m.base_charge) : "Free"}</Td>
                  <Td align="right">{m.free_shipping_threshold ? rupees(m.free_shipping_threshold) : <span className="text-kajal-400">Store default</span>}</Td>
                  <Td className="whitespace-nowrap">{m.min_days}–{m.max_days} days</Td>
                  <Td>{m.is_cod_allowed ? "Allowed" : <span className="text-kajal-400">No</span>}</Td>
                  <Td><Badge tone={m.is_active ? "success" : "neutral"}>{m.is_active ? "Active" : "Off"}</Badge></Td>
                  <Td align="right">{write && <Button variant="ghost" size="sm" className="h-8 text-gold-700 hover:bg-gold-50" onClick={() => setEdit(m)}>Edit</Button>}</Td>
                </Tr>
              ))}
              {!rows.length && <EmptyRow cols={8}>No delivery methods.</EmptyRow>}
            </tbody>
          </Table>
        )}
      </QueryState>
      {edit && <MethodModal m={edit === "new" ? null : edit} onClose={() => setEdit(null)} />}
    </>
  );
}

function MethodModal({ m, onClose }: { m: ShippingMethod | null; onClose: () => void }) {
  const [f, setF] = useState({
    code: m?.code ?? "", name: m?.name ?? "", description: m?.description ?? "", carrier: m?.carrier ?? "LoveVital Logistics (Mock)",
    base_charge: m ? String(Number(m.base_charge)) : "0", free_shipping_threshold: m?.free_shipping_threshold ? String(Number(m.free_shipping_threshold)) : "",
    min_days: String(m?.min_days ?? 3), max_days: String(m?.max_days ?? 6), is_cod_allowed: m?.is_cod_allowed ?? true, is_active: m?.is_active ?? true,
    display_order: String(m?.display_order ?? 0),
  });
  const [err, setErr] = useState<string | null>(null);
  const save = useAdminMutation((b: ShippingMethodPayload) => adminApi.saveShippingMethod(m?.id ?? null, b), { invalidate: [["admin", "shipping-methods"]], success: m ? "Method saved" : "Method created", onSuccess: onClose });
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!/^[a-z0-9_]{2,30}$/.test(f.code)) return setErr("Code: 2–30 lowercase letters, numbers or _");
    if (f.name.trim().length < 2) return setErr("Name needs at least 2 characters");
    if (!/^\d+(\.\d{1,2})?$/.test(f.base_charge)) return setErr("Charge must be an amount");
    if (f.free_shipping_threshold && !/^\d+(\.\d{1,2})?$/.test(f.free_shipping_threshold)) return setErr("Free-shipping threshold must be an amount");
    if (Number(f.max_days) < Number(f.min_days)) return setErr("Max days must be ≥ min days");
    setErr(null);
    save.mutate({
      code: f.code, name: f.name.trim(), description: f.description || null, carrier: f.carrier, base_charge: f.base_charge,
      free_shipping_threshold: f.free_shipping_threshold || null, min_days: Number(f.min_days), max_days: Number(f.max_days),
      is_cod_allowed: f.is_cod_allowed, is_active: f.is_active, display_order: Number(f.display_order) || 0,
    });
  };
  return (
    <Modal open onClose={onClose} title={m ? `Edit ${m.name}` : "New delivery method"} size="lg"
      footer={<><Button variant="ghost" size="sm" onClick={onClose}>Cancel</Button><Button size="sm" type="submit" form="sm-form" loading={save.isPending}>{m ? "Save method" : "Create method"}</Button></>}>
      <form id="sm-form" onSubmit={submit} className="space-y-4">
        {err && <Alert tone="error">{err}</Alert>}
        <FieldGrid>
          <Input label="Name" required value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />
          <Input label="Code" required value={f.code} onChange={(e) => setF({ ...f, code: e.target.value.toLowerCase() })} disabled={!!m} hint="e.g. express" />
          <Input label="Carrier" value={f.carrier} onChange={(e) => setF({ ...f, carrier: e.target.value })} />
          <Input label="Display order" type="number" value={f.display_order} onChange={(e) => setF({ ...f, display_order: e.target.value })} />
          <Input label="Charge (₹)" inputMode="decimal" value={f.base_charge} onChange={(e) => setF({ ...f, base_charge: e.target.value })} />
          <Input label="Free above (₹)" inputMode="decimal" value={f.free_shipping_threshold} onChange={(e) => setF({ ...f, free_shipping_threshold: e.target.value })} hint="Blank uses the store default" />
          <Input label="Min days" type="number" min={0} max={60} value={f.min_days} onChange={(e) => setF({ ...f, min_days: e.target.value })} />
          <Input label="Max days" type="number" min={0} max={60} value={f.max_days} onChange={(e) => setF({ ...f, max_days: e.target.value })} />
        </FieldGrid>
        <Textarea label="Description" rows={2} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} />
        <div className="flex flex-wrap gap-6">
          <Switch label="Cash on delivery allowed" checked={f.is_cod_allowed} onChange={(v) => setF({ ...f, is_cod_allowed: v })} />
          <Switch label="Active" checked={f.is_active} onChange={(v) => setF({ ...f, is_active: v })} />
        </div>
      </form>
    </Modal>
  );
}

const EMPTY_PIN: PinPayload = { pin_code: "", city: "", state: "", region: "national", extra_days: 0, is_serviceable: true, is_cod_available: true };
function Pins({ write, q: search, page, set }: { write: boolean; q: string; page: number; set: (p: Record<string, string>, reset?: boolean) => void }) {
  const confirm = useConfirm();
  const q = useQuery({ queryKey: ["admin", "pins", search, page], queryFn: () => adminApi.pins({ q: search, page, page_size: 50 }), placeholderData: keepPreviousData });
  const [form, setForm] = useState<PinPayload>(EMPTY_PIN);
  const [err, setErr] = useState<string | null>(null);
  const upsert = useAdminMutation((b: PinPayload) => adminApi.upsertPin(b), { invalidate: [["admin", "pins"]], success: (r) => `PIN rule ${r.pin_code} saved`, onSuccess: () => setForm(EMPTY_PIN) });
  const del = useAdminMutation((id: number) => adminApi.deletePin(id), { invalidate: [["admin", "pins"]], success: "PIN rule removed" });
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!/^([1-9][0-9]{5}|[1-9][0-9]{2})$/.test(form.pin_code)) return setErr("Enter a 6-digit PIN code or a 3-digit prefix (not starting with 0)");
    setErr(null);
    upsert.mutate({ ...form, city: form.city || null, state: form.state || null });
  };
  const editRow = (p: PinRule) => { setForm({ pin_code: p.pin_code, city: p.city ?? "", state: p.state ?? "", region: p.region, extra_days: p.extra_days, is_serviceable: p.is_serviceable, is_cod_available: p.is_cod_available }); window.scrollTo({ top: 0, behavior: "smooth" }); };
  return (
    <div className="space-y-5">
      {write && (
        <Panel title="Add or update a PIN rule">
          <form onSubmit={submit} className="space-y-4">
            <p className="text-sm text-kajal-500">A 3-digit prefix (e.g. 110) covers every PIN starting with it; an exact 6-digit PIN overrides its prefix. Saving an existing PIN updates it.</p>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-6">
              <Input label="PIN / prefix" required inputMode="numeric" maxLength={6} value={form.pin_code} onChange={(e) => setForm({ ...form, pin_code: e.target.value.replace(/\D/g, "") })} />
              <Input label="City" value={form.city ?? ""} onChange={(e) => setForm({ ...form, city: e.target.value })} />
              <Input label="State" value={form.state ?? ""} onChange={(e) => setForm({ ...form, state: e.target.value })} />
              <Select label="Region" value={form.region} onChange={(e) => setForm({ ...form, region: e.target.value as PinPayload["region"] })}
                options={[{ value: "metro", label: "Metro" }, { value: "regional", label: "Regional" }, { value: "national", label: "National" }, { value: "remote", label: "Remote" }]} />
              <Input label="Extra days" type="number" min={0} max={30} value={form.extra_days} onChange={(e) => setForm({ ...form, extra_days: Number(e.target.value) || 0 })} />
              <div className="flex flex-col justify-end gap-2 pb-1">
                <Switch label="Serviceable" checked={form.is_serviceable} onChange={(v) => setForm({ ...form, is_serviceable: v })} />
                <Switch label="COD" checked={form.is_cod_available} onChange={(v) => setForm({ ...form, is_cod_available: v })} />
              </div>
            </div>
            {err && <p role="alert" className="text-sm text-kumkum">{err}</p>}
            <div className="flex gap-2">
              <Button type="submit" size="sm" loading={upsert.isPending}>Save PIN rule</Button>
              {form.pin_code && <Button variant="ghost" size="sm" onClick={() => setForm(EMPTY_PIN)}>Clear</Button>}
            </div>
          </form>
        </Panel>
      )}
      <SearchBox className="w-full sm:w-72" value={search} onChange={(v) => set({ q: v })} placeholder="Search PIN or city" label="Search PIN rules" />
      <QueryState q={q} what="Shipping" skeleton={<Table><tbody><TableSkeleton cols={6} /></tbody></Table>}>
        {(d) => (
          <>
            <Table minWidth={720}>
              <thead><tr><Th>PIN / prefix</Th><Th>Location</Th><Th>Region</Th><Th align="right">Extra days</Th><Th>Serviceable</Th><Th>COD</Th><Th align="right"><span className="sr-only">Actions</span></Th></tr></thead>
              <tbody>
                {d.items.map((p) => (
                  <Tr key={p.id}>
                    <Td className="font-mono tabular text-kajal">{p.pin_code}{p.pin_code.length === 3 && <span className="ml-1 font-sans text-xs text-kajal-400">prefix</span>}</Td>
                    <Td>{[p.city, p.state].filter(Boolean).join(", ") || "—"}</Td>
                    <Td className="capitalize">{p.region}</Td>
                    <Td align="right">{p.extra_days}</Td>
                    <Td>{p.is_serviceable ? <Badge tone="success">Yes</Badge> : <Badge tone="sale" className="!bg-kumkum-50 !text-kumkum">No</Badge>}</Td>
                    <Td>{p.is_cod_available ? "Yes" : <span className="text-kajal-400">No</span>}</Td>
                    <Td align="right" className="whitespace-nowrap">
                      {write && <>
                        <Button variant="ghost" size="sm" className="h-8 text-gold-700 hover:bg-gold-50" onClick={() => editRow(p)}>Edit</Button>
                        <button type="button" aria-label={`Delete PIN rule ${p.pin_code}`} className="rounded-full p-2 text-kajal-400 hover:bg-ivory-200 hover:text-kumkum"
                          onClick={async () => { if ((await confirm({ title: `Delete rule ${p.pin_code}?`, body: "Deliveries there fall back to the prefix or national default.", confirmLabel: "Delete rule", danger: true })).ok) del.mutate(p.id); }}>
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </>}
                    </Td>
                  </Tr>
                ))}
                {!d.items.length && <EmptyRow cols={7}>No PIN rules match.</EmptyRow>}
              </tbody>
            </Table>
            <TableFooter total={d.total} page={d.page} pages={d.pages} onPage={(p) => set({ page: String(p) }, false)} noun="rule" />
          </>
        )}
      </QueryState>
    </div>
  );
}

const SHIP_KEYS = ["free_shipping_threshold", "cod_fee", "cod_max_order_value"] as const;
function ShipSettings({ write }: { write: boolean }) {
  const q = useQuery({ queryKey: ["admin", "settings"], queryFn: adminApi.settings });
  const [vals, setVals] = useState<Record<string, string>>({});
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    if (q.data) setVals(Object.fromEntries(q.data.filter((s) => (SHIP_KEYS as readonly string[]).includes(s.key)).map((s) => [s.key, String(Number(s.value))])));
  }, [q.data]);
  const save = useAdminMutation(() => adminApi.saveSettings(vals), { invalidate: [["admin", "settings"]], success: "Shipping settings saved" });
  const labels: Record<string, [string, string]> = {
    free_shipping_threshold: ["Free shipping above (₹)", "Orders at or above this (after discounts) ship free."],
    cod_fee: ["Cash-on-delivery fee (₹)", "Flat fee added to COD orders."],
    cod_max_order_value: ["Maximum COD order value (₹)", "COD is hidden for orders above this."],
  };
  return (
    <QueryState q={q} what="Store settings">
      {() => (
        <Panel className="max-w-2xl">
          <form onSubmit={(e) => {
            e.preventDefault();
            const bad = SHIP_KEYS.find((k) => !/^\d+(\.\d{1,2})?$/.test(vals[k] ?? ""));
            if (bad) return setErr(`${labels[bad][0]} must be a non-negative amount`);
            setErr(null); save.mutate(undefined);
          }} className="space-y-4">
            {!write && <Alert>Only administrators can change these values.</Alert>}
            {SHIP_KEYS.map((k) => (
              <Input key={k} label={labels[k][0]} hint={labels[k][1]} inputMode="decimal" disabled={!write} value={vals[k] ?? ""} onChange={(e) => setVals({ ...vals, [k]: e.target.value })} />
            ))}
            {err && <p role="alert" className="text-sm text-kumkum">{err}</p>}
            {write && <Button type="submit" size="sm" loading={save.isPending}>Save shipping settings</Button>}
          </form>
        </Panel>
      )}
    </QueryState>
  );
}
