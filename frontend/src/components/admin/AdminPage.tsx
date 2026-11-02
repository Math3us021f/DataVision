import type { ReactNode } from "react";

/** Casca comum das telas de administração: título, subtítulo e ações no topo. */
export function AdminPage({
  title,
  subtitle,
  actions,
  children,
}: {
  title: string;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <main className="flex flex-col gap-4 p-4 md:p-6 lg:px-7">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
          {subtitle && <p className="mt-0.5 text-sm text-muted">{subtitle}</p>}
        </div>
        {actions}
      </header>
      {children}
    </main>
  );
}

export function ErrorPanel({ title, message }: { title: string; message: string }) {
  return (
    <div role="alert" className="rounded-card border border-danger/40 bg-danger/10 p-6 text-center text-sm">
      <p className="font-semibold">{title}</p>
      <p className="mt-1 text-muted">{message}</p>
    </div>
  );
}

export function EmptyState({ title, message }: { title: string; message: string }) {
  return (
    <div className="py-10 text-center" role="status">
      <p className="text-sm font-semibold">{title}</p>
      <p className="mt-1 text-sm text-muted">{message}</p>
    </div>
  );
}
