// Todo texto vindo da API é inserido com textContent (nunca innerHTML),
// para que um nome de usuário malicioso apareça como texto e não seja executado (XSS).

const PAGE_SIZE = 20;

const tableBody = document.getElementById("users-table-body");
const usersCount = document.getElementById("users-count");
const emptyState = document.getElementById("users-empty");
const searchInput = document.getElementById("users-search");
const statusSelect = document.getElementById("users-status");
const prevButton = document.getElementById("users-prev");
const nextButton = document.getElementById("users-next");

const state = { page: 1, search: "", status: "all", total: 0 };

// Seleção guardada por id: sobrevive à troca de página e à busca.
const selected = new Map();
let currentPageUsers = [];

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

function renderPagination() {
    const totalPages = Math.max(1, Math.ceil(state.total / PAGE_SIZE));
    const first = state.total === 0 ? 0 : (state.page - 1) * PAGE_SIZE + 1;
    const last = Math.min(state.page * PAGE_SIZE, state.total);

    document.getElementById("users-range").textContent = `Mostrando ${first}–${last} de ${state.total}`;
    document.getElementById("users-page").textContent = `Página ${state.page} de ${totalPages}`;
    prevButton.disabled = state.page <= 1;
    nextButton.disabled = state.page >= totalPages;
}

function renderUsers(users) {
    currentPageUsers = users;
    tableBody.replaceChildren();
    emptyState.hidden = users.length > 0;

    for (const user of users) {
        const isMe = user.username === window.CURRENT_USERNAME;
        const row = el("tr");
        row.classList.toggle("is-selected", selected.has(user.id));

        const checkCell = el("td", "col-check");
        const check = el("input", "row-check");
        check.type = "checkbox";
        check.checked = selected.has(user.id);
        check.disabled = isMe;  // a própria conta não entra em ações em lote
        check.setAttribute("aria-label", `Selecionar ${user.username}`);
        check.addEventListener("change", () => {
            if (check.checked) selected.set(user.id, user);
            else selected.delete(user.id);
            row.classList.toggle("is-selected", check.checked);
            updateBulkBar();
        });
        checkCell.append(check);
        row.append(checkCell);

        const userCell = el("td");
        const wrapper = el("div", "user-cell");
        wrapper.append(el("span", "avatar", initialOf(user.username)), el("span", "", user.username));
        if (isMe) wrapper.append(el("span", "badge badge--neutral badge--plain", "você"));
        userCell.append(wrapper);

        const roleCell = el("td");
        roleCell.append(
            el("span", user.is_admin ? "badge badge--accent badge--plain" : "badge badge--neutral badge--plain",
                user.is_admin ? "Administrador" : "Usuário"),
        );

        const statusCell = el("td");
        statusCell.append(
            el("span", user.is_active ? "badge badge--success" : "badge badge--danger",
                user.is_active ? "Ativo" : "Inativo"),
        );

        const actionCell = el("td", "actions");
        const group = el("div", "actions-group");

        const resetButton = el("button", "button--small button--secondary", "Redefinir senha");
        // A própria senha se troca em "Minha conta", exigindo a senha atual.
        resetButton.disabled = isMe;
        resetButton.title = isMe ? "Troque sua senha em Minha conta" : "";
        resetButton.addEventListener("click", () => openResetDialog(user));

        const toggleButton = el("button",
            `button--small ${user.is_active ? "button--ghost-danger" : "button--ghost-success"}`,
            user.is_active ? "Desativar" : "Ativar");
        // O backend já impede o admin de se desativar; aqui só evitamos o clique inútil.
        toggleButton.disabled = isMe;
        toggleButton.addEventListener("click", () => toggleActive(user));

        const deleteButton = el("button", "button--small button--danger", "Excluir");
        deleteButton.disabled = isMe;
        deleteButton.addEventListener("click", () => deleteUser(user));

        group.append(resetButton, toggleButton, deleteButton);
        actionCell.append(group);
        row.append(userCell, roleCell, statusCell, actionCell);
        tableBody.append(row);
    }
}

async function loadUsers() {
    const params = new URLSearchParams({
        page: state.page,
        page_size: PAGE_SIZE,
        status: state.status,
        search: state.search,
    });

    try {
        const data = await apiRequest(`/users?${params}`);
        state.total = data.total;

        // Se a página atual ficou vazia (ex: filtro mudou), volta para a última existente.
        const totalPages = Math.max(1, Math.ceil(data.total / PAGE_SIZE));
        if (state.page > totalPages) {
            state.page = totalPages;
            return loadUsers();
        }

        usersCount.textContent = `${data.total} ${data.total === 1 ? "usuário encontrado" : "usuários encontrados"}`;
        renderUsers(data.items);
        renderPagination();
        updateBulkBar();
    } catch (err) {
        showToast(err.message, "error");
    }
}

async function toggleActive(user) {
    if (user.is_active) {
        const confirmed = await confirmAction({
            title: "Desativar usuário?",
            message: `"${user.username}" não conseguirá mais entrar, e sessões abertas deixam de valer imediatamente. Dá para reativar depois.`,
            confirmLabel: "Desativar",
        });
        if (!confirmed) return;
    }

    try {
        await apiRequest(`/users/${user.id}`, {
            method: "PATCH",
            body: JSON.stringify({ is_active: !user.is_active }),
        });
        showToast(`Usuário "${user.username}" ${user.is_active ? "desativado" : "ativado"}.`, "success");
        await loadUsers();
    } catch (err) {
        showToast(err.message, "error");
    }
}

async function deleteUser(user) {
    const confirmed = await confirmAction({
        title: "Excluir usuário permanentemente?",
        message: `"${user.username}" será apagado e não poderá ser recuperado. O histórico de auditoria é mantido. Se a ideia é só bloquear o acesso, prefira Desativar.`,
        confirmLabel: "Excluir",
    });
    if (!confirmed) return;

    try {
        await apiRequest(`/users/${user.id}`, { method: "DELETE" });
        selected.delete(user.id);
        showToast(`Usuário "${user.username}" excluído.`, "success");
        await loadUsers();
    } catch (err) {
        showToast(err.message, "error");
    }
}

// ---------- Seleção e ações em lote ----------

const selectAll = document.getElementById("select-all");
const bulkBar = document.getElementById("bulk-bar");

function selectableOnPage() {
    return currentPageUsers.filter((u) => u.username !== window.CURRENT_USERNAME);
}

function updateBulkBar() {
    bulkBar.hidden = selected.size === 0;
    document.getElementById("bulk-count").textContent =
        `${selected.size} ${selected.size === 1 ? "usuário selecionado" : "usuários selecionados"}`;

    const onPage = selectableOnPage();
    const checkedOnPage = onPage.filter((u) => selected.has(u.id)).length;
    selectAll.checked = onPage.length > 0 && checkedOnPage === onPage.length;
    selectAll.indeterminate = checkedOnPage > 0 && checkedOnPage < onPage.length;
}

selectAll.addEventListener("change", () => {
    for (const user of selectableOnPage()) {
        if (selectAll.checked) selected.set(user.id, user);
        else selected.delete(user.id);
    }
    renderUsers(currentPageUsers);
    updateBulkBar();
});

document.getElementById("bulk-clear").addEventListener("click", () => {
    selected.clear();
    renderUsers(currentPageUsers);
    updateBulkBar();
});

// Chama o endpoint de cada usuário, um por vez: cada um passa pelas mesmas
// validações e entra na auditoria individualmente. Falhas não interrompem o lote.
async function runBulk(users, request, verb) {
    let ok = 0;
    const failures = [];
    for (const user of users) {
        try {
            await request(user);
            ok += 1;
            selected.delete(user.id);
        } catch (err) {
            failures.push(`${user.username}: ${err.message}`);
        }
    }

    if (ok) showToast(`${ok} ${ok === 1 ? "usuário" : "usuários"} ${verb}.`, "success");
    if (failures.length) {
        showToast(`${failures.length} não ${failures.length === 1 ? "pôde" : "puderam"} ser ${verb}. ${failures[0]}`, "error");
    }
    await loadUsers();
}

document.getElementById("bulk-activate").addEventListener("click", () => {
    const users = [...selected.values()];
    runBulk(users, (u) => apiRequest(`/users/${u.id}`, {
        method: "PATCH", body: JSON.stringify({ is_active: true }),
    }), "ativados");
});

document.getElementById("bulk-deactivate").addEventListener("click", async () => {
    const users = [...selected.values()];
    const confirmed = await confirmAction({
        title: `Desativar ${users.length} ${users.length === 1 ? "usuário" : "usuários"}?`,
        message: "Eles não conseguirão mais entrar, e sessões abertas deixam de valer imediatamente. Dá para reativar depois.",
        confirmLabel: "Desativar",
    });
    if (!confirmed) return;
    runBulk(users, (u) => apiRequest(`/users/${u.id}`, {
        method: "PATCH", body: JSON.stringify({ is_active: false }),
    }), "desativados");
});

document.getElementById("bulk-delete").addEventListener("click", async () => {
    const users = [...selected.values()];
    const confirmed = await confirmAction({
        title: `Excluir ${users.length} ${users.length === 1 ? "usuário" : "usuários"} permanentemente?`,
        message: "Não dá para desfazer. O histórico de auditoria é mantido. Usuários com datasets serão pulados (desative-os em vez disso).",
        confirmLabel: `Excluir ${users.length}`,
    });
    if (!confirmed) return;
    runBulk(users, (u) => apiRequest(`/users/${u.id}`, { method: "DELETE" }), "excluídos");
});

// ---------- Redefinir senha ----------

const resetDialog = document.getElementById("reset-dialog");
const resetForm = document.getElementById("reset-form");
const resetPassword = document.getElementById("reset-password");
const resetError = document.getElementById("reset-error");
let resetTarget = null;

function openResetDialog(user) {
    resetTarget = user;
    document.getElementById("reset-username").textContent = user.username;
    resetForm.reset();
    resetError.hidden = true;
    resetDialog.showModal();
    resetPassword.focus();
}

document.getElementById("reset-cancel").addEventListener("click", () => resetDialog.close());

resetForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    resetError.hidden = true;

    try {
        await apiRequest(`/users/${resetTarget.id}/password`, {
            method: "PUT",
            body: JSON.stringify({ new_password: resetPassword.value }),
        });
        resetDialog.close();
        showToast(`Senha de "${resetTarget.username}" redefinida.`, "success");
    } catch (err) {
        resetError.textContent = err.message;
        resetError.hidden = false;
    }
});

// ---------- Criar usuário ----------

document.getElementById("create-user-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const submit = document.getElementById("create-user-submit");
    submit.disabled = true;

    try {
        const created = await apiRequest("/users", {
            method: "POST",
            body: JSON.stringify({
                username: document.getElementById("new-username").value.trim(),
                password: document.getElementById("new-password").value,
                is_admin: document.getElementById("new-is-admin").checked,
            }),
        });
        showToast(`Usuário "${created.username}" criado.`, "success");
        event.target.reset();
        await loadUsers();
    } catch (err) {
        showToast(err.message, "error");
    } finally {
        submit.disabled = false;
    }
});

// ---------- Busca, filtro e paginação ----------

let searchTimer = null;
searchInput.addEventListener("input", () => {
    clearTimeout(searchTimer);
    // Espera o usuário parar de digitar antes de chamar a API.
    searchTimer = setTimeout(() => {
        state.search = searchInput.value.trim();
        state.page = 1;
        loadUsers();
    }, 300);
});

statusSelect.addEventListener("change", () => {
    state.status = statusSelect.value;
    state.page = 1;
    loadUsers();
});

prevButton.addEventListener("click", () => {
    state.page -= 1;
    loadUsers();
});

nextButton.addEventListener("click", () => {
    state.page += 1;
    loadUsers();
});

renderSkeleton();
loadUsers();
