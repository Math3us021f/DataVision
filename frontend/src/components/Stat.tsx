import { ArrowUpRight, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { SmartLink } from "@/components/SmartLink";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useCountUp } from "@/hooks/useCountUp";
import { cn } from "@/lib/utils";

function AnimatedValue({ value, format }: { value: number; format: (n: number) => string }) {
  return <>{format(useCountUp(value))}</>;
}

/** Cartão de indicador: ícone, rótulo, valor animado, detalhe e um acessório (gráfico/anel) opcional. */
export function Stat({
  id,
  label,
  icon: Icon,
  value,
  format,
  detail,
  href,
  accessory,
  loading,
  className,
}: {
  id: string;
  label: string;
  icon: LucideIcon;
  value: number | null;
  format: (n: number) => string;
  detail?: ReactNode;
  href?: string;
  accessory?: ReactNode;
  loading?: boolean;
  className?: string;
}) {
  const body = (
    <>
      <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-accent-soft text-accent">
        <Icon className="size-5" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-xs font-medium text-muted">{label}</p>
        {loading || value === null ? (
          <Skeleton className="mt-1.5 h-7 w-20" />
        ) : (
          <p id={id} className="truncate text-2xl leading-8 font-semibold tracking-tight tabular-nums">
            <AnimatedValue value={value} format={format} />
          </p>
        )}
        {detail !== undefined && <p className="truncate text-xs text-subtle short:hidden">{loading ? " " : detail}</p>}
      </div>
      {accessory}
      {href && (
        <ArrowUpRight className="absolute top-2.5 right-2.5 size-3.5 text-subtle opacity-0 transition-opacity group-hover:opacity-100" />
      )}
    </>
  );

  const classes = cn("group relative flex items-center gap-3 p-3.5", className);
  if (href) {
    return (
      <SmartLink href={href} className="block min-w-0 rounded-card focus-visible:outline-2 focus-visible:outline-accent">
        <Card className={cn(classes, "transition-all hover:-translate-y-px hover:border-accent/60")}>{body}</Card>
      </SmartLink>
    );
  }
  return <Card className={classes}>{body}</Card>;
}
