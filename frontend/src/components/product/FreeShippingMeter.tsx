import type { Totals } from "@/types";
import { rupees } from "@/utils/format";
import { Truck } from "lucide-react";

export function FreeShippingMeter({ totals }: { totals: Totals }) {
  const threshold = Number(totals.free_shipping_threshold ?? 0);
  if (!threshold) return null;
  const remaining = Number(totals.amount_to_free_shipping ?? 0);
  const pct = totals.free_shipping ? 100 : Math.min(100, Math.max(4, ((threshold - remaining) / threshold) * 100));
  return (
    <div>
      <p className="flex items-center gap-2 text-sm text-kajal-700">
        <Truck className="h-4 w-4 text-gold-600" aria-hidden />
        {totals.free_shipping ? <span>You've unlocked <strong className="font-medium">free shipping</strong>.</span>
          : <span>Add <strong className="font-medium tabular">{rupees(remaining)}</strong> more for free shipping.</span>}
      </p>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-ivory-300" role="progressbar" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100} aria-label="Progress to free shipping">
        <div className="h-full rounded-full bg-gradient-to-r from-gold-300 to-gold-600 transition-all duration-500" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
