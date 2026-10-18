import { createContext, useContext, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { errorMessage, setCartToken } from "@/services/api";
import { storeApi } from "@/services/store";
import { useToast } from "./toast";
import { useAuth } from "./auth";
import type { Cart } from "@/types";

interface CartUi { open: boolean; setOpen: (v: boolean) => void }
const UiCtx = createContext<CartUi>({ open: false, setOpen: () => {} });

export function CartUiProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return <UiCtx.Provider value={{ open, setOpen }}>{children}</UiCtx.Provider>;
}
export const useCartUi = () => useContext(UiCtx);

/** Only guest carts are identified by token; a logged-in user's cart is found by their account. */
function remember(cart: Cart, isGuest: boolean) {
  if (isGuest && cart?.token) setCartToken(cart.token);
  return cart;
}

export function useCart() {
  const qc = useQueryClient();
  const toast = useToast();
  const { setOpen } = useCartUi();
  const { user, ready } = useAuth();
  const key = ["cart", user?.id ?? "guest"];
  // Wait for the session to be restored, otherwise a logged-in user would briefly be treated as a guest.
  const query = useQuery({ queryKey: key, queryFn: () => storeApi.cart().then((c) => remember(c, !user)), staleTime: 15_000, enabled: ready });
  const set = (c: Cart) => qc.setQueryData(key, remember(c, !user));
  const onError = (e: unknown) => toast(errorMessage(e), "error");

  const add = useMutation({
    mutationFn: ({ variantId, qty }: { variantId: number; qty: number; silent?: boolean }) => storeApi.addToCart(variantId, qty),
    onSuccess: (c, vars) => {
      set(c);
      if (!vars.silent) setOpen(true);
    },
    onError,
  });
  const update = useMutation({ mutationFn: ({ id, qty }: { id: number; qty: number }) => storeApi.updateCartItem(id, qty), onSuccess: set, onError });
  const remove = useMutation({ mutationFn: (id: number) => storeApi.removeCartItem(id), onSuccess: set, onError });
  const applyCoupon = useMutation({ mutationFn: (code: string) => storeApi.applyCoupon(code), onSuccess: set });
  const removeCoupon = useMutation({ mutationFn: () => storeApi.removeCoupon(), onSuccess: set, onError });

  return { cart: query.data, isLoading: query.isPending, refetch: query.refetch, add, update, remove, applyCoupon, removeCoupon };
}
