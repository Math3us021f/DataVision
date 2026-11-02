import { CircleAlert, CircleCheck } from "lucide-react";
import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";

import { cn } from "@/lib/utils";

type Kind = "success" | "error";
interface ToastItem {
  id: number;
  message: string;
  kind: Kind;
}

const ToastContext = createContext<(message: string, kind?: Kind) => void>(() => {});

export const useToast = () => useContext(ToastContext);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const nextId = useRef(1);

  const toast = useCallback((message: string, kind: Kind = "success") => {
    const id = nextId.current++;
    setItems((prev) => [...prev, { id, message, kind }]);
    window.setTimeout(() => setItems((prev) => prev.filter((t) => t.id !== id)), 4000);
  }, []);

  const value = useMemo(() => toast, [toast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed right-4 bottom-4 z-50 flex w-[min(92vw,360px)] flex-col gap-2" role="status" aria-live="polite">
        {items.map((t) => {
          const Icon = t.kind === "success" ? CircleCheck : CircleAlert;
          return (
            <div
              key={t.id}
              className={cn(
                "animate-fade-up pointer-events-auto flex items-start gap-3 rounded-xl border bg-surface p-3.5 text-sm shadow-card",
                t.kind === "success" ? "border-success/40" : "border-danger/40",
              )}
            >
              <Icon className={cn("mt-0.5 size-4 shrink-0", t.kind === "success" ? "text-success" : "text-danger")} />
              <p className="min-w-0 flex-1 break-words">{t.message}</p>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}
