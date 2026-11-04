import { useState } from "react";
import { Link } from "react-router-dom";
import { Mail, Phone, MapPin, ShieldCheck, RotateCcw, Truck, BadgeCheck } from "lucide-react";

const Svg = ({ d, className }: { d: string; className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d={d} /></svg>
);
const Instagram = ({ className }: { className?: string }) => <Svg className={className} d="M7 3h10a4 4 0 0 1 4 4v10a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4V7a4 4 0 0 1 4-4zm5 5.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7zM17.5 6.5h.01" />;
const Facebook = ({ className }: { className?: string }) => <Svg className={className} d="M15 3h-2.5A3.5 3.5 0 0 0 9 6.5V9H6.5v3.5H9V21h3.5v-8.5H15l.5-3.5h-3V7a1 1 0 0 1 1-1H15z" />;
const Youtube = ({ className }: { className?: string }) => <Svg className={className} d="M21 8.2a3 3 0 0 0-2.1-2.1C17 5.6 12 5.6 12 5.6s-5 0-6.9.5A3 3 0 0 0 3 8.2 31 31 0 0 0 2.6 12 31 31 0 0 0 3 15.8a3 3 0 0 0 2.1 2.1c1.9.5 6.9.5 6.9.5s5 0 6.9-.5a3 3 0 0 0 2.1-2.1 31 31 0 0 0 .4-3.8 31 31 0 0 0-.4-3.8zM10 15V9l5.2 3z" />;
import { Logo } from "./Logo";
import { useSettings } from "@/features/settings";
import { storeApi } from "@/services/store";
import { errorMessage } from "@/services/api";
import { Button } from "@/components/ui";

export function Newsletter({ dark }: { dark?: boolean }) {
  const [email, setEmail] = useState("");
  const [state, setState] = useState<{ ok?: string; err?: string; loading?: boolean }>({});
  return (
    <form className={`flex w-full max-w-md flex-col gap-2 ${dark ? "" : "sm:flex-row"}`} onSubmit={async (e) => {
      e.preventDefault();
      setState({ loading: true });
      try {
        const r = await storeApi.subscribe(email);
        setState({ ok: r.message });
        setEmail("");
      } catch (err) {
        setState({ err: errorMessage(err) });
      }
    }}>
      <label htmlFor="nl-email" className="sr-only">Email address</label>
      <input id="nl-email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Your email address"
        className={dark ? "h-11 flex-1 rounded-full border border-ivory/20 bg-transparent px-5 text-ivory placeholder:text-ivory/50 focus:border-gold-200 focus:outline-none" : "input h-11 flex-1 rounded-full px-5"} />
      <Button type="submit" variant="primary" loading={state.loading}>Subscribe</Button>
      {(state.ok || state.err) && <p className={`basis-full text-sm ${state.err ? "text-kumkum-100" : dark ? "text-gold-200" : "text-leaf"}`} role="status">{state.ok || state.err}</p>}
    </form>
  );
}

export function Footer() {
  const s = useSettings();
  const social = s?.social_links ?? {};
  return (
    <footer className="mt-24 bg-kajal text-ivory/80">
      <div className="border-b border-ivory/10">
        <div className="container-site grid grid-cols-2 gap-6 py-8 text-sm md:grid-cols-4">
          {[
            [Truck, "Free shipping above ₹999", "Dispatched in 1–2 days"],
            [RotateCcw, "7-day easy returns", "Hassle-free pickups"],
            [ShieldCheck, "Secure payments", "UPI, cards, net banking & COD"],
            [BadgeCheck, "Skin-safe finishes", "Nickel & lead safe, anti-tarnish"],
          ].map(([I, t, sub]: any) => (
            <div key={t} className="flex items-start gap-3">
              <I className="mt-0.5 h-5 w-5 shrink-0 text-gold-200" aria-hidden />
              <div><p className="text-ivory">{t}</p><p className="text-ivory/60">{sub}</p></div>
            </div>
          ))}
        </div>
      </div>
      <div className="container-site grid gap-10 py-14 lg:grid-cols-12">
        <div className="lg:col-span-4">
          <Logo light />
          <p className="mt-4 max-w-sm leading-7 text-ivory/70">Discover stylish artificial jewellery and lifestyle essentials, thoughtfully selected to bring beauty, quality and everyday elegance to your life with LoveVital.</p>
          <div className="mt-6 flex gap-2">
            {social.instagram && <a href={social.instagram} target="_blank" rel="noopener noreferrer" aria-label="Instagram" className="rounded-full border border-ivory/20 p-2.5 hover:border-gold-200 hover:text-gold-200"><Instagram className="h-4 w-4" /></a>}
            {social.facebook && <a href={social.facebook} target="_blank" rel="noopener noreferrer" aria-label="Facebook" className="rounded-full border border-ivory/20 p-2.5 hover:border-gold-200 hover:text-gold-200"><Facebook className="h-4 w-4" /></a>}
            {social.youtube && <a href={social.youtube} target="_blank" rel="noopener noreferrer" aria-label="YouTube" className="rounded-full border border-ivory/20 p-2.5 hover:border-gold-200 hover:text-gold-200"><Youtube className="h-4 w-4" /></a>}
            {social.pinterest && <a href={social.pinterest} target="_blank" rel="noopener noreferrer" aria-label="Pinterest" className="rounded-full border border-ivory/20 p-2.5 text-sm hover:border-gold-200 hover:text-gold-200"><span className="block h-4 w-4 text-center font-display leading-4">P</span></a>}
          </div>
        </div>
        <div className="grid grid-cols-2 gap-8 sm:grid-cols-3 lg:col-span-5">
          <div>
            <h3 className="font-display text-lg text-ivory">Shop</h3>
            <ul className="mt-4 space-y-2.5 text-[15px]">
              {[["Jewellery", "/jewellery"], ["Apparel", "/apparel"], ["New arrivals", "/new-arrivals"], ["Best sellers", "/best-sellers"], ["Collections", "/collections"], ["Sale", "/sale"]].map(([l, h]) => (
                <li key={h}><Link to={h} className="hover:text-gold-200">{l}</Link></li>
              ))}
            </ul>
          </div>
          <div>
            <h3 className="font-display text-lg text-ivory">Help</h3>
            <ul className="mt-4 space-y-2.5 text-[15px]">
              <li><Link to="/track" className="hover:text-gold-200">Track your order</Link></li>
              <li><Link to="/account/orders" className="hover:text-gold-200">Returns & cancellations</Link></li>
              {(s?.footer_links ?? []).slice(0, 4).map((l) => <li key={l.href}><Link to={l.href} className="hover:text-gold-200">{l.label}</Link></li>)}
            </ul>
          </div>
          <div className="col-span-2 sm:col-span-1">
            <h3 className="font-display text-lg text-ivory">Contact</h3>
            <ul className="mt-4 space-y-3 text-[15px]">
              {s?.support_email && <li className="flex gap-2"><Mail className="mt-1 h-4 w-4 shrink-0 text-gold-200" /><a href={`mailto:${s.support_email}`} className="hover:text-gold-200 break-all">{s.support_email}</a></li>}
              {s?.support_phone && <li className="flex gap-2"><Phone className="mt-1 h-4 w-4 shrink-0 text-gold-200" /><span>{s.support_phone}<br /><span className="text-sm text-ivory/55">{s.support_hours}</span></span></li>}
              {s?.store_address && <li className="flex gap-2"><MapPin className="mt-1 h-4 w-4 shrink-0 text-gold-200" /><span className="text-sm leading-6">{s.store_address}</span></li>}
            </ul>
          </div>
        </div>
        <div className="lg:col-span-3">
          <h3 className="font-display text-lg text-ivory">First look at new drops</h3>
          <p className="mt-2 text-[15px] text-ivory/65">Festive previews and members-only offers, twice a month.</p>
          <div className="mt-4"><Newsletter dark /></div>
        </div>
      </div>
      <div className="border-t border-ivory/10">
        <div className="container-site flex flex-col gap-3 py-6 text-sm text-ivory/50 sm:flex-row sm:items-center sm:justify-between">
          <p>© {new Date().getFullYear()} LoveVital. Demo storefront — prices include GST.</p>
          <div className="flex flex-wrap gap-x-5 gap-y-1">
            {(s?.footer_links ?? []).slice(3).map((l) => <Link key={l.href} to={l.href} className="hover:text-gold-200">{l.label}</Link>)}
            <Link to="/pages/terms" className="hover:text-gold-200">Terms</Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
