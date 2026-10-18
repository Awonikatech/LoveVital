import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { storeApi } from "@/services/store";
import { Breadcrumbs, Skeleton } from "@/components/ui";
import { useSeo } from "@/hooks/useSeo";
import { plural } from "@/utils/format";

export default function Collections() {
  useSeo({ title: "Collections", description: "Curated LoveVital edits for festivals, weddings and everyday wear." });
  const { data, isLoading } = useQuery({ queryKey: ["collections"], queryFn: storeApi.collections });
  return (
    <div className="container-site py-8">
      <Breadcrumbs items={[{ label: "Home", to: "/" }, { label: "Collections" }]} />
      <h1 className="mt-5 text-[40px] sm:text-[48px]">Collections</h1>
      <p className="mt-2 max-w-xl text-kajal-500">Seasonal edits put together by our stylists — each one a complete look.</p>
      <div className="mt-10 grid grid-cols-2 gap-x-6 gap-y-12 lg:grid-cols-3">
        {(isLoading ? Array.from({ length: 6 }) : data ?? []).map((c: any, i) => c ? (
          <Link key={c.slug} to={`/collections/${c.slug}`} className="group">
            <div className="arch arch-frame bg-ivory-200"><img src={c.image_url ?? ""} alt="" className="aspect-[3/4] w-full object-cover transition-transform duration-700 group-hover:scale-[1.03]" /></div>
            <h2 className="mt-5 text-2xl sm:text-[28px]">{c.name}</h2>
            <p className="mt-1 text-[15px] leading-6 text-kajal-500">{c.description}</p>
            <p className="mt-2 text-sm text-gold-700">{plural(c.product_count, "piece")}</p>
          </Link>
        ) : <Skeleton key={i} className="arch aspect-[3/4]" />)}
      </div>
    </div>
  );
}
