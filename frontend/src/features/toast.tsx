import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import { CheckCircle2, AlertCircle, Info, X } from "lucide-react";
import { cn } from "@/utils/cn";

type Kind = "success" | "error" | "info";
interface Toast { id: number; kind: Kind; message: string; action?: { label: string; onClick: () => void } }
const Ctx = createContext<(message: string, kind?: Kind, action?: Toast["action"]) => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const push = useCallback((message: string, kind: Kind = "success", action?: Toast["action"]) => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t.slice(-2), { id, kind, message, action }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), kind === "error" ? 6000 : 3800);
  }, []);
  const Icon = { success: CheckCircle2, error: AlertCircle, info: Info };
  return (
    <Ctx.Provider value={push}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 bottom-4 z-[100] flex flex-col items-center gap-2 px-4 sm:bottom-6 sm:items-end sm:pr-6" aria-live="polite" role="status">
        {toasts.map((t) => {
          const I = Icon[t.kind];
          return (
            <div key={t.id} className={cn("pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-xl border bg-kajal px-4 py-3 text-sm text-ivory shadow-lift",
              t.kind === "error" ? "border-kumkum" : "border-gold-700")}>
              <I className={cn("mt-0.5 h-4 w-4 shrink-0", t.kind === "error" ? "text-kumkum-100" : "text-gold-200")} aria-hidden />
              <p className="flex-1 leading-5">{t.message}</p>
              {t.action && <button className="font-medium text-gold-200 underline underline-offset-2" onClick={t.action.onClick}>{t.action.label}</button>}
              <button aria-label="Dismiss" onClick={() => setToasts((x) => x.filter((y) => y.id !== t.id))}><X className="h-4 w-4 text-kajal-300" /></button>
            </div>
          );
        })}
      </div>
    </Ctx.Provider>
  );
}
export const useToast = () => useContext(Ctx);
