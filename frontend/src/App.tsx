import { BrowserRouter, Route, Routes } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/useApi";
import { ToastProvider } from "@/components/ui/toast";
import Datasets from "@/pages/Datasets";
import Home from "@/pages/Home";
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

export default function App() {
  // A sessão é validada no servidor (a rota /app já redireciona ao login); aqui só pegamos quem é o usuário.
  const me = useApi<Me>("/me");

  return (
    <ToastProvider>
    <BrowserRouter basename="/app">
      <AppShell me={me.data}>
        {me.data ? (
          <Routes>
            <Route path="/" element={<Home me={me.data} />} />
            <Route path="/datasets" element={<Datasets />} />
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
