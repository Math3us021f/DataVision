import type { ReactNode } from "react";

import { buttonStyles } from "@/components/ui/button";
import { Modal } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

export function ConfirmDialog({
  open,
  title,
  children,
  confirmLabel,
  danger = false,
  busy = false,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  children: ReactNode;
  confirmLabel: string;
  danger?: boolean;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <Modal
      open={open}
      onClose={onCancel}
      title={title}
      footer={
        <>
          <button type="button" onClick={onCancel} className={buttonStyles({ variant: "secondary" })}>
            Cancelar
          </button>
          <button
            type="button"
            id="confirm-ok"
            disabled={busy}
            onClick={onConfirm}
            className={cn(buttonStyles({ variant: "primary" }), danger && "bg-danger hover:bg-danger/85 dark:hover:bg-danger/85")}
          >
            {confirmLabel}
          </button>
        </>
      }
    >
      {children}
    </Modal>
  );
}
