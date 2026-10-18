import { useState } from "react";
import { Tag, X } from "lucide-react";
import { Button } from "@/components/ui";
import { useCart } from "@/features/cart";
import { errorMessage } from "@/services/api";
import type { Totals } from "@/types";

export function CouponBox({ totals, onChange }: { totals: Totals; onChange?: () => void }) {
  const { applyCoupon, removeCoupon } = useCart();
  const [code, setCode] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const c = totals.coupon;
  if (c?.applied) {
    return (
      <div className="flex items-center justify-between rounded-xl border border-leaf/30 bg-leaf-50 px-4 py-3">
        <p className="flex items-center gap-2 text-sm text-leaf"><Tag className="h-4 w-4" /><span><strong className="font-medium">{c.code}</strong> applied</span></p>
        <button onClick={() => removeCoupon.mutate(undefined, { onSuccess: onChange })} className="flex items-center gap-1 text-sm text-kajal-500 hover:text-kumkum" aria-label={`Remove coupon ${c.code}`}><X className="h-4 w-4" />Remove</button>
      </div>
    );
  }
  return (
    <form onSubmit={async (e) => {
      e.preventDefault();
      if (!code.trim()) return;
      setErr(null);
      try { await applyCoupon.mutateAsync(code.trim()); setCode(""); onChange?.(); } catch (e2) { setErr(errorMessage(e2)); }
    }}>
      <label htmlFor="coupon" className="label">Have a coupon?</label>
      <div className="flex gap-2">
        <input id="coupon" value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} placeholder="Enter code" className="input h-11 uppercase tracking-wider placeholder:normal-case placeholder:tracking-normal" aria-invalid={!!err} />
        <Button type="submit" variant="outline" loading={applyCoupon.isPending}>Apply</Button>
      </div>
      {(err || (c && !c.applied && c.message)) && <p className="field-error">{err ?? c?.message}</p>}
      <p className="mt-2 text-xs text-kajal-400">Try WELCOME15 on your first order or FESTIVE10 on ₹1,499+.</p>
    </form>
  );
}
