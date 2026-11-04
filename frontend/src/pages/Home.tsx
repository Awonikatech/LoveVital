import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Quote } from "lucide-react";
import { storeApi } from "@/services/store";
import { ButtonLink, ErrorState, SectionHeading, Skeleton, Stars } from "@/components/ui";
import { ProductRail, ProductGrid } from "@/components/product/ProductCard";
import { Newsletter } from "@/components/layout/Footer";
import { useSeo } from "@/hooks/useSeo";
import type { Banner } from "@/types";
import { cn } from "@/utils/cn";

function Hero({ banners }: { banners: Banner[] }) {
  const [i, setI] = useState(0);
  const [paused, setPaused] = useState(false);
  const n = banners.length;
  useEffect(() => {
    if (n < 2 || paused || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const t = setInterval(() => setI((x) => (x + 1) % n), 6500);
    return () => clearInterval(t);
  }, [n, paused]);
  if (!n) return null;
  const b = banners[i];
  return (
    <section className="relative overflow-hidden bg-gradient-to-b from-ivory-200 via-ivory to-ivory" aria-roledescription="carousel" aria-label="Featured"
      onMouseEnter={() => setPaused(true)} onMouseLeave={() => setPaused(false)}>
      <svg aria-hidden className="pointer-events-none absolute -left-40 top-1/2 h-[900px] w-[900px] -translate-y-1/2 text-gold-300/25" viewBox="0 0 200 200">
        {Array.from({ length: 24 }).map((_, k) => <ellipse key={k} cx="100" cy="40" rx="9" ry="34" fill="none" stroke="currentColor" strokeWidth=".4" transform={`rotate(${k * 15} 100 100)`} />)}
        <circle cx="100" cy="100" r="96" fill="none" stroke="currentColor" strokeWidth=".4" /><circle cx="100" cy="100" r="62" fill="none" stroke="currentColor" strokeWidth=".4" />
      </svg>
      <div className="container-site relative grid items-center gap-10 py-10 md:grid-cols-[1fr_auto] md:py-16 lg:gap-20">
        <div key={b.id} className="hero-reveal order-2 max-w-xl md:order-1">
          {b.eyebrow && <p className="text-[15px] text-gold-700">{b.eyebrow}</p>}
          <h1 className="mt-3 text-[44px] leading-[1.04] sm:text-[60px] lg:text-[76px]">{b.title}</h1>
          {b.subtitle && <p className="mt-5 max-w-md text-lg leading-8 text-kajal-700">{b.subtitle}</p>}
          {b.cta_link && (
            <div className="mt-8 flex flex-wrap items-center gap-5">
              <ButtonLink to={b.cta_link} size="lg">{b.cta_text ?? "Shop now"}</ButtonLink>
              <Link to="/new-arrivals" className="link-underline text-[15px]">See what's new</Link>
            </div>
          )}
          {n > 1 && (
            <div className="mt-12 flex items-center gap-3">
              <button onClick={() => setI((i - 1 + n) % n)} className="rounded-full border border-gold-300 p-2 text-gold-700 hover:bg-gold-50" aria-label="Previous slide"><ChevronLeft className="h-4 w-4" /></button>
              <div className="flex gap-2">
                {banners.map((bn, k) => (
                  <button key={bn.id} onClick={() => setI(k)} aria-label={`Show slide ${k + 1}: ${bn.title}`} aria-current={k === i}
                    className={cn("h-1.5 rounded-full transition-all", k === i ? "w-10 bg-gold-500" : "w-4 bg-gold-200")} />
                ))}
              </div>
              <button onClick={() => setI((i + 1) % n)} className="rounded-full border border-gold-300 p-2 text-gold-700 hover:bg-gold-50" aria-label="Next slide"><ChevronRight className="h-4 w-4" /></button>
            </div>
          )}
        </div>
        <div className="order-1 mx-auto md:order-2">
          <div className="rounded-[999px_999px_28px_28px] bg-gradient-to-b from-gold-200 via-gold-500 to-gold-700 p-[3px] shadow-lift">
            <div className="arch arch-frame relative h-[400px] w-[300px] bg-ivory-200 sm:h-[480px] sm:w-[360px] lg:h-[560px] lg:w-[420px]">
              {banners.map((bn, k) => (
                <img key={bn.id} src={bn.image_url} alt="" aria-hidden className={cn("absolute inset-0 h-full w-full object-cover transition-opacity duration-1000", k === i ? "opacity-100" : "opacity-0")}
                  style={{ objectPosition: "85% 50%" }} />
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

export default function Home() {
  useSeo({ title: "LoveVital — Fine Artificial Jewellery & Couture", description: "Handcrafted kundan, temple and oxidised jewellery with festive and everyday apparel. Free shipping above ₹999." });
  const { data, isLoading, isError, refetch } = useQuery({ queryKey: ["home"], queryFn: storeApi.home, staleTime: 60_000 });

  if (isError) return <div className="container-site py-24"><ErrorState message="We couldn't load the store right now." onRetry={() => refetch()} /></div>;

  const hero = data?.banners.filter((b) => b.placement === "hero") ?? [];
  const promo = data?.banners.filter((b) => b.placement === "promo") ?? [];
  const tiles = data ? data.categories.flatMap((c) => (c.slug === "jewellery" ? c.children.slice(0, 5) : c.slug === "ethnic-wear" ? c.children.slice(0, 3) : [])).concat(
    data.categories.filter((c) => ["western-wear", "silver-oxidised"].includes(c.slug))) : [];
  const testimonials = data?.settings.testimonials ?? [];

  return (
    <>
      {isLoading ? <Skeleton className="h-[640px] w-full rounded-none" /> : <Hero banners={hero} />}

      <section className="container-site pt-16 sm:pt-20" aria-labelledby="cats">
        <SectionHeading title={<span id="cats">Shop by category</span>} sub="From temple jhumkas to Banarasi weaves — find your next heirloom." />
        <div className="-mx-4 flex snap-x gap-5 overflow-x-auto px-4 pb-3 scrollbar-none sm:-mx-6 sm:px-6 lg:mx-0 lg:grid lg:grid-cols-10 lg:gap-6 lg:px-0">
          {(isLoading ? Array.from({ length: 10 }) : tiles).map((c: any, k) => (
            <Link key={c?.slug ?? k} to={c ? `/category/${c.slug}` : "#"} className="group w-[104px] shrink-0 snap-start text-center lg:w-auto">
              {c ? (
                <img src={c.image_url} alt="" className="arch mx-auto aspect-[3/4] w-full bg-ivory-200 object-cover ring-1 ring-gold-200/60 transition-transform duration-300 group-hover:-translate-y-1" />
              ) : <Skeleton className="arch aspect-[3/4] w-full" />}
              <span className="mt-3 block text-sm leading-tight text-kajal-700 group-hover:text-kajal">{c?.name}</span>
            </Link>
          ))}
        </div>
      </section>

      <section className="container-site pt-16 sm:pt-24">
        <SectionHeading title="Trending this week" sub="The pieces everyone's adding to their festive looks." action={<Link to="/shop?sort=popularity" className="link-underline hidden text-[15px] sm:inline">View all</Link>} />
        <ProductRail products={data?.trending} loading={isLoading} />
      </section>

      {promo.length > 0 && (
        <section className="container-site grid gap-5 pt-16 sm:pt-24 md:grid-cols-2">
          {promo.map((b) => (
            <Link key={b.id} to={b.cta_link ?? "/"} className="group relative block overflow-hidden rounded-3xl bg-ivory-200">
              <img src={b.image_url} alt="" className="h-72 w-full object-cover object-left transition-transform duration-700 group-hover:scale-[1.02] sm:h-80" />
              <div className="absolute inset-y-0 right-0 flex w-[55%] flex-col justify-center pr-6 sm:pr-10">
                {b.eyebrow && <p className="text-sm text-gold-700">{b.eyebrow}</p>}
                <h3 className="mt-1 text-2xl leading-tight sm:text-[32px]">{b.title}</h3>
                <p className="mt-2 hidden text-[15px] text-kajal-700 sm:block">{b.subtitle}</p>
                <span className="mt-4 text-[15px] link-underline">{b.cta_text}</span>
              </div>
            </Link>
          ))}
        </section>
      )}

      <section className="container-site pt-16 sm:pt-24">
        <SectionHeading title="Best sellers" sub="Loved, reviewed and reordered." action={<Link to="/best-sellers" className="link-underline hidden text-[15px] sm:inline">Shop best sellers</Link>} />
        <ProductGrid products={data?.best_sellers} loading={isLoading} />
      </section>

      {(data?.collections.length ?? 0) > 0 && (
        <section className="mt-16 bg-blush-50 py-16 sm:mt-24 sm:py-24">
          <div className="container-site">
            <SectionHeading title="Seasonal collections" sub="Curated edits for festivals, weddings and every day." action={<Link to="/collections" className="link-underline hidden text-[15px] sm:inline">All collections</Link>} />
            <div className="grid grid-cols-2 gap-5 lg:grid-cols-4 lg:gap-8">
              {data!.collections.map((c) => (
                <Link key={c.slug} to={`/collections/${c.slug}`} className="group">
                  <div className="arch arch-frame bg-ivory-200"><img src={c.image_url ?? ""} alt="" className="aspect-[3/4] w-full object-cover transition-transform duration-700 group-hover:scale-[1.03]" /></div>
                  <h3 className="mt-4 text-xl sm:text-2xl">{c.name}</h3>
                  <p className="mt-1 line-clamp-2 text-sm leading-6 text-kajal-500">{c.description}</p>
                </Link>
              ))}
            </div>
          </div>
        </section>
      )}

      {(data?.promotions.length ?? 0) > 0 && (
        <section className="container-site pt-16 sm:pt-24" aria-labelledby="offers">
          <div className="grid gap-px overflow-hidden rounded-3xl border border-gold-200/60 bg-gold-200/60 sm:grid-cols-2 lg:grid-cols-4">
            <div className="bg-kajal p-7 text-ivory">
              <h2 id="offers" className="text-[28px] text-ivory">Festival offers</h2>
              <p className="mt-2 text-ivory/70">Applied automatically at checkout. Use code <strong className="font-medium text-gold-200">FESTIVE10</strong> for an extra 10% on ₹1,499+.</p>
            </div>
            {data!.promotions.slice(0, 3).map((p) => (
              <div key={p.name} className="bg-ivory-50 p-7">
                {p.badge && <p className="text-sm font-medium text-kumkum">{p.badge}</p>}
                <h3 className="mt-1 text-xl">{p.name}</h3>
                <p className="mt-2 text-[15px] leading-6 text-kajal-500">{p.description}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="container-site pt-16 sm:pt-24">
        <SectionHeading title="New arrivals" sub="Fresh from our artisans this month." action={<Link to="/new-arrivals" className="link-underline hidden text-[15px] sm:inline">See everything new</Link>} />
        <ProductRail products={data?.new_arrivals} loading={isLoading} />
      </section>

      {(data?.on_sale.length ?? 0) > 0 && (
        <section className="container-site pt-16 sm:pt-24">
          <SectionHeading title="Up to 50% off" sub="Signature pieces at their best prices." action={<Link to="/sale" className="link-underline hidden text-[15px] sm:inline">Shop the sale</Link>} />
          <ProductRail products={data?.on_sale} />
        </section>
      )}

      {testimonials.length > 0 && (
        <section className="container-site pt-16 sm:pt-24" aria-labelledby="love">
          <SectionHeading title={<span id="love">Worn and loved</span>} sub="Notes from customers after the celebrations." />
          <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-4">
            {testimonials.map((t) => (
              <figure key={t.name} className="flex flex-col rounded-3xl border border-gold-200/60 bg-white p-6">
                <Quote className="h-6 w-6 text-gold-300" aria-hidden />
                <blockquote className="mt-3 flex-1 text-[15px] leading-7 text-kajal-700">{t.text}</blockquote>
                <figcaption className="mt-5 flex items-center justify-between border-t border-gold-200/50 pt-4 text-sm">
                  <span><span className="text-kajal">{t.name}</span><span className="text-kajal-400"> — {t.city}</span></span>
                  <Stars value={t.rating} size={12} />
                </figcaption>
              </figure>
            ))}
          </div>
        </section>
      )}

      <section className="container-site pt-16 sm:pt-24">
        <div className="flex flex-col items-start justify-between gap-6 rounded-3xl border border-gold-200/60 bg-gradient-to-br from-gold-50 to-blush-50 p-8 sm:p-12 lg:flex-row lg:items-center">
          <div className="max-w-lg">
            <h2 className="text-[30px] leading-tight sm:text-[38px]">Get 15% off your first order</h2>
            <p className="mt-2 text-kajal-700">Join the list for new drops and members-only offers. Your welcome code arrives instantly.</p>
          </div>
          <Newsletter />
        </div>
      </section>
    </>
  );
}
