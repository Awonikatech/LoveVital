import { useEffect, useState, type ReactNode } from "react";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { rupees } from "@/utils/format";
import { daysAgo, isoDay } from "@/services/admin";
import { cn } from "@/utils/cn";
import { Disclosure } from "./kit";

/* Chart palette: one hue (gold) for magnitude; series identity is never colour-alone. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type TipArgs = { active?: boolean; payload?: readonly any[] };

export const CHART = { gold: "#B8862B", goldLight: "#E9C979", grid: "#EFE4CF", axis: "#8C7D80", ink: "#2A1A1F" };

export const compactRupees = (n: number) =>
  n >= 1e7 ? `₹${(n / 1e7).toFixed(1)}Cr` : n >= 1e5 ? `₹${(n / 1e5).toFixed(1)}L` : n >= 1e3 ? `₹${(n / 1e3).toFixed(n >= 1e4 ? 0 : 1)}k` : `₹${Math.round(n)}`;

export function shortDay(iso: string) {
  if (/^\d{4}-\d{2}$/.test(iso)) return new Date(iso + "-01T00:00:00").toLocaleDateString("en-IN", { month: "short", year: "numeric" });
  if (!/^\d{4}-\d{2}-\d{2}$/.test(iso)) return iso;
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

function TipBox({ title, rows }: { title: ReactNode; rows: { label: string; value: string }[] }) {
  return (
    <div className="rounded-lg border border-gold-200/70 bg-white px-3 py-2 text-[13px] shadow-lift">
      <p className="mb-1 font-medium text-kajal">{title}</p>
      {rows.map((r) => (
        <p key={r.label} className="flex justify-between gap-4 text-kajal-500"><span>{r.label}</span><span className="tabular text-kajal">{r.value}</span></p>
      ))}
    </div>
  );
}

export function TrendChart({ data, metric, money, height = 260 }: { data: Record<string, any>[]; metric: string; money: boolean; height?: number }) {
  const rows = data.map((d) => ({ ...d, _v: Number(d[metric] ?? 0) }));
  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="goldFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={CHART.gold} stopOpacity={0.22} />
              <stop offset="100%" stopColor={CHART.gold} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={CHART.grid} vertical={false} />
          <XAxis dataKey="period" tickFormatter={shortDay} tick={{ fill: CHART.axis, fontSize: 12 }} axisLine={false} tickLine={false} minTickGap={24} />
          <YAxis tickFormatter={(v) => (money ? compactRupees(v) : String(v))} tick={{ fill: CHART.axis, fontSize: 12 }} axisLine={false} tickLine={false} width={52} allowDecimals={false} />
          <Tooltip cursor={{ stroke: CHART.goldLight, strokeWidth: 1 }}
            content={({ active, payload }: TipArgs) => active && payload?.length ? (
              <TipBox title={shortDay(String(payload[0].payload.period))} rows={[
                { label: "Orders", value: String(payload[0].payload.orders) },
                ...(payload[0].payload.net_sales !== undefined ? [{ label: "Net sales", value: rupees(payload[0].payload.net_sales) }] : []),
                ...(payload[0].payload.revenue !== undefined ? [{ label: "Revenue", value: rupees(payload[0].payload.revenue) }] : []),
              ]} />
            ) : null} />
          <Area type="monotone" dataKey="_v" name={metric} stroke={CHART.gold} strokeWidth={2} fill="url(#goldFill)" dot={false}
            activeDot={{ r: 4, fill: CHART.gold, stroke: "#fff", strokeWidth: 2 }} isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Horizontal bars — labels on the left so long category names stay readable on mobile. */
export function HBarChart({ data, labelKey, valueKey, money, height }: { data: Record<string, any>[]; labelKey: string; valueKey: string; money: boolean; height?: number }) {
  const rows = data.map((d) => ({ label: String(d[labelKey]), v: Number(d[valueKey] ?? 0), raw: d }));
  const h = height ?? Math.max(120, rows.length * 34 + 16);
  return (
    <div style={{ height: h }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} layout="vertical" margin={{ top: 0, right: 12, left: 0, bottom: 0 }} barCategoryGap={8}>
          <CartesianGrid stroke={CHART.grid} horizontal={false} />
          <XAxis type="number" tickFormatter={(v) => (money ? compactRupees(v) : String(v))} tick={{ fill: CHART.axis, fontSize: 12 }} axisLine={false} tickLine={false} allowDecimals={false} />
          <YAxis type="category" dataKey="label" width={120} tick={{ fill: CHART.ink, fontSize: 12 }} axisLine={false} tickLine={false}
            tickFormatter={(s: string) => (s.length > 18 ? s.slice(0, 17) + "…" : s)} />
          <Tooltip cursor={{ fill: "rgba(233,201,121,0.15)" }}
            content={({ active, payload }: TipArgs) => active && payload?.length ? (
              <TipBox title={payload[0].payload.label} rows={Object.entries(payload[0].payload.raw)
                .filter(([k]) => k !== labelKey && typeof payload[0].payload.raw[k] !== "object")
                .map(([k, v]) => ({ label: k.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase()), value: /sales|amount|value|discount|revenue|margin/.test(k) ? rupees(v as string) : String(v) }))} />
            ) : null} />
          <Bar dataKey="v" fill={CHART.gold} radius={[0, 4, 4, 0]} maxBarSize={22} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function VBarChart({ data, labelKey, valueKey, money, height = 240 }: { data: Record<string, any>[]; labelKey: string; valueKey: string; money: boolean; height?: number }) {
  const rows = data.map((d) => ({ label: String(d[labelKey]), v: Number(d[valueKey] ?? 0), raw: d }));
  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }} barCategoryGap="20%">
          <CartesianGrid stroke={CHART.grid} vertical={false} />
          <XAxis dataKey="label" tickFormatter={shortDay} tick={{ fill: CHART.axis, fontSize: 12 }} axisLine={false} tickLine={false} minTickGap={16} />
          <YAxis tickFormatter={(v) => (money ? compactRupees(v) : String(v))} tick={{ fill: CHART.axis, fontSize: 12 }} axisLine={false} tickLine={false} width={52} allowDecimals={false} />
          <Tooltip cursor={{ fill: "rgba(233,201,121,0.15)" }}
            content={({ active, payload }: TipArgs) => active && payload?.length ? (
              <TipBox title={shortDay(payload[0].payload.label)} rows={Object.entries(payload[0].payload.raw)
                .filter(([k]) => k !== labelKey)
                .map(([k, v]) => ({ label: k.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase()), value: /sales|amount|value|revenue/.test(k) ? rupees(v as string) : String(v) }))} />
            ) : null} />
          <Bar dataKey="v" fill={CHART.gold} radius={[4, 4, 0, 0]} maxBarSize={36} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Proportion bars (used for payment mix) — a labelled list beats a multi-colour donut. */
export function ShareList({ rows }: { rows: { label: string; value: number; display: string; sub?: string }[] }) {
  const total = rows.reduce((a, r) => a + r.value, 0) || 1;
  return (
    <ul className="space-y-3">
      {rows.map((r) => {
        const pct = (r.value / total) * 100;
        return (
          <li key={r.label}>
            <div className="mb-1 flex items-baseline justify-between gap-3 text-[14px]">
              <span className="text-kajal">{r.label}</span>
              <span className="tabular text-kajal-500"><span className="text-kajal">{r.display}</span> · {pct.toFixed(0)}%{r.sub ? ` · ${r.sub}` : ""}</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-ivory-200" role="presentation">
              <div className="h-full rounded-full bg-gold-500" style={{ width: `${Math.max(pct, 1.5)}%` }} />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

/* ------------------------------------------------------------------ date range */
export type Range = { start: string; end: string };
const PRESETS = [7, 30, 90] as const;
export function presetRange(days: number): Range { return { start: daysAgo(days - 1), end: isoDay(new Date()) }; }

export function DateRangeFilter({ value, onChange, presets = PRESETS as unknown as number[] }: { value: Range; onChange: (r: Range) => void; presets?: number[] }) {
  const active = presets.find((d) => value.start === daysAgo(d - 1) && value.end === isoDay(new Date()));
  const [custom, setCustom] = useState(!active);
  const [draft, setDraft] = useState(value);
  useEffect(() => setDraft(value), [value]);
  const invalid = !draft.start || !draft.end || draft.start > draft.end;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <div role="group" aria-label="Date range" className="inline-flex rounded-full border border-kajal-300/50 bg-white p-0.5">
        {presets.map((d) => (
          <button key={d} type="button" aria-pressed={active === d && !custom} onClick={() => { setCustom(false); onChange(presetRange(d)); }}
            className={cn("rounded-full px-3 py-1.5 text-sm transition-colors", active === d && !custom ? "bg-kajal text-ivory" : "text-kajal-700 hover:bg-ivory-200")}>
            {d} days
          </button>
        ))}
        <button type="button" aria-pressed={custom || !active} onClick={() => setCustom(true)}
          className={cn("rounded-full px-3 py-1.5 text-sm transition-colors", custom || !active ? "bg-kajal text-ivory" : "text-kajal-700 hover:bg-ivory-200")}>Custom</button>
      </div>
      {(custom || !active) && (
        <form className="flex flex-wrap items-center gap-2" onSubmit={(e) => { e.preventDefault(); if (!invalid) onChange(draft); }}>
          <label className="sr-only" htmlFor="range-start">Start date</label>
          <input id="range-start" type="date" className="input h-9 w-[150px] py-0 text-sm" value={draft.start} max={draft.end || undefined} onChange={(e) => setDraft({ ...draft, start: e.target.value })} />
          <span className="text-kajal-400" aria-hidden>–</span>
          <label className="sr-only" htmlFor="range-end">End date</label>
          <input id="range-end" type="date" className="input h-9 w-[150px] py-0 text-sm" value={draft.end} min={draft.start || undefined} onChange={(e) => setDraft({ ...draft, end: e.target.value })} />
          <button type="submit" disabled={invalid} className="h-9 rounded-full bg-gold-500 px-4 text-sm font-medium text-white hover:bg-gold-600 disabled:bg-gold-200">Apply</button>
        </form>
      )}
    </div>
  );
}

export function Definitions({ text }: { text: string | undefined }) {
  if (!text) return null;
  const lines = text.split("\n").map((l) => l.trimEnd()).filter((l) => l.trim());
  const items: { term: string; def: string }[] = [];
  let intro = "";
  for (const l of lines) {
    const m = l.match(/^\s{2}(\S[^:]*?)\s*:\s(.*)$/);
    if (m) items.push({ term: m[1].trim(), def: m[2].trim() });
    else if (/^\s{4,}/.test(l) && items.length) items[items.length - 1].def += " " + l.trim();
    else intro += (intro ? " " : "") + l.trim();
  }
  return (
    <Disclosure summary="How these numbers are calculated">
      <div className="card max-w-3xl p-5">
        {intro && <p className="mb-3 text-sm text-kajal-500">{intro}</p>}
        <dl className="grid gap-x-6 gap-y-2.5 sm:grid-cols-[160px_1fr]">
          {items.map((i) => (
            <div key={i.term} className="contents">
              <dt className="text-sm font-medium text-kajal">{i.term}</dt>
              <dd className="text-sm text-kajal-700">{i.def}</dd>
            </div>
          ))}
        </dl>
      </div>
    </Disclosure>
  );
}

/** Report endpoints don't return definitions; this mirrors report_service's docstring. */
export const METRIC_DEFINITIONS = `Reporting metric definitions:
  Counted order   : online order with captured payment (paid_at set), or a COD order that was not cancelled. Pending/abandoned payments never count.
  Gross sales     : Σ order.subtotal (selling price × qty, before order-level discounts).
  Discounts       : Σ (promotion_discount + coupon_discount). MRP markdowns are reported separately.
  Refunds         : Σ processed refunds created in the period.
  Net sales       : Gross sales − Discounts − Refunds.
  Revenue         : Σ grand_total (what customers were charged, incl. shipping & COD fees).
  AOV             : Revenue ÷ counted orders.
  GST collected   : Σ tax_total (included in prices).
  Gross margin    : Σ (line_total − unit_cost × qty) for lines with cost data — admins only.`;
