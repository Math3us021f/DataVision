// Textos vindos da API (nomes de arquivo, usuários) entram sempre com textContent.

const ACTION_LABELS = {
    create_user: "criou o usuário",
    activate_user: "ativou o usuário",
    deactivate_user: "desativou o usuário",
    reset_password: "redefiniu a senha de",
    change_own_password: "trocou a própria senha",
    delete_user: "excluiu um usuário",
};

function setStat(id, value, detail = "") {
    // Cartões só de admin não existem na página do usuário comum.
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = value;
    document.getElementById(`${id}-detail`).textContent = detail;
}

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

// A API devolve o horário com fuso; o navegador converte para o horário local.
function formatDate(iso) {
    return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

function activityItem(main, meta) {
    const li = document.createElement("li");
    li.className = "activity__item";
    const mainEl = document.createElement("span");
    mainEl.textContent = main;
    const metaEl = document.createElement("span");
    metaEl.className = "muted";
    metaEl.textContent = meta;
    li.append(mainEl, metaEl);
    return li;
}

function auditText(entry) {
    const actor = entry.actor ?? "usuário excluído";
    const action = ACTION_LABELS[entry.action] ?? entry.action;
    if (entry.action === "change_own_password") return `${actor} ${action}`;
    if (entry.action === "delete_user") return `${actor} ${action} (${entry.details ?? ""})`;
    return `${actor} ${action} ${entry.target ?? "(excluído)"}`;
}

function renderList(listId, items, emptyTitle, emptyMessage) {
    const list = document.getElementById(listId);
    list.replaceChildren(...items);
    if (items.length === 0) {
        renderState(document.getElementById(`${listId}-empty`), {
            kind: "empty", title: emptyTitle, message: emptyMessage,
        });
    }
}

async function loadSummary() {
    const data = await apiRequest("/dashboard/summary");

    setStat("stat-datasets", data.mine.datasets);
    setStat("stat-storage", formatBytes(data.mine.storage_bytes));
    setStat("stat-profiled", data.mine.profiled, `de ${data.mine.datasets}`);

    renderList(
        "recent-datasets",
        data.recent_datasets.map((d) => activityItem(d.original_name, `${formatBytes(d.size_bytes)} · ${formatDate(d.created_at)}`)),
        "Nenhum arquivo enviado",
        "Os arquivos que você enviar aparecerão aqui.",
    );

    if (data.admin) {
        setStat("stat-users", data.admin.users.active, `${data.admin.users.inactive} inativos · ${data.admin.users.total} no total`);
        setStat("stat-all-datasets", data.admin.datasets_total);
        renderList(
            "recent-audit",
            data.admin.recent_audit.map((e) => activityItem(auditText(e), formatDate(e.created_at))),
            "Nenhuma atividade registrada",
            "Ações administrativas aparecerão aqui.",
        );
    }
}

async function loadMetrics() {
    if (!document.getElementById("stat-cpu")) return;
    try {
        const m = await apiRequest("/metrics/system");
        setStat("stat-cpu", `${m.cpu_percent.toFixed(1)}%`);
        setStat("stat-memory", `${m.memory.percent.toFixed(1)}%`, `${formatBytes(m.memory.used_bytes)} de ${formatBytes(m.memory.total_bytes)}`);
    } catch {
        // Falha nas métricas não deve derrubar o resto do painel.
        setStat("stat-cpu", "—", "indisponível");
        setStat("stat-memory", "—", "indisponível");
    }
}

loadSummary().catch((err) => {
    document.getElementById("home-content").hidden = true;
    renderState(document.getElementById("home-error"), {
        kind: "error", title: "Não foi possível carregar o painel", message: err.message,
    });
});
loadMetrics();
