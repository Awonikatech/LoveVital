import { createContext, forwardRef, useCallback, useContext, useEffect, useRef, useState, type InputHTMLAttributes, type ReactNode, type ThHTMLAttributes, type TdHTMLAttributes } from "react";
import type { UseQueryResult } from "@tanstack/react-query";
import { ChevronDown, ChevronUp, Info, Lock, Search, X } from "lucide-react";
import { Button, ErrorState, Input, Modal, Skeleton, Textarea } from "@/components/ui";
import { errorMessage } from "@/services/api";
import { isForbidden } from "@/services/admin";
import { cn } from "@/utils/cn";
import { useDebounce } from "@/hooks/useDebounce";

/* ------------------------------------------------------------------ page chrome */
export function PageHeader({ title, sub, actions, back }: { title: ReactNode; sub?: ReactNode; actions?: ReactNode; back?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        {back && <div className="mb-2">{back}</div>}
        <h1 className="text-[28px] leading-tight sm:text-[32px]">{title}</h1>
        {sub && <p className="mt-1 text-[15px] text-kajal-500">{sub}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Panel({ title, action, children, className, bodyClass, id }: { title?: ReactNode; action?: ReactNode; children: ReactNode; className?: string; bodyClass?: string; id?: string }) {
  return (
    <section id={id} className={cn("card", className)}>
      {(title || action) && (
        <header className="flex items-center justify-between gap-3 border-b border-gold-200/50 px-5 py-3.5">
          {title && <h2 className="font-sans text-[15px] font-medium text-kajal">{title}</h2>}
          {action}
        </header>
      )}
      <div className={cn("p-5", bodyClass)}>{children}</div>
    </section>
  );
}

/* ------------------------------------------------------------------ access / query states */
export function NoAccess({ what }: { what?: string }) {
  return (
    <div className="card mx-auto mt-6 flex max-w-lg flex-col items-center px-6 py-12 text-center">
      <span className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-gold-50 text-gold-600"><Lock className="h-5 w-5" aria-hidden /></span>
      <h2 className="text-2xl">You don't have access to this</h2>
      <p className="mt-2 text-kajal-500">
        {what ?? "This area"} needs a permission your account doesn't have. Ask a store administrator if you need it.
      </p>
    </div>
  );
}

/** Renders loading / 403 / error for a query, otherwise calls children with data. */
export function QueryState<T>({ q, children, skeleton, what }: { q: UseQueryResult<T>; children: (d: T) => ReactNode; skeleton?: ReactNode; what?: string }) {
  if (q.isPending) return <>{skeleton ?? <BlockSkeleton />}</>;
  if (q.isError) {
    if (isForbidden(q.error)) return <NoAccess what={what} />;
    return <div className="py-8"><ErrorState message={errorMessage(q.error)} onRetry={() => q.refetch()} /></div>;
  }
  return <>{children(q.data as T)}</>;
}

export function BlockSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <div className="card space-y-3 p-5" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }).map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}
    </div>
  );
}

/* ------------------------------------------------------------------ table primitives */
export function Table({ children, className, minWidth = 720 }: { children: ReactNode; className?: string; minWidth?: number }) {
  return (
    <div className={cn("card overflow-hidden", className)}>
      <div className="max-h-[calc(100vh-9rem)] overflow-auto">
        <table className="w-full border-collapse text-[14px]" style={{ minWidth }}>{children}</table>
      </div>
    </div>
  );
}
export function Th({ className, align, ...rest }: ThHTMLAttributes<HTMLTableCellElement> & { align?: "left" | "right" | "center" }) {
  return (
    <th scope="col" {...rest}
      className={cn("sticky top-0 z-[1] whitespace-nowrap border-b border-gold-200/70 bg-ivory-50 px-4 py-2.5 text-[13px] font-medium text-kajal-500",
        align === "right" ? "text-right" : align === "center" ? "text-center" : "text-left", className)} />
  );
}
export function Td({ className, align, ...rest }: TdHTMLAttributes<HTMLTableCellElement> & { align?: "left" | "right" | "center" }) {
  return <td {...rest} className={cn("border-b border-gold-200/30 px-4 py-2.5 align-middle text-kajal-700", align === "right" ? "text-right tabular" : align === "center" ? "text-center" : "", className)} />;
}
export function Tr({ children, className, onClick }: { children: ReactNode; className?: string; onClick?: () => void }) {
  return <tr onClick={onClick} className={cn("transition-colors hover:bg-gold-50/50", onClick && "cursor-pointer", className)}>{children}</tr>;
}
export function TableSkeleton({ cols, rows = 8 }: { cols: number; rows?: number }) {
  return (
    <>
      {Array.from({ length: rows }).map((_, r) => (
        <tr key={r}>{Array.from({ length: cols }).map((__, c) => <Td key={c}><Skeleton className="h-4 w-full max-w-[160px]" /></Td>)}</tr>
      ))}
    </>
  );
}
export function EmptyRow({ cols, children }: { cols: number; children: ReactNode }) {
  return <tr><td colSpan={cols} className="px-4 py-14 text-center text-kajal-500">{children}</td></tr>;
}

export function SortTh({ label, field, sort, onSort, align }: { label: string; field: string; sort: string; onSort: (s: string) => void; align?: "left" | "right" }) {
  const active = sort === field;
  return (
    <Th align={align} aria-sort={active ? "descending" : "none"}>
      <button type="button" className={cn("inline-flex items-center gap-1 hover:text-kajal", active && "text-kajal")} onClick={() => onSort(field)}>
        {label}{active ? <ChevronDown className="h-3.5 w-3.5" aria-hidden /> : <ChevronUp className="h-3.5 w-3.5 opacity-30" aria-hidden />}
      </button>
    </Th>
  );
}

export function TableFooter({ total, page, pages, onPage, noun = "result" }: { total?: number; page: number; pages: number; onPage: (p: number) => void; noun?: string }) {
  return (
    <div className="mt-4 flex flex-col items-center justify-between gap-3 sm:flex-row">
      <p className="text-sm text-kajal-500 tabular">{total !== undefined ? `${total.toLocaleString("en-IN")} ${total === 1 ? noun : noun + "s"}` : ""}</p>
      {pages > 1 && <PaginationLite page={page} pages={pages} onChange={onPage} />}
    </div>
  );
}
function PaginationLite({ page, pages, onChange }: { page: number; pages: number; onChange: (p: number) => void }) {
  return (
    <nav aria-label="Pagination" className="flex items-center gap-2 text-sm">
      <Button variant="ghost" size="sm" disabled={page <= 1} onClick={() => onChange(page - 1)}>Previous</Button>
      <span className="tabular text-kajal-500">Page {page} of {pages}</span>
      <Button variant="ghost" size="sm" disabled={page >= pages} onClick={() => onChange(page + 1)}>Next</Button>
    </nav>
  );
}

/* ------------------------------------------------------------------ filters */
export function SearchBox({ value, onChange, placeholder, className, label = "Search" }: { value: string; onChange: (v: string) => void; placeholder?: string; className?: string; label?: string }) {
  const [v, setV] = useState(value);
  const d = useDebounce(v, 300);
  const first = useRef(true);
  useEffect(() => {
    if (first.current) { first.current = false; return; }
    if (d !== value) onChange(d);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [d]);
  useEffect(() => setV(value), [value]);
  return (
    <div className={cn("relative", className)}>
      <label className="sr-only" htmlFor={`search-${label}`}>{label}</label>
      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-kajal-400" aria-hidden />
      <input id={`search-${label}`} type="search" value={v} onChange={(e) => setV(e.target.value)} placeholder={placeholder}
        className="input h-10 py-0 pl-9 pr-8 text-[14px]" />
      {v && (
        <button type="button" aria-label="Clear search" className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded p-0.5 text-kajal-400 hover:text-kajal" onClick={() => { setV(""); onChange(""); }}>
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}

export function FilterSelect({ label, value, onChange, options, className }: { label: string; value: string; onChange: (v: string) => void; options: { value: string; label: string }[]; className?: string }) {
  return (
    <label className={cn("block", className)}>
      <span className="sr-only">{label}</span>
      <select aria-label={label} value={value} onChange={(e) => onChange(e.target.value)}
        className="input h-10 appearance-none bg-[length:14px] bg-[right_10px_center] bg-no-repeat py-0 pr-8 text-[14px]"
        style={{ backgroundImage: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%236B5A5E' stroke-width='2'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E\")" }}>
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </label>
  );
}

export function FilterBar({ children }: { children: ReactNode }) {
  return <div className="mb-4 flex flex-wrap items-center gap-2 [&>*]:min-w-0">{children}</div>;
}

export function Chip({ active, onClick, children, count }: { active?: boolean; onClick: () => void; children: ReactNode; count?: number }) {
  return (
    <button type="button" aria-pressed={!!active} onClick={onClick} className={cn("chip whitespace-nowrap", active && "chip-active")}>
      {children}
      {count !== undefined && <span className={cn("tabular text-xs", active ? "text-gold-200" : "text-kajal-400")}>{count}</span>}
    </button>
  );
}

/* ------------------------------------------------------------------ toggles */
export function Switch({ checked, onChange, label, disabled, hideLabel }: { checked: boolean; onChange: (v: boolean) => void; label: string; disabled?: boolean; hideLabel?: boolean }) {
  return (
    <label className={cn("inline-flex cursor-pointer select-none items-center gap-2.5 text-[14px] text-kajal-700", disabled && "cursor-not-allowed opacity-60")}>
      <button type="button" role="switch" aria-checked={checked} aria-label={hideLabel ? label : undefined} disabled={disabled} onClick={() => onChange(!checked)}
        className={cn("relative h-5 w-9 shrink-0 rounded-full transition-colors", checked ? "bg-gold-500" : "bg-kajal-300/70")}>
        <span className={cn("absolute left-0 top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform", checked ? "translate-x-[18px]" : "translate-x-0.5")} />
      </button>
      {!hideLabel && <span>{label}</span>}
    </label>
  );
}

/* ------------------------------------------------------------------ confirm */
type ConfirmOpts = { title: string; body?: ReactNode; confirmLabel: string; danger?: boolean; reason?: { label: string; required?: boolean; minLength?: number; placeholder?: string } };
type ConfirmFn = (o: ConfirmOpts) => Promise<{ ok: boolean; reason: string }>;
const ConfirmCtx = createContext<ConfirmFn>(async () => ({ ok: false, reason: "" }));

export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<(ConfirmOpts & { resolve: (r: { ok: boolean; reason: string }) => void }) | null>(null);
  const [reason, setReason] = useState("");
  const confirm = useCallback<ConfirmFn>((o) => new Promise((resolve) => { setReason(""); setState({ ...o, resolve }); }), []);
  const close = (ok: boolean) => { state?.resolve({ ok, reason: reason.trim() }); setState(null); };
  const min = state?.reason?.minLength ?? (state?.reason?.required ? 1 : 0);
  const invalid = !!state?.reason && reason.trim().length < min;
  return (
    <ConfirmCtx.Provider value={confirm}>
      {children}
      <Modal open={!!state} onClose={() => close(false)} title={state?.title ?? ""} size="sm"
        footer={<>
          <Button variant="ghost" size="sm" onClick={() => close(false)}>Keep as is</Button>
          <Button variant={state?.danger ? "danger" : "primary"} size="sm" disabled={invalid} onClick={() => close(true)}>{state?.confirmLabel}</Button>
        </>}>
        {state?.body && <div className="text-[15px] leading-6 text-kajal-700">{state.body}</div>}
        {state?.reason && (
          <Textarea className="mt-4" label={state.reason.label + (state.reason.required ? " (required)" : "")} value={reason}
            placeholder={state.reason.placeholder} onChange={(e) => setReason(e.target.value)} rows={3}
            hint={min > 1 ? `At least ${min} characters.` : undefined} />
        )}
      </Modal>
    </ConfirmCtx.Provider>
  );
}
export const useConfirm = () => useContext(ConfirmCtx);

/* ------------------------------------------------------------------ misc */
export function Disclosure({ summary, children, className, defaultOpen }: { summary: ReactNode; children: ReactNode; className?: string; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(!!defaultOpen);
  return (
    <div className={className}>
      <button type="button" aria-expanded={open} onClick={() => setOpen(!open)} className="inline-flex items-center gap-1.5 text-sm text-kajal-500 hover:text-kajal">
        <Info className="h-4 w-4 text-gold-600" aria-hidden />{summary}
        <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-180")} aria-hidden />
      </button>
      {open && <div className="mt-3">{children}</div>}
    </div>
  );
}

export function KeyVal({ k, v, className }: { k: ReactNode; v: ReactNode; className?: string }) {
  return (
    <div className={cn("flex items-baseline justify-between gap-4 py-1.5 text-[14px]", className)}>
      <dt className="text-kajal-500">{k}</dt>
      <dd className="text-right text-kajal">{v}</dd>
    </div>
  );
}

export function Thumb({ src, alt = "", size = 40 }: { src: string | null | undefined; alt?: string; size?: number }) {
  return src ? (
    <img src={src} alt={alt} width={size} height={size} loading="lazy" className="shrink-0 rounded-md border border-gold-200/50 bg-ivory-200 object-cover" style={{ width: size, height: size }} />
  ) : (
    <span className="block shrink-0 rounded-md border border-gold-200/50 bg-ivory-200" style={{ width: size, height: size }} aria-hidden />
  );
}

export function FieldGrid({ children, cols = 2, className }: { children: ReactNode; cols?: 2 | 3 | 4; className?: string }) {
  const c = { 2: "sm:grid-cols-2", 3: "sm:grid-cols-2 lg:grid-cols-3", 4: "sm:grid-cols-2 lg:grid-cols-4" }[cols];
  return <div className={cn("grid grid-cols-1 gap-4", c, className)}>{children}</div>;
}

/** Plain inline input for dense editors (variants table etc.). */
export const MiniInput = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement> & { label: string }>(function MiniInput({ label, className, ...rest }, ref) {
  return <input ref={ref} aria-label={label} className={cn("input h-9 px-2.5 py-0 text-[14px]", className)} {...rest} />;
});

export function ReadOnlyNote({ children }: { children: ReactNode }) {
  return (
    <p className="mb-4 inline-flex items-center gap-2 rounded-full bg-ivory-200 px-3 py-1 text-sm text-kajal-500">
      <Lock className="h-3.5 w-3.5" aria-hidden />{children}
    </p>
  );
}

export { Input };
