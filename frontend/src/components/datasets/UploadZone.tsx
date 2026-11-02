import { CircleAlert, CircleCheck, FileUp, Loader2 } from "lucide-react";
import { useRef, useState, type DragEvent, type KeyboardEvent } from "react";

import { Card } from "@/components/ui/card";
import { uploadDataset } from "@/lib/upload";
import { cn, formatBytes } from "@/lib/utils";
import { useToast } from "@/components/ui/toast";

const ALLOWED = [".csv", ".xlsx"];
const MAX_BYTES = 10_000_000;

interface QueueItem {
  id: number;
  name: string;
  size: number;
  percent: number;
  status: "uploading" | "done" | "error";
  message?: string;
}

/** Arrastar e soltar (ou clicar) com fila e barra de progresso. A validação final é do servidor. */
export function UploadZone({ onUploaded }: { onUploaded: () => void }) {
  const toast = useToast();
  const input = useRef<HTMLInputElement>(null);
  const nextId = useRef(1);
  const [active, setActive] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [queue, setQueue] = useState<QueueItem[]>([]);

  const patch = (id: number, change: Partial<QueueItem>) =>
    setQueue((prev) => prev.map((item) => (item.id === id ? { ...item, ...change } : item)));

  function start(file: File) {
    setError(null);
    // Checagem só de usabilidade (feedback imediato); quem valida de verdade é o servidor.
    const extension = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
    if (!ALLOWED.includes(extension)) {
      setError(`"${file.name}": formato não permitido (use .csv ou .xlsx).`);
      return;
    }
    if (file.size > MAX_BYTES) {
      setError(`"${file.name}": arquivo maior que 10 MB.`);
      return;
    }

    const id = nextId.current++;
    setQueue((prev) => [{ id, name: file.name, size: file.size, percent: 0, status: "uploading" }, ...prev]);

    uploadDataset(file, (percent) => patch(id, { percent }))
      .then(() => {
        patch(id, { percent: 100, status: "done" });
        toast(`"${file.name}" enviado.`);
        onUploaded();
        window.setTimeout(() => setQueue((prev) => prev.filter((i) => i.id !== id)), 2500);
      })
      .catch((err: Error) => patch(id, { status: "error", message: err.message }));
  }

  const pick = () => {
    if (input.current) {
      input.current.value = "";
      input.current.click();
    }
  };

  const onKey = (e: KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      pick();
    }
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setActive(false);
    Array.from(e.dataTransfer.files).forEach(start);
  };

  return (
    <Card className="p-4">
      <div
        id="dropzone"
        role="button"
        tabIndex={0}
        aria-label="Enviar arquivo CSV ou Excel"
        onClick={pick}
        onKeyDown={onKey}
        onDragEnter={(e) => {
          e.preventDefault();
          setActive(true);
        }}
        onDragOver={(e) => {
          e.preventDefault();
          setActive(true);
        }}
        onDragLeave={(e) => {
          e.preventDefault();
          setActive(false);
        }}
        onDrop={onDrop}
        className={cn(
          "flex cursor-pointer flex-col items-center gap-1.5 rounded-xl border-2 border-dashed border-border px-6 py-7 text-center transition-colors hover:border-accent/60 hover:bg-accent-soft/40 focus-visible:outline-2 focus-visible:outline-accent",
          active && "border-accent bg-accent-soft",
        )}
      >
        <span className="grid size-11 place-items-center rounded-xl bg-accent-soft text-accent">
          <FileUp className="size-5" />
        </span>
        <p className="text-sm font-semibold">Arraste um arquivo aqui ou clique para escolher</p>
        <p className="text-xs text-muted">.csv ou .xlsx · até 10 MB</p>
        <input
          ref={input}
          id="file-input"
          type="file"
          accept=".csv,.xlsx"
          multiple
          hidden
          onChange={(e) => Array.from(e.target.files ?? []).forEach(start)}
        />
      </div>

      {error && (
        <p role="alert" className="mt-3 rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}

      {queue.length > 0 && (
        <ul id="upload-queue" className="mt-3 space-y-2">
          {queue.map((item) => (
            <li key={item.id} className="flex items-center gap-3 rounded-lg bg-surface-2 px-3 py-2 text-sm">
              {item.status === "uploading" && <Loader2 className="size-4 shrink-0 animate-spin text-accent" />}
              {item.status === "done" && <CircleCheck className="size-4 shrink-0 text-success" />}
              {item.status === "error" && <CircleAlert className="size-4 shrink-0 text-danger" />}
              <span className="min-w-0 flex-1 truncate font-medium" title={item.name}>
                {item.name}
              </span>
              <span className="hidden text-xs text-muted sm:inline">{formatBytes(item.size)}</span>
              {item.status === "error" ? (
                <span className="max-w-[45%] truncate text-xs text-danger" title={item.message}>
                  {item.message}
                </span>
              ) : (
                <div className="h-1.5 w-28 overflow-hidden rounded-full bg-border" role="progressbar" aria-valuenow={item.percent} aria-valuemin={0} aria-valuemax={100}>
                  <div className="h-full rounded-full bg-accent transition-[width] duration-200" style={{ width: `${item.percent}%` }} />
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
