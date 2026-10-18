import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Package, ChevronRight } from "lucide-react";
import { ButtonLink, EmptyState, ErrorState, Money, PageSpinner, Pagination, StatusBadge } from "@/components/ui";
import { storeApi } from "@/services/store";
import { date, plural } from "@/utils/format";
import { useSeo } from "@/hooks/useSeo";

export default function Orders() {
  useSeo({ title: "My orders", noindex: true });
  const [page, setPage] = useState(1);
  const { data, isLoading, isError, refetch } = useQuery({ queryKey: ["orders", page], queryFn: () => storeApi.orders(page) });
  if (isLoading) return <PageSpinner />;
  if (isError) return <ErrorState message="We couldn't load your orders." onRetry={() => refetch()} />;
  if (!data?.items.length) return <EmptyState icon={<Package className="h-6 w-6" />} title="No orders yet" body="When you place an order, it'll appear here with live tracking." action={<ButtonLink to="/best-sellers">Start shopping</ButtonLink>} />;
  return (
    <div>
      <h2 className="mb-6 text-[28px]">Orders</h2>
      <ul className="space-y-4">
        {data.items.map((o) => (
          <li key={o.id}>
            <Link to={`/account/orders/${o.order_number}`} className="card flex flex-col gap-4 p-5 transition hover:shadow-lift sm:flex-row sm:items-center">
              <div className="flex -space-x-3">
                {o.thumbnails.slice(0, 3).map((t, i) => <img key={i} src={t ?? ""} alt="" className="h-20 w-16 rounded-xl border-2 border-white bg-ivory-200 object-cover" />)}
              </div>
              <div className="flex-1">
                <div className="flex flex-wrap items-center gap-2"><span className="font-medium tabular">{o.order_number}</span><StatusBadge status={o.status} label={o.status_label} /></div>
                <p className="mt-1 text-sm text-kajal-500">{o.first_item}{o.item_count > 1 ? ` and ${plural(o.item_count - 1, "more item")}` : ""}</p>
                <p className="mt-0.5 text-sm text-kajal-400">Placed {date(o.placed_at)}{o.estimated_delivery_date && !["delivered", "cancelled", "refunded"].includes(o.status) ? ` · Arrives by ${date(o.estimated_delivery_date)}` : ""}</p>
              </div>
              <div className="flex items-center gap-3 sm:text-right"><Money value={o.grand_total} className="text-lg font-medium" /><ChevronRight className="h-5 w-5 text-kajal-300" /></div>
            </Link>
          </li>
        ))}
      </ul>
      <div className="mt-8"><Pagination page={data.page} pages={data.pages} onChange={setPage} /></div>
    </div>
  );
}
