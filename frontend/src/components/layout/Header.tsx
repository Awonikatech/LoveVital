import { useEffect, useState } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Heart, Menu, Search, ShoppingBag, User, X, ChevronRight, LayoutDashboard } from "lucide-react";
import { Logo } from "./Logo";
import { SearchBox } from "./SearchBox";
import { storeApi } from "@/services/store";
import { useAuth } from "@/features/auth";
import { useCart, useCartUi } from "@/features/cart";
import { useWishlist } from "@/features/wishlist";
import { useSettings } from "@/features/settings";
import type { CategoryNode } from "@/types";
import { cn } from "@/utils/cn";
import { Drawer } from "@/components/ui";

interface MenuGroup { title: string; to: string; items: { name: string; to: string }[] }

function useMenus() {
  const cats = useQuery({ queryKey: ["categories"], queryFn: storeApi.categories, staleTime: 10 * 60_000 }).data ?? [];
  const cols = useQuery({ queryKey: ["collections"], queryFn: storeApi.collections, staleTime: 10 * 60_000 }).data ?? [];
  const by = (slug: string): CategoryNode | undefined => cats.find((c) => c.slug === slug);
  const group = (slug: string, title?: string): MenuGroup | null => {
    const c = by(slug);
    return c ? { title: title ?? c.name, to: `/category/${c.slug}`, items: c.children.map((ch) => ({ name: ch.name, to: `/category/${ch.slug}` })) } : null;
  };
  const bridal = by("festive-bridal");
  return {
    jewellery: [group("jewellery", "Shop by type"), group("silver-oxidised"),
      bridal ? { title: "Bridal", to: "/category/bridal-jewellery", items: [{ name: "Bridal jewellery", to: "/category/bridal-jewellery" }, { name: "Wedding Season", to: "/collections/wedding-season" }] } : null,
    ].filter(Boolean) as MenuGroup[],
    apparel: [group("ethnic-wear"), group("western-wear"),
      bridal ? { title: "Festive", to: "/category/festive-apparel", items: [{ name: "Festive apparel", to: "/category/festive-apparel" }, { name: "The Festive Edit", to: "/collections/festive-edit" }] } : null,
    ].filter(Boolean) as MenuGroup[],
    collections: cols,
  };
}

function Mega({ groups, image, imageLabel, to, onNavigate }: { groups: MenuGroup[]; image?: string; imageLabel?: string; to: string; onNavigate: () => void }) {
  return (
    <div className="container-site grid grid-cols-12 gap-8 py-8">
      <div className="col-span-9 grid grid-cols-3 gap-8">
        {groups.map((g) => (
          <div key={g.title}>
            <Link to={g.to} onClick={onNavigate} className="font-display text-lg text-kajal hover:text-gold-700">{g.title}</Link>
            <ul className="mt-3 space-y-2">
              {g.items.map((it) => (
                <li key={it.to}><Link to={it.to} onClick={onNavigate} className="text-[15px] text-kajal-500 hover:text-kajal">{it.name}</Link></li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      {image && (
        <Link to={to} onClick={onNavigate} className="col-span-3 flex items-end gap-4">
          <img src={image} alt="" className="arch h-48 w-36 object-cover" />
          <span className="pb-2 text-sm text-kajal-500">{imageLabel}<span className="mt-1 block text-kajal link-underline">Shop all</span></span>
        </Link>
      )}
    </div>
  );
}

export function Header() {
  const { user, isStaff } = useAuth();
  const { cart } = useCart();
  const { setOpen } = useCartUi();
  const { ids } = useWishlist();
  const settings = useSettings();
  const menus = useMenus();
  const [mega, setMega] = useState<string | null>(null);
  const [mobile, setMobile] = useState(false);
  const [mobileSearch, setMobileSearch] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const loc = useLocation();

  useEffect(() => {
    setMega(null);
    setMobile(false);
    setMobileSearch(false);
  }, [loc.pathname, loc.search]);
  useEffect(() => {
    const h = () => setScrolled(window.scrollY > 8);
    window.addEventListener("scroll", h, { passive: true });
    return () => window.removeEventListener("scroll", h);
  }, []);

  const nav = [
    { key: "jewellery", label: "Jewellery", to: "/jewellery" },
    { key: "apparel", label: "Apparel", to: "/apparel" },
    { key: "new", label: "New Arrivals", to: "/new-arrivals" },
    { key: "best", label: "Best Sellers", to: "/best-sellers" },
    { key: "collections", label: "Collections", to: "/collections" },
    { key: "sale", label: "Sale", to: "/sale" },
  ];
  const count = cart?.item_count ?? 0;

  return (
    <>
      {settings?.announcement_text && (
        <div className="bg-kajal px-4 py-2 text-center text-[13px] tracking-wide text-ivory/90">
          <p className="mx-auto max-w-site">{settings.announcement_text}</p>
        </div>
      )}
      <header className={cn("sticky top-0 z-40 border-b bg-ivory/95 backdrop-blur transition-shadow", scrolled ? "border-gold-200/60 shadow-[0_6px_24px_-18px_rgba(74,52,24,.5)]" : "border-transparent")}
        onMouseLeave={() => setMega(null)}>
        <div className="container-site flex h-[68px] items-center gap-4 lg:h-[76px]">
          <button className="-ml-2 rounded-full p-2 lg:hidden" aria-label="Open menu" onClick={() => setMobile(true)}><Menu className="h-6 w-6" /></button>
          <Logo className="shrink-0" />
          <SearchBox className="mx-auto hidden w-full max-w-md md:block" />
          <nav className="ml-auto flex items-center gap-0 sm:gap-1 md:ml-0" aria-label="Account and cart">
            <button className="rounded-full p-2.5 md:hidden" aria-label="Search" onClick={() => setMobileSearch((v) => !v)}><Search className="h-5 w-5" /></button>
            {isStaff && (
              <Link to="/admin" className="hidden items-center gap-1.5 rounded-full px-3 py-2 text-sm text-kajal-700 hover:bg-ivory-200 lg:inline-flex"><LayoutDashboard className="h-4 w-4" />Admin</Link>
            )}
            <Link to={user ? "/account" : "/login"} className="flex items-center gap-2 rounded-full p-2.5 hover:bg-ivory-200" aria-label={user ? "My account" : "Log in"}>
              <User className="h-5 w-5" />
              <span className="hidden text-sm xl:inline">{user ? user.full_name.split(" ")[0] : "Log in"}</span>
            </Link>
            <Link to="/account/wishlist" className="relative hidden rounded-full p-2.5 hover:bg-ivory-200 sm:block" aria-label={`Wishlist, ${ids.size} items`}>
              <Heart className="h-5 w-5" />
              {ids.size > 0 && <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-gold-500" aria-hidden />}
            </Link>
            <button onClick={() => setOpen(true)} className="relative rounded-full p-2.5 hover:bg-ivory-200" aria-label={`Cart, ${count} items`}>
              <ShoppingBag className="h-5 w-5" />
              {count > 0 && (
                <span className="absolute -right-0.5 -top-0.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-kajal px-1 text-[11px] font-medium tabular text-ivory">{count}</span>
              )}
            </button>
          </nav>
        </div>
        {mobileSearch && <div className="container-site pb-3 md:hidden"><SearchBox autoFocus onDone={() => setMobileSearch(false)} /></div>}
        <nav className="hidden border-t border-gold-200/40 lg:block" aria-label="Main">
          <ul className="container-site flex items-center justify-center gap-9">
            {nav.map((n) => (
              <li key={n.key} onMouseEnter={() => setMega(["jewellery", "apparel", "collections"].includes(n.key) ? n.key : null)}>
                <NavLink to={n.to}
                  className={({ isActive }) => cn("relative block py-3.5 text-[15px] tracking-wide transition-colors",
                    n.key === "sale" ? "text-kumkum" : "text-kajal-700 hover:text-kajal",
                    (isActive || mega === n.key) && "after:absolute after:inset-x-0 after:bottom-0 after:h-[2px] after:bg-gold-500")}>
                  {n.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        {mega && (
          <div className="absolute inset-x-0 top-full hidden border-b border-gold-200/60 bg-ivory-50 shadow-lift lg:block">
            {mega === "jewellery" && <Mega groups={menus.jewellery} image="/static/tiles/earrings.svg" imageLabel="Heritage jhumkas from ₹399" to="/jewellery" onNavigate={() => setMega(null)} />}
            {mega === "apparel" && <Mega groups={menus.apparel} image="/static/tiles/ethnic-wear.svg" imageLabel="Anarkalis, sarees and co-ords" to="/apparel" onNavigate={() => setMega(null)} />}
            {mega === "collections" && (
              <div className="container-site grid grid-cols-5 gap-6 py-8">
                {menus.collections.map((c) => (
                  <Link key={c.slug} to={`/collections/${c.slug}`} onClick={() => setMega(null)} className="group text-center">
                    <img src={c.image_url ?? ""} alt="" className="arch mx-auto h-40 w-32 object-cover transition-transform group-hover:-translate-y-1" />
                    <span className="mt-3 block font-display text-[17px]">{c.name}</span>
                  </Link>
                ))}
              </div>
            )}
          </div>
        )}
      </header>

      <Drawer open={mobile} onClose={() => setMobile(false)} title={<span className="font-display">Menu</span>} side="left">
        <MobileMenu menus={menus} onClose={() => setMobile(false)} isStaff={isStaff} loggedIn={!!user} />
      </Drawer>
    </>
  );
}

function MobileMenu({ menus, onClose, isStaff, loggedIn }: { menus: ReturnType<typeof useMenus>; onClose: () => void; isStaff: boolean; loggedIn: boolean }) {
  const [openKey, setOpenKey] = useState<string | null>("jewellery");
  const Section = ({ k, label, groups }: { k: string; label: string; groups: MenuGroup[] }) => (
    <div className="border-b border-gold-200/40">
      <button className="flex w-full items-center justify-between px-5 py-4 text-left font-display text-lg" aria-expanded={openKey === k} onClick={() => setOpenKey(openKey === k ? null : k)}>
        {label}<ChevronRight className={cn("h-5 w-5 text-kajal-400 transition-transform", openKey === k && "rotate-90")} />
      </button>
      {openKey === k && (
        <div className="space-y-4 px-5 pb-5">
          {groups.map((g) => (
            <div key={g.title}>
              <Link to={g.to} onClick={onClose} className="text-sm font-medium text-gold-700">{g.title}</Link>
              <div className="mt-2 flex flex-wrap gap-2">
                {g.items.map((it) => <Link key={it.to} to={it.to} onClick={onClose} className="chip">{it.name}</Link>)}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
  return (
    <div>
      <Section k="jewellery" label="Jewellery" groups={menus.jewellery} />
      <Section k="apparel" label="Apparel" groups={menus.apparel} />
      {[["New Arrivals", "/new-arrivals"], ["Best Sellers", "/best-sellers"], ["Collections", "/collections"], ["Sale", "/sale"], ["Track an order", "/track"]].map(([l, to]) => (
        <Link key={to} to={to} onClick={onClose} className={cn("block border-b border-gold-200/40 px-5 py-4 font-display text-lg", l === "Sale" && "text-kumkum")}>{l}</Link>
      ))}
      <div className="space-y-1 px-5 py-5 text-[15px]">
        <Link to={loggedIn ? "/account" : "/login"} onClick={onClose} className="block py-1.5">{loggedIn ? "My account" : "Log in or create account"}</Link>
        {isStaff && <Link to="/admin" onClick={onClose} className="block py-1.5">Admin panel</Link>}
        <Link to="/pages/contact" onClick={onClose} className="block py-1.5 text-kajal-500">Contact us</Link>
      </div>
      <button className="sr-only" onClick={onClose}><X /> Close</button>
    </div>
  );
}
