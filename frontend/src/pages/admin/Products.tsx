import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Download, FileUp, MoreHorizontal, Plus, Star, Flame, Sparkle } from "lucide-react";
import { adminApi, type AdminProductRow, type ImportResult, type ProductStatus } from "@/services/admin";
import { downloadFile, errorMessage } from "@/services/api";
import {
  EmptyRow, FilterBar, FilterSelect, PageHeader, QueryState, SearchBox, SortTh, Table, TableFooter, TableSkeleton, Td, Th, Thumb, Tr, useConfirm,
} from "@/components/admin/kit";
import { useAdminMutation, useUrlFilters } from "@/components/admin/hooks";
import { Alert, Button, ButtonLink, Modal, StatusBadge } from "@/components/ui";
import { useAuth } from "@/features/auth";
import { useToast } from "@/features/toast";
import { date, rupees } from "@/utils/format";
import { cn } from "@/utils/cn";

const DEFAULTS = { q: "", status: "", category_id: "", product_type: "", stock: "", flag: "", sort: "newest", page: "1" };

export default function Products() {
  const [f, set] = useUrlFilters(DEFAULTS);
  const { can } = useAuth();
  const write = can("products:write");
  const toast = useToast();
  const [importOpen, setImportOpen] = useState(false);
  const meta = useQuery({ queryKey: ["admin", "product-meta"], queryFn: adminApi.productMeta, staleTime: 5 * 60_000 });
  const q = useQuery({ queryKey: ["admin", "products", f], queryFn: () => adminApi.products({ ...f, page_size: 20 }), placeholderData: keepPreviousData });
  const [exporting, setExporting] = useState(false);

  const exportCsv = async () => {
    setExporting(true);
    try { await downloadFile("/admin/products-export.csv", `products-${new Date().toISOString().slice(0, 10)}.csv`); }
    catch (e) { toast(errorMessage(e), "error"); }
    finally { setExporting(false); }
  };

  return (
    <>
      <PageHeader title="Products" sub="Manage your catalogue, prices and visibility."
        actions={<>
          <Button variant="ghost" size="sm" onClick={exportCsv} loading={exporting}><Download className="h-4 w-4" aria-hidden />Export CSV</Button>
          {write && <Button variant="outline" size="sm" onClick={() => setImportOpen(true)}><FileUp className="h-4 w-4" aria-hidden />Import CSV</Button>}
          {write && <ButtonLink to="/admin/products/new" size="sm"><Plus className="h-4 w-4" aria-hidden />Add product</ButtonLink>}
        </>} />

      <FilterBar>
        <SearchBox className="w-full sm:w-72" value={f.q} onChange={(v) => set({ q: v })} placeholder="Search name or SKU" label="Search products" />
        <FilterSelect label="Status" value={f.status} onChange={(v) => set({ status: v })} options={[
          { value: "", label: "All statuses" }, { value: "active", label: "Active" }, { value: "draft", label: "Draft" }, { value: "archived", label: "Archived" }]} />
        <FilterSelect label="Category" value={f.category_id} onChange={(v) => set({ category_id: v })}
          options={[{ value: "", label: "All categories" }, ...(meta.data?.categories ?? []).map((c) => ({ value: String(c.id), label: c.label }))]} />
        <FilterSelect label="Type" value={f.product_type} onChange={(v) => set({ product_type: v })} options={[
          { value: "", label: "All types" }, { value: "jewellery", label: "Jewellery" }, { value: "apparel", label: "Apparel" }]} />
        <FilterSelect label="Stock" value={f.stock} onChange={(v) => set({ stock: v })} options={[
          { value: "", label: "Any stock" }, { value: "in", label: "In stock" }, { value: "low", label: "Low (1–10)" }, { value: "out", label: "Out of stock" }]} />
        <FilterSelect label="Flag" value={f.flag} onChange={(v) => set({ flag: v })} options={[
          { value: "", label: "Any flag" }, { value: "featured", label: "Featured" }, { value: "bestseller", label: "Bestseller" }, { value: "new", label: "New arrival" }]} />
      </FilterBar>

      <QueryState q={q} what="Products" skeleton={<Table minWidth={980}><tbody><TableSkeleton cols={8} /></tbody></Table>}>
        {(data) => (
          <>
            <Table minWidth={980} className={cn(q.isFetching && "opacity-70")}>
              <thead>
                <tr>
                  <SortTh label="Product" field="name" sort={f.sort} onSort={(s) => set({ sort: f.sort === s ? "newest" : s })} />
                  <Th>Category</Th>
                  <Th>Status</Th>
                  <Th>Flags</Th>
                  <SortTh label="Price" field="price_asc" sort={f.sort} onSort={(s) => set({ sort: f.sort === s ? "price_desc" : s })} align="right" />
                  <SortTh label="Stock" field="stock" sort={f.sort} onSort={(s) => set({ sort: f.sort === s ? "newest" : s })} align="right" />
                  <SortTh label="Sold" field="sold" sort={f.sort} onSort={(s) => set({ sort: f.sort === s ? "newest" : s })} align="right" />
                  <Th align="right"><span className="sr-only">Actions</span></Th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((p) => <ProductRow key={p.id} p={p} write={write} />)}
                {!data.items.length && <EmptyRow cols={8}>No products match these filters.</EmptyRow>}
              </tbody>
            </Table>
            <TableFooter total={data.total} page={data.page} pages={data.pages} onPage={(p) => set({ page: String(p) }, false)} noun="product" />
          </>
        )}
      </QueryState>
      {write && <ImportModal open={importOpen} onClose={() => setImportOpen(false)} />}
    </>
  );
}

function FlagButton({ on, label, icon, onClick, disabled }: { on: boolean; label: string; icon: React.ReactNode; onClick: () => void; disabled?: boolean }) {
  return (
    <button type="button" onClick={onClick} disabled={disabled} aria-pressed={on} title={`${on ? "Remove" : "Mark as"} ${label.toLowerCase()}`}
      className={cn("inline-flex h-7 items-center gap-1 rounded-full border px-2 text-xs transition-colors disabled:cursor-not-allowed",
        on ? "border-gold-300 bg-gold-50 text-gold-800" : "border-transparent text-kajal-300 hover:border-kajal-300/50 hover:text-kajal-500")}>
      {icon}<span className={on ? "" : "sr-only"}>{label}</span>
    </button>
  );
}

function ProductRow({ p, write }: { p: AdminProductRow; write: boolean }) {
  const nav = useNavigate();
  const confirm = useConfirm();
  const [menu, setMenu] = useState(false);
  const patch = useAdminMutation((b: Parameters<typeof adminApi.patchProduct>[1]) => adminApi.patchProduct(p.id, b), {
    invalidate: [["admin", "products"]],
    success: (_, b) => (b.status ? `${p.name} is now ${b.status}` : "Flags updated"),
  });
  const del = useAdminMutation(() => adminApi.deleteProduct(p.id), {
    invalidate: [["admin", "products"]], success: (r) => r.message ?? "Product deleted",
  });
  const setStatus = async (s: ProductStatus) => {
    setMenu(false);
    if (s === "archived") {
      const r = await confirm({ title: "Archive this product?", body: <>“{p.name}” will be hidden from the store. You can restore it later.</>, confirmLabel: "Archive product", danger: true });
      if (!r.ok) return;
    }
    patch.mutate({ status: s });
  };
  const remove = async () => {
    setMenu(false);
    const r = await confirm({ title: "Delete this product?", body: <>“{p.name}” and its variants will be deleted. Products with order history are archived instead.</>, confirmLabel: "Delete product", danger: true });
    if (r.ok) del.mutate(undefined);
  };
  const stockTone = p.total_stock <= 0 ? "text-kumkum" : p.total_stock <= 10 ? "text-[#8A5A00]" : "text-kajal-700";
  return (
    <Tr>
      <Td>
        <div className="flex items-center gap-3">
          <Thumb src={p.image} alt="" />
          <div className="min-w-0">
            <Link to={`/admin/products/${p.id}`} className="block max-w-[300px] truncate font-medium text-kajal hover:underline">{p.name}</Link>
            <p className="text-xs text-kajal-400">{p.sku} · {p.variant_count} variant{p.variant_count === 1 ? "" : "s"} · updated {date(p.updated_at)}</p>
          </div>
        </div>
      </Td>
      <Td className="whitespace-nowrap">{p.category_name}</Td>
      <Td><StatusBadge status={p.status} /></Td>
      <Td>
        <div className="flex gap-1">
          <FlagButton on={p.is_featured} label="Featured" icon={<Star className="h-3.5 w-3.5" aria-hidden />} disabled={!write || patch.isPending} onClick={() => patch.mutate({ is_featured: !p.is_featured })} />
          <FlagButton on={p.is_bestseller} label="Bestseller" icon={<Flame className="h-3.5 w-3.5" aria-hidden />} disabled={!write || patch.isPending} onClick={() => patch.mutate({ is_bestseller: !p.is_bestseller })} />
          <FlagButton on={p.is_new_arrival} label="New" icon={<Sparkle className="h-3.5 w-3.5" aria-hidden />} disabled={!write || patch.isPending} onClick={() => patch.mutate({ is_new_arrival: !p.is_new_arrival })} />
        </div>
      </Td>
      <Td align="right">
        <span className="text-kajal">{rupees(p.price_min)}</span>
        {Number(p.mrp_min) > Number(p.price_min) && <span className="block text-xs text-kajal-400 line-through">{rupees(p.mrp_min)}</span>}
      </Td>
      <Td align="right"><span className={stockTone}>{p.total_stock}</span></Td>
      <Td align="right">{p.sold_count}</Td>
      <Td align="right">
        <div className="relative inline-block text-left">
          <button type="button" aria-haspopup="menu" aria-expanded={menu} aria-label={`Actions for ${p.name}`} onClick={() => setMenu(!menu)}
            className="rounded-full p-1.5 text-kajal-500 hover:bg-ivory-200 hover:text-kajal"><MoreHorizontal className="h-4 w-4" /></button>
          {menu && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setMenu(false)} aria-hidden />
              <div role="menu" className="absolute right-0 z-20 mt-1 w-44 overflow-hidden rounded-xl border border-gold-200/60 bg-white py-1 text-left text-[14px] shadow-lift"
                onKeyDown={(e) => e.key === "Escape" && setMenu(false)}>
                <MenuItem onClick={() => nav(`/admin/products/${p.id}`)}>Edit</MenuItem>
                {write && p.status !== "active" && <MenuItem onClick={() => setStatus("active")}>Make active</MenuItem>}
                {write && p.status !== "draft" && <MenuItem onClick={() => setStatus("draft")}>Move to draft</MenuItem>}
                {write && p.status !== "archived" && <MenuItem onClick={() => setStatus("archived")}>Archive</MenuItem>}
                {write && <MenuItem danger onClick={remove}>Delete</MenuItem>}
                <a role="menuitem" href={`/product/${p.slug}`} target="_blank" rel="noreferrer" className="block px-3.5 py-2 text-kajal-700 hover:bg-ivory-200">View in store</a>
              </div>
            </>
          )}
        </div>
      </Td>
    </Tr>
  );
}

function MenuItem({ children, onClick, danger }: { children: React.ReactNode; onClick: () => void; danger?: boolean }) {
  return <button role="menuitem" type="button" onClick={onClick} className={cn("block w-full px-3.5 py-2 text-left hover:bg-ivory-200", danger ? "text-kumkum" : "text-kajal-700")}>{children}</button>;
}

function ImportModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportResult | null>(null);
  const [done, setDone] = useState<ImportResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const reset = () => { setFile(null); setPreview(null); setDone(null); setErr(null); if (input.current) input.current.value = ""; };
  const dry = useAdminMutation((f: File) => adminApi.importProducts(f, true), { silentError: true, onSuccess: (r) => { setPreview(r); setErr(null); } });
  const commit = useAdminMutation((f: File) => adminApi.importProducts(f, false), {
    silentError: true, invalidate: [["admin", "products"], ["admin", "inventory"]], success: (r) => `Imported: ${r.created} created, ${r.updated} updated`,
    onSuccess: (r) => setDone(r),
  });
  const pick = (f: File | null) => {
    reset();
    if (!f) return;
    if (!/\.csv$/i.test(f.name)) { setErr("Choose a .csv file."); return; }
    if (f.size > 5 * 1024 * 1024) { setErr("CSV must be under 5 MB."); return; }
    setFile(f);
    dry.mutate(f, { onError: (e) => setErr(errorMessage(e)) });
  };
  const close = () => { reset(); onClose(); };
  return (
    <Modal open={open} onClose={close} title="Import products from CSV" size="lg"
      footer={done ? <Button size="sm" onClick={close}>Done</Button> : <>
        <Button variant="ghost" size="sm" onClick={close}>Cancel</Button>
        <Button size="sm" disabled={!file || !preview || dry.isPending} loading={commit.isPending}
          onClick={() => file && commit.mutate(file, { onError: (e) => setErr(errorMessage(e)) })}>
          Import {preview ? `${preview.created + preview.updated} rows` : ""}
        </Button>
      </>}>
      <div className="space-y-4 text-[15px]">
        <p className="text-kajal-500">
          Required columns: <code className="text-sm">product_sku, product_name, product_type, category_slug, variant_sku, mrp, sale_price</code>.
          Optional: slug, brand, status, short_description, tags (pipe-separated), variant_name, cost_price, stock (absolute on-hand), attributes (<code className="text-sm">color=Gold;size=M</code>), image_url.
          Tip: export first to get a template.
        </p>
        <label className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border border-dashed border-gold-300 bg-gold-50/40 px-4 py-8 text-center hover:bg-gold-50">
          <FileUp className="h-6 w-6 text-gold-600" aria-hidden />
          <span className="text-kajal">{file ? file.name : "Choose a CSV file"}</span>
          <span className="text-sm text-kajal-500">We'll check it first — nothing is saved until you confirm.</span>
          <input ref={input} type="file" accept=".csv,text/csv" className="sr-only" onChange={(e) => pick(e.target.files?.[0] ?? null)} />
        </label>
        {dry.isPending && <p className="text-sm text-kajal-500">Checking file…</p>}
        {err && <Alert tone="error">{err}</Alert>}
        {(done ?? preview) && <ImportSummary r={(done ?? preview)!} committed={!!done} />}
      </div>
    </Modal>
  );
}

function ImportSummary({ r, committed }: { r: ImportResult; committed: boolean }) {
  return (
    <div className="space-y-3">
      <Alert tone={r.errors.length ? "warning" : "success"}>
        {committed ? "Import complete: " : "Preview (nothing saved yet): "}
        <strong className="tabular">{r.created}</strong> rows create new products, <strong className="tabular">{r.updated}</strong> update existing ones
        {r.errors.length ? <>, <strong className="tabular">{r.errors.length}</strong> rows have errors and will be skipped.</> : "."}
      </Alert>
      {!!r.errors.length && (
        <div className="max-h-56 overflow-auto rounded-xl border border-gold-200/60">
          <table className="w-full text-sm">
            <thead><tr><Th>Line</Th><Th>Problem</Th></tr></thead>
            <tbody>{r.errors.map((e, i) => <tr key={i}><Td className="tabular">{e.line}</Td><Td>{e.error}</Td></tr>)}</tbody>
          </table>
        </div>
      )}
    </div>
  );
}
