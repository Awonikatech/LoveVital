import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ChevronRight, FolderTree, Plus } from "lucide-react";
import { adminApi, type AdminCategory } from "@/services/admin";
import { FieldGrid, PageHeader, QueryState, Switch, Thumb, useConfirm } from "@/components/admin/kit";
import { useAdminMutation } from "@/components/admin/hooks";
import { ImageField } from "@/components/admin/ImageField";
import { Badge, Button, EmptyState, Input, Modal, Select, Textarea } from "@/components/ui";
import { useAuth } from "@/features/auth";


type Node = AdminCategory & { children: Node[]; depth: number };

function buildTree(rows: AdminCategory[]): Node[] {
  const map = new Map<number, Node>(rows.map((r) => [r.id, { ...r, children: [], depth: 0 }]));
  const roots: Node[] = [];
  for (const n of map.values()) {
    const parent = n.parent_id ? map.get(n.parent_id) : undefined;
    if (parent) parent.children.push(n); else roots.push(n);
  }
  const sort = (xs: Node[], d: number) => { xs.sort((a, b) => a.display_order - b.display_order || a.name.localeCompare(b.name)); xs.forEach((x) => { x.depth = d; sort(x.children, d + 1); }); };
  sort(roots, 0);
  return roots;
}
function flatten(nodes: Node[]): Node[] { return nodes.flatMap((n) => [n, ...flatten(n.children)]); }
function descendants(n: Node): number[] { return n.children.flatMap((c) => [c.id, ...descendants(c)]); }

export default function Categories() {
  const q = useQuery({ queryKey: ["admin", "categories"], queryFn: adminApi.categories });
  const { can } = useAuth();
  const write = can("products:write");
  const [editing, setEditing] = useState<AdminCategory | "new" | null>(null);
  return (
    <>
      <PageHeader title="Categories" sub="Organise the catalogue into a browsable tree."
        actions={write && <Button size="sm" onClick={() => setEditing("new")}><Plus className="h-4 w-4" aria-hidden />Add category</Button>} />
      <QueryState q={q} what="Categories">
        {(rows) => {
          const tree = buildTree(rows);
          if (!rows.length) return <EmptyState title="No categories yet" icon={<FolderTree className="h-8 w-8" />} />;
          return (
            <div className="card divide-y divide-gold-200/40 overflow-hidden">
              {flatten(tree).map((n) => (
                <div key={n.id} className="flex items-center gap-3 px-4 py-3 hover:bg-gold-50/40" style={{ paddingLeft: 16 + n.depth * 28 }}>
                  {n.depth > 0 && <ChevronRight className="h-4 w-4 shrink-0 text-gold-300" aria-hidden />}
                  <Thumb src={n.image_url} size={36} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[15px] text-kajal">{n.name} {!n.is_active && <Badge className="ml-1">Hidden</Badge>}</p>
                    <p className="truncate text-xs text-kajal-400">/{n.slug} · order {n.display_order}</p>
                  </div>
                  <Link to={`/admin/products?category_id=${n.id}`} className="whitespace-nowrap text-sm text-kajal-500 tabular hover:text-kajal">{n.product_count} products</Link>
                  {write && <Button variant="ghost" size="sm" className="h-8 text-gold-700 hover:bg-gold-50" onClick={() => setEditing(n)}>Edit</Button>}
                </div>
              ))}
            </div>
          );
        }}
      </QueryState>
      {editing && q.data && <CategoryModal cat={editing === "new" ? null : editing} all={q.data} onClose={() => setEditing(null)} />}
    </>
  );
}

function CategoryModal({ cat, all, onClose }: { cat: AdminCategory | null; all: AdminCategory[]; onClose: () => void }) {
  const confirm = useConfirm();
  const [f, setF] = useState({
    name: cat?.name ?? "", slug: cat?.slug ?? "", parent_id: cat?.parent_id ? String(cat.parent_id) : "", description: cat?.description ?? "",
    image_url: cat?.image_url ?? "", display_order: String(cat?.display_order ?? 0), is_active: cat?.is_active ?? true,
    seo_title: cat?.seo_title ?? "", seo_description: cat?.seo_description ?? "",
  });
  const [err, setErr] = useState<string | null>(null);
  const tree = useMemo(() => flatten(buildTree(all)), [all]);
  const blocked = useMemo(() => {
    if (!cat) return new Set<number>();
    const me = tree.find((n) => n.id === cat.id);
    return new Set([cat.id, ...(me ? descendants(me) : [])]);
  }, [cat, tree]);
  const save = useAdminMutation(() => adminApi.saveCategory(cat?.id ?? null, {
    ...f, slug: f.slug || null, parent_id: f.parent_id ? Number(f.parent_id) : null, display_order: Number(f.display_order) || 0,
    description: f.description || null, image_url: f.image_url || null, seo_title: f.seo_title || null, seo_description: f.seo_description || null,
  }), { invalidate: [["admin", "categories"], ["admin", "product-meta"]], success: cat ? "Category saved" : "Category created", onSuccess: onClose });
  const del = useAdminMutation(() => adminApi.deleteCategory(cat!.id), { invalidate: [["admin", "categories"], ["admin", "product-meta"]], success: "Category deleted", onSuccess: onClose });
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (f.name.trim().length < 2) return setErr("Name needs at least 2 characters");
    setErr(null);
    save.mutate(undefined);
  };
  return (
    <Modal open onClose={onClose} title={cat ? `Edit ${cat.name}` : "New category"} size="lg"
      footer={<>
        {cat && <Button variant="ghost" size="sm" className="mr-auto text-kumkum" loading={del.isPending}
          onClick={async () => { if ((await confirm({ title: "Delete this category?", body: "Categories with products or sub-categories can't be deleted.", confirmLabel: "Delete category", danger: true })).ok) del.mutate(undefined); }}>Delete</Button>}
        <Button variant="ghost" size="sm" onClick={onClose}>Cancel</Button>
        <Button size="sm" type="submit" form="cat-form" loading={save.isPending}>{cat ? "Save category" : "Create category"}</Button>
      </>}>
      <form id="cat-form" onSubmit={submit} className="space-y-4">
        <FieldGrid>
          <Input label="Name" required value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} error={err ?? undefined} />
          <Input label="Slug" value={f.slug} onChange={(e) => setF({ ...f, slug: e.target.value })} hint="Leave blank to generate." />
          <Select label="Parent category" value={f.parent_id} onChange={(e) => setF({ ...f, parent_id: e.target.value })}>
            <option value="">None (top level)</option>
            {tree.map((n) => <option key={n.id} value={n.id} disabled={blocked.has(n.id)}>{"— ".repeat(n.depth)}{n.name}</option>)}
          </Select>
          <Input label="Display order" type="number" value={f.display_order} onChange={(e) => setF({ ...f, display_order: e.target.value })} hint="Lower numbers show first." />
        </FieldGrid>
        <Textarea label="Description" rows={3} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} />
        <ImageField label="Image" folder="categories" value={f.image_url} onChange={(url) => setF({ ...f, image_url: url })} />
        <FieldGrid>
          <Input label="SEO title" value={f.seo_title} onChange={(e) => setF({ ...f, seo_title: e.target.value })} />
          <Input label="SEO description" value={f.seo_description} onChange={(e) => setF({ ...f, seo_description: e.target.value })} />
        </FieldGrid>
        <Switch label="Visible in store" checked={f.is_active} onChange={(v) => setF({ ...f, is_active: v })} />
      </form>
    </Modal>
  );
}

