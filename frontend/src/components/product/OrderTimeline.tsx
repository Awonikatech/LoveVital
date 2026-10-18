import { Check } from "lucide-react";
import type { OrderDetail } from "@/types";
import { date } from "@/utils/format";
import { cn } from "@/utils/cn";

export function OrderTimeline({ order }: { order: OrderDetail }) {
  const steps = order.timeline;
  const normal = steps.filter((s) => !s.exception);
  const exceptions = steps.filter((s) => s.exception);
  const lastDone = normal.reduce((acc, s, i) => (s.done ? i : acc), -1);
  return (
    <div>
      <ol className="relative grid gap-0 sm:grid-cols-[repeat(auto-fit,minmax(0,1fr))] sm:gap-2">
        {normal.map((s, i) => {
          const done = i <= lastDone;
          return (
            <li key={s.status} className="relative flex gap-3 pb-6 sm:flex-col sm:items-center sm:pb-0 sm:text-center">
              {i < normal.length - 1 && (
                <span aria-hidden className={cn("absolute left-[13px] top-7 h-[calc(100%-1.5rem)] w-px sm:left-[calc(50%+16px)] sm:top-[13px] sm:h-px sm:w-[calc(100%-32px)]", i < lastDone ? "bg-gold-500" : "bg-gold-200")} />
              )}
              <span className={cn("relative z-10 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border-2", done ? "border-gold-500 bg-gold-500 text-white" : "border-gold-200 bg-white")}>
                {done && <Check className="h-3.5 w-3.5" />}
              </span>
              <span className="sm:mt-2">
                <span className={cn("block text-sm", done ? "text-kajal" : "text-kajal-400")}>{s.label}</span>
                {s.at && done && <span className="block text-xs text-kajal-400">{date(s.at)}</span>}
              </span>
            </li>
          );
        })}
      </ol>
      {exceptions.length > 0 && (
        <div className="mt-5 flex flex-wrap gap-2">
          {exceptions.map((e) => <span key={e.status} className="rounded-full bg-[#FCF1DD] px-3 py-1 text-sm text-[#8A5A00]">{e.label} · {date(e.at)}</span>)}
        </div>
      )}
    </div>
  );
}

export function ShipmentEvents({ events }: { events: { status: string; location: string | null; description: string; occurred_at: string }[] }) {
  if (!events.length) return null;
  return (
    <ol className="relative ml-1.5 space-y-5 border-l border-gold-200 pl-5">
      {events.map((e, i) => (
        <li key={i} className="relative">
          <span className={cn("absolute -left-[27px] top-1 h-3 w-3 rounded-full border-2 border-white", i === 0 ? "bg-gold-500 ring-2 ring-gold-200" : "bg-gold-200")} />
          <p className="text-[15px] text-kajal">{e.description}</p>
          <p className="text-sm text-kajal-400">{[e.location, date(e.occurred_at, "long")].filter(Boolean).join(" · ")}</p>
        </li>
      ))}
    </ol>
  );
}
