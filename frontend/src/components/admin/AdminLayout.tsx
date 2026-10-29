import { useEffect, useState, type ComponentType } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import {
  BarChart3, Boxes, CreditCard, FolderTree, LayoutDashboard, LogOut, Menu, Package, PanelsTopLeft, RotateCcw, ScrollText,
  ShoppingBag, Sparkles, Store, TicketPercent, Truck, Users, X,
} from "lucide-react";
import { useAuth } from "@/features/auth";
import { cn } from "@/utils/cn";
import { ArchMark } from "@/components/layout/Logo";
import { ConfirmProvider } from "./kit";

export interface NavItem { to: string; label: string; icon: ComponentType<{ className?: string }>; perm: string; end?: boolean }

export const NAV_GROUPS: { label: string; items: NavItem[] }[] = [
  { label: "Overview", items: [
    { to: "/admin", label: "Dashboard", icon: LayoutDashboard, perm: "dashboard:view", end: true },
    { to: "/admin/reports", label: "Reports", icon: BarChart3, perm: "reports:view" },
  ] },
  { label: "Sales", items: [
    { to: "/admin/orders", label: "Orders", icon: ShoppingBag, perm: "orders:read" },
    { to: "/admin/returns", label: "Returns", icon: RotateCcw, perm: "returns:read" },
    { to: "/admin/customers", label: "Customers", icon: Users, perm: "customers:read" },
    { to: "/admin/coupons", label: "Coupons & offers", icon: TicketPercent, perm: "coupons:read" },
  ] },
  { label: "Catalogue", items: [
    { to: "/admin/products", label: "Products", icon: Package, perm: "products:read" },
    { to: "/admin/categories", label: "Categories", icon: FolderTree, perm: "products:read" },
    { to: "/admin/collections", label: "Collections", icon: Sparkles, perm: "products:read" },
    { to: "/admin/inventory", label: "Inventory", icon: Boxes, perm: "inventory:read" },
  ] },
  { label: "Store", items: [
    { to: "/admin/shipping", label: "Shipping", icon: Truck, perm: "shipping:read" },
    { to: "/admin/payments", label: "Payments", icon: CreditCard, perm: "settings:write" },
    { to: "/admin/content", label: "Content & settings", icon: PanelsTopLeft, perm: "content:write" },
    { to: "/admin/audit", label: "Audit log", icon: ScrollText, perm: "audit:read" },
  ] },
];

const TITLES: [RegExp, string][] = [
  [/^\/admin\/?$/, "Dashboard"], [/^\/admin\/products\/new/, "New product"], [/^\/admin\/products\/\d+/, "Edit product"],
  [/^\/admin\/products/, "Products"], [/^\/admin\/categories/, "Categories"], [/^\/admin\/collections/, "Collections"],
  [/^\/admin\/inventory/, "Inventory"], [/^\/admin\/orders\/\d+/, "Order"], [/^\/admin\/orders/, "Orders"],
  [/^\/admin\/customers\/\d+/, "Customer"], [/^\/admin\/customers/, "Customers"], [/^\/admin\/coupons/, "Coupons & offers"],
  [/^\/admin\/shipping/, "Shipping"], [/^\/admin\/returns/, "Returns"], [/^\/admin\/content/, "Content & settings"], [/^\/admin\/payments/, "Payments"],
  [/^\/admin\/reports/, "Reports"], [/^\/admin\/audit/, "Audit log"],
];

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const { can } = useAuth();
  return (
    <div className="flex h-full flex-col">
      <Link to="/admin" onClick={onNavigate} className="flex items-baseline gap-2 px-6 pb-6 pt-7">
          <ArchMark className="h-8 w-auto shrink-0" />
          <span className="font-display text-[24px] leading-none tracking-[0.1em] text-ivory">LoveVital</span>
        <span className="rounded-full border border-gold-200/40 px-2 py-0.5 text-2xs text-gold-200">Admin</span>
      </Link>
      <nav aria-label="Admin" className="flex-1 overflow-y-auto px-3 pb-6 scrollbar-none">
        {NAV_GROUPS.map((g) => {
          const items = g.items.filter((i) => can(i.perm));
          if (!items.length) return null;
          return (
            <div key={g.label} className="mb-5">
              <p className="px-3 pb-1.5 text-xs text-ivory/40">{g.label}</p>
              <ul className="space-y-0.5">
                {items.map((i) => (
                  <li key={i.to}>
                    <NavLink to={i.to} end={i.end} onClick={onNavigate}
                      className={({ isActive }) => cn(
                        "group relative flex items-center gap-3 rounded-lg px-3 py-2 text-[14.5px] transition-colors",
                        isActive ? "bg-white/[0.07] text-ivory" : "text-ivory/70 hover:bg-white/[0.04] hover:text-ivory",
                      )}>
                      {({ isActive }) => (
                        <>
                          <span className={cn("absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full transition-opacity", isActive ? "bg-gold-200 opacity-100" : "opacity-0")} aria-hidden />
                          <i.icon className={cn("h-[18px] w-[18px] shrink-0", isActive ? "text-gold-200" : "text-ivory/50 group-hover:text-ivory/80")} />
                          {i.label}
                        </>
                      )}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </nav>
      <div className="border-t border-white/10 px-6 py-4 text-xs text-ivory/40">Fine artificial jewellery & couture</div>
    </div>
  );
}

export default function AdminLayout() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();
  const title = TITLES.find(([re]) => re.test(pathname))?.[1] ?? "Admin";

  useEffect(() => { document.title = `${title} · LoveVital Admin`; }, [title]);
  useEffect(() => setOpen(false), [pathname]);
  useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [open]);

  const role = user?.roles.includes("admin") ? "Administrator" : "Staff";

  return (
    <ConfirmProvider>
      <div className="min-h-screen bg-ivory">
        <a href="#admin-main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[90] focus:rounded-lg focus:bg-white focus:px-3 focus:py-2">Skip to content</a>
        {/* desktop sidebar */}
        <aside className="fixed inset-y-0 left-0 z-30 hidden w-[248px] bg-kajal lg:block">
          <SidebarContent />
        </aside>
        {/* mobile drawer */}
        <div className={cn("fixed inset-0 z-[60] lg:hidden", open ? "pointer-events-auto" : "pointer-events-none")} aria-hidden={!open}>
          <div className={cn("absolute inset-0 bg-kajal/50 transition-opacity", open ? "opacity-100" : "opacity-0")} onClick={() => setOpen(false)} />
          <aside role="dialog" aria-modal="true" aria-label="Admin navigation"
            className={cn("absolute inset-y-0 left-0 w-[272px] max-w-[85vw] bg-kajal shadow-lift transition-transform duration-300", open ? "translate-x-0" : "-translate-x-full")}>
            <button aria-label="Close menu" onClick={() => setOpen(false)} className="absolute right-3 top-6 rounded-full p-1.5 text-ivory/70 hover:bg-white/10"><X className="h-5 w-5" /></button>
            {open && <SidebarContent onNavigate={() => setOpen(false)} />}
          </aside>
        </div>

        <div className="lg:pl-[248px]">
          <header className="sticky top-0 z-20 border-b border-gold-200/50 bg-ivory/90 backdrop-blur">
            <div className="flex h-14 items-center gap-3 px-4 sm:px-6 lg:px-8">
              <button className="-ml-1 rounded-lg p-2 text-kajal-700 hover:bg-ivory-200 lg:hidden" aria-label="Open menu" aria-expanded={open} onClick={() => setOpen(true)}>
                <Menu className="h-5 w-5" />
              </button>
              <p className="truncate text-[15px] font-medium text-kajal">{title}</p>
              <div className="ml-auto flex items-center gap-1 sm:gap-3">
                <Link to="/" className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1.5 text-sm text-kajal-700 hover:bg-ivory-200" title="View store">
                  <Store className="h-4 w-4" aria-hidden /><span className="hidden sm:inline">View store</span>
                </Link>
                <div className="hidden text-right leading-tight md:block">
                  <p className="text-sm text-kajal">{user?.full_name}</p>
                  <p className="text-xs text-kajal-500">{role} · {user?.email}</p>
                </div>
                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-gold-100 text-sm font-medium text-gold-800 md:hidden" aria-label={user?.full_name ?? "Account"}>
                  {(user?.full_name ?? "?").slice(0, 1)}
                </span>
                <button onClick={() => logout()} className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1.5 text-sm text-kajal-700 hover:bg-ivory-200">
                  <LogOut className="h-4 w-4" aria-hidden /><span className="hidden sm:inline">Log out</span>
                </button>
              </div>
            </div>
          </header>
          <main id="admin-main" className="mx-auto w-full max-w-[1400px] px-4 pb-16 pt-6 sm:px-6 lg:px-8">
            <Outlet />
          </main>
        </div>
      </div>
    </ConfirmProvider>
  );
}

