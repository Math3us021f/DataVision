/** Envio com progresso real: o fetch não expõe o progresso de upload, o XMLHttpRequest sim. */
export function uploadDataset(file: File, onProgress: (percent: number) => void): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/datasets/upload");
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) return resolve();
      if (xhr.status === 401) window.location.href = "/login";
      let message = `Erro ${xhr.status}`;
      try {
        const detail = JSON.parse(xhr.responseText).detail;
        if (typeof detail === "string") message = detail;
      } catch {
        // corpo não era JSON
      }
      reject(new Error(message));
    };
    xhr.onerror = () => reject(new Error("Falha de conexão"));

    const body = new FormData();
    body.append("file", file);
    xhr.send(body);
  });
}
