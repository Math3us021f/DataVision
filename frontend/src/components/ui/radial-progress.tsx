import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";

const RADIUS = 18;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

/** Anel de progresso (0–100) em SVG: leve e com animação de entrada. */
export function RadialProgress({
  value,
  tone = "accent",
  className,
}: {
  value: number;
  tone?: "accent" | "success" | "warning" | "danger";
  className?: string;
}) {
  const [shown, setShown] = useState(0);
  useEffect(() => {
    const id = requestAnimationFrame(() => setShown(Math.max(0, Math.min(100, value))));
    return () => cancelAnimationFrame(id);
  }, [value]);

  const color = { accent: "stroke-accent", success: "stroke-success", warning: "stroke-warning", danger: "stroke-danger" }[tone];

  return (
    <svg viewBox="0 0 44 44" className={cn("size-11 -rotate-90", className)} aria-hidden="true">
      <circle cx="22" cy="22" r={RADIUS} fill="none" strokeWidth="4.5" className="stroke-surface-2" />
      <circle
        cx="22"
        cy="22"
        r={RADIUS}
        fill="none"
        strokeWidth="4.5"
        strokeLinecap="round"
        strokeDasharray={CIRCUMFERENCE}
        strokeDashoffset={CIRCUMFERENCE * (1 - shown / 100)}
        className={cn("transition-[stroke-dashoffset] duration-700 ease-out", color)}
      />
    </svg>
  );
}

export function toneForUsage(percent: number): "success" | "warning" | "danger" {
  if (percent >= 85) return "danger";
  if (percent >= 70) return "warning";
  return "success";
}
