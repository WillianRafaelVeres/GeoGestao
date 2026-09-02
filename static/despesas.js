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
    initImportarDocumentos();
    initDespesaAiSuggest();

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
    // O mesmo modal serve para "Nova despesa" (cria do zero) e "Classificar"
    // (completa um rascunho ja existente, importado em lote ou nao). O botao
    // que abre o modal decide o modo: se tiver data-despesa-classificar-url,
    // troca o action do form e pre-preenche os campos que ja se sabe.
    const modal = document.getElementById("modalNovaDespesa");
    if (!modal) return;
    const form = document.getElementById("despesaForm");
    const list = document.querySelector("[data-despesa-alocacoes-list]");
    const registroUidField = document.getElementById("despesaRegistroUid");
    const pessoaField = document.querySelector("[data-despesa-pessoa-field]");
    const pessoaNovaField = document.querySelector("[data-despesa-pessoa-nova-field]");
    const filePill = document.querySelector("[data-despesa-file-pill]");
    const dropzone = document.querySelector("[data-despesa-dropzone]");
    const kicker = modal.querySelector("[data-despesa-modal-kicker]");
    const titleEl = modal.querySelector("[data-despesa-modal-title]");
    const submitButton = modal.querySelector("[data-despesa-submit]");
    const comprovanteLabel = modal.querySelector("[data-despesa-comprovante-label]");
    const registroUidInput = document.getElementById("despesaRegistroUid");
    const createUrl = form?.dataset.createUrl;
    const aiSection = modal.querySelector("[data-despesa-ai-suggest]");
    const aiButton = modal.querySelector("[data-despesa-ai-button]");
    const aiStatus = modal.querySelector("[data-despesa-ai-status]");
    let submitDefaultText = submitButton?.textContent || "Salvar despesa";

    modal.addEventListener("show.bs.modal", (event) => {
        form?.reset();
        if (list) list.innerHTML = "";
        if (registroUidField) registroUidField.value = novoDespesaRegistroUid();
        if (pessoaField) pessoaField.hidden = true;
        if (pessoaNovaField) pessoaNovaField.hidden = true;
        if (filePill) filePill.hidden = true;
        dropzone?.classList.remove("has-file");
        if (aiStatus) { aiStatus.textContent = ""; aiStatus.className = "despesa-ai-status"; }

        const botao = event.relatedTarget;
        const classificarUrl = botao?.dataset.despesaClassificarUrl;
        if (classificarUrl && form) {
            form.action = classificarUrl;
            if (registroUidInput) registroUidInput.disabled = true;
            if (kicker) kicker.textContent = "Classificar despesa";
            if (titleEl) titleEl.textContent = botao.dataset.despesaClassificarDescricao || "Despesa importada";
            if (comprovanteLabel) comprovanteLabel.innerHTML = 'Comprovante adicional <span class="text-muted">(opcional -- o original ja esta anexado)</span>';
            submitDefaultText = "Classificar despesa";
            document.getElementById("despesaDescricao").value = botao.dataset.despesaClassificarDescricao || "";
            document.getElementById("despesaValorTotal").value = botao.dataset.despesaClassificarValor || "";
            const dataInput = form.querySelector('[name="data_despesa"]');
            if (dataInput) dataInput.value = botao.dataset.despesaClassificarData || dataInput.value;
            const categoriaSelect = form.querySelector('[name="categoria"]');
            if (categoriaSelect && botao.dataset.despesaClassificarCategoria) {
                categoriaSelect.value = botao.dataset.despesaClassificarCategoria;
            }
            if (aiSection) aiSection.hidden = false;
            if (aiButton) aiButton.dataset.aiUrl = botao.dataset.despesaAiUrl || "";
        } else if (form) {
            form.action = createUrl;
            if (registroUidInput) registroUidInput.disabled = false;
            if (kicker) kicker.textContent = "Nova despesa";
            if (titleEl) titleEl.textContent = "Registrar despesa";
            if (comprovanteLabel) comprovanteLabel.innerHTML = 'Comprovante <span class="text-muted">(opcional)</span>';
            submitDefaultText = "Salvar despesa";
            if (aiSection) aiSection.hidden = true;
        }
        if (submitButton) submitButton.textContent = submitDefaultText;

        // Comeca ja com uma linha de divisao pronta: a maioria das despesas
        // tem 1 projeto so, e o usuario nao devia precisar clicar "+" pra isso.
        document.querySelector("[data-despesa-add-alocacao]")?.click();
        recomputeDespesaTotal(form);
    });

    modal.addEventListener("hidden.bs.modal", () => {
        if (submitButton) {
            submitButton.disabled = false;
            submitButton.textContent = submitDefaultText;
        }
    });
}

function initImportarDocumentos() {
    const dropzone = document.querySelector("[data-import-dropzone]");
    const fileInput = document.getElementById("importarArquivosInput");
    const fileList = document.querySelector("[data-import-file-list]");
    const submitButton = document.querySelector("[data-import-submit]");
    const modal = document.getElementById("modalImportarDocumentos");
    if (!dropzone || !fileInput) return;

    function updateUi() {
        const arquivos = Array.from(fileInput.files || []);
        dropzone.classList.toggle("has-file", arquivos.length > 0);
        if (fileList) {
            fileList.innerHTML = "";
            arquivos.forEach((arquivo) => {
                const item = document.createElement("li");
                item.textContent = arquivo.name;
                fileList.appendChild(item);
            });
        }
        if (submitButton) submitButton.disabled = arquivos.length === 0;
    }

    function assignFiles(files) {
        if (!files || !files.length || !window.DataTransfer) return false;
        const transfer = new DataTransfer();
        Array.from(files).forEach((file) => transfer.items.add(file));
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
        const arquivos = event.dataTransfer?.files;
        if (!arquivos?.length || !assignFiles(arquivos)) return;
        updateUi();
    });

    modal?.addEventListener("show.bs.modal", () => {
        fileInput.value = "";
        updateUi();
    });
    modal?.addEventListener("hidden.bs.modal", () => {
        if (submitButton) {
            submitButton.disabled = true;
            submitButton.textContent = "Importar";
        }
    });
}

function initDespesaAiSuggest() {
    // So aparece no modo "Classificar" (ver initDespesaModalReset). A IA so
    // preenche os campos do formulario -- nunca envia nada sozinha; quem
    // confirma a despesa (com os campos como estiverem na hora) e sempre a
    // pessoa, clicando em "Classificar despesa".
    const button = document.querySelector("[data-despesa-ai-button]");
    const status = document.querySelector("[data-despesa-ai-status]");
    if (!button) return;

    button.addEventListener("click", async () => {
        const url = button.dataset.aiUrl;
        if (!url) return;
        const originalText = button.textContent;
        button.disabled = true;
        button.textContent = "Analisando...";
        if (status) { status.textContent = ""; status.className = "despesa-ai-status"; }
        try {
            const response = await fetch(url, { method: "POST" });
            const data = await response.json();
            if (!response.ok || !data.ok) {
                if (status) {
                    status.textContent = data.error || "Nao foi possivel gerar a sugestao.";
                    status.classList.add("is-error");
                }
                return;
            }
            applyDespesaAiFields(data.analysis?.fields || {});
            if (status) {
                status.textContent = data.message || "Sugestao aplicada. Revise os campos antes de confirmar.";
                status.classList.add("is-success");
            }
        } catch {
            if (status) {
                status.textContent = "Nao foi possivel conectar para gerar a sugestao.";
                status.classList.add("is-error");
            }
        } finally {
            button.disabled = false;
            button.textContent = originalText;
        }
    });
}

function applyDespesaAiFields(fields) {
    // Preenche o MESMO formulario que o usuario ainda vai revisar e enviar --
    // nao ha um "aplicar automaticamente". Projeto, cliente e quem desembolsou
    // nunca vem da IA (item 11): esses campos ficam como o usuario deixar.
    const form = document.getElementById("despesaForm");
    const descricaoInput = document.getElementById("despesaDescricao");
    const valorInput = document.getElementById("despesaValorTotal");
    if (fields.descricao && descricaoInput) descricaoInput.value = fields.descricao;
    if (fields.valor && valorInput) {
        valorInput.value = Number(fields.valor).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    if (fields.data) {
        const dataInput = form?.querySelector('[name="data_despesa"]');
        if (dataInput) dataInput.value = fields.data;
    }
    if (fields.categoria_sugerida) {
        const categoriaSelect = form?.querySelector('[name="categoria"]');
        const opcaoValida = categoriaSelect && Array.from(categoriaSelect.options).some((opt) => opt.value === fields.categoria_sugerida);
        if (opcaoValida) categoriaSelect.value = fields.categoria_sugerida;
    }
    // estabelecimento/numero_documento nao tem campo proprio no formulario;
    // ficam guardados no rascunho (consultavel depois) e, se ainda nao houver
    // observacao, viram uma sugestao de observacao editavel.
    const observacoesInput = form?.querySelector('[name="observacoes"]');
    if (observacoesInput && !observacoesInput.value) {
        const extra = [];
        if (fields.estabelecimento) extra.push(fields.estabelecimento);
        if (fields.numero_documento) extra.push(`Doc. ${fields.numero_documento}`);
        if (extra.length) observacoesInput.value = extra.join(" - ");
    }
    recomputeDespesaTotal(form);
}
