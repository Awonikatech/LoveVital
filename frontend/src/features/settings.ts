import { useQuery } from "@tanstack/react-query";
import { storeApi } from "@/services/store";

export function useSettings() {
  return useQuery({ queryKey: ["settings"], queryFn: storeApi.settings, staleTime: 5 * 60_000 }).data;
}
