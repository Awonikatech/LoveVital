import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Plus, X } from "lucide-react";
import { adminApi } from "@/services/admin";
import { useDebounce } from "@/hooks/useDebounce";
import { Spinner } from "@/components/ui";
import { Thumb } from "./kit";
import { cn } from "@/utils/cn";

export type PickedProduct = { id: number; name: string; sku: string };

/** Search products and add/remove them. `known` gives names for ids already selected. */
export function ProductPicker({ value, onChange, known = [], disabled, label = "Products" }: {
  value: number[]; onChange: (ids: number[], picked: PickedProduct[]) => void; known?: PickedProduct[]; disabled?: boolean; label?: string;
}) {
  const [q, setQ] = useState("");
  const dq = useDebounce(q, 250);
  const [cache, setCache] = useState<Record<number, PickedProduct>>(() => Object.fromEntries(known.map((k) => [k.id, k])));
  const res = useQuery({ queryKey: ["admin", "products", "picker", dq], queryFn: () => adminApi.products({ q: dq, page_size: 8 }), enabled: dq.trim().length > 0 });
  // Names for ids we don't know yet (e.g. coupon product_ids) — fetch a broad page once.
  const missing = value.filter((id) => !cache[id]);
  const all = useQuery({ queryKey: ["admin", "products", "picker-all"], queryFn: () => adminApi.products({ page_size: 100 }), enabled: missing.length > 0, staleTime: 5 * 60_000 });
  const nameOf = (id: number) => cache[id] ?? all.data?.items.find((p) => p.id === id);
  const picked = value.map((id) => nameOf(id) ?? { id, name: `Product #${id}`, sku: "" });
  const add = (p: PickedProduct) => {
    if (value.includes(p.id)) return;
    setCache((c) => ({ ...c, [p.id]: p }));
    onChange([...value, p.id], [...picked, p]);
  };
  const remove = (id: number) => onChange(value.filter((x) => x !== id), picked.filter((p) => p.id !== id));
  return (
    <div>
      <span className="label">{label} <span className="font-normal text-kajal-400">({value.length} selected)</span></span>
      {picked.length > 0 && (
        <ul className="mb-2 flex max-h-40 flex-wrap gap-1.5 overflow-auto">
          {picked.map((p) => (
            <li key={p.id} className="inline-flex items-center gap-1 rounded-full bg-gold-50 py-0.5 pl-2.5 pr-1 text-sm text-kajal-700">
              <span className="max-w-[220px] truncate">{p.name}</span>
              {!disabled && <button type="button" aria-label={`Remove ${p.name}`} onClick={() => remove(p.id)} className="rounded-full p-0.5 hover:bg-gold-100"><X className="h-3.5 w-3.5" /></button>}
            </li>
          ))}
        </ul>
      )}
      {!disabled && (
        <div className="relative">
          <input type="search" className="input h-10 py-0 text-[14px]" placeholder="Search products by name or SKU to add" aria-label={`Search ${label.toLowerCase()} to add`} value={q} onChange={(e) => setQ(e.target.value)} />
          {dq.trim() && (
            <div className="mt-1 max-h-64 overflow-auto rounded-xl border border-gold-200/60 bg-white shadow-sm">
              {res.isPending ? <div className="p-3"><Spinner /></div> : (res.data?.items ?? []).map((p) => {
                const on = value.includes(p.id);
                return (
                  <button key={p.id} type="button" disabled={on} onClick={() => add({ id: p.id, name: p.name, sku: p.sku })}
                    className={cn("flex w-full items-center gap-3 px-3 py-2 text-left text-[14px] hover:bg-ivory-200", on && "opacity-50")}>
                    <Thumb src={p.image} size={32} />
                    <span className="min-w-0 flex-1"><span className="block truncate">{p.name}</span><span className="text-xs text-kajal-400">{p.sku}</span></span>
                    {on ? <span className="text-xs text-kajal-400">Added</span> : <Plus className="h-4 w-4 text-gold-600" aria-hidden />}
                  </button>
                );
              })}
              {res.data && !res.data.items.length && <p className="p-3 text-sm text-kajal-500">No products found.</p>}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function CategoryPicker({ value, onChange, disabled }: { value: number[]; onChange: (ids: number[]) => void; disabled?: boolean }) {
  const meta = useQuery({ queryKey: ["admin", "product-meta"], queryFn: adminApi.productMeta, staleTime: 5 * 60_000 });
  return (
    <fieldset>
      <legend className="label">Categories <span className="font-normal text-kajal-400">({value.length} selected · includes sub-categories)</span></legend>
      {meta.isPending ? <Spinner /> : (
        <div className="flex max-h-48 flex-wrap gap-1.5 overflow-auto">
          {(meta.data?.categories ?? []).map((c) => {
            const on = value.includes(c.id);
            return (
              <button key={c.id} type="button" disabled={disabled} aria-pressed={on} className={cn("chip", on && "chip-active")}
                onClick={() => onChange(on ? value.filter((x) => x !== c.id) : [...value, c.id])}>{c.label}</button>
            );
          })}
        </div>
      )}
    </fieldset>
  );
}
