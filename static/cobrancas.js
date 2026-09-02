// Financeiro -> Cobrancas: o modal "Marcar como cobrado" e compartilhado por
// todos os cards de cliente; o botao que abre o modal carrega a lista de
// despesas "a cobrar" daquele cliente em data-cobranca-despesas (JSON), no
// mesmo padrao de event.relatedTarget ja usado em Reembolsos
// (ver static/reembolsos.js).

document.addEventListener("DOMContentLoaded", () => {
    initCobrancaModal();

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

function novaCobrancaRegistroUid() {
    return (window.crypto && crypto.randomUUID)
        ? crypto.randomUUID()
        : Date.now() + "-" + Math.random().toString(16).slice(2);
}

function formatCobrancaCurrency(value) {
    return "R$ " + value.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function initCobrancaModal() {
    const modal = document.getElementById("modalMarcarCobrado");
    if (!modal) return;
    const list = modal.querySelector("[data-cobranca-despesas-list]");
    const valorDisplay = document.getElementById("cobrancaValor");
    const idField = document.getElementById("cobrancaClienteId");
    const nomeField = document.getElementById("cobrancaClienteNome");
    const registroUidField = document.getElementById("cobrancaRegistroUid");
    const form = document.getElementById("cobrancaForm");

    function recompute() {
        const checked = Array.from(list.querySelectorAll("input[type=checkbox]:checked"));
        const total = checked.reduce((sum, input) => sum + parseFloat(input.dataset.valor || "0"), 0);
        if (valorDisplay) valorDisplay.value = formatCobrancaCurrency(total);
    }

    modal.addEventListener("show.bs.modal", (event) => {
        const botao = event.relatedTarget;
        let despesas = [];
        try {
            despesas = JSON.parse(botao?.dataset.cobrancaDespesas || "[]");
        } catch {
            despesas = [];
        }
        if (idField) idField.value = botao?.dataset.cobrancaClienteId || "";
        if (nomeField) nomeField.textContent = botao?.dataset.cobrancaClienteNome || "Cliente";
        if (registroUidField) registroUidField.value = novaCobrancaRegistroUid();

        list.innerHTML = "";
        despesas.forEach((despesa) => {
            const row = document.createElement("label");
            row.className = "reembolso-despesa-check";
            const checkbox = document.createElement("input");
            checkbox.type = "checkbox";
            checkbox.name = "despesa_id";
            checkbox.value = despesa.id;
            checkbox.checked = true;
            checkbox.dataset.valor = despesa.valor_total;
            checkbox.addEventListener("change", recompute);
            const texto = document.createElement("span");
            texto.innerHTML = `<strong>${escapeHtml(despesa.descricao || "")}</strong> &mdash; ${formatCobrancaCurrency(Number(despesa.valor_total) || 0)}`;
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
            alert("Selecione ao menos uma despesa para cobrar.");
        }
    });

    modal.addEventListener("hidden.bs.modal", () => {
        const submitButton = modal.querySelector("button[type='submit']");
        if (submitButton) {
            submitButton.disabled = false;
            submitButton.textContent = "Marcar como cobrado";
        }
    });
}
