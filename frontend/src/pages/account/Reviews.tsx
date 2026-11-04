import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Star } from "lucide-react";
import { ButtonLink, EmptyState, PageSpinner, Stars } from "@/components/ui";
import { storeApi } from "@/services/store";
import { date } from "@/utils/format";
import { useSeo } from "@/hooks/useSeo";

export default function MyReviews() {
  useSeo({ title: "My reviews", noindex: true });
  const { data, isLoading } = useQuery({ queryKey: ["my-reviews"], queryFn: storeApi.myReviews });
  if (isLoading) return <PageSpinner />;
  if (!data?.length) return <EmptyState icon={<Star className="h-6 w-6" />} title="No reviews yet" body="Reviews you write on delivered orders will appear here." action={<ButtonLink to="/account/orders">Go to my orders</ButtonLink>} />;
  return (
    <div>
      <h2 className="mb-6 text-[28px]">My reviews</h2>
      <ul className="space-y-4">
        {data.map((r) => (
          <li key={r.id} className="card flex gap-4 p-5">
            {r.product && <Link to={`/product/${r.product.slug}`}><img src={r.product.image ?? ""} alt="" className="h-24 w-20 rounded-xl object-cover" /></Link>}
            <div className="flex-1">
              {r.product && <Link to={`/product/${r.product.slug}`} className="text-[15px] hover:text-gold-700">{r.product.name}</Link>}
              <div className="mt-1 flex items-center gap-2"><Stars value={r.rating} /><span className="text-sm font-medium">{r.title}</span></div>
              {r.body && <p className="mt-2 text-[15px] leading-7 text-kajal-700">{r.body}</p>}
              <p className="mt-1 text-sm text-kajal-400">{date(r.created_at)}</p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
