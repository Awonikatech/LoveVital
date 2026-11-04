import { Heart } from "lucide-react";
import { ButtonLink, EmptyState, PageSpinner } from "@/components/ui";
import { ProductGrid } from "@/components/product/ProductCard";
import { useWishlist } from "@/features/wishlist";
import { useSeo } from "@/hooks/useSeo";

export default function Wishlist() {
  useSeo({ title: "Wishlist", noindex: true });
  const { data, isLoading } = useWishlist();
  if (isLoading) return <PageSpinner />;
  if (!data?.items.length) return <EmptyState icon={<Heart className="h-6 w-6" />} title="Your wishlist is empty" body="Tap the heart on any piece to save it for later." action={<ButtonLink to="/new-arrivals">Discover new arrivals</ButtonLink>} />;
  return (
    <div>
      <h2 className="mb-6 text-[28px]">Wishlist</h2>
      <ProductGrid products={data.items.map((i) => i.product)} cols="lg:grid-cols-3" />
    </div>
  );
}
