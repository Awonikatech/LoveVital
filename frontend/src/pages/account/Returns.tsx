import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { RotateCcw } from "lucide-react";
import { ButtonLink, EmptyState, Money, PageSpinner, StatusBadge } from "@/components/ui";
import { storeApi } from "@/services/store";
import { date, titleCase } from "@/utils/format";
import { useSeo } from "@/hooks/useSeo";

export default function MyReturns() {
  useSeo({ title: "Returns", noindex: true });
  const { data, isLoading } = useQuery({ queryKey: ["my-returns"], queryFn: storeApi.returns });
  if (isLoading) return <PageSpinner />;
  return (
    <div>
      <h2 className="text-[28px]">Returns & refunds</h2>
      <p className="mt-1 text-kajal-500">Start a return from the order page within 7 days of delivery. Refunds reach your original payment method in 5–7 business days.</p>
      {!data?.length ? (
        <EmptyState icon={<RotateCcw className="h-6 w-6" />} title="No return requests" body="Returns you request will show their pickup and refund status here." action={<ButtonLink to="/account/orders" variant="outline">View my orders</ButtonLink>} />
      ) : (
        <div className="mt-6 overflow-x-auto rounded-2xl border border-gold-200/60 bg-white">
          <table className="w-full min-w-[600px] text-left text-[15px]">
            <thead className="border-b border-gold-200/60 text-sm text-kajal-500"><tr><th className="px-5 py-3 font-normal">Request</th><th className="px-5 py-3 font-normal">Order</th><th className="px-5 py-3 font-normal">Type</th><th className="px-5 py-3 font-normal">Status</th><th className="px-5 py-3 text-right font-normal">Refund</th></tr></thead>
            <tbody className="divide-y divide-gold-200/40">
              {data.map((r) => (
                <tr key={r.id}>
                  <td className="px-5 py-4">#{r.id}<span className="block text-sm text-kajal-400">{date(r.created_at)}</span></td>
                  <td className="px-5 py-4"><Link to={`/account/orders/${r.order_number}`} className="link-underline tabular">{r.order_number}</Link></td>
                  <td className="px-5 py-4">{titleCase(r.return_type)}<span className="block text-sm text-kajal-400">{titleCase(r.reason)}</span></td>
                  <td className="px-5 py-4"><StatusBadge status={r.status} />{r.admin_note && <span className="mt-1 block text-sm text-kajal-400">{r.admin_note}</span>}</td>
                  <td className="px-5 py-4 text-right">{r.refund_amount && Number(r.refund_amount) > 0 ? <Money value={r.refund_amount} /> : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
