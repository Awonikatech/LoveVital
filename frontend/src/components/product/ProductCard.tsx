import { Link } from "react-router-dom";
import { Heart, Plus } from "lucide-react";
import type { ProductCard as P } from "@/types";
import { Price, Skeleton, Stars } from "@/components/ui";
import { useWishlist } from "@/features/wishlist";
import { useCart } from "@/features/cart";
import { cn } from "@/utils/cn";

export function ProductCard({ p, priority }: { p: P; priority?: boolean }) {
  const { ids, toggle } = useWishlist();
  const { add } = useCart();
  const saved = ids.has(p.id);
  const quickAdd = p.variant_count === 1 && p.in_stock && p.default_variant_id;
  const badge = !p.in_stock ? null : p.badges[0] ?? (p.is_new_arrival ? "New" : p.is_bestseller ? "Bestseller" : null);

  return (
    <article className="group relative flex flex-col">
      <div className="relative overflow-hidden rounded-2xl bg-ivory-200">
        <Link to={`/product/${p.slug}`} aria-label={p.name} className="block aspect-[4/5]">
          <img src={p.image ?? ""} alt={p.name} loading={priority ? "eager" : "lazy"} className={cn("absolute inset-0 h-full w-full object-cover transition-opacity duration-500", p.hover_image && "group-hover:opacity-0")} />
          {p.hover_image && <img src={p.hover_image} alt="" loading="lazy" className="absolute inset-0 h-full w-full object-cover opacity-0 transition-opacity duration-500 group-hover:opacity-100" />}
        </Link>
        {badge && (
          <span className={cn("absolute left-3 top-3 rounded-full px-2.5 py-1 text-[11px] font-medium tracking-wide",
            p.badges[0] ? "bg-kajal text-gold-200" : "bg-white/90 text-kajal-700")}>{badge}</span>
        )}
        {!p.in_stock && <span className="absolute left-3 top-3 rounded-full bg-white/90 px-2.5 py-1 text-[11px] font-medium text-kajal-500">Sold out</span>}
        <button onClick={() => toggle(p.id)} aria-pressed={saved} aria-label={saved ? `Remove ${p.name} from wishlist` : `Save ${p.name} to wishlist`}
          className="absolute right-3 top-3 rounded-full bg-white/90 p-2 text-kajal-700 shadow-sm transition hover:text-kumkum">
          <Heart className={cn("h-4 w-4", saved && "fill-kumkum text-kumkum")} />
        </button>
        {quickAdd ? (
          <button onClick={() => add.mutate({ variantId: p.default_variant_id!, qty: 1 })} disabled={add.isPending}
            className="absolute inset-x-3 bottom-3 flex h-10 translate-y-2 items-center justify-center gap-1.5 rounded-full bg-kajal/95 text-sm text-ivory opacity-0 transition-all focus:translate-y-0 focus:opacity-100 group-hover:translate-y-0 group-hover:opacity-100 max-lg:hidden">
            <Plus className="h-4 w-4" /> Add to bag
          </button>
        ) : p.in_stock ? (
          <Link to={`/product/${p.slug}`} tabIndex={-1}
            className="absolute inset-x-3 bottom-3 flex h-10 translate-y-2 items-center justify-center rounded-full bg-white/95 text-sm text-kajal opacity-0 transition-all group-hover:translate-y-0 group-hover:opacity-100 max-lg:hidden">
            Choose {p.product_type === "apparel" ? "size & colour" : "finish"}
          </Link>
        ) : null}
      </div>
      <div className="mt-3 flex flex-1 flex-col px-0.5">
        <div className="flex items-center justify-between gap-2 text-xs text-kajal-400">
          <span className="truncate">{p.category.name}</span>
          {p.rating_count > 0 && (
            <span className="flex shrink-0 items-center gap-1"><Stars value={p.rating_avg} size={11} /><span className="tabular">({p.rating_count})</span></span>
          )}
        </div>
        <h3 className="mt-1 line-clamp-2 text-[15px] leading-snug text-kajal">
          <Link to={`/product/${p.slug}`} className="hover:text-gold-700">{p.name}</Link>
        </h3>
        <Price price={p.price} mrp={p.mrp} discount={p.discount_pct} size="sm" className="mt-1.5" />
        <div className="mt-1.5 flex items-center gap-2 text-xs">
          {p.colors.length > 1 && (
            <span className="flex items-center gap-1" aria-label={`${p.colors.length} colours`}>
              {p.colors.slice(0, 4).map((c) => <span key={c.slug} title={c.value} className="h-3 w-3 rounded-full border border-kajal/15" style={{ background: c.hex ?? "#ddd" }} />)}
              {p.colors.length > 4 && <span className="text-kajal-400">+{p.colors.length - 4}</span>}
            </span>
          )}
          {p.stock_status === "low_stock" && <span className="text-[#8A5A00]">Only a few left</span>}
          <span className="ml-auto text-kajal-300">{p.sku}</span>
        </div>
      </div>
    </article>
  );
}

export function ProductCardSkeleton() {
  return (
    <div>
      <Skeleton className="aspect-[4/5] w-full rounded-2xl" />
      <Skeleton className="mt-3 h-3 w-1/3" />
      <Skeleton className="mt-2 h-4 w-4/5" />
      <Skeleton className="mt-2 h-4 w-1/2" />
    </div>
  );
}

export function ProductGrid({ products, loading, count = 8, cols = "lg:grid-cols-4" }: { products?: P[]; loading?: boolean; count?: number; cols?: string }) {
  return (
    <div className={cn("grid grid-cols-2 gap-x-4 gap-y-9 sm:gap-x-6 md:grid-cols-3", cols)}>
      {loading ? Array.from({ length: count }).map((_, i) => <ProductCardSkeleton key={i} />) : products?.map((p, i) => <ProductCard key={p.id} p={p} priority={i < 4} />)}
    </div>
  );
}

export function ProductRail({ products, loading }: { products?: P[]; loading?: boolean }) {
  return (
    <div className="-mx-4 flex snap-x snap-mandatory gap-4 overflow-x-auto px-4 pb-2 scrollbar-none sm:-mx-6 sm:gap-6 sm:px-6 lg:mx-0 lg:grid lg:grid-cols-4 lg:overflow-visible lg:px-0">
      {(loading ? Array.from({ length: 4 }) : products ?? []).map((p: any, i) => (
        <div key={p?.id ?? i} className="w-[46%] shrink-0 snap-start sm:w-[31%] lg:w-auto">
          {loading ? <ProductCardSkeleton /> : <ProductCard p={p} />}
        </div>
      ))}
    </div>
  );
}
