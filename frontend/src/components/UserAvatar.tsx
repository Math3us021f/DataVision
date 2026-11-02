import { cn } from "@/lib/utils";
import type { AvatarColor } from "@/types";

/** Cores do avatar de iniciais (o servidor só aceita estes nomes). */
export const AVATAR_STYLES: Record<AvatarColor, string> = {
  orange: "bg-accent-soft text-accent-strong",
  green: "bg-success/15 text-success",
  blue: "bg-[#5a8fd9]/15 text-[#5a8fd9]",
  violet: "bg-[#9b7fd1]/15 text-[#9b7fd1]",
  rose: "bg-[#e0607e]/15 text-[#e0607e]",
  amber: "bg-warning/15 text-warning",
  teal: "bg-[#3aa6a0]/15 text-[#3aa6a0]",
  slate: "bg-surface-2 text-muted",
};

export const AVATAR_LABELS: Record<AvatarColor, string> = {
  orange: "Laranja",
  green: "Verde",
  blue: "Azul",
  violet: "Violeta",
  rose: "Rosa",
  amber: "Âmbar",
  teal: "Azul-petróleo",
  slate: "Cinza",
};

/** "Maria Souza" → "MS"; "admin" → "A". */
export function initialsOf(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "?";
  const first = Array.from(words[0])[0];
  const last = words.length > 1 ? Array.from(words[words.length - 1])[0] : "";
  return (first + last).toUpperCase();
}

const SIZES = { sm: "size-9 text-sm", md: "size-12 text-base", lg: "size-20 text-2xl" } as const;

/** Avatar só com iniciais (sem foto, de propósito: nada de arquivo de usuário nem dado pessoal extra). */
export function UserAvatar({
  name,
  color,
  size = "sm",
  className,
}: {
  name: string;
  color: AvatarColor | null;
  size?: keyof typeof SIZES;
  className?: string;
}) {
  return (
    <span
      aria-hidden="true"
      className={cn("grid shrink-0 place-items-center rounded-full font-semibold", SIZES[size], AVATAR_STYLES[color ?? "orange"], className)}
    >
      {initialsOf(name)}
    </span>
  );
}

export const displayNameOf = (me: { username: string; display_name: string | null }): string => me.display_name ?? me.username;
