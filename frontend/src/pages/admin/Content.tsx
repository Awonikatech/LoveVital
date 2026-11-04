import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Download, ExternalLink, Plus, Star, Trash2 } from "lucide-react";
import { adminApi, localInputToUtc, utcToLocalInput, type BannerPayload, type BannerRow, type CmsPageRow, type SettingRow } from "@/services/admin";
import { downloadFile, errorMessage } from "@/services/api";
import { EmptyRow, FieldGrid, MiniInput, PageHeader, Panel, QueryState, Switch, Table, TableSkeleton, Td, Th, Tr, useConfirm } from "@/components/admin/kit";
import { useAdminMutation, useUrlFilters } from "@/components/admin/hooks";
import { ImageField } from "@/components/admin/ImageField";
import { MarkdownPreview } from "@/components/admin/Markdown";
import { Alert, Badge, Button, Input, Modal, Select, StatusBadge, Tabs, Textarea } from "@/components/ui";
import { useAuth } from "@/features/auth";
import { useToast } from "@/features/toast";
import { date } from "@/utils/format";
import { cn } from "@/utils/cn";

type Tab = "banners" | "pages" | "settings" | "newsletter";

export default function Content() {
  const [f, set] = useUrlFilters({ tab: "banners" });
  return (
    <>
      <PageHeader title="Content & settings" sub="Homepage banners, policy pages, store details and newsletter." />
      <Tabs className="mb-5" value={f.tab as Tab} onChange={(t) => set({ tab: t })}
        tabs={[{ value: "banners", label: "Banners" }, { value: "pages", label: "Pages" }, { value: "settings", label: "Store settings" }, { value: "newsletter", label: "Newsletter" }]} />
      {f.tab === "banners" && <Banners />}
      {f.tab === "pages" && <Pages />}
      {f.tab === "settings" && <StoreSettings />}
      {f.tab === "newsletter" && <Newsletter />}
    </>
  );
}

/* ================================================================== banners */
function Banners() {
  const q = useQuery({ queryKey: ["admin", "banners"], queryFn: adminApi.banners });
  const [edit, setEdit] = useState<BannerRow | "new" | null>(null);
  return (
    <>
      <div className="mb-4 flex justify-end"><Button size="sm" onClick={() => setEdit("new")}><Plus className="h-4 w-4" aria-hidden />Add banner</Button></div>
      <QueryState q={q} what="Content" skeleton={<Table><tbody><TableSkeleton cols={5} /></tbody></Table>}>
        {(rows) => (
          <Table minWidth={760}>
            <thead><tr><Th>Banner</Th><Th>Placement</Th><Th>Link</Th><Th>Schedule</Th><Th>Status</Th><Th align="right"><span className="sr-only">Actions</span></Th></tr></thead>
            <tbody>
              {rows.map((b) => (
                <Tr key={b.id}>
                  <Td>
                    <div className="flex items-center gap-3">
                      <img src={b.image_url} alt="" className="h-12 w-20 shrink-0 rounded-md border border-gold-200/50 bg-ivory-200 object-cover" />
                      <div className="min-w-0"><p className="max-w-[260px] truncate text-kajal">{b.title}</p><p className="max-w-[260px] truncate text-xs text-kajal-400">{b.eyebrow ?? b.subtitle}</p></div>
                    </div>
                  </Td>
                  <Td className="capitalize">{b.placement} <span className="text-xs text-kajal-400">#{b.display_order}</span></Td>
                  <Td className="text-kajal-500">{b.cta_text ? <>{b.cta_text} → <span className="text-xs">{b.cta_link}</span></> : "—"}</Td>
                  <Td className="whitespace-nowrap text-xs">{b.starts_at || b.ends_at ? `${date(b.starts_at)} – ${b.ends_at ? date(b.ends_at) : "no end"}` : "Always"}</Td>
                  <Td><Badge tone={b.is_active ? "success" : "neutral"}>{b.is_active ? "Active" : "Hidden"}</Badge></Td>
                  <Td align="right"><Button variant="ghost" size="sm" className="h-8 text-gold-700 hover:bg-gold-50" onClick={() => setEdit(b)}>Edit</Button></Td>
                </Tr>
              ))}
              {!rows.length && <EmptyRow cols={6}>No banners yet.</EmptyRow>}
            </tbody>
          </Table>
        )}
      </QueryState>
      {edit && <BannerModal b={edit === "new" ? null : edit} onClose={() => setEdit(null)} />}
    </>
  );
}

function BannerModal({ b, onClose }: { b: BannerRow | null; onClose: () => void }) {
  const confirm = useConfirm();
  const [f, setF] = useState({
    title: b?.title ?? "", subtitle: b?.subtitle ?? "", eyebrow: b?.eyebrow ?? "", image_url: b?.image_url ?? "", cta_text: b?.cta_text ?? "",
    cta_link: b?.cta_link ?? "", placement: b?.placement ?? "hero", display_order: String(b?.display_order ?? 0), is_active: b?.is_active ?? true,
    starts_at: utcToLocalInput(b?.starts_at), ends_at: utcToLocalInput(b?.ends_at),
  });
  const [err, setErr] = useState<string | null>(null);
  const save = useAdminMutation((p: BannerPayload) => adminApi.saveBanner(b?.id ?? null, p), { invalidate: [["admin", "banners"]], success: b ? "Banner saved" : "Banner created", onSuccess: onClose });
  const del = useAdminMutation(() => adminApi.deleteBanner(b!.id), { invalidate: [["admin", "banners"]], success: "Banner deleted", onSuccess: onClose });
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (f.title.trim().length < 2) return setErr("Title needs at least 2 characters");
    if (!f.image_url) return setErr("Add an image");
    if (f.cta_link && !(f.cta_link.startsWith("/") || f.cta_link.startsWith("https://"))) return setErr("Link must be a site path (/…) or an https:// URL");
    if (f.starts_at && f.ends_at && f.ends_at <= f.starts_at) return setErr("End must be after start");
    setErr(null);
    save.mutate({
      title: f.title.trim(), subtitle: f.subtitle || null, eyebrow: f.eyebrow || null, image_url: f.image_url, cta_text: f.cta_text || null, cta_link: f.cta_link || null,
      placement: f.placement as BannerRow["placement"], display_order: Number(f.display_order) || 0, is_active: f.is_active,
      starts_at: localInputToUtc(f.starts_at), ends_at: localInputToUtc(f.ends_at),
    });
  };
  return (
    <Modal open onClose={onClose} title={b ? "Edit banner" : "New banner"} size="lg"
      footer={<>
        {b && <Button variant="ghost" size="sm" className="mr-auto text-kumkum" loading={del.isPending}
          onClick={async () => { if ((await confirm({ title: "Delete this banner?", confirmLabel: "Delete banner", danger: true })).ok) del.mutate(undefined); }}>Delete</Button>}
        <Button variant="ghost" size="sm" onClick={onClose}>Cancel</Button>
        <Button size="sm" type="submit" form="banner-form" loading={save.isPending}>{b ? "Save banner" : "Create banner"}</Button>
      </>}>
      <form id="banner-form" onSubmit={submit} className="space-y-4">
        {err && <Alert tone="error">{err}</Alert>}
        <ImageField label="Image" folder="banners" value={f.image_url} onChange={(url) => setF({ ...f, image_url: url })} />
        <FieldGrid>
          <Input label="Title" required value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} />
          <Input label="Eyebrow" value={f.eyebrow} onChange={(e) => setF({ ...f, eyebrow: e.target.value })} hint="Small line above the title" />
        </FieldGrid>
        <Textarea label="Subtitle" rows={2} value={f.subtitle} onChange={(e) => setF({ ...f, subtitle: e.target.value })} />
        <FieldGrid>
          <Input label="Button text" value={f.cta_text} onChange={(e) => setF({ ...f, cta_text: e.target.value })} />
          <Input label="Button link" value={f.cta_link} onChange={(e) => setF({ ...f, cta_link: e.target.value })} placeholder="/collections/festive-edit" />
          <Select label="Placement" value={f.placement} onChange={(e) => setF({ ...f, placement: e.target.value as BannerRow["placement"] })}
            options={[{ value: "hero", label: "Hero carousel" }, { value: "promo", label: "Promo tile" }, { value: "strip", label: "Strip" }]} />
          <Input label="Display order" type="number" value={f.display_order} onChange={(e) => setF({ ...f, display_order: e.target.value })} />
          <Input label="Starts" type="datetime-local" value={f.starts_at} onChange={(e) => setF({ ...f, starts_at: e.target.value })} />
          <Input label="Ends" type="datetime-local" value={f.ends_at} onChange={(e) => setF({ ...f, ends_at: e.target.value })} />
        </FieldGrid>
        <Switch label="Active" checked={f.is_active} onChange={(v) => setF({ ...f, is_active: v })} />
      </form>
    </Modal>
  );
}

/* ================================================================== pages */
function Pages() {
  const q = useQuery({ queryKey: ["admin", "pages"], queryFn: adminApi.pages });
  const [sel, setSel] = useState<string | "new" | null>(null);
  return (
    <QueryState q={q} what="Content">
      {(pages) => {
        const current = sel === "new" ? null : pages.find((p) => p.slug === (sel ?? pages[0]?.slug)) ?? null;
        const key = sel === "new" ? "new" : current?.slug ?? "none";
        return (
          <div className="grid gap-6 lg:grid-cols-[240px_1fr]">
            <div>
              <ul className="card divide-y divide-gold-200/40 overflow-hidden">
                {pages.map((p) => (
                  <li key={p.slug}>
                    <button type="button" onClick={() => setSel(p.slug)} aria-current={current?.slug === p.slug && sel !== "new"}
                      className={cn("block w-full px-4 py-2.5 text-left text-[14px] hover:bg-gold-50/50", current?.slug === p.slug && sel !== "new" && "bg-gold-50 text-kajal")}>
                      {p.title}<span className="block text-xs text-kajal-400">/pages/{p.slug}{!p.is_published && " · draft"}</span>
                    </button>
                  </li>
                ))}
              </ul>
              <Button variant="ghost" size="sm" className="mt-2" onClick={() => setSel("new")}><Plus className="h-4 w-4" aria-hidden />New page</Button>
            </div>
            <PageEditor key={key} page={current} isNew={sel === "new"} onSaved={(slug) => setSel(slug)} />
          </div>
        );
      }}
    </QueryState>
  );
}

function PageEditor({ page, isNew, onSaved }: { page: CmsPageRow | null; isNew: boolean; onSaved: (slug: string) => void }) {
  const [f, setF] = useState({ slug: page?.slug ?? "", title: page?.title ?? "", body: page?.body ?? "", seo_title: page?.seo_title ?? "", seo_description: page?.seo_description ?? "", is_published: page?.is_published ?? true });
  const [view, setView] = useState<"write" | "preview">("write");
  const [err, setErr] = useState<string | null>(null);
  const save = useAdminMutation(() => adminApi.savePage(isNew ? f.slug : page!.slug, { ...f, seo_title: f.seo_title || null, seo_description: f.seo_description || null }), {
    invalidate: [["admin", "pages"]], success: "Page saved", onSuccess: (r) => onSaved(r.slug),
  });
  if (!page && !isNew) return <p className="text-kajal-500">Select a page.</p>;
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (isNew && !/^[a-z0-9-]{2,100}$/.test(f.slug)) return setErr("Slug: lowercase letters, numbers and hyphens");
    if (f.title.trim().length < 2) return setErr("Title needs at least 2 characters");
    if (!f.body.trim()) return setErr("The page needs some content");
    setErr(null);
    save.mutate(undefined);
  };
  return (
    <Panel title={isNew ? "New page" : `Edit ${page!.title}`} action={!isNew && <a href={`/pages/${page!.slug}`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-sm text-kajal-500 hover:text-kajal">View <ExternalLink className="h-3.5 w-3.5" aria-hidden /></a>}>
      <form onSubmit={submit} className="space-y-4">
        {err && <Alert tone="error">{err}</Alert>}
        <FieldGrid>
          <Input label="Title" required value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} />
          <Input label="Slug" value={f.slug} disabled={!isNew} onChange={(e) => setF({ ...f, slug: e.target.value.toLowerCase() })} hint={`/pages/${f.slug || "…"}`} />
        </FieldGrid>
        <div>
          <div className="mb-1.5 flex items-center justify-between">
            <span className="label mb-0">Body (Markdown)</span>
            <div role="tablist" className="inline-flex rounded-full bg-ivory-200 p-0.5 text-[13px]">
              {(["write", "preview"] as const).map((v) => (
                <button key={v} type="button" role="tab" aria-selected={view === v} onClick={() => setView(v)} className={cn("rounded-full px-3 py-1", view === v ? "bg-white text-kajal shadow-sm" : "text-kajal-500")}>{v === "write" ? "Write" : "Preview"}</button>
              ))}
            </div>
          </div>
          {view === "write" ? (
            <textarea aria-label="Page body in Markdown" className="input min-h-[360px] font-mono text-[13px] leading-6" value={f.body} onChange={(e) => setF({ ...f, body: e.target.value })} />
          ) : (
            <div className="min-h-[360px] rounded-lg border border-kajal-300/60 bg-white px-5 py-4"><MarkdownPreview source={f.body} /></div>
          )}
          <p className="mt-1 text-sm text-kajal-500">Use ## for headings, **bold**, *italic*, - for lists and [text](/link) for links.</p>
        </div>
        <FieldGrid>
          <Input label="SEO title" value={f.seo_title} onChange={(e) => setF({ ...f, seo_title: e.target.value })} />
          <Input label="SEO description" value={f.seo_description} onChange={(e) => setF({ ...f, seo_description: e.target.value })} />
        </FieldGrid>
        <Switch label="Published" checked={f.is_published} onChange={(v) => setF({ ...f, is_published: v })} />
        <div><Button type="submit" size="sm" loading={save.isPending}>Save page</Button></div>
      </form>
    </Panel>
  );
}

/* ================================================================== settings */
type Testimonial = { name: string; city: string; text: string; rating: number };
type FooterLink = { label: string; href: string };
const SENSITIVE = new Set(["free_shipping_threshold", "cod_fee", "cod_max_order_value", "allow_coupon_with_promotions", "gstin"]);

function StoreSettings() {
  const q = useQuery({ queryKey: ["admin", "settings"], queryFn: adminApi.settings });
  return <QueryState q={q} what="Store settings">{(rows) => <SettingsForm rows={rows} />}</QueryState>;
}

function SettingsForm({ rows }: { rows: SettingRow[] }) {
  const { can } = useAuth();
  const admin = can("settings:write");
  const initial = useMemo(() => Object.fromEntries(rows.map((r) => [r.key, r.value])), [rows]);
  const [v, setV] = useState<Record<string, any>>(initial);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => setV(initial), [initial]);
  const desc = Object.fromEntries(rows.map((r) => [r.key, r.description]));
  const changed = Object.keys(v).filter((k) => JSON.stringify(v[k]) !== JSON.stringify(initial[k]));
  const save = useAdminMutation(() => adminApi.saveSettings(Object.fromEntries(changed.map((k) => [k, v[k]]))), { invalidate: [["admin", "settings"]], success: "Settings saved" });
  const set = (k: string, val: unknown) => setV((p) => ({ ...p, [k]: val }));
  const text = (k: string, label?: string, opts: { multiline?: boolean; hint?: string } = {}) => {
    const locked = SENSITIVE.has(k) && !admin;
    const common = { label: label ?? desc[k], value: v[k] ?? "", disabled: locked, hint: locked ? "Administrators only" : opts.hint };
    return opts.multiline
      ? <Textarea key={k} rows={2} {...common} onChange={(e) => set(k, e.target.value)} />
      : <Input key={k} {...common} onChange={(e) => set(k, e.target.value)} />;
  };
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    for (const k of ["free_shipping_threshold", "cod_fee", "cod_max_order_value"]) if (changed.includes(k) && !/^\d+(\.\d{1,2})?$/.test(String(v[k]))) return setErr(`${desc[k]} must be a non-negative amount`);
    for (const k of ["low_stock_default_threshold", "return_window_days"]) if (changed.includes(k) && !/^\d+$/.test(String(v[k]))) return setErr(`${desc[k]} must be a whole number`);
    const links = (v.footer_links as FooterLink[]) ?? [];
    if (links.some((l) => !l.label.trim() || !l.href.trim())) return setErr("Every footer link needs a label and a link");
    const ts = (v.testimonials as Testimonial[]) ?? [];
    if (ts.some((t) => !t.name.trim() || !t.text.trim())) return setErr("Every testimonial needs a name and text");
    setErr(null);
    save.mutate(undefined);
  };
  const socials = (v.social_links ?? {}) as Record<string, string>;
  return (
    <form onSubmit={submit} className="space-y-6">
      {!admin && <Alert>Shipping fees, COD limits, coupon stacking and GSTIN can only be changed by an administrator.</Alert>}
      <Panel title="Store">
        <FieldGrid>
          {text("store_name", "Store name")}
          {text("store_tagline", "Tagline")}
          <div className="sm:col-span-2">{text("announcement_text", "Announcement bar text", { multiline: true, hint: "Shown across the top of every page." })}</div>
          {text("gstin", "GSTIN")}
          {text("store_address", "Registered address")}
        </FieldGrid>
      </Panel>
      <Panel title="Support contacts">
        <FieldGrid cols={3}>{text("support_email", "Support email")}{text("support_phone", "Support phone")}{text("support_hours", "Support hours")}</FieldGrid>
      </Panel>
      <Panel title="Checkout & policies">
        <FieldGrid cols={3}>
          {text("free_shipping_threshold", "Free shipping above (₹)")}
          {text("cod_fee", "COD fee (₹)")}
          {text("cod_max_order_value", "Maximum COD order (₹)")}
          {text("return_window_days", "Default return window (days)")}
          {text("low_stock_default_threshold", "Default low-stock threshold")}
        </FieldGrid>
        <div className="mt-4">
          <Switch label="Allow coupons together with automatic promotions" disabled={!admin} checked={!!v.allow_coupon_with_promotions} onChange={(x) => set("allow_coupon_with_promotions", x)} />
        </div>
      </Panel>
      <Panel title="Social links">
        <div className="space-y-2">
          {Object.entries(socials).map(([k, url]) => (
            <div key={k} className="flex items-center gap-2">
              <span className="w-24 shrink-0 text-sm capitalize text-kajal-700">{k}</span>
              <MiniInput label={`${k} URL`} value={url} className="flex-1" onChange={(e) => set("social_links", { ...socials, [k]: e.target.value })} />
              <button type="button" aria-label={`Remove ${k}`} className="rounded p-1.5 text-kajal-400 hover:text-kumkum" onClick={() => { const n = { ...socials }; delete n[k]; set("social_links", n); }}><Trash2 className="h-4 w-4" /></button>
            </div>
          ))}
          <AddSocial onAdd={(k) => set("social_links", { ...socials, [k]: "https://" })} existing={Object.keys(socials)} />
        </div>
      </Panel>
      <Panel title="Footer links">
        <ListEditor<FooterLink> items={(v.footer_links as FooterLink[]) ?? []} onChange={(x) => set("footer_links", x)} blank={{ label: "", href: "/pages/" }} addLabel="Add link"
          render={(it, upd, i) => (
            <div className="flex flex-1 flex-wrap gap-2">
              <MiniInput label={`Footer link ${i + 1} label`} placeholder="Label" value={it.label} className="w-48" onChange={(e) => upd({ ...it, label: e.target.value })} />
              <MiniInput label={`Footer link ${i + 1} URL`} placeholder="/pages/about" value={it.href} className="min-w-[200px] flex-1" onChange={(e) => upd({ ...it, href: e.target.value })} />
            </div>
          )} />
      </Panel>
      <Panel title="Testimonials">
        <ListEditor<Testimonial> items={(v.testimonials as Testimonial[]) ?? []} onChange={(x) => set("testimonials", x)} blank={{ name: "", city: "", text: "", rating: 5 }} addLabel="Add testimonial"
          render={(it, upd, i) => (
            <div className="flex-1 space-y-2 rounded-xl border border-gold-200/50 bg-ivory-50/60 p-3">
              <div className="flex flex-wrap gap-2">
                <MiniInput label={`Testimonial ${i + 1} name`} placeholder="Name" value={it.name} className="w-44" onChange={(e) => upd({ ...it, name: e.target.value })} />
                <MiniInput label={`Testimonial ${i + 1} city`} placeholder="City" value={it.city} className="w-40" onChange={(e) => upd({ ...it, city: e.target.value })} />
                <div className="flex items-center gap-0.5" role="radiogroup" aria-label={`Testimonial ${i + 1} rating`}>
                  {[1, 2, 3, 4, 5].map((n) => (
                    <button key={n} type="button" role="radio" aria-checked={it.rating === n} aria-label={`${n} star${n > 1 ? "s" : ""}`} onClick={() => upd({ ...it, rating: n })} className="p-0.5">
                      <Star className={cn("h-4 w-4", n <= it.rating ? "fill-gold-500 text-gold-500" : "text-gold-200")} />
                    </button>
                  ))}
                </div>
              </div>
              <textarea aria-label={`Testimonial ${i + 1} text`} className="input min-h-[64px] text-[14px]" value={it.text} onChange={(e) => upd({ ...it, text: e.target.value })} />
            </div>
          )} />
      </Panel>
      <div className="sticky bottom-0 z-10 -mx-4 flex items-center justify-end gap-3 border-t border-gold-200/60 bg-ivory/95 px-4 py-3 backdrop-blur sm:mx-0 sm:rounded-2xl sm:border">
        {err && <p role="alert" className="mr-auto text-sm text-kumkum">{err}</p>}
        {changed.length > 0 && <span className="text-sm text-kajal-500">{changed.length} unsaved change{changed.length > 1 ? "s" : ""}</span>}
        <Button type="submit" size="sm" disabled={!changed.length} loading={save.isPending}>Save settings</Button>
      </div>
    </form>
  );
}

function AddSocial({ onAdd, existing }: { onAdd: (k: string) => void; existing: string[] }) {
  const [k, setK] = useState("");
  return (
    <div className="flex items-center gap-2 pt-1">
      <MiniInput label="New social network name" placeholder="e.g. whatsapp" value={k} className="w-40" onChange={(e) => setK(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ""))} />
      <Button variant="ghost" size="sm" disabled={!k || existing.includes(k)} onClick={() => { onAdd(k); setK(""); }}><Plus className="h-4 w-4" aria-hidden />Add network</Button>
    </div>
  );
}

function ListEditor<T>({ items, onChange, render, blank, addLabel }: { items: T[]; onChange: (x: T[]) => void; render: (it: T, upd: (n: T) => void, i: number) => React.ReactNode; blank: T; addLabel: string }) {
  const move = (i: number, d: -1 | 1) => { const n = [...items]; [n[i], n[i + d]] = [n[i + d], n[i]]; onChange(n); };
  return (
    <div className="space-y-2">
      {items.map((it, i) => (
        <div key={i} className="flex items-start gap-2">
          {render(it, (n) => onChange(items.map((x, j) => (j === i ? n : x))), i)}
          <div className="flex shrink-0 flex-col">
            <button type="button" aria-label="Move up" disabled={i === 0} onClick={() => move(i, -1)} className="rounded px-1.5 text-kajal-400 hover:text-kajal disabled:opacity-30">↑</button>
            <button type="button" aria-label="Move down" disabled={i === items.length - 1} onClick={() => move(i, 1)} className="rounded px-1.5 text-kajal-400 hover:text-kajal disabled:opacity-30">↓</button>
          </div>
          <button type="button" aria-label="Remove" onClick={() => onChange(items.filter((_, j) => j !== i))} className="rounded p-1.5 text-kajal-400 hover:text-kumkum"><Trash2 className="h-4 w-4" /></button>
        </div>
      ))}
      <Button variant="ghost" size="sm" onClick={() => onChange([...items, structuredClone(blank)])}><Plus className="h-4 w-4" aria-hidden />{addLabel}</Button>
    </div>
  );
}

/* ================================================================== newsletter */
function Newsletter() {
  const q = useQuery({ queryKey: ["admin", "newsletter"], queryFn: adminApi.newsletter });
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const exportCsv = async () => {
    setBusy(true);
    try { await downloadFile("/admin/newsletter?format=csv", "newsletter.csv"); } catch (e) { toast(errorMessage(e), "error"); } finally { setBusy(false); }
  };
  return (
    <QueryState q={q} what="Content" skeleton={<Table><tbody><TableSkeleton cols={4} /></tbody></Table>}>
      {(rows) => (
        <>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-kajal-500 tabular">{rows.filter((r) => r.status === "subscribed").length} subscribed · {rows.length} total</p>
            <Button variant="outline" size="sm" onClick={exportCsv} loading={busy}><Download className="h-4 w-4" aria-hidden />Export CSV</Button>
          </div>
          <Table minWidth={560}>
            <thead><tr><Th>Email</Th><Th>Status</Th><Th>Source</Th><Th>Subscribed</Th></tr></thead>
            <tbody>
              {rows.map((r) => (
                <Tr key={r.email}><Td className="text-kajal">{r.email}</Td><Td><StatusBadge status={r.status === "subscribed" ? "active" : r.status} label={r.status} /></Td><Td>{r.source ?? "—"}</Td><Td>{date(r.subscribed_at)}</Td></Tr>
              ))}
              {!rows.length && <EmptyRow cols={4}>No subscribers yet.</EmptyRow>}
            </tbody>
          </Table>
        </>
      )}
    </QueryState>
  );
}

