import { useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { SlidersHorizontal, X, Check, SearchX } from "lucide-react";
import { storeApi } from "@/services/store";
import { Breadcrumbs, Button, Drawer, EmptyState, ErrorState, Pagination, Select } from "@/components/ui";
import { ProductGrid } from "@/components/product/ProductCard";
import { useSeo } from "@/hooks/useSeo";
import type { Facets } from "@/types";
import { rupees, plural } from "@/utils/format";
import { cn } from "@/utils/cn";
import { rememberSearch } from "@/components/layout/SearchBox";

type Mode = "all" | "search" | "category" | "collection" | "type" | "flag";
const ATTR_KEYS = ["color", "size", "material", "plating", "stone", "style", "fabric", "fit", "occasion"];
const SORTS = [
  { value: "popularity", label: "Most popular" },
  { value: "newest", label: "Newest first" },
  { value: "price_asc", label: "Price: low to high" },
  { value: "price_desc", label: "Price: high to low" },
  { value: "rating", label: "Customer rating" },
  { value: "discount", label: "Biggest discount" },
];
const PRICE_BANDS = [
  { label: "Under ₹500", min: undefined, max: 500 },
  { label: "₹500 – ₹1,000", min: 500, max: 1000 },
  { label: "₹1,000 – ₹2,500", min: 1000, max: 2500 },
  { label: "₹2,500 – ₹5,000", min: 2500, max: 5000 },
  { label: "Above ₹5,000", min: 5000, max: undefined },
];
const FLAG_COPY: Record<string, { title: string; sub: string }> = {
  new_arrival: { title: "New arrivals", sub: "Just in from our ateliers — the newest jewellery and apparel." },
  bestseller: { title: "Best sellers", sub: "The pieces our customers reorder and gift most." },
  on_sale: { title: "Sale", sub: "Signature styles at reduced prices, for a limited time." },
};

function FilterGroup({ title, children, defaultOpen = true }: { title: string; children: React.ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border-b border-gold-200/50 py-5">
      <button className="flex w-full items-center justify-between text-left text-[15px] font-medium" aria-expanded={open} onClick={() => setOpen(!open)}>
        {title}<span className="text-kajal-400">{open ? "−" : "+"}</span>
      </button>
      {open && <div className="mt-3">{children}</div>}
    </div>
  );
}

function Filters({ facets, params, set, toggle }: { facets?: Facets; params: URLSearchParams; set: (k: string, v?: string) => void; toggle: (k: string, v: string) => void }) {
  const has = (k: string, v: string) => (params.get(k) ?? "").split(",").includes(v);
  const [minP, setMinP] = useState(params.get("min_price") ?? "");
  const [maxP, setMaxP] = useState(params.get("max_price") ?? "");
  return (
    <div>
      <FilterGroup title="Availability">
        <label className="flex cursor-pointer items-center gap-2.5 text-[15px] text-kajal-700">
          <input type="checkbox" className="h-4 w-4 accent-[#2A1A1F]" checked={params.get("in_stock") === "true"} onChange={(e) => set("in_stock", e.target.checked ? "true" : undefined)} />
          In stock only
        </label>
      </FilterGroup>
      <FilterGroup title="Price">
        <div className="space-y-2">
          {PRICE_BANDS.map((b) => {
            const active = (params.get("min_price") ?? "") === String(b.min ?? "") && (params.get("max_price") ?? "") === String(b.max ?? "");
            return (
              <button key={b.label} className={cn("flex w-full items-center gap-2.5 text-left text-[15px]", active ? "text-kajal" : "text-kajal-700")}
                onClick={() => { set("min_price", active ? undefined : b.min?.toString()); set("max_price", active ? undefined : b.max?.toString()); }}>
                <span className={cn("flex h-4 w-4 items-center justify-center rounded-full border", active ? "border-kajal bg-kajal" : "border-kajal-300")}>{active && <Check className="h-3 w-3 text-ivory" />}</span>
                {b.label}
              </button>
            );
          })}
        </div>
        <form className="mt-3 flex items-center gap-2" onSubmit={(e) => { e.preventDefault(); set("min_price", minP || undefined); set("max_price", maxP || undefined); }}>
          <input aria-label="Minimum price" inputMode="numeric" value={minP} onChange={(e) => setMinP(e.target.value.replace(/\D/g, ""))} placeholder={facets ? `₹${Math.floor(Number(facets.price.min))}` : "Min"} className="input h-9 px-2.5 text-sm" />
          <span className="text-kajal-400">–</span>
          <input aria-label="Maximum price" inputMode="numeric" value={maxP} onChange={(e) => setMaxP(e.target.value.replace(/\D/g, ""))} placeholder={facets ? `₹${Math.ceil(Number(facets.price.max))}` : "Max"} className="input h-9 px-2.5 text-sm" />
          <Button type="submit" size="sm" variant="outline">Go</Button>
        </form>
      </FilterGroup>
      <FilterGroup title="Discount">
        <div className="flex flex-wrap gap-2">
          {[10, 25, 40, 50].map((d) => (
            <button key={d} className={cn("chip", params.get("min_discount") === String(d) && "chip-active")} onClick={() => set("min_discount", params.get("min_discount") === String(d) ? undefined : String(d))}>{d}%+</button>
          ))}
        </div>
      </FilterGroup>
      <FilterGroup title="Customer rating">
        <div className="flex flex-wrap gap-2">
          {[4, 3].map((r) => (
            <button key={r} className={cn("chip", params.get("min_rating") === String(r) && "chip-active")} onClick={() => set("min_rating", params.get("min_rating") === String(r) ? undefined : String(r))}>{r}★ & above</button>
          ))}
        </div>
      </FilterGroup>
      {facets?.attributes.map((a) => (
        <FilterGroup key={a.code} title={a.name} defaultOpen={["color", "size", "material", "fabric"].includes(a.code)}>
          {a.code === "color" ? (
            <div className="flex flex-wrap gap-2.5">
              {a.values.map((v) => (
                <button key={v.slug} onClick={() => toggle(a.code, v.slug)} aria-pressed={has(a.code, v.slug)} title={`${v.value} (${v.count})`}
                  className={cn("flex items-center gap-2 rounded-full border py-1 pl-1 pr-3 text-sm", has(a.code, v.slug) ? "border-kajal" : "border-kajal-300/50 hover:border-gold-500")}>
                  <span className="h-5 w-5 rounded-full border border-kajal/10" style={{ background: v.hex ?? "#ddd" }} />{v.value}
                </button>
              ))}
            </div>
          ) : a.code === "size" ? (
            <div className="flex flex-wrap gap-2">
              {a.values.map((v) => <button key={v.slug} className={cn("chip min-w-11 justify-center", has(a.code, v.slug) && "chip-active")} onClick={() => toggle(a.code, v.slug)}>{v.value}</button>)}
            </div>
          ) : (
            <div className="space-y-2">
              {a.values.map((v) => (
                <label key={v.slug} className="flex cursor-pointer items-center gap-2.5 text-[15px] text-kajal-700">
                  <input type="checkbox" className="h-4 w-4 accent-[#2A1A1F]" checked={has(a.code, v.slug)} onChange={() => toggle(a.code, v.slug)} />
                  <span className="flex-1">{v.value}</span><span className="text-sm text-kajal-400 tabular">{v.count}</span>
                </label>
              ))}
            </div>
          )}
        </FilterGroup>
      ))}
      {(facets?.brands.length ?? 0) > 1 && (
        <FilterGroup title="Brand" defaultOpen={false}>
          <div className="space-y-2">
            {facets!.brands.map((b) => (
              <label key={b.value} className="flex cursor-pointer items-center gap-2.5 text-[15px] text-kajal-700">
                <input type="checkbox" className="h-4 w-4 accent-[#2A1A1F]" checked={has("brand", b.value)} onChange={() => toggle("brand", b.value)} />
                <span className="flex-1">{b.value}</span><span className="text-sm text-kajal-400 tabular">{b.count}</span>
              </label>
            ))}
          </div>
        </FilterGroup>
      )}
    </div>
  );
}

export default function Listing({ mode, productType, flag }: { mode: Mode; productType?: "jewellery" | "apparel"; flag?: string }) {
  const { slug } = useParams();
  const [params, setParams] = useSearchParams();
  const [filtersOpen, setFiltersOpen] = useState(false);
  const page = Number(params.get("page") ?? 1);
  const sort = params.get("sort") ?? (mode === "flag" && flag === "new_arrival" ? "newest" : mode === "flag" && flag === "on_sale" ? "discount" : "popularity");
  const q = params.get("q") ?? "";

  const apiParams = useMemo(() => {
    const p: Record<string, string | number | boolean | undefined> = { page, sort, page_size: 24 };
    if (mode === "category") p.category = slug;
    if (mode === "collection") p.collection = slug;
    if (mode === "type") p.product_type = productType;
    if (mode === "flag" && flag) p[flag] = true;
    if (mode === "search") p.q = q;
    if (mode === "all" && params.get("q")) p.q = q;
    for (const k of [...ATTR_KEYS, "brand", "min_price", "max_price", "min_discount", "min_rating", "in_stock"]) {
      const v = params.get(k);
      if (v) p[k] = v;
    }
    return p;
  }, [mode, slug, productType, flag, params, page, sort, q]);

  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ["products", apiParams],
    queryFn: () => storeApi.products(apiParams),
    placeholderData: keepPreviousData,
    enabled: mode !== "search" || q.length > 0,
  });

  const update = (fn: (p: URLSearchParams) => void) => {
    const next = new URLSearchParams(params);
    fn(next);
    if (!next.has("page_keep")) next.delete("page");
    next.delete("page_keep");
    setParams(next, { replace: false });
  };
  const set = (k: string, v?: string) => update((p) => (v ? p.set(k, v) : p.delete(k)));
  const toggle = (k: string, v: string) =>
    update((p) => {
      const cur = new Set((p.get(k) ?? "").split(",").filter(Boolean));
      cur.has(v) ? cur.delete(v) : cur.add(v);
      cur.size ? p.set(k, [...cur].join(",")) : p.delete(k);
    });

  const active: { key: string; value: string; label: string }[] = [];
  for (const k of [...ATTR_KEYS, "brand"]) {
    (params.get(k) ?? "").split(",").filter(Boolean).forEach((v) => {
      const label = data?.facets.attributes.find((a) => a.code === k)?.values.find((x) => x.slug === v)?.value ?? v;
      active.push({ key: k, value: v, label });
    });
  }
  if (params.get("min_price") || params.get("max_price")) active.push({ key: "price", value: "", label: `${params.get("min_price") ? rupees(params.get("min_price")) : "₹0"} – ${params.get("max_price") ? rupees(params.get("max_price")) : "any"}` });
  if (params.get("min_discount")) active.push({ key: "min_discount", value: "", label: `${params.get("min_discount")}%+ off` });
  if (params.get("min_rating")) active.push({ key: "min_rating", value: "", label: `${params.get("min_rating")}★ & above` });
  if (params.get("in_stock")) active.push({ key: "in_stock", value: "", label: "In stock" });
  const clearAll = () => update((p) => { [...ATTR_KEYS, "brand", "min_price", "max_price", "min_discount", "min_rating", "in_stock"].forEach((k) => p.delete(k)); });
  const removeChip = (c: (typeof active)[number]) => (c.key === "price" ? update((p) => { p.delete("min_price"); p.delete("max_price"); }) : ATTR_KEYS.includes(c.key) || c.key === "brand" ? toggle(c.key, c.value) : set(c.key));

  let title = "All products";
  let sub: string | null = "Jewellery and apparel, handcrafted in India.";
  let crumbs: { label: string; to?: string }[] = [{ label: "Home", to: "/" }];
  if (mode === "category" && data?.category) {
    title = data.category.name;
    sub = data.category.description;
    if (data.category.parent) crumbs.push({ label: data.category.parent.name, to: `/category/${data.category.parent.slug}` });
  } else if (mode === "collection" && data?.collection) {
    title = data.collection.name;
    sub = data.collection.description;
    crumbs.push({ label: "Collections", to: "/collections" });
  } else if (mode === "type") {
    title = productType === "jewellery" ? "Jewellery" : "Apparel";
    sub = productType === "jewellery" ? "Kundan, temple, oxidised and contemporary pieces in gold, rose-gold and silver finishes." : "Kurtis, sarees, anarkalis, lehengas and western wear for every occasion.";
  } else if (mode === "flag" && flag) {
    ({ title, sub } = FLAG_COPY[flag]);
  } else if (mode === "search") {
    title = q ? `Results for “${q}”` : "Search";
    sub = data ? plural(data.total, "piece") + " found" : null;
  }
  crumbs.push({ label: mode === "search" ? "Search" : title });

  useSeo({
    title: mode === "category" && data?.category?.seo_title ? data.category.seo_title : title,
    description: (mode === "category" && data?.category?.seo_description) || sub || undefined,
    noindex: mode === "search" || active.length > 0,
  });

  if (isError) return <div className="container-site py-24"><ErrorState message="We couldn't load these products." onRetry={() => refetch()} /></div>;
  if (mode === "category" && data && !data.category) {
    return <EmptyState title="Category not found" body="This category may have moved." action={<Link to="/shop" className="link-underline">Browse all products</Link>} />;
  }

  return (
    <div className="container-site pb-8 pt-6">
      <Breadcrumbs items={crumbs} />
      <header className="mt-5 flex flex-col gap-3 border-b border-gold-200/50 pb-6 sm:flex-row sm:items-end sm:justify-between">
        <div className="max-w-2xl">
          <h1 className="text-[34px] leading-tight sm:text-[44px]">{title}</h1>
          {sub && <p className="mt-2 text-kajal-500">{sub}</p>}
        </div>
        {mode === "category" && (data?.category?.children.length ?? 0) > 0 && (
          <div className="flex flex-wrap gap-2">
            {data!.category!.children.map((c) => <Link key={c.slug} to={`/category/${c.slug}`} className="chip">{c.name}</Link>)}
          </div>
        )}
      </header>

      {mode === "search" && data?.did_you_mean && (
        <p className="mt-4 text-kajal-700">Did you mean <Link to={`/search?q=${encodeURIComponent(data.did_you_mean)}`} onClick={() => rememberSearch(data.did_you_mean!)} className="link-underline font-medium">{data.did_you_mean}</Link>?</p>
      )}

      <div className="mt-6 grid gap-10 lg:grid-cols-[250px_1fr]">
        <aside className="hidden lg:block" aria-label="Filters">
          <div className="sticky top-36 max-h-[calc(100vh-10rem)] overflow-y-auto pr-2 scrollbar-none">
            <Filters facets={data?.facets} params={params} set={set} toggle={toggle} />
          </div>
        </aside>
        <section aria-live="polite" aria-busy={isFetching}>
          <div className="mb-5 flex flex-wrap items-center gap-3">
            <Button variant="outline" size="sm" className="lg:hidden" onClick={() => setFiltersOpen(true)}>
              <SlidersHorizontal className="h-4 w-4" />Filters{active.length ? ` (${active.length})` : ""}
            </Button>
            <p className="text-sm text-kajal-500 tabular">{data ? plural(data.total, "product") : " "}</p>
            <div className="ml-auto w-48 sm:w-56">
              <Select aria-label="Sort by" value={sort} onChange={(e) => set("sort", e.target.value)} options={SORTS} className="[&_select]:h-9 [&_select]:py-1.5 [&_select]:text-sm" />
            </div>
          </div>
          {active.length > 0 && (
            <div className="mb-6 flex flex-wrap items-center gap-2">
              {active.map((c) => (
                <button key={c.key + c.value} className="chip chip-active" onClick={() => removeChip(c)} aria-label={`Remove filter ${c.label}`}>{c.label}<X className="h-3.5 w-3.5" /></button>
              ))}
              <button className="text-sm link-underline" onClick={clearAll}>Clear all</button>
            </div>
          )}
          {mode === "search" && !q ? (
            <EmptyState title="What are you looking for?" body="Search by product name, SKU, category or style." icon={<SearchX className="h-6 w-6" />} />
          ) : !isLoading && data?.items.length === 0 ? (
            <EmptyState icon={<SearchX className="h-6 w-6" />}
              title={mode === "search" ? `Nothing matches “${q}”` : "No pieces match these filters"}
              body={mode === "search" ? <>Check the spelling or try a broader word.{data?.did_you_mean && <> Maybe <Link className="link-underline" to={`/search?q=${data.did_you_mean}`}>{data.did_you_mean}</Link>?</>}</> : "Remove a filter or two to see more."}
              action={active.length ? <Button variant="outline" onClick={clearAll}>Clear filters</Button> : <Link to="/best-sellers" className="link-underline">Browse best sellers</Link>} />
          ) : (
            <div className={cn("transition-opacity", isFetching && !isLoading && "opacity-60")}>
              <ProductGrid products={data?.items} loading={isLoading} count={12} cols="lg:grid-cols-3 xl:grid-cols-4" />
            </div>
          )}
          {data && data.pages > 1 && (
            <div className="mt-12">
              <Pagination page={data.page} pages={data.pages} onChange={(p) => { update((x) => { x.set("page", String(p)); x.set("page_keep", "1"); }); window.scrollTo({ top: 0, behavior: "smooth" }); }} />
            </div>
          )}
        </section>
      </div>

      <Drawer open={filtersOpen} onClose={() => setFiltersOpen(false)} title="Filters" side="left"
        footer={<div className="grid grid-cols-2 gap-2"><Button variant="outline" onClick={clearAll}>Clear all</Button><Button onClick={() => setFiltersOpen(false)}>Show {data ? plural(data.total, "result") : "results"}</Button></div>}>
        <div className="px-5"><Filters facets={data?.facets} params={params} set={set} toggle={toggle} /></div>
      </Drawer>
    </div>
  );
}
