import { BrowserRouter, Navigate, Outlet, Route, Routes } from "react-router-dom";

import { EmailReminder } from "@/components/EmailReminder";
import { IdleGuard } from "@/components/IdleGuard";
import { AppShell } from "@/components/layout/AppShell";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/useApi";
import { ToastProvider } from "@/components/ui/toast";
import Account from "@/pages/Account";
import DatasetDashboard from "@/pages/DatasetDashboard";
import Datasets from "@/pages/Datasets";
import Home from "@/pages/Home";
import Audit from "@/pages/admin/Audit";
import Files from "@/pages/admin/Files";
import Logs from "@/pages/admin/Logs";
import Metrics from "@/pages/admin/Metrics";
import Users from "@/pages/admin/Users";
import type { Me } from "@/types";

function NotFound() {
  return (
    <main className="grid flex-1 place-items-center p-8 text-center">
      <div>
        <p className="text-sm font-semibold">Página não encontrada</p>
        <a href="/app" className="mt-2 inline-block text-sm text-accent underline-offset-4 hover:underline">
          Voltar ao início
        </a>
      </div>
    </main>
  );
}

/** Só administradores entram nas telas de /admin (a API também confere, em cada rota). */
function AdminOnly({ me }: { me: Me }) {
  return me.is_admin ? <Outlet /> : <Navigate to="/" replace />;
}

export default function App() {
  // A sessão é validada no servidor (a rota /app já redireciona ao login); aqui só pegamos quem é o usuário.
  const me = useApi<Me>("/me");

  return (
    <ToastProvider>
    <BrowserRouter basename="/app">
      <AppShell me={me.data}>
        {me.data && <IdleGuard idleSeconds={me.data.idle_timeout_seconds} />}
        {me.data && me.data.email_masked === null && <EmailReminder />}
        {me.data ? (
          <Routes>
            <Route path="/" element={<Home me={me.data} />} />
            <Route path="/datasets" element={<Datasets />} />
            <Route path="/datasets/:id/dashboard" element={<DatasetDashboard />} />
            <Route path="/account" element={<Account me={me.data} onSaved={me.reload} />} />
            <Route path="/admin" element={<AdminOnly me={me.data} />}>
              <Route index element={<Navigate to="/admin/users" replace />} />
              <Route path="users" element={<Users me={me.data} />} />
              <Route path="audit" element={<Audit />} />
              <Route path="metrics" element={<Metrics />} />
              <Route path="logs" element={<Logs />} />
              <Route path="files" element={<Files />} />
            </Route>
            <Route path="*" element={<NotFound />} />
          </Routes>
        ) : (
          <main className="space-y-4 p-6">
            <Skeleton className="h-8 w-48" />
            <Skeleton className="h-24 w-full" />
          </main>
        )}
      </AppShell>
    </BrowserRouter>
    </ToastProvider>
  );
}
