// Financeiro -> Reembolsos: o modal "Registrar reembolso" e compartilhado por
// todos os cards de pessoa; o botao que abre o modal carrega a lista de
// despesas pendentes daquela pessoa em data-reembolso-despesas (JSON), no
// mesmo padrao de event.relatedTarget ja usado nos modais de custo/pagamento
// em financeiro.html.

document.addEventListener("DOMContentLoaded", () => {
    initReembolsoModal();
    initReembolsoDropzone();

    document.querySelectorAll("[data-modal-finance-form]").forEach((formulario) => {
        formulario.addEventListener("submit", () => {
            const botao = formulario.querySelector("button[type='submit']");
            if (botao) {
                botao.disabled = true;
                botao.textContent = "Salvando...";
            }
        });
    });
});

function novoReembolsoRegistroUid() {
    return (window.crypto && crypto.randomUUID)
        ? crypto.randomUUID()
        : Date.now() + "-" + Math.random().toString(16).slice(2);
}

function formatReembolsoCurrency(value) {
    return "R$ " + value.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function initReembolsoModal() {
    const modal = document.getElementById("modalRegistrarReembolso");
    if (!modal) return;
    const list = modal.querySelector("[data-reembolso-despesas-list]");
    const valorDisplay = document.getElementById("reembolsoValor");
    const idField = document.getElementById("reembolsoDesembolsanteId");
    const nomeField = document.getElementById("reembolsoDesembolsanteNome");
    const registroUidField = document.getElementById("reembolsoRegistroUid");
    const form = document.getElementById("reembolsoForm");

    function recompute() {
        const checked = Array.from(list.querySelectorAll("input[type=checkbox]:checked"));
        const total = checked.reduce((sum, input) => sum + parseFloat(input.dataset.valor || "0"), 0);
        if (valorDisplay) valorDisplay.value = formatReembolsoCurrency(total);
    }

    modal.addEventListener("show.bs.modal", (event) => {
        const botao = event.relatedTarget;
        let despesas = [];
        try {
            despesas = JSON.parse(botao?.dataset.reembolsoDespesas || "[]");
        } catch {
            despesas = [];
        }
        if (idField) idField.value = botao?.dataset.reembolsoDesembolsanteId || "";
        if (nomeField) nomeField.textContent = botao?.dataset.reembolsoDesembolsanteNome || "Pessoa";
        if (registroUidField) registroUidField.value = novoReembolsoRegistroUid();

        list.innerHTML = "";
        despesas.forEach((despesa) => {
            const row = document.createElement("label");
            row.className = "reembolso-despesa-check";
            const checkbox = document.createElement("input");
            checkbox.type = "checkbox";
            checkbox.name = "despesa_id";
            checkbox.value = despesa.id;
            checkbox.checked = true;
            checkbox.dataset.valor = despesa.saldo_pendente;
            checkbox.addEventListener("change", recompute);
            const texto = document.createElement("span");
            texto.innerHTML = `<strong>${escapeHtml(despesa.descricao || "")}</strong> &mdash; ${formatReembolsoCurrency(Number(despesa.saldo_pendente) || 0)}`;
            row.appendChild(checkbox);
            row.appendChild(texto);
            list.appendChild(row);
        });
        recompute();
    });

    form?.addEventListener("submit", (event) => {
        const checked = list.querySelectorAll("input[type=checkbox]:checked");
        if (!checked.length) {
            event.preventDefault();
            alert("Selecione ao menos uma despesa para reembolsar.");
        }
    });

    modal.addEventListener("hidden.bs.modal", () => {
        const submitButton = modal.querySelector("button[type='submit']");
        if (submitButton) {
            submitButton.disabled = false;
            submitButton.textContent = "Confirmar reembolso";
        }
    });
}

function initReembolsoDropzone() {
    const dropzone = document.querySelector("[data-reembolso-dropzone]");
    const fileInput = document.getElementById("reembolsoComprovanteInput");
    const filePill = document.querySelector("[data-reembolso-file-pill]");
    if (!dropzone || !fileInput) return;

    function updateUi() {
        const arquivo = fileInput.files?.[0];
        dropzone.classList.toggle("has-file", Boolean(arquivo));
        if (filePill) {
            filePill.hidden = !arquivo;
            filePill.textContent = arquivo ? arquivo.name : "Nenhum arquivo selecionado";
        }
    }

    function assignSingleFile(file) {
        if (!file || !window.DataTransfer) return false;
        const transfer = new DataTransfer();
        transfer.items.add(file);
        fileInput.files = transfer.files;
        return true;
    }

    fileInput.addEventListener("change", updateUi);
    dropzone.addEventListener("click", () => fileInput.click());
    dropzone.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            fileInput.click();
        }
    });
    ["dragenter", "dragover"].forEach((eventName) => {
        dropzone.addEventListener(eventName, (event) => {
            event.preventDefault();
            dropzone.classList.add("is-dragover");
        });
    });
    ["dragleave", "dragend", "drop"].forEach((eventName) => {
        dropzone.addEventListener(eventName, (event) => {
            event.preventDefault();
            if (eventName !== "drop" || !dropzone.contains(event.relatedTarget)) {
                dropzone.classList.remove("is-dragover");
            }
        });
    });
    dropzone.addEventListener("drop", (event) => {
        const arquivo = event.dataTransfer?.files?.[0];
        if (!arquivo || !assignSingleFile(arquivo)) return;
        updateUi();
    });
}
