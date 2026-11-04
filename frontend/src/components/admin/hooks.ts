import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQueryClient, type QueryKey } from "@tanstack/react-query";
import { errorMessage } from "@/services/api";
import { useToast } from "@/features/toast";

/** Filters kept in the URL so lists are linkable (dashboard queues link to filtered lists). */
export function useUrlFilters<T extends Record<string, string>>(defaults: T) {
  const [sp, setSp] = useSearchParams();
  const values = useMemo(() => {
    const out = { ...defaults } as Record<string, string>;
    for (const k of Object.keys(defaults)) out[k] = sp.get(k) ?? defaults[k];
    return out as T;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sp]);
  const set = useCallback(
    (patch: Partial<T>, resetPage = true) => {
      setSp((prev) => {
        const next = new URLSearchParams(prev);
        for (const [k, v] of Object.entries(patch)) {
          if (v === undefined || v === "" || v === defaults[k]) next.delete(k);
          else next.set(k, String(v));
        }
        if (resetPage && !("page" in patch)) next.delete("page");
        return next;
      }, { replace: true });
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [setSp],
  );
  return [values, set] as const;
}

/** useMutation with toast on success/failure and query invalidation. */
export function useAdminMutation<TVars, TData = unknown>(
  fn: (v: TVars) => Promise<TData>,
  opts: { success?: string | ((d: TData, v: TVars) => string | null); invalidate?: QueryKey[]; onSuccess?: (d: TData, v: TVars) => void; silentError?: boolean } = {},
) {
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: fn,
    onSuccess: (d, v) => {
      opts.invalidate?.forEach((k) => qc.invalidateQueries({ queryKey: k }));
      const msg = typeof opts.success === "function" ? opts.success(d, v) : opts.success;
      if (msg) toast(msg, "success");
      opts.onSuccess?.(d, v);
    },
    onError: (e) => {
      if (!opts.silentError) toast(errorMessage(e), "error");
    },
  });
}
