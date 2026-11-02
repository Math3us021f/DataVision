import { ChevronLeft, ChevronRight } from "lucide-react";

import { buttonStyles } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function Pagination({
  page,
  pageSize,
  total,
  onPage,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPage: (page: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const first = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const last = Math.min(page * pageSize, total);

  return (
    <div className="mt-3 flex items-center justify-between border-t border-border pt-3 text-xs text-muted">
      <span data-pagination-range>
        Mostrando {first}–{last} de {total}
      </span>
      <div className="flex items-center gap-1">
        <button
          type="button"
          aria-label="Página anterior"
          disabled={page <= 1}
          onClick={() => onPage(page - 1)}
          className={cn(buttonStyles({ variant: "ghost", size: "icon" }), "size-8")}
        >
          <ChevronLeft className="size-4" />
        </button>
        <span className="px-1 tabular-nums">
          {page} / {pages}
        </span>
        <button
          type="button"
          aria-label="Próxima página"
          disabled={page >= pages}
          onClick={() => onPage(page + 1)}
          className={cn(buttonStyles({ variant: "ghost", size: "icon" }), "size-8")}
        >
          <ChevronRight className="size-4" />
        </button>
      </div>
    </div>
  );
}
