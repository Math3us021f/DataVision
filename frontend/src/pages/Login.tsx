import { ChartNoAxesColumn, Eye, EyeOff, LoaderCircle } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

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

interface PasswordStepResult {
  status: "ok" | "2fa_required";
  email_hint?: string;
  resend_in?: number;
}

function Spinner({ children }: { children: string }) {
  return (
    <>
      <LoaderCircle className="size-4 animate-spin" /> {children}
    </>
  );
}

/** Tela de entrada (fora do menu lateral). Sem cadastro: contas são criadas por um administrador.
 * Em duas etapas quando a conta tem e-mail: usuário e senha, depois o código enviado ao e-mail. */
export default function Login() {
  const notice = EXPIRED_NOTICES[new URLSearchParams(window.location.search).get("expired") ?? ""];
  const [step, setStep] = useState<"password" | "code">("password");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [code, setCode] = useState("");
  const [hint, setHint] = useState("");
  const [cooldown, setCooldown] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (cooldown <= 0) return;
    const id = window.setTimeout(() => setCooldown((s) => s - 1), 1000);
    return () => window.clearTimeout(id);
  }, [cooldown]);

  async function submitPassword(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (!username.trim() || !password) {
      setError("Preencha usuário e senha.");
      return;
    }
    setBusy(true);
    try {
      const result = await api<PasswordStepResult>("/login", {
        method: "POST",
        body: JSON.stringify({ username: username.trim(), password }),
      });
      if (result.status === "2fa_required") {
        setHint(result.email_hint ?? "");
        setCooldown(result.resend_in ?? 0);
        setCode("");
        setStep("code");
        setBusy(false);
      } else {
        window.location.href = "/app";
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Não foi possível conectar ao servidor.");
      setBusy(false);
    }
  }

  async function submitCode(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await api("/login/verify", { method: "POST", body: JSON.stringify({ code }) });
      window.location.href = "/app";
    } catch (e) {
      const message = e instanceof Error ? e.message : "Não foi possível conectar ao servidor.";
      setError(message);
      setBusy(false);
      // Código esgotado ou vencido: não há o que tentar de novo aqui, recomeça pela senha.
      if (message.includes("Entre novamente")) {
        setStep("password");
        setPassword("");
      }
    }
  }

  async function resend() {
    setError(null);
    setBusy(true);
    try {
      const result = await api<{ resend_in: number }>("/login/resend", { method: "POST" });
      setCooldown(result.resend_in);
      setCode("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Não foi possível reenviar o código.");
    } finally {
      setBusy(false);
    }
  }

  function backToPassword() {
    setStep("password");
    setPassword("");
    setCode("");
    setError(null);
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

        {step === "password" ? (
          <>
            <p className="mt-3 text-sm text-muted">Entre com sua conta para continuar.</p>
            {notice && (
              <div id="login-notice" role="status" className="mt-4 rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm">
                {notice}
              </div>
            )}

            <form id="login-form" onSubmit={submitPassword} noValidate className="mt-5 flex flex-col gap-4">
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
                {busy ? <Spinner>Entrando...</Spinner> : "Entrar"}
              </button>
            </form>
          </>
        ) : (
          <form id="code-form" onSubmit={submitCode} noValidate className="mt-4 flex flex-col gap-4">
            <p className="text-sm text-muted">
              Enviamos um código de 6 dígitos para <strong id="code-hint" className="text-foreground">{hint}</strong>. Digite-o abaixo; ele vale por 10 minutos.
            </p>
            <Field label="Código de verificação" htmlFor="code">
              <Input
                id="code"
                name="code"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={12}
                placeholder="000000"
                className="text-center text-lg tracking-[0.4em]"
                autoFocus
                required
              />
            </Field>

            {error && (
              <div id="login-error" role="alert" className="rounded-lg border border-danger/40 bg-danger/10 p-3 text-sm">
                {error}
              </div>
            )}

            <button type="submit" id="code-submit" disabled={busy || code.trim().length < 6} className={cn(buttonStyles({ variant: "primary" }), "w-full")}>
              {busy ? <Spinner>Verificando...</Spinner> : "Verificar e entrar"}
            </button>

            <div className="flex items-center justify-between text-sm">
              <button type="button" id="code-back" onClick={backToPassword} className="text-muted underline-offset-4 hover:text-foreground hover:underline">
                Voltar
              </button>
              <button
                type="button"
                id="code-resend"
                disabled={cooldown > 0 || busy}
                onClick={resend}
                className="text-accent underline-offset-4 hover:underline disabled:text-subtle disabled:no-underline"
              >
                {cooldown > 0 ? `Reenviar em ${cooldown} s` : "Reenviar código"}
              </button>
            </div>
          </form>
        )}

        <p className="mt-5 text-center text-xs text-subtle">Acesso restrito. Contas são criadas por um administrador.</p>
      </Card>
    </main>
  );
}
