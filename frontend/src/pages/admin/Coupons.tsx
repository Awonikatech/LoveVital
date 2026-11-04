import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Controller, useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Plus } from "lucide-react";
import {
  adminApi, localInputToUtc, utcToLocalInput, type Coupon, type CouponPayload, type Promotion, type PromotionPayload, type PromoType,
} from "@/services/admin";
import {
  EmptyRow, FieldGrid, PageHeader, QueryState, ReadOnlyNote, Switch, Table, TableSkeleton, Td, Th, Tr, useConfirm,
} from "@/components/admin/kit";
import { useAdminMutation, useUrlFilters } from "@/components/admin/hooks";
import { CategoryPicker, ProductPicker } from "@/components/admin/Pickers";
import { Alert, Badge, Button, Drawer, Input, Modal, Select, StatusBadge, Tabs, Textarea } from "@/components/ui";
import { useAuth } from "@/features/auth";
import { date, plural, rupees } from "@/utils/format";

function validity(x: { starts_at: string | null; ends_at: string | null }) {
  if (!x.starts_at && !x.ends_at) return "Always";
  if (!x.starts_at) return `Until ${date(x.ends_at)}`;
  return `${date(x.starts_at)} – ${x.ends_at ? date(x.ends_at) : "no end"}`;
}

function liveState(x: { is_active: boolean; starts_at: string | null; ends_at: string | null }) {
  const now = Date.now();
  if (!x.is_active) return { label: "Inactive", tone: "neutral" as const };
  if (x.starts_at && new Date(x.starts_at + "Z").getTime() > now) return { label: "Scheduled", tone: "info" as const };
  if (x.ends_at && new Date(x.ends_at + "Z").getTime() < now) return { label: "Expired", tone: "neutral" as const };
  return { label: "Live", tone: "success" as const };
}

export default function Coupons() {
  const [f, set] = useUrlFilters({ tab: "coupons" });
  const { can } = useAuth();
  const write = can("coupons:write");
  return (
    <>
      <PageHeader title="Coupons & offers" sub="Codes customers enter at checkout, and automatic promotions." />
      <Tabs className="mb-5" value={f.tab as "coupons" | "promotions"} onChange={(t) => set({ tab: t })}
        tabs={[{ value: "coupons", label: "Coupons" }, { value: "promotions", label: "Automatic promotions" }]} />
      {!write && <ReadOnlyNote>View only — an administrator can create or change offers.</ReadOnlyNote>}
      {f.tab === "coupons" ? <CouponsTab write={write} /> : <PromotionsTab write={write} />}
    </>
  );
}

/* ================================================================== coupons */
function CouponsTab({ write }: { write: boolean }) {
  const q = useQuery({ queryKey: ["admin", "coupons"], queryFn: adminApi.coupons });
  const [edit, setEdit] = useState<Coupon | "new" | null>(null);
  const [red, setRed] = useState<Coupon | null>(null);
  return (
    <>
      {write && <div className="mb-4 flex justify-end"><Button size="sm" onClick={() => setEdit("new")}><Plus className="h-4 w-4" aria-hidden />Create coupon</Button></div>}
      <QueryState q={q} what="Coupons" skeleton={<Table><tbody><TableSkeleton cols={7} /></tbody></Table>}>
        {(rows) => (
          <Table minWidth={980}>
            <thead><tr><Th>Code</Th><Th>Discount</Th><Th>Conditions</Th><Th>Validity</Th><Th align="right">Used</Th><Th align="right">Discount given</Th><Th>Status</Th><Th align="right"><span className="sr-only">Actions</span></Th></tr></thead>
            <tbody>
              {rows.map((c) => {
                const st = liveState(c);
                return (
                  <Tr key={c.id}>
                    <Td><span className="font-mono text-[13px] font-medium tracking-wide text-kajal">{c.code}</span><span className="block max-w-[220px] truncate text-xs text-kajal-400">{c.description}</span></Td>
                    <Td className="whitespace-nowrap">{c.discount_type === "percent" ? `${Number(c.value)}% off` : c.discount_type === "fixed" ? `${rupees(c.value)} off` : "Free shipping"}{c.max_discount && <span className="block text-xs text-kajal-400">up to {rupees(c.max_discount)}</span>}</Td>
                    <Td className="text-xs text-kajal-500">
                      {Number(c.min_cart_value) > 0 && <span className="block">Min cart {rupees(c.min_cart_value)}</span>}
                      {c.applies_to !== "all" && <span className="block">{c.applies_to === "categories" ? plural(c.category_ids.length, "category", "categories") : plural(c.product_ids.length, "product")}</span>}
                      {c.first_order_only && <span className="block">First order only</span>}
                      {c.customer_emails.length > 0 && <span className="block">{c.customer_emails.length} customer{c.customer_emails.length > 1 ? "s" : ""} only</span>}
                      {!c.combinable_with_promotions && <span className="block">Not with promotions</span>}
                    </Td>
                    <Td className="whitespace-nowrap text-xs">{validity(c)}</Td>
                    <Td align="right" className="whitespace-nowrap">{c.times_used}{c.usage_limit_total ? <span className="text-kajal-400"> / {c.usage_limit_total}</span> : ""}</Td>
                    <Td align="right">{rupees(c.discount_given)}</Td>
                    <Td><Badge tone={st.tone}>{st.label}</Badge></Td>
                    <Td align="right" className="whitespace-nowrap">
                      <Button variant="ghost" size="sm" className="h-8 text-kajal-500" onClick={() => setRed(c)}>Redemptions</Button>
                      {write && <Button variant="ghost" size="sm" className="h-8 text-gold-700 hover:bg-gold-50" onClick={() => setEdit(c)}>Edit</Button>}
                    </Td>
                  </Tr>
                );
              })}
              {!rows.length && <EmptyRow cols={8}>No coupons yet.</EmptyRow>}
            </tbody>
          </Table>
        )}
      </QueryState>
      {edit && <CouponModal coupon={edit === "new" ? null : edit} onClose={() => setEdit(null)} />}
      <RedemptionsDrawer coupon={red} onClose={() => setRed(null)} />
    </>
  );
}

function RedemptionsDrawer({ coupon, onClose }: { coupon: Coupon | null; onClose: () => void }) {
  const q = useQuery({ queryKey: ["admin", "redemptions", coupon?.id], queryFn: () => adminApi.redemptions(coupon!.id), enabled: !!coupon });
  return (
    <Drawer open={!!coupon} onClose={onClose} title={coupon ? `${coupon.code} redemptions` : ""}>
      <div className="p-5">
        <QueryState q={q} what="Coupons">
          {(rows) => rows.length ? (
            <ul className="divide-y divide-gold-200/40">
              {rows.map((r) => (
                <li key={r.id} className="flex items-center justify-between gap-3 py-3">
                  <div className="min-w-0">
                    <Link to={`/admin/orders/${r.order_id}`} className="text-kajal hover:underline">{r.order_number}</Link>
                    <p className="truncate text-xs text-kajal-400">{r.email} · {date(r.at, "long")}</p>
                  </div>
                  <div className="text-right">
                    <p className="tabular text-kumkum">−{rupees(r.discount_amount)}</p>
                    <StatusBadge status={r.status} />
                  </div>
                </li>
              ))}
            </ul>
          ) : <p className="py-10 text-center text-sm text-kajal-500">This coupon hasn't been used yet.</p>}
        </QueryState>
      </div>
    </Drawer>
  );
}

const amt = z.string().trim().refine((v) => v === "" || (/^\d+(\.\d{1,2})?$/.test(v)), "Enter an amount");
const intOpt = z.string().trim().refine((v) => v === "" || (/^\d+$/.test(v) && Number(v) >= 1), "Whole number ≥ 1");
const couponSchema = z.object({
  code: z.string().trim().min(3, "At least 3 characters").max(40).regex(/^[A-Za-z0-9_\-]+$/, "Letters, numbers, - and _ only"),
  description: z.string().max(255),
  discount_type: z.enum(["percent", "fixed", "free_shipping"]),
  value: amt, min_cart_value: amt, max_discount: amt,
  starts_at: z.string(), ends_at: z.string(),
  usage_limit_total: intOpt, usage_limit_per_user: intOpt,
  first_order_only: z.boolean(),
  applies_to: z.enum(["all", "categories", "products"]),
  category_ids: z.array(z.number()), product_ids: z.array(z.number()),
  customer_emails: z.string(),
  combinable_with_promotions: z.boolean(), is_active: z.boolean(),
}).superRefine((v, ctx) => {
  const n = Number(v.value || 0);
  if (v.discount_type === "percent" && !(n > 0 && n <= 90)) ctx.addIssue({ code: "custom", path: ["value"], message: "Percentage must be between 1 and 90" });
  if (v.discount_type === "fixed" && !(n > 0)) ctx.addIssue({ code: "custom", path: ["value"], message: "Enter an amount greater than 0" });
  if (v.max_discount && !(Number(v.max_discount) > 0)) ctx.addIssue({ code: "custom", path: ["max_discount"], message: "Must be greater than 0" });
  if (v.starts_at && v.ends_at && v.ends_at <= v.starts_at) ctx.addIssue({ code: "custom", path: ["ends_at"], message: "End must be after start" });
  if (v.applies_to === "categories" && !v.category_ids.length) ctx.addIssue({ code: "custom", path: ["category_ids"], message: "Choose at least one category" });
  if (v.applies_to === "products" && !v.product_ids.length) ctx.addIssue({ code: "custom", path: ["product_ids"], message: "Choose at least one product" });
  const bad = v.customer_emails.split(/[\s,;]+/).filter(Boolean).find((e) => !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(e));
  if (bad) ctx.addIssue({ code: "custom", path: ["customer_emails"], message: `“${bad}” isn't a valid email` });
});
type CouponForm = z.infer<typeof couponSchema>;

function CouponModal({ coupon, onClose }: { coupon: Coupon | null; onClose: () => void }) {
  const confirm = useConfirm();
  const [serverErr, setServerErr] = useState<string | null>(null);
  const { register, control, handleSubmit, formState: { errors } } = useForm<CouponForm>({
    resolver: zodResolver(couponSchema),
    defaultValues: {
      code: coupon?.code ?? "", description: coupon?.description ?? "", discount_type: coupon?.discount_type ?? "percent",
      value: coupon ? String(Number(coupon.value)) : "10", min_cart_value: coupon ? String(Number(coupon.min_cart_value)) : "0",
      max_discount: coupon?.max_discount ? String(Number(coupon.max_discount)) : "", starts_at: utcToLocalInput(coupon?.starts_at), ends_at: utcToLocalInput(coupon?.ends_at),
      usage_limit_total: coupon?.usage_limit_total ? String(coupon.usage_limit_total) : "", usage_limit_per_user: coupon ? (coupon.usage_limit_per_user ? String(coupon.usage_limit_per_user) : "") : "1",
      first_order_only: coupon?.first_order_only ?? false, applies_to: coupon?.applies_to ?? "all", category_ids: coupon?.category_ids ?? [],
      product_ids: coupon?.product_ids ?? [], customer_emails: (coupon?.customer_emails ?? []).join(", "),
      combinable_with_promotions: coupon?.combinable_with_promotions ?? true, is_active: coupon?.is_active ?? true,
    },
  });
  const type = useWatch({ control, name: "discount_type" });
  const applies = useWatch({ control, name: "applies_to" });
  const inv = [["admin", "coupons"]];
  const save = useAdminMutation((b: CouponPayload) => adminApi.saveCoupon(coupon?.id ?? null, b), {
    invalidate: inv, success: (c) => `Coupon ${c.code} ${coupon ? "saved" : "created"}`, onSuccess: onClose, silentError: true,
  });
  const del = useAdminMutation(() => adminApi.deleteCoupon(coupon!.id), { invalidate: inv, success: (r) => r.message, onSuccess: onClose });
  const submit = (v: CouponForm) => {
    setServerErr(null);
    save.mutate({
      code: v.code.toUpperCase(), description: v.description || null, discount_type: v.discount_type,
      value: v.discount_type === "free_shipping" ? "0" : v.value, min_cart_value: v.min_cart_value || "0",
      max_discount: v.discount_type === "percent" && v.max_discount ? v.max_discount : null,
      starts_at: localInputToUtc(v.starts_at), ends_at: localInputToUtc(v.ends_at),
      usage_limit_total: v.usage_limit_total ? Number(v.usage_limit_total) : null, usage_limit_per_user: v.usage_limit_per_user ? Number(v.usage_limit_per_user) : null,
      first_order_only: v.first_order_only, applies_to: v.applies_to, category_ids: v.applies_to === "categories" ? v.category_ids : [],
      product_ids: v.applies_to === "products" ? v.product_ids : [], customer_emails: v.customer_emails.split(/[\s,;]+/).filter(Boolean),
      combinable_with_promotions: v.combinable_with_promotions, is_active: v.is_active,
    }, { onError: (e) => setServerErr((e as any)?.response?.data?.error?.message ?? "Couldn't save the coupon") });
  };
  return (
    <Modal open onClose={onClose} title={coupon ? `Edit ${coupon.code}` : "Create coupon"} size="xl"
      footer={<>
        {coupon && <Button variant="ghost" size="sm" className="mr-auto text-kumkum" loading={del.isPending}
          onClick={async () => { if ((await confirm({ title: `Delete ${coupon.code}?`, body: "Coupons that have been used are deactivated instead, to keep order history intact.", confirmLabel: "Delete coupon", danger: true })).ok) del.mutate(undefined); }}>Delete</Button>}
        <Button variant="ghost" size="sm" onClick={onClose}>Cancel</Button>
        <Button size="sm" type="submit" form="coupon-form" loading={save.isPending}>{coupon ? "Save coupon" : "Create coupon"}</Button>
      </>}>
      <form id="coupon-form" onSubmit={handleSubmit(submit)} noValidate className="space-y-5">
        {serverErr && <Alert tone="error">{serverErr}</Alert>}
        <FieldGrid>
          <Input label="Code" required {...register("code")} error={errors.code?.message} className="[&_input]:font-mono [&_input]:uppercase" />
          <Input label="Description" {...register("description")} hint="Internal — e.g. Diwali campaign" />
          <Select label="Discount type" {...register("discount_type")} options={[{ value: "percent", label: "Percentage off" }, { value: "fixed", label: "Fixed amount off" }, { value: "free_shipping", label: "Free shipping" }]} />
          {type !== "free_shipping" && <Input label={type === "percent" ? "Percentage (%)" : "Amount (₹)"} inputMode="decimal" {...register("value")} error={errors.value?.message} />}
          <Input label="Minimum cart value (₹)" inputMode="decimal" {...register("min_cart_value")} error={errors.min_cart_value?.message} />
          {type === "percent" && <Input label="Maximum discount (₹)" inputMode="decimal" {...register("max_discount")} error={errors.max_discount?.message} hint="Optional cap" />}
        </FieldGrid>
        <FieldGrid cols={4}>
          <Input label="Starts" type="datetime-local" {...register("starts_at")} />
          <Input label="Ends" type="datetime-local" {...register("ends_at")} error={errors.ends_at?.message} />
          <Input label="Total uses" inputMode="numeric" {...register("usage_limit_total")} error={errors.usage_limit_total?.message} hint="Blank = unlimited" />
          <Input label="Uses per customer" inputMode="numeric" {...register("usage_limit_per_user")} error={errors.usage_limit_per_user?.message} hint="Blank = unlimited" />
        </FieldGrid>
        <div>
          <Select label="Applies to" {...register("applies_to")} className="max-w-xs" options={[{ value: "all", label: "Whole cart" }, { value: "categories", label: "Specific categories" }, { value: "products", label: "Specific products" }]} />
          <div className="mt-3">
            {applies === "categories" && <Controller control={control} name="category_ids" render={({ field }) => <CategoryPicker value={field.value} onChange={field.onChange} />} />}
            {applies === "products" && <Controller control={control} name="product_ids" render={({ field }) => <ProductPicker value={field.value} onChange={(ids) => field.onChange(ids)} />} />}
            {(errors.category_ids || errors.product_ids) && <p className="field-error">{errors.category_ids?.message ?? errors.product_ids?.message}</p>}
          </div>
        </div>
        <Textarea label="Restrict to customer emails" rows={2} {...register("customer_emails")} error={errors.customer_emails?.message} hint="Optional. Comma or newline separated; leave blank for everyone." />
        <div className="flex flex-wrap gap-x-6 gap-y-3">
          <Controller control={control} name="first_order_only" render={({ field }) => <Switch label="First order only" checked={field.value} onChange={field.onChange} />} />
          <Controller control={control} name="combinable_with_promotions" render={({ field }) => <Switch label="Can combine with promotions" checked={field.value} onChange={field.onChange} />} />
          <Controller control={control} name="is_active" render={({ field }) => <Switch label="Active" checked={field.value} onChange={field.onChange} />} />
        </div>
      </form>
    </Modal>
  );
}

/* ================================================================== promotions */
const PROMO_LABEL: Record<PromoType, string> = {
  percent_off: "Percentage off", fixed_off: "Fixed amount off", bogo: "Buy X get Y", quantity_discount: "Quantity discount", free_shipping: "Free shipping",
};
function describePromo(p: Promotion) {
  const c = p.config ?? {};
  switch (p.promo_type) {
    case "percent_off": return `${Number(p.value)}% off${c.max_discount ? `, up to ${rupees(String(c.max_discount))}` : ""}`;
    case "fixed_off": return `${rupees(p.value)} off`;
    case "bogo": return `Buy ${c.buy_qty ?? 1} get ${c.get_qty ?? 1} at ${c.get_discount_pct ?? 100}% off`;
    case "quantity_discount": return `${Number(p.value)}% off when buying ${c.min_qty ?? 2}+`;
    case "free_shipping": return "Free shipping";
  }
}

function PromotionsTab({ write }: { write: boolean }) {
  const q = useQuery({ queryKey: ["admin", "promotions"], queryFn: adminApi.promotions });
  const [edit, setEdit] = useState<Promotion | "new" | null>(null);
  return (
    <>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-2xl text-sm text-kajal-500">Promotions apply automatically in priority order (lowest number first); once a non-stackable promotion gives a discount, no later promotions apply (free shipping is evaluated separately).</p>
        {write && <Button size="sm" onClick={() => setEdit("new")}><Plus className="h-4 w-4" aria-hidden />Create promotion</Button>}
      </div>
      <QueryState q={q} what="Promotions" skeleton={<Table><tbody><TableSkeleton cols={6} /></tbody></Table>}>
        {(rows) => (
          <Table minWidth={900}>
            <thead><tr><Th align="right">Priority</Th><Th>Promotion</Th><Th>Offer</Th><Th>Applies to</Th><Th>Schedule</Th><Th>Status</Th><Th align="right"><span className="sr-only">Actions</span></Th></tr></thead>
            <tbody>
              {rows.map((p) => {
                const st = liveState(p);
                return (
                  <Tr key={p.id}>
                    <Td align="right">{p.priority}</Td>
                    <Td><span className="text-kajal">{p.name}</span> {p.badge_text && <Badge tone="gold" className="ml-1">{p.badge_text}</Badge>}<span className="block text-xs text-kajal-400">{PROMO_LABEL[p.promo_type]}{p.is_stackable ? " · stackable" : " · exclusive"}</span></Td>
                    <Td>{describePromo(p)}{p.config?.min_cart_value ? <span className="block text-xs text-kajal-400">Min cart {rupees(String(p.config.min_cart_value))}</span> : null}</Td>
                    <Td className="text-kajal-500">{p.applies_to === "all" ? "Everything" : p.applies_to === "categories" ? plural(p.category_ids.length, "category", "categories") : plural(p.product_ids.length, "product")}</Td>
                    <Td className="whitespace-nowrap text-xs">{validity(p)}</Td>
                    <Td><Badge tone={st.tone}>{st.label}</Badge></Td>
                    <Td align="right">{write && <Button variant="ghost" size="sm" className="h-8 text-gold-700 hover:bg-gold-50" onClick={() => setEdit(p)}>Edit</Button>}</Td>
                  </Tr>
                );
              })}
              {!rows.length && <EmptyRow cols={7}>No promotions yet.</EmptyRow>}
            </tbody>
          </Table>
        )}
      </QueryState>
      {edit && <PromotionModal promo={edit === "new" ? null : edit} onClose={() => setEdit(null)} />}
    </>
  );
}

function PromotionModal({ promo, onClose }: { promo: Promotion | null; onClose: () => void }) {
  const confirm = useConfirm();
  const c = promo?.config ?? {};
  const s = (v: unknown) => (v === undefined || v === null ? "" : String(v));
  const [f, setF] = useState({
    name: promo?.name ?? "", description: promo?.description ?? "", badge_text: promo?.badge_text ?? "", promo_type: (promo?.promo_type ?? "percent_off") as PromoType,
    value: promo ? String(Number(promo.value)) : "10", buy_qty: s(c.buy_qty ?? 1), get_qty: s(c.get_qty ?? 1), get_discount_pct: s(c.get_discount_pct ?? 100),
    min_qty: s(c.min_qty ?? 2), min_cart_value: s(c.min_cart_value), max_discount: s(c.max_discount),
    applies_to: promo?.applies_to ?? "all", category_ids: promo?.category_ids ?? [], product_ids: promo?.product_ids ?? [],
    priority: String(promo?.priority ?? 100), is_stackable: promo?.is_stackable ?? true, is_active: promo?.is_active ?? true,
    starts_at: utcToLocalInput(promo?.starts_at), ends_at: utcToLocalInput(promo?.ends_at),
  });
  const [err, setErr] = useState<string | null>(null);
  const inv = [["admin", "promotions"]];
  const save = useAdminMutation((b: PromotionPayload) => adminApi.savePromotion(promo?.id ?? null, b), { invalidate: inv, success: promo ? "Promotion saved" : "Promotion created", onSuccess: onClose, silentError: true });
  const del = useAdminMutation(() => adminApi.deletePromotion(promo!.id), { invalidate: inv, success: "Promotion deleted", onSuccess: onClose });
  const t = f.promo_type;
  const needsValue = t === "percent_off" || t === "fixed_off" || t === "quantity_discount";
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const v = Number(f.value);
    if (f.name.trim().length < 3) return setErr("Name needs at least 3 characters");
    if ((t === "percent_off" || t === "quantity_discount") && !(v > 0 && v <= 90)) return setErr("Percentage must be between 1 and 90");
    if (t === "fixed_off" && !(v > 0)) return setErr("Enter an amount greater than 0");
    if (t === "bogo" && (!(Number(f.buy_qty) >= 1) || !(Number(f.get_qty) >= 1))) return setErr("Buy and get quantities must be at least 1");
    if (t === "bogo" && !(Number(f.get_discount_pct) > 0 && Number(f.get_discount_pct) <= 100)) return setErr("Discount on the free items must be 1–100%");
    if (t === "quantity_discount" && !(Number(f.min_qty) >= 2)) return setErr("Minimum quantity must be at least 2");
    if (f.applies_to === "categories" && !f.category_ids.length) return setErr("Choose at least one category");
    if (f.applies_to === "products" && !f.product_ids.length) return setErr("Choose at least one product");
    if (f.starts_at && f.ends_at && f.ends_at <= f.starts_at) return setErr("End must be after start");
    if (!/^\d+$/.test(f.priority)) return setErr("Priority must be a whole number");
    setErr(null);
    const config: Record<string, number> = {};
    if (t === "bogo") Object.assign(config, { buy_qty: Number(f.buy_qty), get_qty: Number(f.get_qty), get_discount_pct: Number(f.get_discount_pct) });
    if (t === "quantity_discount") config.min_qty = Number(f.min_qty);
    if (f.min_cart_value) config.min_cart_value = Number(f.min_cart_value);
    if (f.max_discount && (t === "percent_off" || t === "quantity_discount")) config.max_discount = Number(f.max_discount);
    save.mutate({
      name: f.name.trim(), description: f.description || null, badge_text: f.badge_text || null, promo_type: t, value: needsValue ? f.value : "0", config,
      applies_to: f.applies_to, category_ids: f.applies_to === "categories" ? f.category_ids : [], product_ids: f.applies_to === "products" ? f.product_ids : [],
      priority: Number(f.priority), is_stackable: f.is_stackable, is_active: f.is_active, starts_at: localInputToUtc(f.starts_at), ends_at: localInputToUtc(f.ends_at),
    }, { onError: (e) => setErr((e as any)?.response?.data?.error?.message ?? "Couldn't save the promotion") });
  };
  return (
    <Modal open onClose={onClose} title={promo ? `Edit ${promo.name}` : "Create promotion"} size="xl"
      footer={<>
        {promo && <Button variant="ghost" size="sm" className="mr-auto text-kumkum" loading={del.isPending}
          onClick={async () => { if ((await confirm({ title: "Delete this promotion?", body: "It stops applying to carts immediately.", confirmLabel: "Delete promotion", danger: true })).ok) del.mutate(undefined); }}>Delete</Button>}
        <Button variant="ghost" size="sm" onClick={onClose}>Cancel</Button>
        <Button size="sm" type="submit" form="promo-form" loading={save.isPending}>{promo ? "Save promotion" : "Create promotion"}</Button>
      </>}>
      <form id="promo-form" onSubmit={submit} className="space-y-5">
        {err && <Alert tone="error">{err}</Alert>}
        <FieldGrid>
          <Input label="Name" required value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />
          <Input label="Badge text" value={f.badge_text} onChange={(e) => setF({ ...f, badge_text: e.target.value })} hint="Shown on product cards, e.g. ‘Buy 2 Get 1’" maxLength={40} />
        </FieldGrid>
        <Textarea label="Description" rows={2} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} maxLength={300} />
        <FieldGrid cols={3}>
          <Select label="Promotion type" value={t} onChange={(e) => setF({ ...f, promo_type: e.target.value as PromoType })} options={Object.entries(PROMO_LABEL).map(([value, label]) => ({ value, label }))} />
          {needsValue && <Input label={t === "fixed_off" ? "Amount off (₹)" : "Percentage off (%)"} inputMode="decimal" value={f.value} onChange={(e) => setF({ ...f, value: e.target.value })} />}
          {t === "bogo" && <>
            <Input label="Buy quantity" inputMode="numeric" value={f.buy_qty} onChange={(e) => setF({ ...f, buy_qty: e.target.value })} />
            <Input label="Get quantity" inputMode="numeric" value={f.get_qty} onChange={(e) => setF({ ...f, get_qty: e.target.value })} />
            <Input label="Discount on ‘get’ items (%)" inputMode="numeric" value={f.get_discount_pct} onChange={(e) => setF({ ...f, get_discount_pct: e.target.value })} hint="100 = free" />
          </>}
          {t === "quantity_discount" && <Input label="Minimum quantity" inputMode="numeric" value={f.min_qty} onChange={(e) => setF({ ...f, min_qty: e.target.value })} />}
          <Input label="Minimum cart value (₹)" inputMode="decimal" value={f.min_cart_value} onChange={(e) => setF({ ...f, min_cart_value: e.target.value })} hint="Optional" />
          {(t === "percent_off" || t === "quantity_discount") && <Input label="Maximum discount (₹)" inputMode="decimal" value={f.max_discount} onChange={(e) => setF({ ...f, max_discount: e.target.value })} hint="Optional cap" />}
        </FieldGrid>
        <div>
          <Select label="Applies to" className="max-w-xs" value={f.applies_to} onChange={(e) => setF({ ...f, applies_to: e.target.value as typeof f.applies_to })}
            options={[{ value: "all", label: "Everything" }, { value: "categories", label: "Specific categories" }, { value: "products", label: "Specific products" }]} />
          <div className="mt-3">
            {f.applies_to === "categories" && <CategoryPicker value={f.category_ids} onChange={(ids) => setF({ ...f, category_ids: ids })} />}
            {f.applies_to === "products" && <ProductPicker value={f.product_ids} onChange={(ids) => setF({ ...f, product_ids: ids })} />}
          </div>
        </div>
        <FieldGrid cols={3}>
          <Input label="Priority" inputMode="numeric" value={f.priority} onChange={(e) => setF({ ...f, priority: e.target.value })} hint="Lower runs first" />
          <Input label="Starts" type="datetime-local" value={f.starts_at} onChange={(e) => setF({ ...f, starts_at: e.target.value })} />
          <Input label="Ends" type="datetime-local" value={f.ends_at} onChange={(e) => setF({ ...f, ends_at: e.target.value })} />
        </FieldGrid>
        <div className="flex flex-wrap gap-x-6 gap-y-3">
          <Switch label="Stackable with other promotions" checked={f.is_stackable} onChange={(v) => setF({ ...f, is_stackable: v })} />
          <Switch label="Active" checked={f.is_active} onChange={(v) => setF({ ...f, is_active: v })} />
        </div>
      </form>
    </Modal>
  );
}
