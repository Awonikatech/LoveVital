import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useLocation } from "react-router-dom";
import { storeApi } from "@/services/store";
import { useAuth } from "./auth";
import { useToast } from "./toast";

export function useWishlist() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const nav = useNavigate();
  const loc = useLocation();
  const q = useQuery({ queryKey: ["wishlist"], queryFn: storeApi.wishlist, enabled: !!user, staleTime: 60_000 });
  const ids = new Set(q.data?.product_ids ?? []);
  const toggle = useMutation({
    mutationFn: async (productId: number) => (ids.has(productId) ? storeApi.removeWishlist(productId) : storeApi.addWishlist(productId)),
    onSuccess: (_r, productId) => {
      toast(ids.has(productId) ? "Removed from your wishlist" : "Saved to your wishlist");
      qc.invalidateQueries({ queryKey: ["wishlist"] });
    },
  });
  return {
    ids,
    data: q.data,
    isLoading: q.isLoading,
    toggle: (productId: number) => {
      if (!user) {
        toast("Log in to save pieces to your wishlist", "info", { label: "Log in", onClick: () => nav(`/login?next=${encodeURIComponent(loc.pathname)}`) });
        return;
      }
      toggle.mutate(productId);
    },
  };
}
