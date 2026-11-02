import { X } from "lucide-react";
import { useEffect, useRef, type ReactNode } from "react";

import { cn } from "@/lib/utils";

/** <dialog> nativo: o navegador cuida do foco preso, da tecla Esc e do fundo escurecido. */
function useNativeDialog(open: boolean, onClose: () => void, dismissible = true) {
  const ref = useRef<HTMLDialogElement>(null);
  // O navegador dispara o evento `close` de forma assíncrona, também quando fechamos por código. Sem este marcador, o
  // evento de um diálogo que acabou de fechar podia chegar depois de outro já ter aberto no lugar (ex.: a segunda
  // confirmação da exclusão forçada) e apagar o novo. Só o fechamento feito pela pessoa (Esc) chama `onClose`.
  const closedByCode = useRef(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (open && !el.open) el.showModal();
    if (!open && el.open) {
      closedByCode.current = true;
      el.close();
    }
  }, [open]);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const handleClose = () => {
      if (closedByCode.current) {
        closedByCode.current = false;
        return;
      }
      onClose();
    };
    el.addEventListener("close", handleClose);
    // Janela que exige uma resposta explícita: a tecla Esc não a fecha.
    const keepOpen = (e: Event) => !dismissible && e.preventDefault();
    el.addEventListener("cancel", keepOpen);
    return () => {
      el.removeEventListener("close", handleClose);
      el.removeEventListener("cancel", keepOpen);
    };
  }, [onClose, dismissible]);

  return ref;
}

interface BaseProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
}

/** Janela centralizada (confirmações). Clicar no fundo fecha, a menos que `dismissible` seja falso
 * (aí só os botões respondem: nem o fundo nem a tecla Esc fecham). */
export function Modal({ open, onClose, title, children, footer, dismissible = true }: BaseProps & { dismissible?: boolean }) {
  const ref = useNativeDialog(open, onClose, dismissible);
  return (
    <dialog
      ref={ref}
      aria-label={title}
      onClick={(e) => dismissible && e.target === ref.current && onClose()}
      className="m-auto w-[min(92vw,440px)] rounded-card border border-border bg-surface p-0 text-foreground shadow-card backdrop:bg-black/60 backdrop:backdrop-blur-[2px]"
    >
      {open && (
        <div className="p-6">
          <h2 className="text-base font-semibold tracking-tight">{title}</h2>
          <div className="mt-2 text-sm text-muted">{children}</div>
          {footer && <div className="mt-6 flex justify-end gap-2">{footer}</div>}
        </div>
      )}
    </dialog>
  );
}

/** Painel que desliza da direita (detalhes). Clicar no fundo fecha. */
export function Drawer({
  open,
  onClose,
  title,
  subtitle,
  children,
  footer,
  className,
}: BaseProps & { subtitle?: string; className?: string }) {
  const ref = useNativeDialog(open, onClose);
  return (
    <dialog
      ref={ref}
      aria-label={title}
      onClick={(e) => e.target === ref.current && onClose()}
      className={cn(
        "m-0 ml-auto h-dvh max-h-none w-[min(760px,100vw)] max-w-none border-l border-border bg-surface p-0 text-foreground shadow-card backdrop:bg-black/60 open:flex open:animate-[drawer-in_0.22s_ease-out] open:flex-col",
        className,
      )}
    >
      {open && (
        <>
          <header className="flex items-start justify-between gap-4 border-b border-border px-6 py-4">
            <div className="min-w-0">
              <h2 className="text-base font-semibold tracking-tight">{title}</h2>
              {subtitle && <p className="mt-0.5 truncate text-sm text-muted">{subtitle}</p>}
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="Fechar"
              className="grid size-8 shrink-0 place-items-center rounded-lg text-muted transition-colors hover:bg-surface-2 hover:text-foreground"
            >
              <X className="size-[18px]" />
            </button>
          </header>
          <div className="scroll-thin min-h-0 flex-1 overflow-y-auto px-6 py-5">{children}</div>
          {footer && <footer className="flex items-center justify-end gap-2 border-t border-border px-6 py-3">{footer}</footer>}
        </>
      )}
    </dialog>
  );
}
