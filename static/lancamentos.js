// Financeiro -> Lancamentos: caixa de entrada de documentos financeiros.
// Reaproveita o autocomplete generico de cliente (initProjectClientAutocompletes,
// em app.js) para "Proprietario"; o resto (projeto em cascata, sugestao por IA
// automatica, "Salvar e proximo" sem reload) e proprio desta tela.

document.addEventListener("DOMContentLoaded", () => {
    initLancamentoImportDropzone();
    initLancamentoProjetoAutocomplete();
    initLancamentoDesembolsoToggle();
    initLancamentoForm();
    initLancamentoFilaTrash();
    initLancamentoAutoAi();
});

function lancamentoNormalize(value) {
    if (window.SearchUtils) return window.SearchUtils.normalizeSearchText(value);
    return String(value || "").toLowerCase().trim();
}

function formatLancamentoCurrency(value) {
    return Number(value || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// --- Importar documentos: dropzone que envia o form assim que ha arquivo ---

function initLancamentoImportDropzone() {
    const dropzone = document.querySelector("[data-lancamento-dropzone]");
    const fileInput = document.getElementById("lancamentoArquivosInput");
    const form = document.getElementById("lancamentoImportForm");
    if (!dropzone || !fileInput || !form) return;

    function assignFiles(files) {
        if (!files || !files.length || !window.DataTransfer) return false;
        const transfer = new DataTransfer();
        Array.from(files).forEach((file) => transfer.items.add(file));
        fileInput.files = transfer.files;
        return true;
    }

    function submitWithFeedback() {
        dropzone.classList.add("has-file");
        dropzone.querySelector(".finance-dropzone__copy strong").textContent = "Enviando...";
        form.submit();
    }

    fileInput.addEventListener("change", () => {
        if (fileInput.files && fileInput.files.length) submitWithFeedback();
    });
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
        submitWithFeedback();
    });
}

// --- Projeto em cascata: proprietario -> so os projetos dele, com busca direta ---

const lancamentoProjetoState = {
    ownerProjects: [],
};

function initLancamentoProjetoAutocomplete() {
    const widget = document.querySelector("[data-lancamento-projeto-autocomplete]");
    const clienteInput = document.getElementById("lancamentoClienteInput");
    const clienteId = document.getElementById("lancamentoClienteId");
    if (!widget) return;
    const input = widget.querySelector("[data-lancamento-projeto-input]");
    const list = widget.querySelector("[data-lancamento-projeto-list]");
    const hidden = document.getElementById("lancamentoProjetoId");
    if (!input || !list || !hidden) return;

    function setOpen(open) {
        list.classList.toggle("open", open && list.children.length > 0);
    }

    function pick(projeto) {
        input.value = `${projeto.codigo} - ${projeto.nome}`;
        hidden.value = projeto.id;
        list.innerHTML = "";
        setOpen(false);
    }

    function candidatePool() {
        const all = Array.isArray(window.despesaProjetosOptions) ? window.despesaProjetosOptions : [];
        const ownerIds = new Set(lancamentoProjetoState.ownerProjects.map((projeto) => projeto.id));
        // Projetos do proprietario primeiro (item 4 do redesenho); o resto entra
        // depois, para permitir buscar qualquer projeto diretamente se precisar.
        return [...lancamentoProjetoState.ownerProjects, ...all.filter((projeto) => !ownerIds.has(projeto.id))];
    }

    function render() {
        const query = input.value.trim();
        list.innerHTML = "";
        const pool = candidatePool();
        const hits = (query
            ? pool.filter((projeto) => lancamentoNormalize(`${projeto.codigo} ${projeto.nome}`).includes(lancamentoNormalize(query)))
            : lancamentoProjetoState.ownerProjects
        ).slice(0, 8);

        hits.forEach((projeto) => {
            const item = document.createElement("div");
            item.className = "ac-item";
            item.setAttribute("role", "option");
            item.innerHTML = `<span><strong>${escapeHtml(projeto.codigo || "")}</strong> - ${escapeHtml(projeto.nome || "")}</span>`;
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
    input.addEventListener("focus", () => { if (!input.disabled) render(); });
    input.addEventListener("blur", () => setTimeout(() => setOpen(false), 120));

    async function loadOwnerProjects(id) {
        lancamentoProjetoState.ownerProjects = [];
        input.value = "";
        hidden.value = "";
        if (!id) {
            input.disabled = true;
            input.placeholder = "Selecione o proprietario primeiro...";
            return;
        }
        input.disabled = false;
        input.placeholder = "Carregando projetos...";
        try {
            const response = await fetch(`/api/clientes/${id}/projetos`);
            const data = await response.json();
            lancamentoProjetoState.ownerProjects = (data.ok && data.projetos) || [];
        } catch {
            lancamentoProjetoState.ownerProjects = [];
        }
        input.placeholder = lancamentoProjetoState.ownerProjects.length
            ? "Buscar projeto do proprietario..."
            : "Nenhum projeto deste proprietario -- buscar outro";
        if (lancamentoProjetoState.ownerProjects.length === 1) pick(lancamentoProjetoState.ownerProjects[0]);
    }

    clienteInput?.addEventListener("change", () => loadOwnerProjects(clienteId?.value || ""));

    widget.dataset.reset = "1";
    window.resetLancamentoProjeto = () => {
        lancamentoProjetoState.ownerProjects = [];
        input.value = "";
        hidden.value = "";
        input.disabled = true;
        input.placeholder = "Selecione o proprietario primeiro...";
    };
}

function resetLancamentoOwner() {
    const clienteInput = document.getElementById("lancamentoClienteInput");
    const clienteId = document.getElementById("lancamentoClienteId");
    if (clienteInput) clienteInput.value = "";
    if (clienteId) clienteId.value = "";
    window.resetLancamentoProjeto?.();
}

// --- "Mais opcoes": quem pagou (mesma logica de despesas.js, IDs proprios) ---

function initLancamentoDesembolsoToggle() {
    const radios = document.querySelectorAll("[data-lancamento-tipo-radio]");
    if (!radios.length) return;
    const pessoaField = document.querySelector("[data-lancamento-pessoa-field]");
    const pessoaNovaField = document.querySelector("[data-lancamento-pessoa-nova-field]");
    const select = document.getElementById("lancamentoDesembolsanteSelect");

    function tipoAtual() {
        return document.querySelector("[data-lancamento-tipo-radio]:checked")?.value || "EMPRESA";
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

// --- Sugestao automatica por IA ao abrir um documento ------------------

function setLancamentoAiStatus(message, tone) {
    const status = document.querySelector("[data-lancamento-ai-status]");
    if (!status) return;
    status.textContent = message || "";
    status.className = "despesa-ai-status" + (tone ? ` is-${tone}` : "");
}

function applyLancamentoAiFields(fields) {
    if (!fields) return;
    const descricaoInput = document.getElementById("lancamentoDescricao");
    const valorInput = document.getElementById("lancamentoValor");
    const dataInput = document.getElementById("lancamentoData");
    const categoriaSelect = document.getElementById("lancamentoCategoria");
    const observacoesInput = document.querySelector('#lancamentoForm [name="observacoes"]');

    if (fields.descricao && descricaoInput && !descricaoInput.value) descricaoInput.value = fields.descricao;
    if (fields.valor && valorInput && !valorInput.value) valorInput.value = formatLancamentoCurrency(fields.valor);
    if (fields.data && dataInput) dataInput.value = fields.data;
    if (fields.categoria_sugerida && categoriaSelect) {
        const valido = Array.from(categoriaSelect.options).some((opt) => opt.value === fields.categoria_sugerida);
        if (valido) categoriaSelect.value = fields.categoria_sugerida;
    }
    if (observacoesInput && !observacoesInput.value) {
        const extra = [];
        if (fields.estabelecimento) extra.push(fields.estabelecimento);
        if (fields.numero_documento) extra.push(`Doc. ${fields.numero_documento}`);
        if (extra.length) observacoesInput.value = extra.join(" - ");
    }
}

async function autoAnalyzeLancamento(aiUrl) {
    if (!aiUrl) return;
    setLancamentoAiStatus("Analisando documento...");
    try {
        const getResponse = await fetch(aiUrl);
        const getData = await getResponse.json();
        if (getData.analysis && getData.analysis.status) {
            applyLancamentoAiFields(getData.analysis.fields);
            setLancamentoAiStatus("Informacoes sugeridas pela leitura do documento.", "success");
            return;
        }
        const postResponse = await fetch(aiUrl, { method: "POST" });
        const postData = await postResponse.json();
        applyLancamentoAiFields(postData.analysis?.fields);
        if (postResponse.ok && postData.ok) {
            setLancamentoAiStatus("Informacoes sugeridas pela leitura do documento.", "success");
        } else {
            // Item 6 do redesenho: falha da IA nunca impede o lancamento manual.
            setLancamentoAiStatus(postData.error || "Nao foi possivel ler automaticamente. Preencha manualmente.", "error");
        }
    } catch {
        setLancamentoAiStatus("Nao foi possivel ler automaticamente. Preencha manualmente.", "error");
    }
}

function initLancamentoAutoAi() {
    if (window.lancamentoAberto?.ai_analysis_url) {
        autoAnalyzeLancamento(window.lancamentoAberto.ai_analysis_url);
    }
}

// --- Salvar e proximo: classifica e abre o proximo documento sem reload ---

function lancamentoFilaCount() {
    return document.querySelectorAll("[data-lancamento-fila-item]").length;
}

function updateLancamentoDoc(despesa) {
    window.lancamentoAberto = despesa || null;
    const main = document.querySelector("[data-lancamento-main]");
    const empty = document.querySelector("[data-lancamento-empty]");
    const form = document.getElementById("lancamentoForm");

    if (!despesa) {
        if (main) main.hidden = true;
        if (empty) empty.hidden = false;
        return;
    }
    if (main) main.hidden = false;
    if (empty) empty.hidden = true;

    document.querySelector("[data-lancamento-doc-nome]").textContent = despesa.anexo_nome || despesa.descricao || "";
    const link = document.querySelector("[data-lancamento-doc-link]");
    if (link) {
        link.hidden = !despesa.anexo_url;
        if (despesa.anexo_url) link.href = despesa.anexo_url;
    }

    form?.reset();
    resetLancamentoOwner();
    setLancamentoAiStatus("");

    document.querySelectorAll("[data-lancamento-fila-item]").forEach((item) => {
        item.classList.toggle("is-active", item.dataset.lancamentoFilaItem === String(despesa.id));
    });

    autoAnalyzeLancamento(despesa.ai_analysis_url);
}

function lancamentoUrl(action, currentId) {
    const params = new URLSearchParams();
    if (window.lancamentoLoteId) params.set("lote_id", window.lancamentoLoteId);
    return `/financeiro/lancamentos/${currentId}/${action}${params.toString() ? `?${params}` : ""}`;
}

async function postLancamento(url, formData) {
    // Sempre manda um body (mesmo vazio) no POST: alguns proxies/servidores
    // tratam POST sem Content-Length de forma inconsistente. O header
    // X-Requested-With e o que a rota usa pra devolver JSON em vez do
    // fallback classico (flash + redirect).
    const response = await fetch(url, {
        method: "POST",
        headers: { "X-Requested-With": "XMLHttpRequest" },
        body: formData || new FormData(),
    });
    let data;
    try {
        data = await response.json();
    } catch {
        throw new Error(`O servidor respondeu de forma inesperada (HTTP ${response.status}). Recarregue a pagina e tente novamente.`);
    }
    if (!response.ok || !data.ok) {
        throw new Error(data.error || "Nao foi possivel concluir a operacao.");
    }
    return data;
}

function applyLancamentoAdvance(currentId, data) {
    const savedItem = document.querySelector(`[data-lancamento-fila-item="${currentId}"]`);
    savedItem?.remove();
    const countBadge = document.querySelector("[data-lancamento-fila-count]");
    if (countBadge) countBadge.textContent = String(lancamentoFilaCount());
    const filaEmpty = document.querySelector("[data-lancamento-fila-empty]");
    if (filaEmpty) filaEmpty.hidden = lancamentoFilaCount() > 0;
    updateLancamentoDoc(data.next);
}

function initLancamentoForm() {
    const form = document.getElementById("lancamentoForm");
    if (!form) return;
    const submitButton = form.querySelector("[data-lancamento-submit]");
    const errorBox = form.querySelector("[data-lancamento-form-error]");
    const originalText = submitButton?.textContent || "Salvar e proximo";

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const currentId = window.lancamentoAberto?.id;
        if (!currentId) return;
        if (errorBox) errorBox.textContent = "";
        if (submitButton) {
            submitButton.disabled = true;
            submitButton.textContent = "Salvando...";
        }
        try {
            const data = await postLancamento(lancamentoUrl("salvar-proximo", currentId), new FormData(form));
            applyLancamentoAdvance(currentId, data);
        } catch (error) {
            if (errorBox) errorBox.textContent = error.message || "Nao foi possivel salvar. Tente novamente.";
        } finally {
            if (submitButton) {
                submitButton.disabled = false;
                submitButton.textContent = originalText;
            }
        }
    });

    const cancelButton = form.querySelector("[data-lancamento-cancelar]");
    cancelButton?.addEventListener("click", async () => {
        const currentId = window.lancamentoAberto?.id;
        if (!currentId) return;
        if (!confirm("Descartar este documento? Ele sai da fila sem virar despesa (fica preservado no historico como cancelado).")) return;
        if (errorBox) errorBox.textContent = "";
        cancelButton.disabled = true;
        if (submitButton) submitButton.disabled = true;
        try {
            const data = await postLancamento(lancamentoUrl("cancelar", currentId));
            applyLancamentoAdvance(currentId, data);
        } catch (error) {
            if (errorBox) errorBox.textContent = error.message || "Nao foi possivel descartar este documento.";
        } finally {
            cancelButton.disabled = false;
            if (submitButton) submitButton.disabled = false;
        }
    });
}

// --- Lixeira na lista de pendentes: descarta um item sem precisar abri-lo ---

function initLancamentoFilaTrash() {
    const list = document.querySelector("[data-lancamento-fila-list]");
    if (!list) return;

    list.addEventListener("click", async (event) => {
        const button = event.target.closest("[data-lancamento-fila-trash]");
        if (!button) return;
        event.preventDefault();
        const id = button.dataset.lancamentoFilaTrash;
        if (!confirm("Descartar este documento? Ele sai da fila sem virar despesa (fica preservado no historico como cancelado).")) return;

        const row = button.closest("[data-lancamento-fila-item]");
        row?.classList.add("is-busy");
        try {
            const data = await postLancamento(lancamentoUrl("cancelar", id));
            row?.remove();
            const countBadge = document.querySelector("[data-lancamento-fila-count]");
            if (countBadge) countBadge.textContent = String(lancamentoFilaCount());
            const filaEmpty = document.querySelector("[data-lancamento-fila-empty]");
            if (filaEmpty) filaEmpty.hidden = lancamentoFilaCount() > 0;
            // So troca o documento aberto se a lixeira clicada era a do
            // proprio documento em edicao -- descartar outro item da lista
            // nao deve tirar o usuario do que ele esta preenchendo agora.
            if (String(window.lancamentoAberto?.id) === String(id)) {
                updateLancamentoDoc(data.next);
            }
        } catch (error) {
            alert(error.message || "Nao foi possivel descartar este documento.");
            row?.classList.remove("is-busy");
        }
    });
}
