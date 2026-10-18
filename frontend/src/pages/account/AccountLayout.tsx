import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { Package, MapPin, Heart, Star, User, RotateCcw, LogOut } from "lucide-react";
import { useAuth } from "@/features/auth";
import { cn } from "@/utils/cn";

const LINKS = [
  { to: "orders", label: "Orders", icon: Package },
  { to: "returns", label: "Returns & refunds", icon: RotateCcw },
  { to: "wishlist", label: "Wishlist", icon: Heart },
  { to: "addresses", label: "Addresses", icon: MapPin },
  { to: "reviews", label: "My reviews", icon: Star },
  { to: "profile", label: "Profile & security", icon: User },
];

export default function AccountLayout() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  return (
    <div className="container-site py-10">
      <div className="mb-8">
        <p className="text-kajal-500">Namaste,</p>
        <h1 className="text-[36px] leading-tight">{user?.full_name}</h1>
      </div>
      <div className="grid gap-8 lg:grid-cols-[240px_1fr]">
        <nav aria-label="Account" className="-mx-4 flex gap-2 overflow-x-auto px-4 scrollbar-none lg:mx-0 lg:flex-col lg:gap-1 lg:px-0">
          {LINKS.map((l) => (
            <NavLink key={l.to} to={l.to} className={({ isActive }) => cn("flex shrink-0 items-center gap-3 rounded-full px-4 py-2.5 text-[15px] transition lg:rounded-xl",
              isActive ? "bg-kajal text-ivory" : "text-kajal-700 hover:bg-ivory-200")}>
              <l.icon className="h-4 w-4" />{l.label}
            </NavLink>
          ))}
          <button onClick={async () => { await logout(); nav("/"); }} className="flex shrink-0 items-center gap-3 rounded-full px-4 py-2.5 text-[15px] text-kajal-500 hover:bg-ivory-200 lg:mt-4 lg:rounded-xl">
            <LogOut className="h-4 w-4" />Log out
          </button>
        </nav>
        <div className="min-w-0"><Outlet /></div>
      </div>
    </div>
  );
}
