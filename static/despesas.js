// Financeiro -> Despesas: autocomplete local de projeto (mesmo padrao visual
// do autocomplete de cliente, sem a parte de "criar novo"), linhas dinamicas
// de divisao entre projetos com soma ao vivo, e o dropzone de comprovante
// (mesmo comportamento do dropzone de custo em financeiro.html).

document.addEventListener("DOMContentLoaded", () => {
    initDespesaProjetoAutocompletes();
    initDespesaAlocacaoRows();
    initDespesaDesembolsoToggle();
    initDespesaDropzone();
    initDespesaModalReset();

    document.getElementById("despesaValorTotal")?.addEventListener("input", () => {
        recomputeDespesaTotal(document.getElementById("despesaForm"));
    });

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

function despesaProjetos() {
    return Array.isArray(window.despesaProjetosOptions) ? window.despesaProjetosOptions : [];
}

function despesaNormalize(value) {
    if (window.SearchUtils) return window.SearchUtils.normalizeSearchText(value);
    return String(value || "").toLowerCase().trim();
}

function initDespesaProjetoAutocompletes(root = document) {
    root.querySelectorAll("[data-despesa-projeto-autocomplete]").forEach((widget) => {
        if (widget.dataset.despesaProjetoReady === "1") return;
        const input = widget.querySelector("[data-despesa-projeto-input]");
        const hidden = widget.querySelector("[data-despesa-projeto-id]");
        const list = widget.querySelector("[data-despesa-projeto-list]");
        if (!input || !hidden || !list) return;
        widget.dataset.despesaProjetoReady = "1";

        let activeIndex = -1;

        function setOpen(open) {
            list.classList.toggle("open", open && list.children.length > 0);
        }

        function matches(projeto, query) {
            if (window.SearchUtils) return window.SearchUtils.matchesSearch([projeto.search], query);
            return despesaNormalize(projeto.search).includes(despesaNormalize(query));
        }

        function pick(projeto) {
            input.value = projeto.label || "";
            hidden.value = projeto.id;
            list.innerHTML = "";
            setOpen(false);
            recomputeDespesaTotal(widget.closest("form"));
        }

        function render() {
            const query = input.value.trim();
            list.innerHTML = "";
            activeIndex = -1;
            const projetos = despesaProjetos();
            const hits = (query ? projetos.filter((projeto) => matches(projeto, query)) : projetos).slice(0, 8);

            hits.forEach((projeto) => {
                const item = document.createElement("div");
                item.className = "ac-item";
                item.setAttribute("role", "option");
                item.innerHTML = `<span><strong>${escapeHtml(projeto.label || "")}</strong>${projeto.proprietarios ? `<span class="ac-item-meta">${escapeHtml(projeto.proprietarios)}</span>` : ""}</span>`;
                item.addEventListener("mousedown", (event) => {
                    event.preventDefault();
                    pick(projeto);
                });
                list.appendChild(item);
            });
            if (!hits.length) {
                const empty = document.createElement("div");
                empty.className = "ac-empty";
                empty.textContent = "Nenhum projeto encontrado";
                list.appendChild(empty);
            }
            setOpen(true);
        }

        input.addEventListener("input", () => {
            hidden.value = "";
            render();
        });
        input.addEventListener("focus", render);
        input.addEventListener("keydown", (event) => {
            const options = Array.from(list.querySelectorAll(".ac-item"));
            if (!options.length || !list.classList.contains("open")) return;
            if (event.key === "ArrowDown") {
                event.preventDefault();
                activeIndex = (activeIndex + 1) % options.length;
            } else if (event.key === "ArrowUp") {
                event.preventDefault();
                activeIndex = (activeIndex - 1 + options.length) % options.length;
            } else if (event.key === "Enter" && activeIndex >= 0) {
                event.preventDefault();
                options[activeIndex].dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
            } else if (event.key === "Escape") {
                setOpen(false);
                return;
            } else {
                return;
            }
            options.forEach((option, index) => option.classList.toggle("is-active", index === activeIndex));
        });
        input.addEventListener("blur", () => {
            setTimeout(() => setOpen(false), 120);
        });
    });
}

function initDespesaAlocacaoRows() {
    document.querySelectorAll("[data-despesa-alocacoes-list]").forEach((list) => {
        if (list.dataset.despesaRowsReady === "1") return;
        list.dataset.despesaRowsReady = "1";
        const container = list.parentElement;
        const template = container?.querySelector("[data-despesa-alocacao-template]");
        const addButton = container?.querySelector("[data-despesa-add-alocacao]");
        const form = list.closest("form");

        function bindRow(row) {
            row.querySelector("[data-despesa-remove-alocacao]")?.addEventListener("click", () => {
                row.remove();
                recomputeDespesaTotal(form);
            });
            row.querySelector("[data-despesa-alocacao-valor]")?.addEventListener("input", () => recomputeDespesaTotal(form));
            initDespesaProjetoAutocompletes(row);
        }

        addButton?.addEventListener("click", () => {
            if (!template) return;
            const fragment = template.content.cloneNode(true);
            const row = fragment.querySelector("[data-despesa-alocacao-row]");
            list.appendChild(fragment);
            if (row) bindRow(row);
            row?.querySelector("[data-despesa-projeto-input]")?.focus();
        });

        list.querySelectorAll("[data-despesa-alocacao-row]").forEach(bindRow);
    });
}

function parseBrCurrency(value) {
    if (!value) return 0;
    const cleaned = String(value)
        .replace(/[^\d,.-]/g, "")
        .replace(/\.(?=\d{3}(?:\D|$))/g, "")
        .replace(",", ".");
    const parsed = parseFloat(cleaned);
    return Number.isFinite(parsed) ? parsed : 0;
}

function formatBrCurrency(value) {
    return "R$ " + value.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function recomputeDespesaTotal(form) {
    if (!form) return;
    const rows = Array.from(form.querySelectorAll("[data-despesa-alocacao-valor]"));
    const total = rows.reduce((sum, input) => sum + parseBrCurrency(input.value), 0);
    const esperado = parseBrCurrency(form.querySelector("#despesaValorTotal")?.value);
    const totalEl = form.querySelector("[data-despesa-total-alocado]");
    const esperadoEl = form.querySelector("[data-despesa-total-esperado]");
    const wrapper = form.querySelector("[data-despesa-alocacoes-total]");
    if (totalEl) totalEl.textContent = formatBrCurrency(total);
    if (esperadoEl) esperadoEl.textContent = formatBrCurrency(esperado);
    if (wrapper) {
        const bate = rows.length > 0 && Math.abs(total - esperado) < 0.015;
        wrapper.classList.toggle("is-balanced", bate);
        wrapper.classList.toggle("is-unbalanced", rows.length > 0 && !bate);
    }
}

function initDespesaDesembolsoToggle() {
    const radios = document.querySelectorAll("[data-despesa-tipo-radio]");
    if (!radios.length) return;
    const pessoaField = document.querySelector("[data-despesa-pessoa-field]");
    const pessoaNovaField = document.querySelector("[data-despesa-pessoa-nova-field]");
    const select = document.getElementById("despesaDesembolsanteSelect");

    function tipoAtual() {
        return document.querySelector("[data-despesa-tipo-radio]:checked")?.value || "EMPRESA";
    }

    function update() {
        const isPessoa = tipoAtual() === "PESSOA";
        if (pessoaField) pessoaField.hidden = !isPessoa;
        if (pessoaNovaField) pessoaNovaField.hidden = !(isPessoa && select && !select.value);
    }

    radios.forEach((radio) => radio.addEventListener("change", update));
    select?.addEventListener("change", update);
    update();
}

function initDespesaDropzone() {
    const dropzone = document.querySelector("[data-despesa-dropzone]");
    const fileInput = document.getElementById("despesaComprovanteInput");
    const filePill = document.querySelector("[data-despesa-file-pill]");
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

function novoDespesaRegistroUid() {
    return (window.crypto && crypto.randomUUID)
        ? crypto.randomUUID()
        : Date.now() + "-" + Math.random().toString(16).slice(2);
}

function initDespesaModalReset() {
    const modal = document.getElementById("modalNovaDespesa");
    if (!modal) return;
    const form = document.getElementById("despesaForm");
    const list = document.querySelector("[data-despesa-alocacoes-list]");
    const registroUidField = document.getElementById("despesaRegistroUid");
    const pessoaField = document.querySelector("[data-despesa-pessoa-field]");
    const pessoaNovaField = document.querySelector("[data-despesa-pessoa-nova-field]");
    const filePill = document.querySelector("[data-despesa-file-pill]");
    const dropzone = document.querySelector("[data-despesa-dropzone]");

    modal.addEventListener("show.bs.modal", () => {
        form?.reset();
        if (list) list.innerHTML = "";
        if (registroUidField) registroUidField.value = novoDespesaRegistroUid();
        if (pessoaField) pessoaField.hidden = true;
        if (pessoaNovaField) pessoaNovaField.hidden = true;
        if (filePill) filePill.hidden = true;
        dropzone?.classList.remove("has-file");
        // Comeca ja com uma linha de divisao pronta: a maioria das despesas
        // tem 1 projeto so, e o usuario nao devia precisar clicar "+" pra isso.
        document.querySelector("[data-despesa-add-alocacao]")?.click();
        recomputeDespesaTotal(form);
    });

    const submitButton = modal.querySelector("button[type='submit']");
    modal.addEventListener("hidden.bs.modal", () => {
        if (submitButton) {
            submitButton.disabled = false;
            submitButton.textContent = "Salvar despesa";
        }
    });
}
