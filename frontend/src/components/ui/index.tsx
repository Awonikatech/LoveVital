import {
  forwardRef, useEffect, useId, useRef, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode,
  type SelectHTMLAttributes, type TextareaHTMLAttributes,
} from "react";
import { createPortal } from "react-dom";
import { Link } from "react-router-dom";
import { ChevronLeft, ChevronRight, Loader2, Minus, Plus, Star, X } from "lucide-react";
import { cn } from "@/utils/cn";
import { rupees } from "@/utils/format";

/* ------------------------------------------------------------------ Button */
type Variant = "primary" | "gold" | "outline" | "ghost" | "danger" | "link";
type Size = "sm" | "md" | "lg";
export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  block?: boolean;
}
const variants: Record<Variant, string> = {
  primary: "bg-gradient-to-b from-gold-500 to-gold-700 text-white shadow-[inset_0_1px_0_rgba(255,255,255,.25)] hover:from-gold-600 hover:to-gold-800 disabled:from-gold-200 disabled:to-gold-300",
  gold: "bg-kajal text-gold-200 hover:bg-kajal-700 disabled:bg-kajal-400",
  outline: "border border-kajal/80 text-kajal hover:bg-kajal hover:text-ivory disabled:border-kajal-300 disabled:text-kajal-400 disabled:hover:bg-transparent",
  ghost: "text-kajal-700 hover:bg-ivory-200",
  danger: "bg-kumkum text-white hover:bg-kumkum-600",
  link: "text-kajal underline decoration-gold-300 underline-offset-4 hover:decoration-gold-600 px-0",
};
const sizes: Record<Size, string> = { sm: "h-9 px-3.5 text-sm", md: "h-11 px-5 text-[15px]", lg: "h-[52px] px-7 text-base" };

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", loading, block, className, children, disabled, type = "button", ...rest }, ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(
        "inline-flex select-none items-center justify-center gap-2 rounded-full font-medium tracking-wide transition-colors disabled:cursor-not-allowed",
        variants[variant], variant !== "link" && sizes[size], block && "w-full", className,
      )}
      {...rest}
    >
      {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
      {children}
    </button>
  );
});

export function ButtonLink({ to, variant = "primary", size = "md", className, children }: { to: string; variant?: Variant; size?: Size; className?: string; children: ReactNode }) {
  return (
    <Link to={to} className={cn("inline-flex items-center justify-center gap-2 rounded-full font-medium tracking-wide transition-colors", variants[variant], variant !== "link" && sizes[size], className)}>
      {children}
    </Link>
  );
}

/* ------------------------------------------------------------------ Form fields */
interface FieldWrap { label?: ReactNode; error?: string; hint?: ReactNode; className?: string; required?: boolean }

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement> & FieldWrap>(function Input(
  { label, error, hint, className, id, required, ...rest }, ref,
) {
  const auto = useId();
  const fid = id ?? auto;
  return (
    <div className={className}>
      {label && <label htmlFor={fid} className="label">{label}{required && <span className="text-kumkum"> *</span>}</label>}
      <input ref={ref} id={fid} aria-invalid={!!error || undefined} aria-describedby={error ? `${fid}-err` : undefined}
        className={cn("input", error && "border-kumkum focus:border-kumkum focus:ring-kumkum-100")} required={required} {...rest} />
      {error ? <p id={`${fid}-err`} className="field-error">{error}</p> : hint ? <p className="mt-1 text-sm text-kajal-500">{hint}</p> : null}
    </div>
  );
});

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement> & FieldWrap>(function Textarea(
  { label, error, hint, className, id, ...rest }, ref,
) {
  const auto = useId();
  const fid = id ?? auto;
  return (
    <div className={className}>
      {label && <label htmlFor={fid} className="label">{label}</label>}
      <textarea ref={ref} id={fid} aria-invalid={!!error || undefined} className={cn("input min-h-[96px]", error && "border-kumkum")} {...rest} />
      {error ? <p className="field-error">{error}</p> : hint ? <p className="mt-1 text-sm text-kajal-500">{hint}</p> : null}
    </div>
  );
});

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement> & FieldWrap & { options?: { value: string | number; label: string }[] }>(
  function Select({ label, error, hint, className, id, options, children, ...rest }, ref) {
    const auto = useId();
    const fid = id ?? auto;
    return (
      <div className={className}>
        {label && <label htmlFor={fid} className="label">{label}</label>}
        <select ref={ref} id={fid} aria-invalid={!!error || undefined} className={cn("input appearance-none bg-[length:16px] bg-[right_12px_center] bg-no-repeat pr-9", error && "border-kumkum")}
          style={{ backgroundImage: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%236B5A5E' stroke-width='2'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E\")" }} {...rest}>
          {options ? options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>) : children}
        </select>
        {error ? <p className="field-error">{error}</p> : hint ? <p className="mt-1 text-sm text-kajal-500">{hint}</p> : null}
      </div>
    );
  },
);

export const Checkbox = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement> & { label: ReactNode }>(function Checkbox(
  { label, className, ...rest }, ref,
) {
  return (
    <label className={cn("inline-flex cursor-pointer items-start gap-2.5 text-[15px] text-kajal-700", className)}>
      <input ref={ref} type="checkbox" className="mt-0.5 h-4 w-4 shrink-0 rounded border-kajal-300 accent-[#2A1A1F]" {...rest} />
      <span>{label}</span>
    </label>
  );
});

/* ------------------------------------------------------------------ Price */
export function Price({ price, mrp, discount, size = "md", className }: { price: string; mrp?: string; discount?: number; size?: "sm" | "md" | "lg"; className?: string }) {
  const showMrp = mrp && Number(mrp) > Number(price);
  return (
    <div className={cn("flex flex-wrap items-baseline gap-x-2 gap-y-0.5 tabular", className)}>
      <span className={cn("font-medium text-kajal", size === "lg" ? "text-[28px] leading-none" : size === "md" ? "text-lg" : "text-[15px]")}>{rupees(price)}</span>
      {showMrp && (
        <>
          <span className={cn("text-kajal-400 line-through", size === "lg" ? "text-lg" : "text-sm")}>
            <span className="sr-only">MRP </span>{rupees(mrp)}
          </span>
          {!!discount && <span className={cn("font-medium text-kumkum", size === "lg" ? "text-lg" : "text-sm")}>{discount}% off</span>}
        </>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ Rating */
export function Stars({ value, size = 14, className }: { value: number; size?: number; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-0.5", className)} aria-label={`${value.toFixed(1)} out of 5 stars`} role="img">
      {[1, 2, 3, 4, 5].map((i) => (
        <Star key={i} width={size} height={size} className={i <= Math.round(value) ? "fill-gold-500 text-gold-500" : "fill-transparent text-gold-200"} aria-hidden />
      ))}
    </span>
  );
}

/* ------------------------------------------------------------------ Badge */
export function Badge({ children, tone = "neutral", className }: { children: ReactNode; tone?: "neutral" | "gold" | "sale" | "success" | "warning" | "dark" | "info"; className?: string }) {
  const tones = {
    neutral: "bg-ivory-200 text-kajal-700",
    gold: "bg-gold-100 text-gold-800",
    sale: "bg-kumkum text-white",
    success: "bg-leaf-50 text-leaf",
    warning: "bg-[#FCF1DD] text-[#8A5A00]",
    dark: "bg-kajal text-ivory",
    info: "bg-[#E8EEF8] text-[#2F4CA0]",
  };
  return <span className={cn("inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium", tones[tone], className)}>{children}</span>;
}

const STATUS_TONE: Record<string, Parameters<typeof Badge>[0]["tone"]> = {
  order_placed: "info", payment_pending: "warning", payment_confirmed: "info", processing: "info", packed: "info", shipped: "gold",
  out_for_delivery: "gold", delivered: "success", cancellation_requested: "warning", cancelled: "neutral", return_requested: "warning",
  returned: "neutral", refund_initiated: "warning", refunded: "neutral", delivery_failed: "sale",
  paid: "success", pending: "warning", failed: "sale", partially_refunded: "warning", captured: "success", processed: "success",
  requested: "warning", approved: "info", rejected: "neutral", received: "info", completed: "success", active: "success", draft: "neutral", archived: "neutral",
};
export function StatusBadge({ status, label }: { status: string; label?: string }) {
  return <Badge tone={STATUS_TONE[status] ?? "neutral"}>{label ?? status.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase())}</Badge>;
}

/* ------------------------------------------------------------------ Spinner / skeleton / states */
export function Spinner({ className, label = "Loading" }: { className?: string; label?: string }) {
  return (
    <span role="status" className={cn("inline-flex items-center gap-2 text-kajal-500", className)}>
      <Loader2 className="h-5 w-5 animate-spin text-gold-500" aria-hidden />
      <span className="sr-only">{label}</span>
    </span>
  );
}
export function PageSpinner() {
  return <div className="flex min-h-[40vh] items-center justify-center"><Spinner /></div>;
}
export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton", className)} aria-hidden />;
}

/** Empty states sit inside the brand's arch to stay recognisable. */
export function EmptyState({ title, body, action, icon }: { title: string; body?: ReactNode; action?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center px-4 py-14 text-center">
      <div className="arch arch-frame mb-6 flex h-36 w-28 items-end justify-center bg-gradient-to-b from-gold-50 to-blush pb-7 text-gold-600">
        {icon}
      </div>
      <h2 className="text-2xl">{title}</h2>
      {body && <div className="mt-2 text-kajal-500">{body}</div>}
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="mx-auto max-w-md rounded-2xl border border-kumkum-100 bg-kumkum-50 px-5 py-6 text-center" role="alert">
      <p className="text-kumkum-600">{message}</p>
      {onRetry && <Button variant="outline" size="sm" className="mt-4" onClick={onRetry}>Try again</Button>}
    </div>
  );
}

export function Alert({ tone = "info", children, className }: { tone?: "info" | "error" | "success" | "warning"; children: ReactNode; className?: string }) {
  const t = {
    info: "border-gold-200 bg-gold-50 text-kajal-700",
    error: "border-kumkum-100 bg-kumkum-50 text-kumkum-600",
    success: "border-leaf/20 bg-leaf-50 text-leaf",
    warning: "border-[#F0D9A8] bg-[#FCF5E6] text-[#7A4F00]",
  };
  return <div role={tone === "error" ? "alert" : undefined} className={cn("rounded-xl border px-4 py-3 text-sm leading-6", t[tone], className)}>{children}</div>;
}

/* ------------------------------------------------------------------ Quantity */
export function QuantityStepper({ value, min = 1, max = 10, onChange, disabled, size = "md" }: { value: number; min?: number; max?: number; onChange: (v: number) => void; disabled?: boolean; size?: "sm" | "md" }) {
  const h = size === "sm" ? "h-8 w-8" : "h-11 w-11";
  return (
    <div className="inline-flex items-center rounded-full border border-kajal-300/70 bg-white">
      <button type="button" className={cn("flex items-center justify-center rounded-full text-kajal-700 disabled:text-kajal-300", h)}
        onClick={() => onChange(Math.max(min, value - 1))} disabled={disabled || value <= min} aria-label="Decrease quantity"><Minus className="h-4 w-4" /></button>
      <span className={cn("min-w-[2ch] text-center tabular font-medium", size === "sm" ? "text-sm" : "")} aria-live="polite">{value}</span>
      <button type="button" className={cn("flex items-center justify-center rounded-full text-kajal-700 disabled:text-kajal-300", h)}
        onClick={() => onChange(Math.min(max, value + 1))} disabled={disabled || value >= max} aria-label="Increase quantity"><Plus className="h-4 w-4" /></button>
    </div>
  );
}

/* ------------------------------------------------------------------ Modal & drawer */
function useLockScroll(open: boolean) {
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);
}

function useEscape(open: boolean, onClose: () => void) {
  useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [open, onClose]);
}

export function Modal({ open, onClose, title, children, footer, size = "md" }: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode; footer?: ReactNode; size?: "sm" | "md" | "lg" | "xl" }) {
  useLockScroll(open);
  useEscape(open, onClose);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (open) ref.current?.querySelector<HTMLElement>("input,select,textarea,button:not([aria-label='Close'])")?.focus();
  }, [open]);
  if (!open) return null;
  const w = { sm: "max-w-md", md: "max-w-lg", lg: "max-w-2xl", xl: "max-w-4xl" }[size];
  return createPortal(
    <div className="fixed inset-0 z-[80] flex items-end justify-center bg-kajal/50 p-0 sm:items-center sm:p-4" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div ref={ref} role="dialog" aria-modal="true" aria-label={typeof title === "string" ? title : undefined}
        className={cn("flex max-h-[92vh] w-full flex-col rounded-t-3xl bg-ivory-50 shadow-lift sm:rounded-3xl", w)}>
        <div className="flex items-center justify-between gap-4 border-b border-gold-200/50 px-5 py-4 sm:px-6">
          <h2 className="text-xl">{title}</h2>
          <button aria-label="Close" onClick={onClose} className="rounded-full p-1.5 text-kajal-500 hover:bg-ivory-200"><X className="h-5 w-5" /></button>
        </div>
        <div className="flex-1 overflow-y-auto px-5 py-5 sm:px-6">{children}</div>
        {footer && <div className="flex flex-wrap justify-end gap-2 border-t border-gold-200/50 px-5 py-4 sm:px-6">{footer}</div>}
      </div>
    </div>,
    document.body,
  );
}

export function Drawer({ open, onClose, title, children, footer, side = "right" }: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode; footer?: ReactNode; side?: "right" | "left" }) {
  useLockScroll(open);
  useEscape(open, onClose);
  return createPortal(
    <div className={cn("fixed inset-0 z-[70]", open ? "pointer-events-auto" : "pointer-events-none")} aria-hidden={!open}>
      <div className={cn("absolute inset-0 bg-kajal/40 transition-opacity duration-300", open ? "opacity-100" : "opacity-0")} onClick={onClose} />
      <aside role="dialog" aria-modal="true" aria-label={typeof title === "string" ? title : undefined}
        className={cn("absolute top-0 flex h-full w-full max-w-md flex-col bg-ivory-50 shadow-lift transition-transform duration-300",
          side === "right" ? "right-0" : "left-0", open ? "translate-x-0" : side === "right" ? "translate-x-full" : "-translate-x-full")}>
        <div className="flex items-center justify-between border-b border-gold-200/50 px-5 py-4">
          <div className="text-xl font-display">{title}</div>
          <button aria-label="Close" onClick={onClose} className="rounded-full p-1.5 text-kajal-500 hover:bg-ivory-200"><X className="h-5 w-5" /></button>
        </div>
        <div className="flex-1 overflow-y-auto">{open && children}</div>
        {footer && open && <div className="border-t border-gold-200/50 px-5 py-4">{footer}</div>}
      </aside>
    </div>,
    document.body,
  );
}

/* ------------------------------------------------------------------ Pagination */
export function Pagination({ page, pages, onChange }: { page: number; pages: number; onChange: (p: number) => void }) {
  if (pages <= 1) return null;
  const nums: (number | "…")[] = [];
  for (let i = 1; i <= pages; i++) {
    if (i === 1 || i === pages || Math.abs(i - page) <= 1) nums.push(i);
    else if (nums[nums.length - 1] !== "…") nums.push("…");
  }
  const btn = "flex h-10 min-w-10 items-center justify-center rounded-full px-3 text-sm tabular";
  return (
    <nav aria-label="Pagination" className="flex items-center justify-center gap-1">
      <button className={cn(btn, "text-kajal-700 hover:bg-ivory-200 disabled:text-kajal-300")} disabled={page <= 1} onClick={() => onChange(page - 1)} aria-label="Previous page"><ChevronLeft className="h-4 w-4" /></button>
      {nums.map((n, i) => n === "…" ? <span key={`e${i}`} className="px-1 text-kajal-400">…</span> : (
        <button key={n} className={cn(btn, n === page ? "bg-kajal text-ivory" : "text-kajal-700 hover:bg-ivory-200")} aria-current={n === page ? "page" : undefined} onClick={() => onChange(n)}>{n}</button>
      ))}
      <button className={cn(btn, "text-kajal-700 hover:bg-ivory-200 disabled:text-kajal-300")} disabled={page >= pages} onClick={() => onChange(page + 1)} aria-label="Next page"><ChevronRight className="h-4 w-4" /></button>
    </nav>
  );
}

/* ------------------------------------------------------------------ Tabs */
export function Tabs<T extends string>({ tabs, value, onChange, className }: { tabs: { value: T; label: ReactNode }[]; value: T; onChange: (v: T) => void; className?: string }) {
  return (
    <div role="tablist" className={cn("flex gap-6 overflow-x-auto border-b border-gold-200/60 scrollbar-none", className)}>
      {tabs.map((t) => (
        <button key={t.value} role="tab" aria-selected={t.value === value} onClick={() => onChange(t.value)}
          className={cn("-mb-px whitespace-nowrap border-b-2 pb-3 pt-1 text-[15px] transition-colors", t.value === value ? "border-gold-500 text-kajal" : "border-transparent text-kajal-500 hover:text-kajal")}>
          {t.label}
        </button>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ Breadcrumbs */
export function Breadcrumbs({ items }: { items: { label: string; to?: string }[] }) {
  return (
    <nav aria-label="Breadcrumb" className="text-sm text-kajal-500">
      <ol className="flex flex-wrap items-center gap-1.5">
        {items.map((it, i) => (
          <li key={i} className="flex items-center gap-1.5">
            {i > 0 && <span aria-hidden className="text-gold-300">/</span>}
            {it.to ? <Link to={it.to} className="hover:text-kajal">{it.label}</Link> : <span aria-current="page" className="text-kajal-700">{it.label}</span>}
          </li>
        ))}
      </ol>
    </nav>
  );
}

export function SectionHeading({ title, sub, action, className }: { title: ReactNode; sub?: ReactNode; action?: ReactNode; className?: string }) {
  return (
    <div className={cn("mb-6 flex items-end justify-between gap-4 sm:mb-8", className)}>
      <div>
        <h2 className="text-[26px] leading-tight sm:text-[34px]">{title}</h2>
        {sub && <p className="mt-1.5 max-w-xl text-kajal-500">{sub}</p>}
      </div>
      {action}
    </div>
  );
}

export function Money({ value, className, negative }: { value: string | null | undefined; className?: string; negative?: boolean }) {
  return <span className={cn("tabular", className)}>{negative && Number(value) > 0 ? "−" : ""}{rupees(value)}</span>;
}
