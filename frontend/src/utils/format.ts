const inr = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2, minimumFractionDigits: 0 });
const inr2 = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** Format a decimal string from the API. Whole rupees drop the paise ("₹499"); others keep 2 dp. */
export function rupees(v: string | number | null | undefined, opts: { exact?: boolean } = {}): string {
  if (v === null || v === undefined || v === "") return "—";
  const n = typeof v === "number" ? v : Number(v);
  if (!Number.isFinite(n)) return "—";
  if (opts.exact) return inr2.format(n);
  return Number.isInteger(Math.round(n * 100) / 100) && Math.round(n * 100) % 100 === 0 ? inr.format(n) : inr2.format(n);
}

export function isPositive(v: string | null | undefined) {
  return !!v && Number(v) > 0;
}

export function date(v: string | null | undefined, style: "short" | "long" | "day" = "short"): string {
  if (!v) return "—";
  const dt = new Date(v.length === 10 ? v + "T00:00:00" : v.endsWith("Z") || v.includes("+") ? v : v + "Z");
  if (style === "day") return dt.toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" });
  if (style === "long") return dt.toLocaleString("en-IN", { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" });
  return dt.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

export function plural(n: number, one: string, many = one + "s") {
  return `${n} ${n === 1 ? one : many}`;
}

export function titleCase(s: string) {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function uuid(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}
