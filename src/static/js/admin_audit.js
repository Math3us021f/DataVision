// Todo texto vindo da API é inserido com textContent (nunca innerHTML),
// para que um nome de usuário ou detalhe malicioso apareça como texto e não seja executado (XSS).

const PAGE_SIZE = 20;

const tableBody = document.getElementById("audit-table-body");
const auditCount = document.getElementById("audit-count");
const stateBox = document.getElementById("audit-state");
const searchInput = document.getElementById("audit-search");
const actionSelect = document.getElementById("audit-action");
const prevButton = document.getElementById("audit-prev");
const nextButton = document.getElementById("audit-next");

const state = { page: 1, search: "", action: "", total: 0 };

const ACTION_LABELS = {
    create_user: "Criação de usuário",
    activate_user: "Ativação de usuário",
    deactivate_user: "Desativação de usuário",
    delete_user: "Exclusão de usuário",
    force_delete_user_datasets: "Exclusão forçada de datasets",
    reset_password: "Redefinição de senha (admin)",
    change_own_password: "Troca da própria senha",
};

function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
}

function renderSkeleton(rows = 5) {
    tableBody.replaceChildren();
    for (let i = 0; i < rows; i++) {
        const row = el("tr", "skeleton-row");
        for (let c = 0; c < 5; c++) row.append(el("td", "", "."));
        tableBody.append(row);
    }
}

function formatWhen(isoString) {
    return new Date(isoString).toLocaleString("pt-BR");
}

function renderPagination() {
    const totalPages = Math.max(1, Math.ceil(state.total / PAGE_SIZE));
    const first = state.total === 0 ? 0 : (state.page - 1) * PAGE_SIZE + 1;
    const last = Math.min(state.page * PAGE_SIZE, state.total);

    document.getElementById("audit-range").textContent = `Mostrando ${first}–${last} de ${state.total}`;
    document.getElementById("audit-page").textContent = `Página ${state.page} de ${totalPages}`;
    prevButton.disabled = state.page <= 1;
    nextButton.disabled = state.page >= totalPages;
}

function renderEntries(entries) {
    tableBody.replaceChildren();
    stateBox.hidden = true;
    if (entries.length === 0) {
        const filtering = state.search || state.action;
        renderState(stateBox, {
            kind: "empty",
            title: "Nenhum registro encontrado",
            message: filtering ? "Tente outro termo de busca ou mude o filtro de ação." : "Nenhuma ação administrativa foi registrada ainda.",
        });
    }

    for (const entry of entries) {
        const row = el("tr");

        row.append(el("td", "", formatWhen(entry.created_at)));
        row.append(el("td", "", ACTION_LABELS[entry.action] || entry.action));
        row.append(el("td", "", entry.actor_username || "—"));
        row.append(el("td", "", entry.target_username || "—"));
        row.append(el("td", "muted", entry.details || "—"));

        tableBody.append(row);
    }
}

async function loadActions() {
    try {
        const actions = await apiRequest("/audit-logs/actions");
        for (const action of actions) {
            const option = el("option", "", ACTION_LABELS[action] || action);
            option.value = action;
            actionSelect.append(option);
        }
    } catch {
        // Sem a lista de ações, o filtro fica só com "Todas" — não é crítico.
    }
}

async function loadAudit() {
    const params = new URLSearchParams({
        page: state.page,
        page_size: PAGE_SIZE,
        search: state.search,
        action: state.action,
    });

    try {
        const data = await apiRequest(`/audit-logs?${params}`);
        state.total = data.total;

        const totalPages = Math.max(1, Math.ceil(data.total / PAGE_SIZE));
        if (state.page > totalPages) {
            state.page = totalPages;
            return loadAudit();
        }

        auditCount.textContent = `${data.total} ${data.total === 1 ? "registro" : "registros"}`;
        renderEntries(data.items);
        renderPagination();
    } catch (err) {
        tableBody.replaceChildren();
        renderState(stateBox, { kind: "error", title: "Não foi possível carregar a auditoria", message: err.message });
    }
}

let searchTimer = null;
searchInput.addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
        state.search = searchInput.value.trim();
        state.page = 1;
        loadAudit();
    }, 300);
});

actionSelect.addEventListener("change", () => {
    state.action = actionSelect.value;
    state.page = 1;
    loadAudit();
});

prevButton.addEventListener("click", () => {
    state.page -= 1;
    loadAudit();
});

nextButton.addEventListener("click", () => {
    state.page += 1;
    loadAudit();
});

renderSkeleton();
loadActions();
loadAudit();
