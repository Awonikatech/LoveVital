import type { Totals } from "@/types";
import { Money } from "@/components/ui";
import { isPositive } from "@/utils/format";

export function TotalsBreakdown({ totals, showShipping = true, codSelected }: { totals: Totals; showShipping?: boolean; codSelected?: boolean }) {
  const Row = ({ label, children, tone }: { label: React.ReactNode; children: React.ReactNode; tone?: "save" | "muted" }) => (
    <div className="flex items-baseline justify-between gap-4 py-1.5 text-[15px]">
      <dt className={tone === "muted" ? "text-kajal-500" : "text-kajal-700"}>{label}</dt>
      <dd className={tone === "save" ? "text-kumkum tabular" : "tabular"}>{children}</dd>
    </div>
  );
  return (
    <div>
      <dl>
        <Row label="Total MRP"><Money value={totals.subtotal_mrp} /></Row>
        {isPositive(totals.item_discount) && <Row label="Discount on MRP" tone="save"><Money value={totals.item_discount} negative /></Row>}
        {totals.applied_promotions.filter((p) => Number(p.amount) > 0).map((p) => (
          <Row key={p.id} label={<span>Offer: {p.name}</span>} tone="save"><Money value={p.amount} negative /></Row>
        ))}
        {isPositive(totals.coupon_discount) && <Row label={`Coupon ${totals.coupon?.code ?? ""}`} tone="save"><Money value={totals.coupon_discount} negative /></Row>}
        {showShipping && (
          <Row label="Shipping">{totals.free_shipping || !isPositive(totals.shipping_charge) ? <span className="text-leaf">Free</span> : <Money value={totals.shipping_charge} />}</Row>
        )}
        {(codSelected || isPositive(totals.cod_charge)) && <Row label="Cash on Delivery fee"><Money value={totals.cod_charge} /></Row>}
      </dl>
      <div className="mt-3 flex items-baseline justify-between border-t border-gold-200/60 pt-4">
        <span className="text-lg">Total payable</span>
        <Money value={totals.grand_total} className="font-display text-[28px] leading-none" />
      </div>
      <p className="mt-1 text-right text-xs text-kajal-400">Inclusive of GST <Money value={totals.tax_total} /></p>
      {isPositive(totals.total_savings) && (
        <p className="mt-4 rounded-xl bg-kumkum-50 px-4 py-2.5 text-center text-sm text-kumkum">You're saving <strong className="font-medium tabular"><Money value={totals.total_savings} /></strong> on this order</p>
      )}
      {totals.messages.map((m) => <p key={m} className="mt-2 text-sm text-kajal-500">{m}</p>)}
    </div>
  );
}
