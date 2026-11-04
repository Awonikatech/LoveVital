import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Plus, Sparkles } from "lucide-react";
import { adminApi, localInputToUtc, utcToLocalInput, type AdminCollection } from "@/services/admin";
import { FieldGrid, PageHeader, QueryState, Switch, Thumb, useConfirm } from "@/components/admin/kit";
import { useAdminMutation } from "@/components/admin/hooks";
import { ImageField } from "@/components/admin/ImageField";
import { ProductPicker } from "@/components/admin/Pickers";
import { Badge, Button, EmptyState, Input, Modal, Textarea } from "@/components/ui";
import { useAuth } from "@/features/auth";
import { date } from "@/utils/format";

function schedule(c: AdminCollection) {
  const now = Date.now();
  const s = c.starts_at ? new Date(c.starts_at + "Z").getTime() : null;
  const e = c.ends_at ? new Date(c.ends_at + "Z").getTime() : null;
  if (s && s > now) return { label: `Starts ${date(c.starts_at)}`, tone: "info" as const };
  if (e && e < now) return { label: "Ended", tone: "neutral" as const };
  if (e) return { label: `Until ${date(c.ends_at)}`, tone: "gold" as const };
  return null;
}

export default function Collections() {
  const q = useQuery({ queryKey: ["admin", "collections"], queryFn: adminApi.collections });
  const { can } = useAuth();
  const write = can("products:write");
  const [editing, setEditing] = useState<AdminCollection | "new" | null>(null);
  return (
    <>
      <PageHeader title="Collections" sub="Curated edits shown on the storefront, with optional schedules."
        actions={write && <Button size="sm" onClick={() => setEditing("new")}><Plus className="h-4 w-4" aria-hidden />Add collection</Button>} />
      <QueryState q={q} what="Collections">
        {(rows) => rows.length ? (
          <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {rows.map((c) => {
              const sch = schedule(c);
              return (
                <li key={c.id} className="card flex gap-4 p-4">
                  <Thumb src={c.image_url} size={72} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[15px] font-medium text-kajal">{c.name}</p>
                    <p className="truncate text-xs text-kajal-400">/{c.slug} · order {c.display_order}</p>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      <Badge tone={c.is_active ? "success" : "neutral"}>{c.is_active ? "Active" : "Hidden"}</Badge>
                      {c.is_featured && <Badge tone="gold">Featured</Badge>}
                      {sch && <Badge tone={sch.tone}>{sch.label}</Badge>}
                      <Badge>{c.products.length} products</Badge>
                    </div>
                  </div>
                  {write && <Button variant="ghost" size="sm" className="h-8 self-start text-gold-700 hover:bg-gold-50" onClick={() => setEditing(c)}>Edit</Button>}
                </li>
              );
            })}
          </ul>
        ) : <EmptyState title="No collections yet" body="Group products into edits like ‘Festive’ or ‘Bridal’." icon={<Sparkles className="h-8 w-8" />} />}
      </QueryState>
      {editing && <CollectionModal col={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
    </>
  );
}

function CollectionModal({ col, onClose }: { col: AdminCollection | null; onClose: () => void }) {
  const confirm = useConfirm();
  const [f, setF] = useState({
    name: col?.name ?? "", slug: col?.slug ?? "", description: col?.description ?? "", image_url: col?.image_url ?? "",
    is_featured: col?.is_featured ?? false, is_active: col?.is_active ?? true, display_order: String(col?.display_order ?? 0),
    starts_at: utcToLocalInput(col?.starts_at), ends_at: utcToLocalInput(col?.ends_at), product_ids: col?.product_ids ?? [],
  });
  const [err, setErr] = useState<string | null>(null);
  const inv = [["admin", "collections"], ["admin", "product-meta"]];
  const save = useAdminMutation(() => adminApi.saveCollection(col?.id ?? null, {
    name: f.name.trim(), slug: f.slug || null, description: f.description || null, image_url: f.image_url || null, is_featured: f.is_featured,
    is_active: f.is_active, display_order: Number(f.display_order) || 0, starts_at: localInputToUtc(f.starts_at), ends_at: localInputToUtc(f.ends_at),
    product_ids: f.product_ids,
  }), { invalidate: inv, success: col ? "Collection saved" : "Collection created", onSuccess: onClose });
  const del = useAdminMutation(() => adminApi.deleteCollection(col!.id), { invalidate: inv, success: "Collection deleted", onSuccess: onClose });
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (f.name.trim().length < 2) return setErr("Name needs at least 2 characters");
    if (f.starts_at && f.ends_at && f.ends_at <= f.starts_at) return setErr("End must be after start");
    setErr(null);
    save.mutate(undefined);
  };
  return (
    <Modal open onClose={onClose} title={col ? `Edit ${col.name}` : "New collection"} size="xl"
      footer={<>
        {col && <Button variant="ghost" size="sm" className="mr-auto text-kumkum" loading={del.isPending}
          onClick={async () => { if ((await confirm({ title: "Delete this collection?", body: "Products stay in the catalogue; only the grouping is removed.", confirmLabel: "Delete collection", danger: true })).ok) del.mutate(undefined); }}>Delete</Button>}
        <Button variant="ghost" size="sm" onClick={onClose}>Cancel</Button>
        <Button size="sm" type="submit" form="col-form" loading={save.isPending}>{col ? "Save collection" : "Create collection"}</Button>
      </>}>
      <form id="col-form" onSubmit={submit} className="space-y-4">
        {err && <p role="alert" className="text-sm text-kumkum">{err}</p>}
        <FieldGrid>
          <Input label="Name" required value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />
          <Input label="Slug" value={f.slug} onChange={(e) => setF({ ...f, slug: e.target.value })} hint="Leave blank to generate." />
        </FieldGrid>
        <Textarea label="Description" rows={2} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} />
        <ImageField label="Cover image" folder="collections" value={f.image_url} onChange={(url) => setF({ ...f, image_url: url })} />
        <FieldGrid cols={3}>
          <Input label="Starts" type="datetime-local" value={f.starts_at} onChange={(e) => setF({ ...f, starts_at: e.target.value })} hint="Optional" />
          <Input label="Ends" type="datetime-local" value={f.ends_at} onChange={(e) => setF({ ...f, ends_at: e.target.value })} hint="Optional" />
          <Input label="Display order" type="number" value={f.display_order} onChange={(e) => setF({ ...f, display_order: e.target.value })} />
        </FieldGrid>
        <div className="flex flex-wrap gap-6">
          <Switch label="Active" checked={f.is_active} onChange={(v) => setF({ ...f, is_active: v })} />
          <Switch label="Featured on home page" checked={f.is_featured} onChange={(v) => setF({ ...f, is_featured: v })} />
        </div>
        <ProductPicker value={f.product_ids} known={col?.products ?? []} onChange={(ids) => setF({ ...f, product_ids: ids })} />
      </form>
    </Modal>
  );
}
