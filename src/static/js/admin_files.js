// Conteúdo de arquivos e nomes vindos da API entram sempre com textContent:
// um .txt com HTML ou <script> dentro é exibido como texto, nunca interpretado.
// A proteção contra path traversal fica no servidor (resolve_safe_path); aqui
// só montamos caminhos a partir dos nomes que o próprio servidor listou.

const tableBody = document.getElementById("files-table-body");
const breadcrumb = document.getElementById("breadcrumb");
const filesError = document.getElementById("files-error");
const emptyMessage = document.getElementById("files-empty");
const viewer = document.getElementById("viewer");
const viewerTitle = document.getElementById("viewer-title");
const viewerContent = document.getElementById("viewer-content");
const viewerError = document.getElementById("viewer-error");

let currentPath = "";

function joinPath(base, name) {
    return base ? `${base}/${name}` : name;
}

function formatBytes(bytes) {
    if (bytes === null || bytes === undefined) return "";
    const units = ["B", "KB", "MB", "GB"];
    let value = bytes;
    let unit = 0;
    while (value >= 1024 && unit < units.length - 1) {
        value /= 1024;
        unit += 1;
    }
    return `${value.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
}

function renderBreadcrumb() {
    breadcrumb.replaceChildren();

    const rootLink = document.createElement("a");
    rootLink.href = "#";
    rootLink.textContent = "data";
    rootLink.addEventListener("click", (e) => {
        e.preventDefault();
        openDirectory("");
    });
    breadcrumb.append(rootLink);

    const parts = currentPath ? currentPath.split("/") : [];
    parts.forEach((part, index) => {
        const separator = document.createElement("span");
        separator.textContent = " / ";
        breadcrumb.append(separator);

        const target = parts.slice(0, index + 1).join("/");
        const link = document.createElement("a");
        link.href = "#";
        link.textContent = part;
        link.addEventListener("click", (e) => {
            e.preventDefault();
            openDirectory(target);
        });
        breadcrumb.append(link);
    });
}

function renderEntries(entries) {
    tableBody.replaceChildren();
    emptyMessage.hidden = entries.length > 0;

    // Pastas primeiro, depois arquivos, cada grupo em ordem alfabética.
    const sorted = [...entries].sort((a, b) =>
        a.is_dir === b.is_dir ? a.name.localeCompare(b.name) : a.is_dir ? -1 : 1,
    );

    for (const entry of sorted) {
        const row = document.createElement("tr");

        const nameCell = document.createElement("td");
        const link = document.createElement("a");
        link.href = "#";
        link.className = entry.is_dir ? "entry entry--dir" : "entry entry--file";
        link.textContent = entry.is_dir ? `${entry.name}/` : entry.name;
        link.addEventListener("click", (e) => {
            e.preventDefault();
            const path = joinPath(currentPath, entry.name);
            if (entry.is_dir) {
                openDirectory(path);
            } else {
                openFile(path);
            }
        });
        nameCell.append(link);

        const sizeCell = document.createElement("td");
        sizeCell.textContent = entry.is_dir ? "—" : formatBytes(entry.size_bytes);

        row.append(nameCell, sizeCell);
        tableBody.append(row);
    }
}

async function openDirectory(path) {
    filesError.hidden = true;
    try {
        const data = await apiRequest(`/files?path=${encodeURIComponent(path)}`);
        currentPath = path;
        viewer.hidden = true;
        renderBreadcrumb();
        renderEntries(data.entries);
    } catch (err) {
        filesError.textContent = err.message;
        filesError.hidden = false;
    }
}

async function openFile(path) {
    viewer.hidden = false;
    viewerTitle.textContent = path;
    viewerContent.textContent = "";
    viewerContent.hidden = true;
    viewerError.hidden = true;

    try {
        const data = await apiRequest(`/files/content?path=${encodeURIComponent(path)}`);
        viewerContent.textContent = data.content;
        viewerContent.hidden = false;
    } catch (err) {
        viewerError.textContent = err.message;
        viewerError.hidden = false;
    }
}

document.getElementById("viewer-close").addEventListener("click", () => {
    viewer.hidden = true;
});

openDirectory("");
