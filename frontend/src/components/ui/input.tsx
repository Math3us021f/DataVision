import type { InputHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export const inputStyles =
  "h-9 w-full rounded-lg border border-border bg-background px-3 text-sm placeholder:text-subtle focus-visible:outline-2 focus-visible:outline-accent disabled:opacity-50";

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={cn(inputStyles, className)} />;
}
