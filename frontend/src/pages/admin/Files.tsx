import { File as FileIcon, FolderOpen, Folder, HardDrive, ListTree, X } from "lucide-react";
import { Fragment, useEffect, useState } from "react";

import { AdminPage, EmptyState, ErrorPanel } from "@/components/admin/AdminPage";
import { Stat } from "@/components/Stat";
import { buttonStyles } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { formatBytes, formatNumber } from "@/lib/utils";
import type { FileEntry } from "@/types";

const joinPath = (base: string, name: string) => (base ? `${base}/${name}` : name);

export default function Files() {
  // A proteção contra path traversal fica no servidor (resolve_safe_path); aqui só montamos
  // caminhos a partir dos nomes que o próprio servidor listou.
  const [path, setPath] = useState("");
  const [openFile, setOpenFile] = useState<string | null>(null);
  const [content, setContent] = useState<{ text: string | null; error: string | null }>({ text: null, error: null });

  const listing = useApi<{ path: string; entries: FileEntry[] }>(`/files?path=${encodeURIComponent(path)}`);

  useEffect(() => {
    if (openFile === null) return;
    const controller = new AbortController();
    setContent({ text: null, error: null });
    api<{ content: string }>(`/files/content?path=${encodeURIComponent(openFile)}`, {}, controller.signal)
      .then((data) => setContent({ text: data.content, error: null }))
      .catch((err: unknown) => {
        if (!controller.signal.aborted) setContent({ text: null, error: err instanceof Error ? err.message : "Erro ao abrir o arquivo" });
      });
    return () => controller.abort();
  }, [openFile]);

  function openDirectory(next: string) {
    setPath(next);
    setOpenFile(null);
  }

  // Pastas primeiro, depois arquivos, cada grupo em ordem alfabética.
  const entries = [...(listing.data?.entries ?? [])].sort((a, b) => (a.is_dir === b.is_dir ? a.name.localeCompare(b.name) : a.is_dir ? -1 : 1));
  const totalBytes = entries.filter((e) => !e.is_dir).reduce((sum, e) => sum + (e.size_bytes ?? 0), 0);
  const parts = path ? path.split("/") : [];
  const loaded = listing.data !== null;

  return (
    <AdminPage
      title="Explorador de arquivos"
      subtitle={
        <>
          Somente leitura, restrito à pasta <code className="rounded bg-surface-2 px-1">data/</code>. Abre <code className="rounded bg-surface-2 px-1">.csv</code>,{" "}
          <code className="rounded bg-surface-2 px-1">.txt</code> e <code className="rounded bg-surface-2 px-1">.json</code> de até 1 MB.
        </>
      }
    >
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Stat id="folder-count" label="Itens nesta pasta" icon={ListTree} loading={!loaded} value={entries.length} format={(n) => formatNumber(Math.round(n))} />
        <Stat id="folder-size" label="Tamanho total" icon={HardDrive} loading={!loaded} value={totalBytes} format={formatBytes} />
      </div>

      <Card className="p-4">
        <nav id="breadcrumb" aria-label="Caminho" className="flex flex-wrap items-center gap-1 text-sm">
          <button type="button" onClick={() => openDirectory("")} className="rounded px-1 font-medium text-accent hover:underline">
            data
          </button>
          {parts.map((part, index) => (
            <Fragment key={index}>
              <span className="text-subtle">/</span>
              <button type="button" onClick={() => openDirectory(parts.slice(0, index + 1).join("/"))} className="rounded px-1 font-medium text-accent hover:underline">
                {part}
              </button>
            </Fragment>
          ))}
        </nav>

        {listing.error && !listing.data ? (
          <div className="mt-4">
            <ErrorPanel title="Não foi possível abrir a pasta" message={listing.error} />
          </div>
        ) : (
          <div className="scroll-thin -mx-1 mt-3 overflow-x-auto px-1">
            <table className="w-full min-w-[420px] text-sm">
              <thead>
                <tr className="text-left text-[11px] font-semibold tracking-[0.08em] text-subtle uppercase">
                  <th className="py-2 pr-3 font-semibold">Nome</th>
                  <th className="py-2 pl-3 text-right font-semibold">Tamanho</th>
                </tr>
              </thead>
              <tbody id="files-table-body">
                {!loaded && (
                  <tr className="border-t border-border">
                    <td colSpan={2} className="py-3">
                      <Skeleton className="h-6 w-full" />
                    </td>
                  </tr>
                )}
                {entries.map((entry) => {
                  const Icon = entry.is_dir ? Folder : FileIcon;
                  const target = joinPath(path, entry.name);
                  return (
                    <tr key={entry.name} className="border-t border-border transition-colors hover:bg-surface-2/60">
                      <td className="py-2 pr-3">
                        <button
                          type="button"
                          data-entry={entry.is_dir ? "dir" : "file"}
                          onClick={() => (entry.is_dir ? openDirectory(target) : setOpenFile(target))}
                          className="flex items-center gap-2.5 text-left font-medium hover:text-accent"
                        >
                          <Icon className={entry.is_dir ? "size-4 text-accent" : "size-4 text-muted"} />
                          <span className="break-all">{entry.name}</span>
                        </button>
                      </td>
                      <td className="py-2 pl-3 text-right whitespace-nowrap text-muted tabular-nums">{entry.is_dir ? "—" : formatBytes(entry.size_bytes ?? 0)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {loaded && entries.length === 0 && <EmptyState title="Esta pasta está vazia." message="Não há arquivos nem subpastas aqui." />}
          </div>
        )}
      </Card>

      {openFile !== null && (
        <Card id="viewer" className="p-4">
          <CardHeader className="items-center">
            <CardTitle id="viewer-title" className="flex items-center gap-2 break-all">
              <FolderOpen className="size-4 shrink-0 text-accent" /> {openFile}
            </CardTitle>
            <button type="button" id="viewer-close" onClick={() => setOpenFile(null)} className={buttonStyles({ size: "sm" })}>
              <X className="size-3.5" /> Fechar
            </button>
          </CardHeader>
          {content.error && (
            <div id="viewer-error" role="alert" className="mt-3 rounded-lg border border-danger/40 bg-danger/10 p-3 text-sm">
              {content.error}
            </div>
          )}
          {content.text === null && !content.error && <Skeleton className="mt-3 h-24 w-full" />}
          {content.text !== null && (
            // Conteúdo de arquivo é sempre exibido como texto: um .txt com HTML aparece literalmente.
            <pre id="viewer-content" className="scroll-thin mt-3 max-h-[60vh] overflow-auto rounded-lg border border-border bg-background p-3 font-mono text-xs whitespace-pre-wrap">
              {content.text}
            </pre>
          )}
        </Card>
      )}
    </AdminPage>
  );
}
