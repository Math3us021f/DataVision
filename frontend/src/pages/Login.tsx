import { ChartNoAxesColumn, Eye, EyeOff, LoaderCircle } from "lucide-react";
import { useState, type FormEvent } from "react";

import { buttonStyles } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/ui/select";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

const EXPIRED_NOTICES: Record<string, string> = {
  idle: "Sua sessão foi encerrada por inatividade. Entre novamente para continuar.",
  time: "Sua sessão expirou (tempo máximo de uso). Entre novamente para continuar.",
};

/** Tela de entrada (fora do menu lateral). Sem cadastro: contas são criadas por um administrador. */
export default function Login() {
  const notice = EXPIRED_NOTICES[new URLSearchParams(window.location.search).get("expired") ?? ""];
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (!username.trim() || !password) {
      setError("Preencha usuário e senha.");
      return;
    }
    setBusy(true);
    try {
      await api("/login", { method: "POST", body: JSON.stringify({ username: username.trim(), password }) });
      window.location.href = "/app";
    } catch (e) {
      setError(e instanceof Error ? e.message : "Não foi possível conectar ao servidor.");
      setBusy(false);
    }
  }

  return (
    <main className="grid min-h-full place-items-center p-4">
      <Card className="w-full max-w-sm p-7">
        <div className="flex items-center gap-3">
          <span className="grid size-10 place-items-center rounded-xl bg-accent text-white shadow-[0_6px_20px_rgb(255_90_31/0.35)]">
            <ChartNoAxesColumn className="size-5" />
          </span>
          <h1 className="text-xl font-semibold tracking-tight">DataVision</h1>
        </div>
        <p className="mt-3 text-sm text-muted">Entre com sua conta para continuar.</p>
        {notice && (
          <div id="login-notice" role="status" className="mt-4 rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm">
            {notice}
          </div>
        )}

        <form id="login-form" onSubmit={submit} noValidate className="mt-5 flex flex-col gap-4">
          <Field label="Usuário" htmlFor="username">
            <Input id="username" name="username" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" autoFocus required />
          </Field>
          <Field label="Senha" htmlFor="password">
            <div className="relative">
              <Input
                id="password"
                name="password"
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                className="pr-10"
                required
              />
              <button
                type="button"
                id="password-toggle"
                onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? "Ocultar senha" : "Mostrar senha"}
                title={showPassword ? "Ocultar senha" : "Mostrar senha"}
                className="absolute top-1/2 right-1.5 grid size-7 -translate-y-1/2 place-items-center rounded-md text-muted hover:bg-surface-2 hover:text-foreground"
              >
                {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
              </button>
            </div>
          </Field>

          {error && (
            <div id="login-error" role="alert" className="rounded-lg border border-danger/40 bg-danger/10 p-3 text-sm">
              {error}
            </div>
          )}

          <button type="submit" id="login-submit" disabled={busy} className={cn(buttonStyles({ variant: "primary" }), "w-full")}>
            {busy ? (
              <>
                <LoaderCircle className="size-4 animate-spin" /> Entrando...
              </>
            ) : (
              "Entrar"
            )}
          </button>
        </form>

        <p className="mt-5 text-center text-xs text-subtle">Acesso restrito. Contas são criadas por um administrador.</p>
      </Card>
    </main>
  );
}
