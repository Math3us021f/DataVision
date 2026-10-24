const REFRESH_INTERVAL_MS = 5000;

let timerId = null;

function formatBytes(bytes) {
    const units = ["B", "KB", "MB", "GB", "TB"];
    let value = bytes;
    let unit = 0;
    while (value >= 1024 && unit < units.length - 1) {
        value /= 1024;
        unit += 1;
    }
    return `${value.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
}

function setPercent(valueId, barId, percent) {
    document.getElementById(valueId).textContent = `${percent.toFixed(1)}%`;
    const bar = document.getElementById(barId);
    bar.style.width = `${Math.min(percent, 100)}%`;
    bar.classList.toggle("bar__fill--warning", percent >= 70 && percent < 90);
    bar.classList.toggle("bar__fill--danger", percent >= 90);
}

function render(metrics) {
    document.getElementById("metrics-scope").textContent = metrics.aviso_escopo;

    setPercent("cpu-value", "cpu-bar", metrics.cpu_percent);

    setPercent("memory-value", "memory-bar", metrics.memory.percent);
    document.getElementById("memory-detail").textContent =
        `${formatBytes(metrics.memory.used_bytes)} de ${formatBytes(metrics.memory.total_bytes)}`;

    setPercent("disk-value", "disk-bar", metrics.disk.percent);
    document.getElementById("disk-detail").textContent =
        `${formatBytes(metrics.disk.used_bytes)} de ${formatBytes(metrics.disk.total_bytes)}`;

    document.getElementById("net-sent").textContent = formatBytes(metrics.network.bytes_sent);
    document.getElementById("net-recv").textContent = formatBytes(metrics.network.bytes_recv);

    document.getElementById("metrics-updated").textContent =
        `Atualizado às ${new Date().toLocaleTimeString("pt-BR")}`;
}

async function refresh() {
    const errorEl = document.getElementById("metrics-error");
    try {
        render(await apiRequest("/metrics/system"));
        errorEl.hidden = true;
        schedule();
    } catch (err) {
        // Sessão expirada ou permissão retirada: para de atualizar em vez de insistir.
        errorEl.textContent = `${err.message}. Atualização automática interrompida — recarregue a página.`;
        errorEl.hidden = false;
    }
}

function schedule() {
    clearTimeout(timerId);
    if (!document.hidden) {
        timerId = setTimeout(refresh, REFRESH_INTERVAL_MS);
    }
}

// Não fica consultando a API com a aba em segundo plano; retoma ao voltar.
document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
        clearTimeout(timerId);
    } else {
        refresh();
    }
});

refresh();
