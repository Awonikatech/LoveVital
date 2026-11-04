import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Clock, Search, X } from "lucide-react";
import { storeApi } from "@/services/store";
import { useDebounce } from "@/hooks/useDebounce";
import { rupees } from "@/utils/format";
import { cn } from "@/utils/cn";

const RECENT_KEY = "swk_recent_searches";
const POPULAR = ["Jhumkas", "Kundan set", "Silk saree", "Oxidised", "Bangles", "Anarkali"];

export function recentSearches(): string[] {
  try {
    return JSON.parse(localStorage.getItem(RECENT_KEY) || "[]");
  } catch {
    return [];
  }
}
export function rememberSearch(q: string) {
  try {
    const list = [q, ...recentSearches().filter((x) => x.toLowerCase() !== q.toLowerCase())].slice(0, 6);
    localStorage.setItem(RECENT_KEY, JSON.stringify(list));
  } catch {
    /* ignore */
  }
}

export function SearchBox({ className, autoFocus, onDone }: { className?: string; autoFocus?: boolean; onDone?: () => void }) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const dq = useDebounce(q.trim(), 200);
  const nav = useNavigate();
  const wrap = useRef<HTMLDivElement>(null);
  const { data, isFetching } = useQuery({ queryKey: ["suggest", dq], queryFn: () => storeApi.suggest(dq), enabled: dq.length >= 2, staleTime: 60_000 });
  const recent = recentSearches();

  useEffect(() => {
    const h = (e: MouseEvent) => !wrap.current?.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  const go = (term: string) => {
    const t = term.trim();
    if (!t) return;
    rememberSearch(t);
    setOpen(false);
    setQ("");
    onDone?.();
    nav(`/search?q=${encodeURIComponent(t)}`);
  };

  const products = dq.length >= 2 ? data?.products ?? [] : [];
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(products.length - 1, a + 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(-1, a - 1)); }
    else if (e.key === "Enter") {
      e.preventDefault();
      if (active >= 0 && products[active]) { setOpen(false); onDone?.(); nav(`/product/${products[active].slug}`); }
      else go(q);
    } else if (e.key === "Escape") setOpen(false);
  };

  return (
    <div ref={wrap} className={cn("relative", className)}>
      <form role="search" onSubmit={(e) => { e.preventDefault(); go(q); }}>
        <label htmlFor="site-search" className="sr-only">Search jewellery and apparel</label>
        <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-kajal-400" aria-hidden />
        <input id="site-search" value={q} autoFocus={autoFocus} autoComplete="off" onFocus={() => setOpen(true)}
          onChange={(e) => { setQ(e.target.value); setOpen(true); setActive(-1); }} onKeyDown={onKey}
          placeholder="Search jhumkas, sarees, SKU…" role="combobox" aria-expanded={open} aria-controls="search-panel" aria-autocomplete="list"
          className="h-11 w-full rounded-full border border-kajal-300/50 bg-white pl-11 pr-10 text-[15px] placeholder:text-kajal-400 focus:border-gold-500 focus:outline-none focus:ring-2 focus:ring-gold-100" />
        {q && <button type="button" aria-label="Clear search" onClick={() => setQ("")} className="absolute right-3 top-1/2 -translate-y-1/2 rounded-full p-1 text-kajal-400 hover:text-kajal"><X className="h-4 w-4" /></button>}
      </form>
      {open && (
        <div id="search-panel" className="absolute left-0 right-0 top-[calc(100%+8px)] z-50 overflow-hidden rounded-2xl border border-gold-200/60 bg-white shadow-lift">
          {dq.length < 2 ? (
            <div className="p-4">
              {recent.length > 0 && (
                <>
                  <p className="mb-2 text-sm text-kajal-500">Recent searches</p>
                  <div className="mb-4 flex flex-wrap gap-2">
                    {recent.map((r) => <button key={r} className="chip" onClick={() => go(r)}><Clock className="h-3.5 w-3.5 text-kajal-400" />{r}</button>)}
                  </div>
                </>
              )}
              <p className="mb-2 text-sm text-kajal-500">Popular right now</p>
              <div className="flex flex-wrap gap-2">{POPULAR.map((p) => <button key={p} className="chip" onClick={() => go(p)}>{p}</button>)}</div>
            </div>
          ) : (
            <div className="max-h-[70vh] overflow-y-auto">
              {products.length === 0 && !isFetching && (
                <p className="px-4 py-5 text-sm text-kajal-500">No matches for “{dq}”. Try a broader word like “earrings” or “kurti”.</p>
              )}
              {(data?.categories?.length ?? 0) > 0 && (
                <div className="flex flex-wrap gap-2 border-b border-gold-200/50 px-4 py-3">
                  {data!.categories.map((c) => <Link key={c.slug} to={`/category/${c.slug}`} onClick={() => { setOpen(false); onDone?.(); }} className="chip">in {c.name}</Link>)}
                </div>
              )}
              <ul role="listbox">
                {products.map((p, i) => (
                  <li key={p.slug} role="option" aria-selected={i === active}>
                    <Link to={`/product/${p.slug}`} onClick={() => { rememberSearch(dq); setOpen(false); onDone?.(); }}
                      className={cn("flex items-center gap-3 px-4 py-2.5 hover:bg-ivory", i === active && "bg-ivory")}>
                      <img src={p.image ?? ""} alt="" className="h-12 w-10 rounded-md bg-ivory-200 object-cover" loading="lazy" />
                      <span className="flex-1">
                        <span className="block text-[15px] text-kajal">{p.name}</span>
                        <span className="text-xs text-kajal-400">{p.sku}</span>
                      </span>
                      <span className="tabular text-sm text-kajal-700">{rupees(p.price)}</span>
                    </Link>
                  </li>
                ))}
              </ul>
              {products.length > 0 && (
                <button onClick={() => go(dq)} className="w-full border-t border-gold-200/50 px-4 py-3 text-left text-sm font-medium text-gold-700 hover:bg-ivory">
                  See all results for “{dq}”
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
