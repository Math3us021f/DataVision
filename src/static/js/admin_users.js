// Todo texto vindo da API é inserido com textContent (nunca innerHTML),
// para que um nome de usuário malicioso apareça como texto e não seja executado (XSS).

const PAGE_SIZE = 20;

const tableBody = document.getElementById("users-table-body");
const usersCount = document.getElementById("users-count");
const stateBox = document.getElementById("users-state");
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

// ---------- Menu de ações por linha ("⋯") ----------

function closeAllRowMenus() {
    document.querySelectorAll(".row-menu__list").forEach((list) => {
        list.hidden = true;
        list.previousElementSibling.setAttribute("aria-expanded", "false");
    });
}

function buildRowMenu(items, username) {
    const wrapper = el("div", "row-menu");

    const trigger = el("button", "icon-button row-menu__trigger");
    trigger.type = "button";
    trigger.setAttribute("aria-haspopup", "menu");
    trigger.setAttribute("aria-expanded", "false");
    trigger.setAttribute("aria-label", `Ações para ${username}`);
    trigger.append(document.getElementById("icon-more").content.cloneNode(true));

    const list = el("div", "row-menu__list");
    list.setAttribute("role", "menu");
    list.hidden = true;

    for (const item of items) {
        const option = el("button", `row-menu__item${item.danger ? " row-menu__item--danger" : ""}`, item.label);
        option.type = "button";
        option.setAttribute("role", "menuitem");
        option.addEventListener("click", () => {
            closeAllRowMenus();
            item.onClick();
        });
        list.append(option);
    }

    trigger.addEventListener("click", (event) => {
        event.stopPropagation();
        const willOpen = list.hidden;
        closeAllRowMenus();
        list.hidden = !willOpen;
        trigger.setAttribute("aria-expanded", String(willOpen));
        if (willOpen) list.querySelector("button").focus();
    });

    wrapper.append(trigger, list);
    return wrapper;
}

document.addEventListener("click", closeAllRowMenus);
document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeAllRowMenus();
});

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
    stateBox.hidden = true;
    if (users.length === 0) {
        const filtering = state.search || state.status !== "all";
        renderState(stateBox, {
            kind: "empty",
            title: "Nenhum usuário encontrado",
            message: filtering ? "Tente outro termo de busca ou mude o filtro de status." : "Crie o primeiro usuário pelo botão \"Novo usuário\".",
        });
    }

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
        if (isMe) {
            // A própria conta não tem ações aqui: a senha se troca em "Minha conta".
            actionCell.append(el("span", "muted", "—"));
        } else {
            actionCell.append(buildRowMenu([
                { label: "Redefinir senha", onClick: () => openResetDialog(user) },
                user.is_active
                    ? { label: "Desativar", onClick: () => toggleActive(user), danger: true }
                    : { label: "Ativar", onClick: () => toggleActive(user) },
                { label: "Excluir", onClick: () => deleteUser(user), danger: true },
            ], user.username));
        }
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

        usersCount.textContent = `${data.total} ${data.total === 1 ? "usuário" : "usuários"}`;
        renderUsers(data.items);
        renderPagination();
        updateBulkBar();
    } catch (err) {
        tableBody.replaceChildren();
        renderState(stateBox, { kind: "error", title: "Não foi possível carregar os usuários", message: err.message });
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
        if (err.status === 409) {
            await offerForceDelete(user, err.message);
            return;
        }
        showToast(err.message, "error");
    }
}

// Usuário com datasets: o servidor recusou (409) e explicou o motivo na mensagem.
// Uma segunda confirmação, mais séria, é exigida antes de apagar os arquivos junto.
async function offerForceDelete(user, reason) {
    const confirmed = await confirmAction({
        title: "Apagar também os datasets?",
        message: `${reason} Esta segunda confirmação apaga TUDO: usuário, datasets e arquivos no MinIO, sem volta.`,
        confirmLabel: "Apagar tudo",
    });
    if (!confirmed) return;

    try {
        await apiRequest(`/users/${user.id}?force=true`, { method: "DELETE" });
        selected.delete(user.id);
        showToast(`Usuário "${user.username}" e seus datasets foram excluídos.`, "success");
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
// Devolve { ok, failures } em vez de já mostrar o resultado, para quem chama decidir o que fazer
// com as falhas (ex: excluir em lote oferece forçar só quem falhou por ter datasets).
async function runBulk(users, request) {
    let ok = 0;
    const failures = [];
    for (const user of users) {
        try {
            await request(user);
            ok += 1;
            selected.delete(user.id);
        } catch (err) {
            failures.push({ user, err });
        }
    }
    return { ok, failures };
}

function reportBulkResult({ ok, failures }, verb) {
    if (ok) showToast(`${ok} ${ok === 1 ? "usuário" : "usuários"} ${verb}.`, "success");
    if (failures.length) {
        showToast(
            `${failures.length} não ${failures.length === 1 ? "pôde" : "puderam"} ser ${verb}. ${failures[0].user.username}: ${failures[0].err.message}`,
            "error",
        );
    }
}

document.getElementById("bulk-activate").addEventListener("click", async () => {
    const users = [...selected.values()];
    reportBulkResult(await runBulk(users, (u) => apiRequest(`/users/${u.id}`, {
        method: "PATCH", body: JSON.stringify({ is_active: true }),
    })), "ativados");
    await loadUsers();
});

document.getElementById("bulk-deactivate").addEventListener("click", async () => {
    const users = [...selected.values()];
    const confirmed = await confirmAction({
        title: `Desativar ${users.length} ${users.length === 1 ? "usuário" : "usuários"}?`,
        message: "Eles não conseguirão mais entrar, e sessões abertas deixam de valer imediatamente. Dá para reativar depois.",
        confirmLabel: "Desativar",
    });
    if (!confirmed) return;
    reportBulkResult(await runBulk(users, (u) => apiRequest(`/users/${u.id}`, {
        method: "PATCH", body: JSON.stringify({ is_active: false }),
    })), "desativados");
    await loadUsers();
});

document.getElementById("bulk-delete").addEventListener("click", async () => {
    const users = [...selected.values()];
    const confirmed = await confirmAction({
        title: `Excluir ${users.length} ${users.length === 1 ? "usuário" : "usuários"} permanentemente?`,
        message: "Não dá para desfazer. O histórico de auditoria é mantido. Quem tiver datasets será pulado nesta primeira passada — você poderá optar por apagar os dados deles também, em seguida.",
        confirmLabel: `Excluir ${users.length}`,
    });
    if (!confirmed) return;

    const firstPass = await runBulk(users, (u) => apiRequest(`/users/${u.id}`, { method: "DELETE" }));
    if (firstPass.ok) showToast(`${firstPass.ok} ${firstPass.ok === 1 ? "usuário" : "usuários"} excluído(s).`, "success");

    const withDatasets = firstPass.failures.filter((f) => f.err.status === 409);
    const otherFailures = firstPass.failures.filter((f) => f.err.status !== 409);
    if (otherFailures.length) {
        showToast(
            `${otherFailures.length} não ${otherFailures.length === 1 ? "pôde" : "puderam"} ser excluído(s): ${otherFailures[0].user.username}: ${otherFailures[0].err.message}`,
            "error",
        );
    }

    if (withDatasets.length) {
        const confirmedForce = await confirmAction({
            title: `Apagar também os datasets de ${withDatasets.length} ${withDatasets.length === 1 ? "usuário" : "usuários"}?`,
            message: "Esta segunda confirmação apaga usuário, datasets e os arquivos correspondentes no MinIO, de todos os selecionados abaixo. Sem volta.",
            confirmLabel: "Apagar tudo",
        });
        if (confirmedForce) {
            const secondPass = await runBulk(
                withDatasets.map((f) => f.user),
                (u) => apiRequest(`/users/${u.id}?force=true`, { method: "DELETE" }),
            );
            reportBulkResult(secondPass, "excluídos (com datasets)");
        }
    }

    await loadUsers();
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

const createError = document.getElementById("create-user-error");

document.getElementById("create-user-drawer").addEventListener("close", () => {
    document.getElementById("create-user-form").reset();
    createError.hidden = true;
});

document.getElementById("create-user-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const submit = document.getElementById("create-user-submit");
    submit.disabled = true;
    createError.hidden = true;

    try {
        const created = await apiRequest("/users", {
            method: "POST",
            body: JSON.stringify({
                username: document.getElementById("new-username").value.trim(),
                password: document.getElementById("new-password").value,
                is_admin: document.getElementById("new-is-admin").checked,
            }),
        });
        closeDrawer("create-user-drawer");
        showToast(`Usuário "${created.username}" criado.`, "success");
        await loadUsers();
    } catch (err) {
        // O erro aparece dentro do painel, ao lado do formulário que o causou.
        createError.textContent = err.message;
        createError.hidden = false;
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
