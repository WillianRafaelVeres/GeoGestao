document.addEventListener("shown.bs.offcanvas", (event) => {
    const firstInput = event.target.querySelector("input:not([type='hidden']), select, textarea");
    if (firstInput) {
        firstInput.focus({ preventScroll: true });
    }
});

// Fechar offcanvas ao abrir modal (evita conflito de z-index)
document.addEventListener("show.bs.modal", () => {
    document.querySelectorAll(".offcanvas.show").forEach((el) => {
        bootstrap.Offcanvas.getInstance(el)?.hide();
    });
});

async function toggleChecklist(btn) {
    const itemId = btn.dataset.itemId;
    const stageId = btn.dataset.stageId;
    const wasChecked = btn.classList.contains("checked");
    const label = document.getElementById(`check-label-${itemId}`);
    const counter = document.querySelector(`.checklist-counter-${stageId}`);
    const previousCounter = counter?.textContent || "";
    btn.disabled = true;
    btn.classList.toggle("checked", !wasChecked);
    btn.innerHTML = wasChecked ? "" : "&#10003;";
    if (label) {
        label.style.color = wasChecked ? "" : "#9ca3af";
        label.style.textDecoration = wasChecked ? "" : "line-through";
    }
    const match = previousCounter.match(/(\d+)\s*\/\s*(\d+)/);
    if (counter && match) {
        const total = Number(match[2]);
        const done = Math.max(0, Math.min(total, Number(match[1]) + (wasChecked ? -1 : 1)));
        counter.textContent = `${done}/${total}`;
    }
    try {
        const resp = await fetch(`/api/checklist/${itemId}/toggle`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ concluido: !wasChecked }),
        });
        if (!resp.ok) throw new Error("Falha");
        const data = await resp.json();
        if (data.concluido) {
            btn.classList.add("checked");
            btn.innerHTML = "&#10003;";
            if (label) { label.style.color = "#9ca3af"; label.style.textDecoration = "line-through"; }
        } else {
            btn.classList.remove("checked");
            btn.innerHTML = "";
            if (label) { label.style.color = ""; label.style.textDecoration = ""; }
        }
        if (counter) counter.textContent = `${data.done}/${data.total}`;
    } catch {
        btn.classList.toggle("checked", wasChecked);
        btn.innerHTML = wasChecked ? "&#10003;" : "";
        if (label) {
            label.style.color = wasChecked ? "#9ca3af" : "";
            label.style.textDecoration = wasChecked ? "line-through" : "";
        }
        if (counter) counter.textContent = previousCounter;
        alert("Erro ao atualizar checklist. Tente novamente.");
    } finally {
        btn.disabled = false;
    }
}

if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
        navigator.serviceWorker.register("/static/service-worker.js").catch(() => {});
    });
}

window.addEventListener("DOMContentLoaded", () => {
    if (window.bootstrap && window.location.hash) {
        const tabTrigger = document.querySelector(`[data-bs-target="${window.location.hash}"]`);
        if (tabTrigger) {
            window.bootstrap.Tab.getOrCreateInstance(tabTrigger).show();
        }
    }

    document.querySelectorAll('[data-bs-toggle="tab"]').forEach((tab) => {
        tab.addEventListener("shown.bs.tab", (event) => {
            const target = event.target.getAttribute("data-bs-target");
            if (target) {
                history.replaceState(null, "", target);
            }
        });
    });

    const matrixShell = document.querySelector(".matrix-shell");
    const densityButtons = document.querySelectorAll("[data-density]");
    const storedDensity = localStorage.getItem("geogestao.matrixDensity") || "comfortable";
    if (matrixShell) {
        matrixShell.dataset.matrixDensity = storedDensity;
    }
    densityButtons.forEach((button) => {
        button.classList.toggle("active", button.dataset.density === storedDensity);
        button.addEventListener("click", () => {
            const density = button.dataset.density;
            localStorage.setItem("geogestao.matrixDensity", density);
            if (matrixShell) {
                matrixShell.dataset.matrixDensity = density;
            }
            densityButtons.forEach((item) => item.classList.toggle("active", item === button));
        });
    });

    document.querySelectorAll("[data-copy]").forEach((button) => {
        button.addEventListener("click", async () => {
            try {
                await navigator.clipboard.writeText(button.dataset.copy);
                const originalText = button.textContent;
                button.textContent = "Copiado";
                setTimeout(() => {
                    button.textContent = originalText;
                }, 1200);
            } catch {
                button.textContent = "Copie manualmente";
            }
        });
    });

    document.addEventListener("click", async (e) => {
        const button = e.target.closest("[data-copy-target]");
        if (!button) return;
        const targetEl = document.querySelector(button.dataset.copyTarget);
        if (!targetEl) return;
        const textToCopy = targetEl.value || targetEl.innerText || targetEl.textContent || "";
        try {
            await navigator.clipboard.writeText(textToCopy);
            const originalHtml = button.innerHTML;
            button.innerHTML = "✓ Copiado!";
            setTimeout(() => {
                button.innerHTML = originalHtml;
            }, 1500);
        } catch {
            button.textContent = "Copie manualmente";
        }
    });

    // Abre a pasta do projeto: Explorer quando o app roda local, senao Dropbox (web/desktop).
    document.querySelectorAll("[data-open-folder]").forEach((button) => {
        button.addEventListener("click", async () => {
            const path = button.dataset.openFolder;
            if (!path) return;
            const originalText = button.textContent;
            button.disabled = true;
            button.textContent = "Abrindo...";
            try {
                const resp = await fetch("/api/open-folder", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ path }),
                });
                const data = await resp.json();
                if (data.url) {
                    window.open(data.url, "_blank", "noopener");
                } else if (data.error) {
                    alert(data.error);
                }
            } catch {
                alert("Nao foi possivel abrir a pasta.");
            } finally {
                button.disabled = false;
                button.textContent = originalText;
            }
        });
    });

    initDocumentalClientForm();
    initRepresentativeManagers();
    initRepresentationManagers();
    initClientLiveSearch();
    initClientLazyModals();
    initProjectClientAutocompletes();
    initProjectOwnerManagers();
    initCartorioLookup();
    initSingleSubmitForms();
    initMissionQuickActions();
    initMatrixLiveFilters();
    initAutoGrowTextareas();
    initExigenciaAi();
});

function initAutoGrowTextareas() {
    const textareas = Array.from(document.querySelectorAll("textarea[data-auto-grow]"));
    if (!textareas.length) return;

    const resize = (textarea) => {
        textarea.style.height = "auto";
        const styles = window.getComputedStyle(textarea);
        const minHeight = parseFloat(styles.minHeight) || 78;
        const maxHeight = Math.max(minHeight, Math.min(520, Math.floor(window.innerHeight * 0.56)));
        textarea.style.maxHeight = `${maxHeight}px`;
        const nextHeight = Math.min(maxHeight, Math.max(minHeight, textarea.scrollHeight));
        textarea.style.height = `${nextHeight}px`;
        textarea.style.overflowY = textarea.scrollHeight > maxHeight ? "auto" : "hidden";
    };

    textareas.forEach((textarea) => {
        resize(textarea);
        textarea.addEventListener("input", () => resize(textarea));
    });
    window.addEventListener("resize", () => textareas.forEach(resize));
}

function initSingleSubmitForms() {
    document.querySelectorAll("form[data-single-submit]").forEach((form) => {
        if (form.closest("[data-project-detail-tabs]")) return;
        form.addEventListener("submit", (event) => {
            if (event.defaultPrevented) return;
            if (form.dataset.submitting === "1") {
                event.preventDefault();
                return;
            }
            form.dataset.submitting = "1";
            form.querySelectorAll('button[type="submit"], input[type="submit"]').forEach((button) => {
                button.disabled = true;
                if (button.tagName === "BUTTON" && !button.dataset.originalText) {
                    button.dataset.originalText = button.textContent;
                    button.textContent = "Salvando...";
                }
            });
        });
    });
}

function syncMissionEmptyState(list) {
    if (!list) return;
    const hasMissions = Boolean(list.querySelector("[data-mission-row]"));
    let empty = list.querySelector("[data-mission-empty]");
    if (hasMissions) {
        empty?.remove();
        return;
    }
    if (!empty) {
        empty = document.createElement("tr");
        empty.dataset.missionEmpty = "1";
        const cell = document.createElement("td");
        cell.colSpan = 8;
        cell.textContent = "Voce nao possui missoes ativas.";
        empty.appendChild(cell);
        list.appendChild(empty);
    }
}

function setMissionFeedback(message, state) {
    const feedback = document.querySelector("[data-mission-feedback]");
    if (!feedback) return;
    feedback.textContent = message || "";
    feedback.classList.remove("d-none", "alert-success", "alert-danger");
    feedback.classList.add(state === "error" ? "alert-danger" : "alert-success");
}

function initMissionQuickActions() {
    document.querySelectorAll("form[data-mission-quick-form]").forEach((form) => {
        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            if (form.dataset.submitting === "1") return;

            const row = form.closest("[data-mission-row]");
            const list = row?.closest("[data-mission-list]");
            if (!row || !list) return;

            const button = form.querySelector('button[type="submit"]');
            const originalText = button?.textContent || "";
            const placeholder = document.createComment("missao sendo atualizada");
            form.dataset.submitting = "1";
            if (button) {
                button.disabled = true;
                button.textContent = "Salvando...";
            }

            // A missao some imediatamente; em caso de erro, o marcador preserva
            // exatamente a posicao em que a linha deve ser restaurada.
            row.replaceWith(placeholder);
            syncMissionEmptyState(list);

            try {
                const response = await fetch(form.action, {
                    method: "POST",
                    body: new FormData(form),
                    credentials: "same-origin",
                    headers: {
                        Accept: "application/json",
                        "X-Requested-With": "XMLHttpRequest",
                    },
                });
                if (response.redirected && new URL(response.url, window.location.origin).pathname === "/login") {
                    window.location.assign(response.url);
                    return;
                }
                const data = await response.json().catch(() => ({}));
                if (!response.ok || !data.ok) {
                    throw new Error(data.error || data.message || "Nao foi possivel atualizar a missao.");
                }
                placeholder.remove();
                setMissionFeedback(data.message || "Missao atualizada.", "success");
            } catch (error) {
                if (placeholder.parentNode) placeholder.replaceWith(row);
                setMissionFeedback(error.message || "Nao foi possivel atualizar a missao.", "error");
            } finally {
                delete form.dataset.submitting;
                if (button) {
                    button.disabled = false;
                    button.textContent = originalText;
                }
                syncMissionEmptyState(list);
            }
        });
    });
}

function initCartorioLookup() {
    document.querySelectorAll("[data-cartorio-lookup]").forEach((lookup) => {
        const form = lookup.closest("[data-cartorio-form]") || lookup.closest("form");
        if (!form) return;
        const ufSelect = lookup.querySelector("[data-cartorio-lookup-uf]");
        const citySelect = lookup.querySelector("[data-cartorio-lookup-city]");
        const officeSelect = lookup.querySelector("[data-cartorio-lookup-office]");
        const cnsInput = lookup.querySelector("[data-cartorio-lookup-cns]");
        const cityStatus = lookup.querySelector("[data-cartorio-city-status]");
        const cnsStatus = lookup.querySelector("[data-cartorio-cns-status]");
        const cityApplyButton = lookup.querySelector("[data-cartorio-apply-city]");
        const cnsApplyButton = lookup.querySelector("[data-cartorio-apply-cns]");
        const catalogSource = form.querySelector("[data-cartorio-catalog-source]");
        const catalogSingle = form.querySelector("[data-cartorio-catalog-single]");
        let selectedCityItem = null;
        let selectedCnsItem = null;
        let cityRequest = null;
        let cnsRequest = null;

        const cleanCns = (value) => String(value || "").replace(/\D/g, "").slice(0, 6);
        const formatCns = (value) => cleanCns(value).replace(/^(\d{2})(\d)/, "$1.$2").replace(/^(\d{2})\.(\d{3})(\d)/, "$1.$2-$3");
        const setStatus = (element, message, state = "") => {
            if (!element) return;
            element.textContent = message;
            element.dataset.state = state;
        };
        const setOffices = (items, placeholder = "Selecione o Registro de Imóveis") => {
            if (!officeSelect) return;
            officeSelect.innerHTML = "";
            const first = document.createElement("option");
            first.value = "";
            first.textContent = placeholder;
            officeSelect.appendChild(first);
            items.forEach((item, index) => {
                const option = document.createElement("option");
                option.value = String(index);
                option.textContent = item.cns ? `${item.nome} - CNS ${formatCns(item.cns)}` : item.nome;
                officeSelect.appendChild(option);
            });
            officeSelect.disabled = items.length === 0;
            officeSelect._cartorioItems = items;
            selectedCityItem = null;
            if (cityApplyButton) cityApplyButton.disabled = true;
        };
        const setField = (name, value) => {
            const field = form.querySelector(`[data-cartorio-field="${name}"]`) || form.querySelector(`[name="${name}"]`);
            if (!field) return;
            field.value = value || "";
            field.dispatchEvent(new Event("input", { bubbles: true }));
            field.dispatchEvent(new Event("change", { bubbles: true }));
        };
        const fillForm = (item) => {
            if (!item) return;
            if (catalogSource) catalogSource.value = item.fonte ? "cnj" : "";
            if (catalogSingle) catalogSingle.value = item.unico_na_cidade ? "1" : "0";
            ["nome", "cns", "cidade", "uf", "contato", "email", "telefone", "whatsapp", "oficial", "observacoes"].forEach((field) => {
                setField(field, field === "cns" ? formatCns(item[field]) : item[field] || "");
            });
        };
        const requestCatalog = async (params, mode) => {
            if (mode === "city" && cityRequest) cityRequest.abort();
            if (mode === "cns" && cnsRequest) cnsRequest.abort();
            const controller = new AbortController();
            if (mode === "city") cityRequest = controller;
            if (mode === "cns") cnsRequest = controller;
            const query = new URLSearchParams(params);
            const response = await fetch(`/api/cartorios/catalogo?${query}`, {
                headers: { Accept: "application/json" },
                signal: controller.signal,
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(data.message || "Não foi possível consultar o catálogo oficial.");
            return Array.isArray(data.items) ? data.items : [];
        };
        const refreshOffices = async () => {
            const uf = ufSelect?.value || "";
            const city = citySelect?.value?.trim() || "";
            setOffices([], city ? "Consultando o Justiça Aberta/CNJ..." : "Escolha a cidade");
            if (!uf || !city) return;
            setStatus(cityStatus, "Consultando Registros de Imóveis no Justiça Aberta/CNJ...", "loading");
            try {
                const offices = await requestCatalog({ uf, cidade: city }, "city");
                setOffices(offices, offices.length ? "Selecione o Registro de Imóveis" : "Nenhum Registro de Imóveis encontrado");
                setStatus(
                    cityStatus,
                    offices.length ? `${offices.length} Registro(s) de Imóveis encontrado(s).` : "Nenhum Registro de Imóveis encontrado nesta cidade.",
                    offices.length ? "success" : "warning"
                );
            } catch (error) {
                if (error.name === "AbortError") return;
                setOffices([], "Consulta indisponível");
                setStatus(cityStatus, error.message, "error");
            }
        };

        ufSelect?.addEventListener("change", () => {
            if (citySelect) citySelect.value = "";
            setOffices([], "Escolha a cidade");
            setStatus(cityStatus, "");
        });
        citySelect?.addEventListener("change", refreshOffices);
        officeSelect?.addEventListener("change", () => {
            const index = Number(officeSelect.value);
            selectedCityItem = officeSelect.value === "" ? null : officeSelect._cartorioItems?.[index] || null;
            if (cityApplyButton) cityApplyButton.disabled = !selectedCityItem;
            if (selectedCityItem) setStatus(cityStatus, `Cartório selecionado: ${selectedCityItem.nome}. Clique em Aplicar para preencher.`, "success");
        });
        cityApplyButton?.addEventListener("click", () => {
            fillForm(selectedCityItem);
            if (selectedCityItem) setStatus(cityStatus, `Dados de ${selectedCityItem.nome} aplicados ao cadastro.`, "success");
        });
        cnsInput?.addEventListener("input", async () => {
            const cns = cleanCns(cnsInput.value);
            cnsInput.value = formatCns(cns);
            if (cns.length < 6) {
                selectedCnsItem = null;
                if (cnsApplyButton) cnsApplyButton.disabled = true;
                setStatus(cnsStatus, cns.length ? `Digite os ${6 - cns.length} numero(s) restantes.` : "");
                return;
            }
            setStatus(cnsStatus, "Consultando CNS no Justiça Aberta/CNJ...", "loading");
            try {
                const items = await requestCatalog({ cns }, "cns");
                selectedCnsItem = items[0] || null;
                if (!selectedCnsItem) throw new Error("CNS não encontrado ou não pertence a Registro de Imóveis.");
                if (cnsApplyButton) cnsApplyButton.disabled = false;
                const location = [selectedCnsItem.cidade, selectedCnsItem.uf].filter(Boolean).join(" / ");
                setStatus(cnsStatus, `CNS encontrado: ${selectedCnsItem.nome}${location ? ` — ${location}` : ""}. Clique em Aplicar dados deste CNS.`, "success");
            } catch (error) {
                if (error.name === "AbortError") return;
                selectedCnsItem = null;
                if (cnsApplyButton) cnsApplyButton.disabled = true;
                setStatus(cnsStatus, error.message, "error");
            }
        });
        cnsApplyButton?.addEventListener("click", () => {
            fillForm(selectedCnsItem);
            if (selectedCnsItem) setStatus(cnsStatus, `Dados de ${selectedCnsItem.nome} aplicados ao cadastro.`, "success");
        });

        setOffices([], "Escolha a cidade");
    });
}

function initMatrixLiveFilters() {
    const filterInput = document.querySelector("[data-live-filter-input]");
    const globalForm = document.querySelector(".global-search");
    const globalInput = globalForm?.querySelector('input[name="q"]');
    const inputs = [filterInput, globalInput].filter(Boolean);
    const getRows = () => Array.from(document.querySelectorAll(".matrix-project-row[data-project-id]"));
    const emptyRow = document.querySelector("[data-matrix-search-empty]");
    if (!inputs.length || !getRows().length || !window.SearchUtils) return;

    const syncUrl = window.SearchUtils.debounce((query) => {
        const url = new URL(window.location.href);
        if (query.trim()) url.searchParams.set("q", query.trim());
        else url.searchParams.delete("q");
        window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
    }, 120);

    const applySearch = (query, updateUrl = true) => {
        let visible = 0;
        getRows().forEach((row) => {
            const matches = window.SearchUtils.matchesSearch(
                [row.dataset.projectSearch || ""],
                query,
            );
            row.hidden = !matches;
            if (matches) visible += 1;
        });
        inputs.forEach((input) => {
            if (input.value !== query) input.value = query;
            input.classList.toggle("is-active", Boolean(query.trim()));
        });
        if (emptyRow) emptyRow.hidden = visible !== 0;
        if (updateUrl) syncUrl(query);
    };

    inputs.forEach((input) => {
        input.addEventListener("input", () => applySearch(input.value));
    });
    globalForm?.addEventListener("submit", (event) => {
        event.preventDefault();
        applySearch(globalInput?.value || "");
    });
    document.addEventListener("geogestao:matrix-updated", () => {
        applySearch(filterInput?.value || globalInput?.value || "", false);
    });
    applySearch(filterInput?.value || globalInput?.value || "", false);
}

function initRepresentativeManagers(root = document) {
    root.querySelectorAll("[data-representative-manager]").forEach((manager) => {
        if (manager.dataset.representativeManagerReady === "1") return;
        const list = manager.querySelector("[data-rep-list]");
        const empty = manager.querySelector("[data-rep-empty]");
        const addButton = manager.querySelector("[data-rep-add]");
        const popout = manager.querySelector("[data-rep-popout]");
        const template = manager.querySelector("[data-rep-template]");
        const title = manager.querySelector("[data-rep-popout-title]");
        const saveButton = manager.querySelector("[data-rep-save]");
        let editingRow = null;

        if (!list || !popout || !template) return;
        manager.dataset.representativeManagerReady = "1";

        const fields = Array.from(popout.querySelectorAll("[data-rep-field]"));

        function updateEmptyState() {
            const hasRows = Boolean(list.querySelector("[data-rep-row]"));
            if (empty) empty.style.display = hasRows ? "none" : "block";
        }

        function rowInput(row, field) {
            return row.querySelector(`[data-rep-value="${field}"]`);
        }

        function getRowValue(row, field) {
            const input = rowInput(row, field);
            return input ? input.value : "";
        }

        function setRowValue(row, field, value) {
            const input = rowInput(row, field);
            if (input) input.value = value || "";
        }

        function typeLabel(value) {
            const select = popout.querySelector('[data-rep-field="tipo_representacao"]');
            if (!select) return value || "Procurador";
            const option = Array.from(select.options).find((item) => item.value === value);
            return option ? option.textContent : "Procurador";
        }

        function refreshRowLabels(row) {
            const name = getRowValue(row, "nome_completo") || "Sem nome";
            const cpf = getRowValue(row, "cpf") || "CPF pendente";
            const type = getRowValue(row, "tipo_representacao") || "PROCURADOR";
            const nameLabel = row.querySelector("[data-rep-label-name]");
            const cpfLabel = row.querySelector("[data-rep-label-cpf]");
            const typeNode = row.querySelector("[data-rep-label-type]");
            if (nameLabel) nameLabel.textContent = name;
            if (cpfLabel) cpfLabel.textContent = cpf;
            if (typeNode) typeNode.textContent = typeLabel(type);
        }

        function openPopout(row = null) {
            editingRow = row;
            fields.forEach((field) => {
                field.value = row ? getRowValue(row, field.dataset.repField) : "";
            });
            const typeField = popout.querySelector('[data-rep-field="tipo_representacao"]');
            if (typeField && !typeField.value) typeField.value = "PROCURADOR";
            const addressTypeField = popout.querySelector('[data-rep-field="tipo_endereco"]');
            if (addressTypeField && !addressTypeField.value) addressTypeField.value = "URBANO";
            if (title) title.textContent = row ? "Editar responsavel" : "Novo responsavel";
            popout.classList.remove("is-hidden");
            const first = popout.querySelector('[data-rep-field="nome_completo"]');
            if (first) first.focus();
        }

        function closePopout() {
            editingRow = null;
            popout.classList.add("is-hidden");
            fields.forEach((field) => {
                field.value = "";
                field.classList.remove("is-invalid");
            });
        }

        function createRow() {
            const fragment = template.content.cloneNode(true);
            const row = fragment.querySelector("[data-rep-row]");
            list.insertBefore(fragment, empty || null);
            return row || list.querySelector("[data-rep-row]:last-of-type");
        }

        function savePopout() {
            const name = (popout.querySelector('[data-rep-field="nome_completo"]')?.value || "").trim();
            const cpf = (popout.querySelector('[data-rep-field="cpf"]')?.value || "").trim();
            if (!name && !cpf) {
                alert("Informe ao menos o nome ou CPF do responsavel.");
                return;
            }
            const row = editingRow || createRow();
            if (!row) return;
            fields.forEach((field) => {
                setRowValue(row, field.dataset.repField, field.value.trim());
            });
            refreshRowLabels(row);
            updateEmptyState();
            closePopout();
        }

        if (addButton) addButton.addEventListener("click", () => openPopout());
        if (saveButton) saveButton.addEventListener("click", savePopout);
        popout.querySelectorAll("[data-rep-cancel]").forEach((button) => {
            button.addEventListener("click", closePopout);
        });

        list.addEventListener("click", (event) => {
            const edit = event.target.closest("[data-rep-edit]");
            const remove = event.target.closest("[data-rep-remove]");
            const row = event.target.closest("[data-rep-row]");
            if (edit && row) {
                openPopout(row);
            }
            if (remove && row && confirm("Remover este responsavel?")) {
                row.remove();
                updateEmptyState();
            }
        });

        list.querySelectorAll("[data-rep-row]").forEach(refreshRowLabels);
        updateEmptyState();
    });
}

function initRepresentationManagers(root = document) {
    root.querySelectorAll("[data-representation-manager]").forEach((manager) => {
        if (manager.dataset.representationReady === "1") return;
        manager.dataset.representationReady = "1";

        const clientId = manager.dataset.clientId;
        const saveUrl = manager.dataset.saveUrl;
        const searchUrl = manager.dataset.searchUrl;
        const createPessoaUrl = manager.dataset.createPessoaUrl;

        const modal = document.getElementById(`modal-representacao-${clientId}`);
        if (!modal) return;
        const papeis = JSON.parse(modal.dataset.papeis || "{}");

        const form = {
            id: modal.querySelector('[data-rp-field="representacao_id"]'),
            natureza: modal.querySelector('[data-rp-field="natureza"]'),
            principal: modal.querySelector('[data-rp-field="principal"]'),
            documentoBase: modal.querySelector('[data-rp-field="documento_base"]'),
            referenciaDocumento: modal.querySelector('[data-rp-field="referencia_documento"]'),
            escopoPoderes: modal.querySelector('[data-rp-field="escopo_poderes"]'),
            validadeInicio: modal.querySelector('[data-rp-field="validade_inicio"]'),
            validadeFim: modal.querySelector('[data-rp-field="validade_fim"]'),
            observacoes: modal.querySelector('[data-rp-field="observacoes"]'),
        };
        const repList = modal.querySelector("[data-rp-representantes]");
        const repEmpty = modal.querySelector("[data-rp-representantes-empty]");
        const repRowTemplate = modal.querySelector("[data-rp-representante-template]");
        const searchInput = modal.querySelector("[data-rp-search-input]");
        const searchResults = modal.querySelector("[data-rp-search-results]");
        const newPersonToggle = modal.querySelector("[data-rp-new-person]");
        const newPersonForm = modal.querySelector("[data-rp-new-person-form]");
        const newPersonSave = modal.querySelector("[data-rp-new-person-save]");
        const errorBox = modal.querySelector("[data-rp-error]");
        const saveButton = modal.querySelector("[data-rp-save]");
        const modalTitle = modal.querySelector("[data-representation-modal-title]");

        let representantes = [];
        let bsModal = null;

        function showError(message) {
            if (!errorBox) return;
            errorBox.textContent = message || "";
            errorBox.style.display = message ? "block" : "none";
        }

        function renderRepresentantes() {
            if (!repList) return;
            repList.querySelectorAll("[data-rp-representante-row]").forEach((row) => row.remove());
            representantes.forEach((rep, index) => {
                const row = repRowTemplate.content.firstElementChild.cloneNode(true);
                row.querySelector("[data-rp-rep-nome]").textContent = rep.nome;
                const select = row.querySelector("[data-rp-rep-papel]");
                Object.entries(papeis).forEach(([key, label]) => {
                    const option = document.createElement("option");
                    option.value = key;
                    option.textContent = label;
                    if (key === rep.papel) option.selected = true;
                    select.appendChild(option);
                });
                select.addEventListener("change", () => { rep.papel = select.value; });
                row.querySelector("[data-rp-rep-remove]").addEventListener("click", () => {
                    representantes.splice(index, 1);
                    renderRepresentantes();
                });
                repList.insertBefore(row, repEmpty);
            });
            if (repEmpty) repEmpty.hidden = representantes.length > 0;
        }

        function addRepresentante(pessoaId, nome, papel) {
            if (representantes.some((rep) => rep.pessoa_id === pessoaId)) return;
            representantes.push({ pessoa_id: pessoaId, nome, papel: papel || "PROCURADOR" });
            renderRepresentantes();
            if (searchInput) searchInput.value = "";
            if (searchResults) searchResults.innerHTML = "";
        }

        function resetForm() {
            form.id.value = "";
            form.natureza.value = "";
            form.principal.checked = false;
            if (form.documentoBase) form.documentoBase.value = "";
            if (form.referenciaDocumento) form.referenciaDocumento.value = "";
            if (form.escopoPoderes) form.escopoPoderes.value = "";
            if (form.validadeInicio) form.validadeInicio.value = "";
            if (form.validadeFim) form.validadeFim.value = "";
            if (form.observacoes) form.observacoes.value = "";
            representantes = [];
            renderRepresentantes();
            modal.querySelectorAll("[data-rp-representado]").forEach((checkbox) => {
                checkbox.checked = checkbox.disabled; // titular vem marcado e travado
            });
            modal.querySelectorAll("[data-rp-modo-option]").forEach((radio) => {
                radio.checked = radio.value === "INDIVIDUAL";
            });
            if (newPersonForm) newPersonForm.classList.add("is-hidden");
            showError("");
            if (modalTitle) modalTitle.textContent = "Nova representação";
        }

        function fillFormForEdit(representacao) {
            resetForm();
            form.id.value = representacao.representacao_id;
            form.natureza.value = representacao.natureza || "";
            form.principal.checked = Boolean(representacao.principal);
            if (form.documentoBase) form.documentoBase.value = representacao.documento_base || "";
            if (form.referenciaDocumento) form.referenciaDocumento.value = representacao.referencia_documento || "";
            if (form.escopoPoderes) form.escopoPoderes.value = representacao.escopo_poderes || "";
            if (form.validadeInicio) form.validadeInicio.value = representacao.validade_inicio || "";
            if (form.validadeFim) form.validadeFim.value = representacao.validade_fim || "";
            if (form.observacoes) form.observacoes.value = representacao.observacoes || "";
            (representacao.representantes || []).forEach((rep) => {
                representantes.push({ pessoa_id: rep.pessoa_id, nome: rep.nome, papel: rep.papel });
            });
            renderRepresentantes();
            modal.querySelectorAll("[data-rp-modo-option]").forEach((radio) => {
                radio.checked = radio.value === representacao.modo_atuacao;
            });
            const representadoIds = new Set((representacao.representados || []).map((item) => item.cliente_id || item.pessoa_id));
            modal.querySelectorAll("[data-rp-representado]").forEach((checkbox) => {
                if (representadoIds.has(checkbox.dataset.id)) checkbox.checked = true;
            });
            if (modalTitle) modalTitle.textContent = "Editar representação";
        }

        function openModal() {
            if (!bsModal) bsModal = window.bootstrap?.Modal.getOrCreateInstance(modal);
            bsModal?.show();
        }

        manager.querySelector("[data-representation-add]")?.addEventListener("click", () => {
            resetForm();
            openModal();
        });

        manager.querySelectorAll("[data-representation-edit]").forEach((button) => {
            button.addEventListener("click", () => {
                const card = button.closest("[data-representation-card]");
                const representacao = JSON.parse(card.dataset.representacao || "{}");
                fillFormForEdit(representacao);
                openModal();
            });
        });

        manager.querySelectorAll("[data-representation-deactivate]").forEach((button) => {
            button.addEventListener("click", async () => {
                if (!confirm("Desativar esta representação? Ela deixa de aparecer como ativa, mas continua no histórico.")) return;
                const representacaoId = button.dataset.representacaoId;
                button.disabled = true;
                try {
                    const response = await fetch(`/clients/${clientId}/representacoes/${representacaoId}/desativar`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                    });
                    const data = await response.json().catch(() => ({}));
                    if (!response.ok) throw new Error(data.error || "Não foi possível desativar.");
                    await window.GeoGestaoClients?.reloadClientFragment(clientId);
                } catch (error) {
                    alert(error.message || "Não foi possível desativar a representação.");
                    button.disabled = false;
                }
            });
        });

        let searchTimer = null;
        searchInput?.addEventListener("input", () => {
            window.clearTimeout(searchTimer);
            const termo = searchInput.value.trim();
            searchTimer = window.setTimeout(async () => {
                if (!searchResults) return;
                if (!termo) { searchResults.innerHTML = ""; return; }
                try {
                    const response = await fetch(`${searchUrl}?q=${encodeURIComponent(termo)}`, {
                        headers: { "X-Requested-With": "XMLHttpRequest" },
                    });
                    const data = await response.json();
                    searchResults.innerHTML = "";
                    (data.pessoas || []).forEach((pessoa) => {
                        const item = document.createElement("button");
                        item.type = "button";
                        item.className = "representation-search-item";
                        item.textContent = `${pessoa.nome_display}${pessoa.documento ? " — " + pessoa.documento : ""}`;
                        item.addEventListener("click", () => addRepresentante(pessoa.pessoa_id, pessoa.nome_display, "PROCURADOR"));
                        searchResults.appendChild(item);
                    });
                    if (!(data.pessoas || []).length) {
                        const empty = document.createElement("div");
                        empty.className = "representation-search-empty";
                        empty.textContent = "Nenhuma pessoa encontrada.";
                        searchResults.appendChild(empty);
                    }
                } catch {
                    searchResults.innerHTML = "";
                }
            }, 250);
        });

        newPersonToggle?.addEventListener("click", () => {
            newPersonForm?.classList.toggle("is-hidden");
        });

        newPersonSave?.addEventListener("click", async () => {
            const tipo = modal.querySelector("[data-rp-new-tipo]")?.value || "PESSOA_FISICA";
            const nome = modal.querySelector("[data-rp-new-nome]")?.value.trim();
            const documento = modal.querySelector("[data-rp-new-documento]")?.value.trim();
            if (!nome) { showError("Informe o nome da nova pessoa."); return; }
            const payload = { tipo_pessoa: tipo, nome_exibicao: nome, documento };
            if (tipo === "PESSOA_JURIDICA") payload.pessoa_juridica = { razao_social: nome, cnpj: documento };
            else payload.pessoa_fisica = { nome_completo: nome, cpf: documento };
            try {
                const response = await fetch(createPessoaUrl, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload),
                });
                const data = await response.json();
                if (!response.ok) throw new Error(data.error || "Não foi possível cadastrar a pessoa.");
                addRepresentante(data.pessoa_id, nome, "PROCURADOR");
                newPersonForm?.classList.add("is-hidden");
                modal.querySelectorAll("[data-rp-new-nome],[data-rp-new-documento]").forEach((input) => { input.value = ""; });
                showError("");
            } catch (error) {
                showError(error.message || "Não foi possível cadastrar a pessoa.");
            }
        });

        saveButton?.addEventListener("click", async () => {
            showError("");
            if (!representantes.length) { showError("Adicione ao menos um representante."); return; }
            const representados = Array.from(modal.querySelectorAll("[data-rp-representado]:checked")).map((checkbox) => (
                checkbox.dataset.tipo === "cliente" ? { cliente_id: Number(checkbox.dataset.id) } : { pessoa_id: checkbox.dataset.id }
            ));
            if (!representados.length) { showError("Selecione ao menos um representado."); return; }
            const modoSelecionado = modal.querySelector("[data-rp-modo-option]:checked")?.value || "INDIVIDUAL";
            const payload = {
                representacao_id: form.id.value || undefined,
                natureza: form.natureza.value.trim() || undefined,
                modo_atuacao: modoSelecionado,
                principal: form.principal.checked,
                ativo: true,
                documento_base: form.documentoBase?.value.trim() || undefined,
                referencia_documento: form.referenciaDocumento?.value.trim() || undefined,
                escopo_poderes: form.escopoPoderes?.value.trim() || undefined,
                validade_inicio: form.validadeInicio?.value || undefined,
                validade_fim: form.validadeFim?.value || undefined,
                observacoes: form.observacoes?.value.trim() || undefined,
                representantes: representantes.map((rep, index) => ({
                    pessoa_id: rep.pessoa_id, papel: rep.papel || "PROCURADOR", principal: index === 0, ordem: index,
                })),
                representados,
            };
            saveButton.disabled = true;
            try {
                const response = await fetch(saveUrl, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload),
                });
                const data = await response.json();
                if (!response.ok) throw new Error(data.error || "Não foi possível salvar a representação.");
                bsModal?.hide();
                await window.GeoGestaoClients?.reloadClientFragment(clientId);
            } catch (error) {
                showError(error.message || "Não foi possível salvar a representação.");
            } finally {
                saveButton.disabled = false;
            }
        });
    });
}

function initClientLiveSearch() {
    const form = document.querySelector("[data-client-search-form]");
    const input = document.querySelector("[data-client-search-input]");
    const clearButton = document.querySelector("[data-client-search-clear]");
    const rows = Array.from(document.querySelectorAll("[data-client-row]"));
    const filterLinks = Array.from(document.querySelectorAll(".client-filter-bar a"));
    const resultCount = document.querySelector("[data-client-result-count]");
    const emptyState = document.querySelector("[data-client-empty-state]");
    if (!form || !input || !window.SearchUtils || !rows.length) return;

    const applySearch = () => {
        const query = input.value;
        let visible = 0;
        rows.forEach((row) => {
            const fields = [row.dataset.searchText || ""];
            const match = window.SearchUtils.matchesSearch(fields, query);
            row.hidden = !match;
            if (match) visible += 1;
        });

        if (resultCount) {
            resultCount.textContent = visible === 1 ? "1 cliente encontrado" : `${visible} clientes encontrados`;
        }
        if (emptyState) {
            emptyState.hidden = visible !== 0;
        }
        if (clearButton) {
            clearButton.hidden = !query;
        }
        updateFilterLinks(query);
    };

    const debouncedApplySearch = window.SearchUtils.debounce(applySearch, 180);
    form.addEventListener("submit", (event) => {
        event.preventDefault();
        applySearch();
    });
    input.addEventListener("input", debouncedApplySearch);
    if (clearButton) {
        clearButton.addEventListener("click", () => {
            input.value = "";
            input.focus();
            applySearch();
        });
    }
    applySearch();

    function updateFilterLinks(query) {
        filterLinks.forEach((link) => {
            const url = new URL(link.href, window.location.origin);
            if (query) {
                url.searchParams.set("q", query);
            } else {
                url.searchParams.delete("q");
            }
            link.href = `${url.pathname}${url.search}`;
        });
    }
}

function initClientLazyModals() {
    const host = document.querySelector("[data-client-modal-host]");
    const triggers = Array.from(document.querySelectorAll("[data-client-modal-trigger]"));
    if (!host || !triggers.length || !window.bootstrap) return;

    const cacheTtlMs = 30 * 1000;
    const responseCache = new Map();
    let activeRequest = null;

    function getCached(clientId) {
        const cached = responseCache.get(clientId);
        if (!cached) return null;
        if (cached.expiresAt <= Date.now()) {
            responseCache.delete(clientId);
            return null;
        }
        return cached.html;
    }

    async function loadHtml(trigger, interactive = false) {
        const clientId = trigger.dataset.clientId;
        const url = trigger.dataset.clientModalUrl;
        if (!clientId || !url) throw new Error("Cliente invalido.");

        const cached = getCached(clientId);
        if (cached) return cached;
        if (activeRequest && activeRequest.clientId === clientId) {
            if (interactive) activeRequest.interactive = true;
            return activeRequest.promise;
        }
        if (activeRequest) {
            if (activeRequest.interactive && !interactive) return null;
            activeRequest.controller.abort();
        }

        const controller = new AbortController();
        const requestState = { clientId, controller, interactive, promise: null };
        requestState.promise = fetch(url, {
            method: "GET",
            credentials: "same-origin",
            cache: "no-store",
            headers: { "X-Requested-With": "XMLHttpRequest" },
            signal: controller.signal,
        }).then(async (response) => {
            if (response.redirected && new URL(response.url, window.location.origin).pathname === "/login") {
                window.location.assign(response.url);
                throw new Error("Sua sessao expirou. Redirecionando para o login.");
            }
            if (!response.ok) {
                const message = (await response.text()).trim();
                throw new Error(message || "Nao foi possivel carregar o cliente.");
            }
            const html = await response.text();
            const version = Date.now();
            responseCache.set(clientId, {
                html,
                expiresAt: Date.now() + cacheTtlMs,
                version,
            });
            window.setTimeout(() => evictExpiredFragment(clientId, version), cacheTtlMs + 250);
            return html;
        }).finally(() => {
            if (activeRequest === requestState) activeRequest = null;
        });
        activeRequest = requestState;
        return requestState.promise;
    }

    function initializeFragment(root) {
        if (window.CityService) window.CityService.initPickers(root);
        initDocumentalClientForm(root);
        initRepresentativeManagers(root);
        initRepresentationManagers(root);
        initPendingFocusShortcuts(root);
    }

    function disposeFragment(wrapper) {
        if (!wrapper) return;
        wrapper.querySelectorAll(".modal").forEach((modal) => {
            bootstrap.Modal.getInstance(modal)?.dispose();
        });
        wrapper.remove();
    }

    function evictExpiredFragment(clientId, version) {
        const cached = responseCache.get(clientId);
        if (!cached || cached.version !== version || cached.expiresAt > Date.now()) return;
        responseCache.delete(clientId);
        const wrapper = host.querySelector(`[data-client-modal-fragment="${clientId}"]`);
        if (!wrapper) return;
        const openedModal = wrapper.querySelector(".modal.show");
        if (!openedModal) {
            disposeFragment(wrapper);
            return;
        }
        openedModal.addEventListener("hidden.bs.modal", () => {
            window.setTimeout(() => {
                if (!wrapper.querySelector(".modal.show")) disposeFragment(wrapper);
            }, 300);
        }, { once: true });
    }

    function installFragment(clientId, html) {
        let wrapper = host.querySelector(`[data-client-modal-fragment="${clientId}"]`);
        const cached = responseCache.get(clientId);
        const version = cached ? String(cached.version) : "";
        if (wrapper && wrapper.dataset.clientModalVersion === version) return wrapper;
        if (wrapper) disposeFragment(wrapper);

        const template = document.createElement("template");
        template.innerHTML = String(html || "").trim();
        wrapper = template.content.querySelector(`[data-client-modal-fragment="${clientId}"]`);
        if (!wrapper) throw new Error("Resposta invalida ao carregar o cliente.");
        host.appendChild(template.content);
        wrapper = host.querySelector(`[data-client-modal-fragment="${clientId}"]`);
        wrapper.dataset.clientModalVersion = version;
        initializeFragment(wrapper);
        return wrapper;
    }

    function setLoading(trigger, loading) {
        if (!trigger.dataset.originalText) trigger.dataset.originalText = trigger.textContent;
        trigger.classList.toggle("is-loading", loading);
        trigger.setAttribute("aria-busy", loading ? "true" : "false");
        trigger.textContent = loading ? "Carregando..." : trigger.dataset.originalText;
    }

    async function openFromTrigger(trigger) {
        setLoading(trigger, true);
        try {
            const clientId = trigger.dataset.clientId;
            const html = await loadHtml(trigger, true);
            const wrapper = installFragment(clientId, html);
            const kind = trigger.dataset.clientModalKind;
            const prefix = kind === "pending" ? "modal-pendencias-" : (kind === "qualification" ? "modal-qualificacao-" : "modal-client-");
            const modalElement = wrapper.querySelector(`#${prefix}${clientId}`);
            if (!modalElement) throw new Error("Modal do cliente nao encontrado.");
            bootstrap.Modal.getOrCreateInstance(modalElement).show();
        } catch (error) {
            if (error && error.name === "AbortError") return;
            alert(error.message || "Nao foi possivel carregar o cliente.");
        } finally {
            setLoading(trigger, false);
        }
    }

    function preload(trigger) {
        loadHtml(trigger, false).catch((error) => {
            if (!error || error.name !== "AbortError") {
                console.warn("Falha ao pre-carregar cliente:", error);
            }
        });
    }

    triggers.forEach((trigger) => {
        trigger.addEventListener("pointerenter", () => preload(trigger));
        trigger.addEventListener("focus", () => preload(trigger));
        trigger.addEventListener("click", () => openFromTrigger(trigger));
    });

    // Depois de salvar/desativar uma representacao via AJAX (fora do form
    // principal do cliente), o fragmento em cache fica desatualizado. Isso
    // permite descartar o cache e reabrir o mesmo modal ja atualizado.
    window.GeoGestaoClients = window.GeoGestaoClients || {};
    window.GeoGestaoClients.reloadClientFragment = async (clientId) => {
        responseCache.delete(String(clientId));
        const trigger = triggers.find((item) => item.dataset.clientId === String(clientId) && item.dataset.clientModalKind === "edit");
        if (trigger) await openFromTrigger(trigger);
    };
}

function initProjectClientAutocompletes(root = document) {
    const widgets = Array.from(root.querySelectorAll("[data-client-autocomplete]"));
    if (!widgets.length) return;

    widgets.forEach((widget) => {
        if (widget.dataset.clientAutocompleteReady === "1") return;
        const input = widget.querySelector("[data-client-autocomplete-input]");
        const hidden = widget.querySelector("[data-client-autocomplete-id]");
        const list = widget.querySelector("[data-client-autocomplete-list]");
        const sourceName = widget.dataset.clientSource || "projectClientes";
        if (!input || !hidden || !list || input.disabled || input.readOnly) return;
        widget.dataset.clientAutocompleteReady = "1";

        const getSource = () => Array.isArray(window[sourceName]) ? window[sourceName] : [];
        let selectedLabel = input.value.trim();
        let activeIndex = -1;
        let creatingClient = false;

        function normalize(value) {
            if (window.SearchUtils) return window.SearchUtils.normalizeSearchText(value);
            return String(value || "").toLowerCase().trim();
        }

        function matchClient(client, query) {
            const fields = [client.nome, client.search, client.cidade, client.uf];
            if (window.SearchUtils) return window.SearchUtils.matchesSearch(fields, query);
            return normalize(fields.join(" ")).includes(normalize(query));
        }

        function setListOpen(open) {
            list.classList.toggle("open", open && list.children.length > 0);
        }

        function pick(client) {
            input.value = client.nome || "";
            hidden.value = client.id || "";
            selectedLabel = input.value.trim();
            list.innerHTML = "";
            setListOpen(false);
            input.dispatchEvent(new Event("change", { bubbles: true }));
        }

        function findExact(query) {
            const normalizedQuery = normalize(query);
            return getSource().find((client) => normalize(client.nome) === normalizedQuery);
        }

        async function createDraftClient(name, item, extra = {}) {
            const cleanName = String(name || "").trim();
            if (!cleanName || creatingClient) return;
            creatingClient = true;
            if (item) item.textContent = `Adicionando "${cleanName}"...`;
            try {
                const response = await fetch("/api/add-cliente", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ nome: cleanName, ...extra }),
                });
                const data = await response.json();
                if (response.status === 409 && data.requires_confirmation) {
                    const names = (data.matches || []).map((client) => `- ${client.nome}`).join("\n");
                    const proceed = confirm(`Ja existe cliente com este nome:\n${names}\n\nDeseja criar outro cadastro mesmo assim?`);
                    if (!proceed) {
                        if (data.matches && data.matches[0]) pick(data.matches[0]);
                        return;
                    }
                    const note = prompt("Informe um dado para diferenciar este cadastro (CPF/CNPJ, telefone ou observacao):");
                    if (!note || !note.trim()) {
                        alert("Cadastro cancelado. Para duplicar um nome, informe um dado diferente.");
                        return;
                    }
                    creatingClient = false;
                    await createDraftClient(cleanName, item, { confirm_duplicate: true, duplicate_note: note.trim() });
                    return;
                }
                if (!response.ok || !data.id) throw new Error(data.error || "Falha ao criar cliente");
                const client = { id: data.id, nome: data.nome || cleanName, search: data.search || cleanName };
                window[sourceName] = [...getSource(), client];
                pick(client);
            } catch (error) {
                if (item) item.textContent = error.message || "Nao foi possivel adicionar. Tente novamente.";
            } finally {
                creatingClient = false;
            }
        }

        function render() {
            const query = input.value.trim();
            list.innerHTML = "";
            activeIndex = -1;

            if (!query) {
                hidden.value = "";
                selectedLabel = "";
                getSource().slice(0, 4).forEach((client) => {
                    const item = document.createElement("div");
                    item.className = "ac-item";
                    item.setAttribute("role", "option");
                    item.innerHTML = `<span><strong>${escapeHtml(client.nome || "")}</strong>${client.cidade ? `<span class="ac-item-meta">${escapeHtml([client.cidade, client.uf].filter(Boolean).join(" - "))}</span>` : ""}</span>`;
                    item.addEventListener("mousedown", (event) => {
                        event.preventDefault();
                        pick(client);
                    });
                    list.appendChild(item);
                });
                if (!list.children.length) {
                    const empty = document.createElement("div");
                    empty.className = "ac-empty";
                    empty.textContent = "Nenhum cliente cadastrado";
                    list.appendChild(empty);
                }
                setListOpen(true);
                return;
            }

            if (query !== selectedLabel) hidden.value = "";
            const clients = getSource();
            const hits = clients.filter((client) => matchClient(client, query)).slice(0, 8);

            hits.forEach((client) => {
                const item = document.createElement("div");
                item.className = "ac-item";
                item.setAttribute("role", "option");
                item.innerHTML = `<span><strong>${escapeHtml(client.nome || "")}</strong>${client.cidade ? `<span class="ac-item-meta">${escapeHtml([client.cidade, client.uf].filter(Boolean).join(" - "))}</span>` : ""}</span>`;
                item.addEventListener("mousedown", (event) => {
                    event.preventDefault();
                    pick(client);
                });
                list.appendChild(item);
            });

            if (!hits.length) {
                const empty = document.createElement("div");
                empty.className = "ac-empty";
                empty.textContent = "Nenhum cliente encontrado";
                list.appendChild(empty);
            }

            if (query.length >= 2 && !findExact(query)) {
                const create = document.createElement("div");
                create.className = "ac-item ac-new";
                create.setAttribute("role", "option");
                create.textContent = ` Adicionar cliente: ${query}`;
                create.addEventListener("mousedown", (event) => {
                    event.preventDefault();
                    createDraftClient(query, create);
                });
                list.appendChild(create);
            }

            setListOpen(true);
        }

        input.addEventListener("input", render);
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
                setListOpen(false);
                return;
            } else {
                return;
            }
            options.forEach((option, index) => option.classList.toggle("is-active", index === activeIndex));
        });
        input.addEventListener("blur", () => {
            const exact = !hidden.value && findExact(input.value.trim());
            if (exact) pick(exact);
            setTimeout(() => setListOpen(false), 120);
        });
        if (input.form) {
            input.form.addEventListener("submit", () => {
                const exact = !hidden.value && findExact(input.value.trim());
                if (exact) {
                    input.value = exact.nome;
                    hidden.value = exact.id;
                }
            });
        }
    });
}

function initProjectOwnerManagers() {
    document.querySelectorAll("[data-project-owners-manager]").forEach((manager) => {
        const list = manager.querySelector("[data-project-owner-list]");
        const template = manager.querySelector("[data-project-owner-template]");
        const addButton = manager.querySelector("[data-add-project-owner]");
        const form = manager.closest("form");
        if (!list || manager.dataset.projectOwnersReady === "1") return;
        manager.dataset.projectOwnersReady = "1";

        function removeRow(button) {
            const row = button.closest("[data-project-owner-row]");
            if (row) row.remove();
        }

        function bindRow(row) {
            row.querySelector("[data-remove-project-owner]")?.addEventListener("click", (event) => {
                removeRow(event.currentTarget);
            });
            initProjectClientAutocompletes(row);
            row.querySelector("[data-client-autocomplete-input]")?.focus();
        }

        list.querySelectorAll("[data-project-owner-row]").forEach((row) => {
            row.querySelector("[data-remove-project-owner]")?.addEventListener("click", (event) => {
                removeRow(event.currentTarget);
            });
        });

        addButton?.addEventListener("click", () => {
            if (!template) return;
            const fragment = template.content.cloneNode(true);
            const row = fragment.querySelector("[data-project-owner-row]");
            list.appendChild(fragment);
            if (row) bindRow(row);
        });

        form?.addEventListener("submit", (event) => {
            const primaryId = form.querySelector('[name="cliente_id"]')?.value || "";
            const selected = new Set(primaryId ? [primaryId] : []);
            let duplicateFound = false;
            list.querySelectorAll("[data-project-owner-row]").forEach((row) => {
                const hidden = row.querySelector('[name="proprietario_adicional_id"]');
                if (!hidden?.value) return;
                if (selected.has(hidden.value)) {
                    duplicateFound = true;
                    row.querySelector("[data-client-autocomplete-input]")?.focus();
                    return;
                }
                selected.add(hidden.value);
            });
            if (duplicateFound) {
                event.preventDefault();
                alert("O mesmo proprietario foi selecionado mais de uma vez.");
            }
        });
    });
}

function escapeHtml(value) {
    const element = document.createElement("span");
    element.textContent = String(value || "");
    return element.innerHTML;
}

function initDocumentalClientForm(root = document) {
    const forms = root.querySelectorAll(".cliente-form");
    if (!forms.length) return;

    const spouseRequiredRegimes = [
        "COMUNHAO_BENS",
        "COMUNHAO_PARCIAL",
        "COMUNHAO_PARCIAL_APOS_6515",
        "COMUNHAO_UNIVERSAL",
        "COMUNHAO_UNIVERSAL_ANTES_6515",
        "PARTICIPACAO_FINAL_AQUESTOS",
        "OUTRO_PACTO_ANTENUPCIAL",
    ];
    const spouseOptionalRegimes = ["SEPARACAO_TOTAL", "SEPARACAO_OBRIGATORIA"];

    forms.forEach((form) => {
        if (form.dataset.documentalClientReady === "1") return;
        form.dataset.documentalClientReady = "1";
        const tipoCliente = form.querySelector('[data-role="tipo-cliente"]');
        const quemAssina = form.querySelector('[data-role="quem-assina"]');
        const estadoCivil = form.querySelector('[data-role="estado-civil"]');
        const regimeCasamento = form.querySelector('[data-role="regime-casamento"]');
        const incluirConjuge = form.querySelector('[data-role="incluir-conjuge"]');
        const regimeField = form.querySelector('[data-role="regime-field"]');
        const pjNotice = form.querySelector(".pj-notice");
        const pfSexo = form.querySelector('[data-role="pf-sexo"]');
        const pfNacionalidade = form.querySelector('[data-role="pf-nacionalidade"]');
        let nacionalidadeTouched = Boolean(pfNacionalidade && pfNacionalidade.value.trim());

        function setSectionVisible(sectionName, visible, clearWhenHidden = false) {
            form.querySelectorAll(`[data-section="${sectionName}"]`).forEach((section) => {
                section.classList.toggle("is-hidden", !visible);
                if (!visible && clearWhenHidden) clearSection(section);
            });
        }

        function clearSection(section) {
            section.querySelectorAll("input, textarea, select").forEach((field) => {
                if (field.type === "checkbox" || field.type === "radio") {
                    field.checked = false;
                } else {
                    field.value = "";
                }
                field.classList.remove("is-invalid");
            });
        }

        function updateVisibility() {
            const isPJ = tipoCliente && tipoCliente.value === "PESSOA_JURIDICA";
            if (quemAssina) {
                if (isPJ) {
                    quemAssina.value = "PROCURADOR";
                    quemAssina.setAttribute("disabled", "disabled");
                } else {
                    quemAssina.removeAttribute("disabled");
                }
            }

            setSectionVisible("pf", !isPJ);
            setSectionVisible("pf-address", !isPJ);
            setSectionVisible("pj", isPJ);

            const civil = estadoCivil ? estadoCivil.value : "";
            const hasCivilRegime = civil === "CASADO" || civil === "UNIAO_ESTAVEL";
            if (regimeField) regimeField.classList.toggle("is-hidden", !hasCivilRegime || isPJ);
            if ((!hasCivilRegime || isPJ) && regimeCasamento) regimeCasamento.value = "";
            const regime = regimeCasamento ? regimeCasamento.value : "";

            const isSeparationTotal = hasCivilRegime && spouseOptionalRegimes.includes(regime);
            if (incluirConjuge) {
                incluirConjuge.closest(".spouse-opt-in").classList.toggle("is-hidden", isPJ || !isSeparationTotal);
                if (!isSeparationTotal) incluirConjuge.checked = false;
            }
            const requiresSpouse = hasCivilRegime && spouseRequiredRegimes.includes(regime);
            const showSpouse = !isPJ && (requiresSpouse || (isSeparationTotal && incluirConjuge && incluirConjuge.checked));
            setSectionVisible("conjuge", showSpouse, !showSpouse);

            const showProcurador = isPJ || (quemAssina && quemAssina.value === "PROCURADOR");
            setSectionVisible("procurador", showProcurador);
            if (pjNotice) pjNotice.style.display = isPJ ? "block" : "none";

            const summaryType = form.querySelector("[data-summary-type]");
            const summarySign = form.querySelector("[data-summary-sign]");
            if (summaryType && tipoCliente) summaryType.textContent = tipoCliente.options[tipoCliente.selectedIndex].textContent;
            if (summarySign && quemAssina) summarySign.textContent = quemAssina.options[quemAssina.selectedIndex].textContent;
            updateDefaultNationality();
            updateCityWarnings(form);
        }

        [tipoCliente, quemAssina, estadoCivil, regimeCasamento, incluirConjuge].forEach((element) => {
            if (element) element.addEventListener("change", updateVisibility);
        });

        form.querySelectorAll("[data-mask]").forEach((input) => {
            input.addEventListener("input", () => applyDocumentMask(input));
            applyDocumentMask(input);
        });

        if (pfNacionalidade) {
            pfNacionalidade.addEventListener("input", () => {
                nacionalidadeTouched = Boolean(pfNacionalidade.value.trim());
            });
        }
        if (pfSexo) {
            pfSexo.addEventListener("change", updateDefaultNationality);
        }

        setupCepLookup(form, updateCityWarnings);
        setupCpfInlineValidation(form);
        setupCnpjLookup(form, updateCityWarnings);

        form.addEventListener("submit", (event) => {
            if (quemAssina && quemAssina.disabled) {
                quemAssina.removeAttribute("disabled");
                quemAssina.value = "PROCURADOR";
            }
            if (!validateClientForm(form)) {
                event.preventDefault();
                event.stopPropagation();
            }
        });

        updateVisibility();

        function updateDefaultNationality() {
            if (!pfSexo || !pfNacionalidade || nacionalidadeTouched || pfNacionalidade.value.trim()) return;
            if (pfSexo.value === "MASCULINO") {
                pfNacionalidade.value = "brasileiro";
            } else if (pfSexo.value === "FEMININO") {
                pfNacionalidade.value = "brasileira";
            }
        }
    });

    initPendingFocusShortcuts(root);

    function updateCityWarnings(form) {
        // A validacao de cidade x UF vive no CityService (lista oficial do IBGE).
        if (window.CityService) window.CityService.refreshWarnings(form);
    }
}

function setupCepLookup(form, updateCityWarnings) {
    if (!window.CepService) return;
    const timers = new Map();
    form.querySelectorAll("[data-cep-prefix]").forEach((input) => {
        input.addEventListener("input", () => {
            clearTimeout(timers.get(input));
            timers.set(input, setTimeout(() => lookupCep(input), 450));
        });
        input.addEventListener("blur", () => lookupCep(input));
    });

    async function lookupCep(input) {
        const prefix = input.dataset.cepPrefix;
        const clean = window.CepService.cleanCep(input.value);
        const status = ensureCepStatus(input);
        if (!window.CepService.isCepCompleto(clean)) {
            setCepStatus(status, "", "");
            return;
        }
        if (input.dataset.lastCep === clean) return;
        input.dataset.lastCep = clean;
        setCepStatus(status, "Buscando CEP...", "loading");
        try {
            const data = await window.CepService.buscarEnderecoPorCep(clean);
            if (window.CepService.cleanCep(input.value) !== clean) return;
            if (!data || data.erro) {
                setCepStatus(status, "CEP nao encontrado. Preencha o endereco manualmente.", "warning");
                return;
            }
            window.CepService.aplicarEnderecoViaCep(form, prefix, data);
            setCepStatus(status, "Endereco atualizado pelo CEP.", "success");
            updateCityWarnings(form);
        } catch {
            setCepStatus(status, "Nao foi possivel buscar o CEP agora. Preencha manualmente.", "warning");
        }
    }
}

function ensureCepStatus(input) {
    const label = input.closest("label");
    if (!label) return null;
    let status = label.querySelector(".cep-status");
    if (!status) {
        status = document.createElement("small");
        status.className = "cep-status";
        label.appendChild(status);
    }
    return status;
}

function setCepStatus(status, message, state) {
    if (!status) return;
    status.textContent = message;
    status.dataset.state = state || "";
}

function initPendingFocusShortcuts(root = document) {
    root.querySelectorAll("[data-pending-focus]").forEach((button) => {
        if (button.dataset.pendingFocusReady === "1") return;
        button.dataset.pendingFocusReady = "1";
        button.addEventListener("click", () => {
            const pendingModalEl = button.closest(".modal");
            const fragment = button.closest("[data-client-modal-fragment]");
            const editModalEl = (fragment && fragment.querySelector(button.dataset.editModal)) || document.querySelector(button.dataset.editModal);
            if (!editModalEl || !window.bootstrap) return;

            const openEdit = () => {
                const editModal = bootstrap.Modal.getOrCreateInstance(editModalEl);
                editModalEl.addEventListener("shown.bs.modal", () => {
                    focusClientField(editModalEl, button.dataset.section, button.dataset.field);
                }, { once: true });
                editModal.show();
            };

            if (pendingModalEl && pendingModalEl.classList.contains("show")) {
                pendingModalEl.addEventListener("hidden.bs.modal", openEdit, { once: true });
                bootstrap.Modal.getOrCreateInstance(pendingModalEl).hide();
            } else {
                openEdit();
            }
        });
    });
}

function focusClientField(modalEl, sectionName, fieldName) {
    const field = modalEl.querySelector(`[name="${fieldName}"]`);
    const section = modalEl.querySelector(`[data-client-section="${sectionName}"]`) || (field ? field.closest(".client-section") : null);
    if (section) {
        section.classList.remove("is-hidden");
        section.scrollIntoView({ behavior: "smooth", block: "center" });
    }
    if (!field) return;
    setTimeout(() => {
        field.focus({ preventScroll: true });
        field.classList.add("field-highlight");
        const label = field.closest("label");
        if (label) label.classList.add("field-highlight-label");
        setTimeout(() => {
            field.classList.remove("field-highlight");
            if (label) label.classList.remove("field-highlight-label");
        }, 2600);
    }, 250);
}

function applyDocumentMask(input) {
    const mask = input.dataset.mask;
    let value = input.value || "";
    const digits = value.replace(/\D+/g, "");
    if (mask === "cpf") {
        input.value = digits
            .slice(0, 11)
            .replace(/^(\d{3})(\d)/, "$1.$2")
            .replace(/^(\d{3})\.(\d{3})(\d)/, "$1.$2.$3")
            .replace(/\.(\d{3})(\d)/, ".$1-$2");
    } else if (mask === "cnpj") {
        input.value = digits
            .slice(0, 14)
            .replace(/^(\d{2})(\d)/, "$1.$2")
            .replace(/^(\d{2})\.(\d{3})(\d)/, "$1.$2.$3")
            .replace(/\.(\d{3})(\d)/, ".$1/$2")
            .replace(/(\d{4})(\d)/, "$1-$2");
    } else if (mask === "cep") {
        input.value = digits.slice(0, 8).replace(/^(\d{5})(\d)/, "$1-$2");
    } else if (mask === "phone") {
        const limited = digits.slice(0, 11);
        if (limited.length > 10) {
            input.value = limited
                .replace(/^(\d{2})(\d)/, "($1) $2")
                .replace(/(\d{5})(\d)/, "$1-$2");
        } else {
            input.value = limited
                .replace(/^(\d{2})(\d)/, "($1) $2")
                .replace(/(\d{4})(\d)/, "$1-$2");
        }
    } else if (mask === "money" || mask === "decimal") {
        input.value = value.replace(/[^\d,.-]/g, "");
    }
}

function validateClientForm(form) {
    let ok = true;
    form.querySelectorAll(".field-error").forEach((error) => {
        error.textContent = "";
    });
    form.querySelectorAll(".is-invalid").forEach((field) => field.classList.remove("is-invalid"));

    function isApplicable(field) {
        const section = field.closest(".conditional-section");
        return !section || !section.classList.contains("is-hidden");
    }

    function setError(field, message) {
        ok = false;
        field.classList.add("is-invalid");
        const error = form.querySelector(`[data-error-for="${field.name}"]`);
        if (error) error.textContent = message;
    }

    form.querySelectorAll('[data-mask="cpf"]').forEach((field) => {
        if (isApplicable(field) && field.value && !validateCpf(field.value)) {
            setError(field, "Informe um CPF valido.");
        }
    });
    form.querySelectorAll('[data-mask="cnpj"]').forEach((field) => {
        if (isApplicable(field) && field.value && !validateCnpj(field.value)) {
            setError(field, "Informe um CNPJ valido.");
        }
    });
    form.querySelectorAll('[data-mask="cep"]').forEach((field) => {
        const digits = onlyDigits(field.value);
        if (isApplicable(field) && field.value && digits.length !== 8) {
            setError(field, "Informe um CEP no formato 00000-000.");
        }
    });
    form.querySelectorAll('input[type="email"]').forEach((field) => {
        if (isApplicable(field) && field.value && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(field.value)) {
            setError(field, "Informe um e-mail valido.");
        }
    });
    form.querySelectorAll('input[type="date"]').forEach((field) => {
        if (isApplicable(field) && field.value && !isValidDateInput(field.value)) {
            setError(field, "Informe uma data valida.");
        }
    });
    form.querySelectorAll('[data-mask="phone"]').forEach((field) => {
        const digits = onlyDigits(field.value);
        if (isApplicable(field) && field.value && ![10, 11].includes(digits.length)) {
            setError(field, "Informe um telefone valido.");
        }
    });

    return ok;
}

function isValidDateInput(value) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
    const date = new Date(`${value}T00:00:00`);
    return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value;
}

function onlyDigits(value) {
    return (value || "").replace(/\D+/g, "");
}

function validateCpf(value) {
    const cpf = onlyDigits(value);
    if (cpf.length !== 11 || /^(\d)\1{10}$/.test(cpf)) return false;
    for (const size of [9, 10]) {
        let total = 0;
        for (let index = 0; index < size; index += 1) {
            total += Number(cpf[index]) * ((size + 1) - index);
        }
        let digit = (total * 10) % 11;
        if (digit === 10) digit = 0;
        if (digit !== Number(cpf[size])) return false;
    }
    return true;
}

function validateCnpj(value) {
    const cnpj = onlyDigits(value);
    if (cnpj.length !== 14 || /^(\d)\1{13}$/.test(cnpj)) return false;
    const weights = [
        [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2],
        [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2],
    ];
    for (let round = 0; round < weights.length; round += 1) {
        let total = 0;
        for (let index = 0; index < weights[round].length; index += 1) {
            total += Number(cnpj[index]) * weights[round][index];
        }
        let digit = 11 - (total % 11);
        if (digit >= 10) digit = 0;
        if (digit !== Number(cnpj[12 + round])) return false;
    }
    return true;
}

// --- CPF inline validation ---

function setupCpfInlineValidation(form) {
    form.querySelectorAll('[data-mask="cpf"]').forEach((input) => {
        input.addEventListener("input", () => checkCpfStatus(input));
    });
}

function checkCpfStatus(input) {
    const digits = onlyDigits(input.value);
    const status = ensureDocStatus(input, "doc-status");
    if (digits.length < 11) {
        setDocStatus(status, "", "");
        return;
    }
    if (validateCpf(input.value)) {
        setDocStatus(status, "CPF valido.", "success");
    } else {
        setDocStatus(status, "Informe um CPF valido.", "error");
    }
}

// --- CNPJ lookup e autopreenchimento de Pessoa Juridica ---

function setupCnpjLookup(form, updateCityWarnings) {
    if (!window.CnpjService) return;
    const pjSection = form.querySelector('[data-section="pj"]');
    if (!pjSection) return;
    const cnpjInput = pjSection.querySelector('[data-mask="cnpj"]');
    if (!cnpjInput) return;

    let timer = null;

    cnpjInput.addEventListener("input", () => {
        const status = ensureDocStatus(cnpjInput, "doc-status");
        const digits = onlyDigits(cnpjInput.value);
        clearTimeout(timer);

        if (digits.length < 14) {
            setDocStatus(status, "", "");
            return;
        }
        if (!window.CnpjService.validarCnpj(cnpjInput.value)) {
            setDocStatus(status, "Informe um CNPJ valido.", "error");
            return;
        }
        timer = setTimeout(() => doLookupCnpj(cnpjInput, form, updateCityWarnings), 400);
    });
}

async function doLookupCnpj(cnpjInput, form, updateCityWarnings) {
    const clean = window.CnpjService.cleanCnpj(cnpjInput.value);
    if (!window.CnpjService.validarCnpj(clean)) return;
    const status = ensureDocStatus(cnpjInput, "doc-status");

    setDocStatus(status, "Consultando CNPJ...", "loading");
    try {
        const data = await window.CnpjService.consultarCnpj(clean);
        if (window.CnpjService.cleanCnpj(cnpjInput.value) !== clean) return;
        if (!data) {
            setDocStatus(status, "CNPJ valido, mas nao encontrado na consulta. Preencha manualmente.", "warning");
            return;
        }
        const empresa = window.CnpjService.mapBrasilApiCnpjToEmpresa(data);
        const confirmed = await confirmCompanyImport(empresa, clean);
        if (!confirmed) {
            setDocStatus(status, "Empresa encontrada. Preenchimento manual mantido.", "warning");
            return;
        }
        aplicarDadosEmpresa(form, empresa, updateCityWarnings);
        setDocStatus(status, "Dados da empresa importados.", "success");
    } catch {
        setDocStatus(status, "Nao foi possivel consultar o CNPJ agora. Voce pode preencher manualmente.", "warning");
    }
}

function confirmCompanyImport(empresa, cnpj) {
    return new Promise((resolve) => {
        const existing = document.getElementById("cnpj-confirm-modal");
        if (existing) existing.remove();
        const modal = document.createElement("div");
        modal.className = "modal fade";
        modal.id = "cnpj-confirm-modal";
        modal.tabIndex = -1;
        modal.innerHTML = `
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-header">
                        <div><span class="module-label">Consulta CNPJ</span><h2 class="modal-title">Empresa encontrada</h2></div>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Fechar"></button>
                    </div>
                    <div class="modal-body">
                        <p>Encontramos os dados desta empresa. E esta a empresa com que voce esta trabalhando?</p>
                        <dl class="cnpj-confirm-details"></dl>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-outline-secondary" data-cnpj-manual>Não, preencher manualmente</button>
                        <button type="button" class="btn btn-primary" data-cnpj-import>Sim, importar dados</button>
                    </div>
                </div>
            </div>`;
        document.body.appendChild(modal);
        const details = modal.querySelector(".cnpj-confirm-details");
        const rows = [
            ["CNPJ", cnpj.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5")],
            ["Razao social", empresa.razao_social],
            ["Nome fantasia", empresa.nome_fantasia],
            ["Endereco", [empresa.logradouro, empresa.numero, empresa.bairro].filter(Boolean).join(", ")],
            ["Cidade/UF", [empresa.cidade, empresa.uf].filter(Boolean).join(" / ")],
            ["Telefone", empresa.telefone],
            ["E-mail", empresa.email],
        ];
        rows.filter(([, value]) => value).forEach(([label, value]) => {
            const dt = document.createElement("dt");
            const dd = document.createElement("dd");
            dt.textContent = label;
            dd.textContent = value;
            details.append(dt, dd);
        });
        let answered = false;
        const finish = (answer) => {
            if (answered) return;
            answered = true;
            resolve(answer);
            bootstrap.Modal.getInstance(modal)?.hide();
        };
        modal.querySelector("[data-cnpj-import]").addEventListener("click", () => finish(true));
        modal.querySelector("[data-cnpj-manual]").addEventListener("click", () => finish(false));
        modal.addEventListener("hidden.bs.modal", () => {
            if (!answered) resolve(false);
            modal.remove();
        }, { once: true });
        bootstrap.Modal.getOrCreateInstance(modal).show();
    });
}

function aplicarDadosEmpresa(form, empresa, updateCityWarnings) {
    function setField(name, value) {
        if (!String(value || "").trim()) return;
        const field = form.querySelector(`[name="${name}"]`);
        if (!field) return;
        field.value = value;
        field.dispatchEvent(new Event("change", { bubbles: true }));
    }

    setField("pj_razao_social", empresa.razao_social);
    setField("pj_nome_fantasia", empresa.nome_fantasia);
    setField("pj_logradouro", empresa.logradouro);
    setField("pj_numero", empresa.numero);
    setField("pj_bairro", empresa.bairro);
    setField("pj_cidade", empresa.cidade);
    setField("pj_uf", empresa.uf);

    // CEP: aplicar e marcar como ja resolvido se o endereco veio completo da API (evita re-consulta ViaCEP)
    if (empresa.cep) {
        const cepInput = form.querySelector('[name="pj_cep"]');
        if (cepInput) {
            cepInput.value = empresa.cep.replace(/^(\d{5})(\d{3})$/, "$1-$2");
            cepInput.dispatchEvent(new Event("change", { bubbles: true }));
            if (empresa.logradouro && empresa.cidade && empresa.uf) {
                cepInput.dataset.lastCep = empresa.cep;
            }
        }
    }

    // Complemento nao e preenchido automaticamente — fica sempre manual.

    // Telefone e email: preencher apenas se o campo estiver vazio
    if (empresa.telefone) {
        const phoneField = form.querySelector('[name="pj_telefone"]');
        if (phoneField && !phoneField.value.trim()) {
            const d = empresa.telefone;
            let formatted = d;
            if (d.length === 11) formatted = `(${d.slice(0, 2)}) ${d.slice(2, 7)}-${d.slice(7)}`;
            else if (d.length === 10) formatted = `(${d.slice(0, 2)}) ${d.slice(2, 6)}-${d.slice(6)}`;
            phoneField.value = formatted;
        }
    }
    if (empresa.email) {
        const emailField = form.querySelector('[name="pj_email"]');
        if (emailField && !emailField.value.trim()) {
            emailField.value = empresa.email;
        }
    }

    updateCityWarnings(form);
}

// --- Helpers de status para CPF/CNPJ ---

function ensureDocStatus(input, className) {
    const label = input.closest("label");
    if (!label) return null;
    let status = label.querySelector(`.${className}`);
    if (!status) {
        status = document.createElement("small");
        status.className = className;
        label.appendChild(status);
    }
    return status;
}

function setDocStatus(status, message, state) {
    if (!status) return;
    status.textContent = message;
    status.dataset.state = state || "";
}

// --- Rascunho de checklist a partir da nota de exigencia ---

function initExigenciaAi() {
    const modalElement = document.getElementById("exigencia-ai-modal");
    if (!modalElement || !window.bootstrap) return;

    const elements = {
        modalElement,
        modal: bootstrap.Modal.getOrCreateInstance(modalElement),
        noteName: modalElement.querySelector("[data-ai-note-name]"),
        loading: modalElement.querySelector("[data-ai-loading]"),
        error: modalElement.querySelector("[data-ai-error]"),
        warning: modalElement.querySelector("[data-ai-warning]"),
        review: modalElement.querySelector("[data-ai-review]"),
        empty: modalElement.querySelector("[data-ai-empty]"),
        items: modalElement.querySelector("[data-ai-items]"),
        count: modalElement.querySelector("[data-ai-count]"),
        reanalyze: modalElement.querySelector("[data-ai-reanalyze]"),
        add: modalElement.querySelector("[data-ai-add]"),
        apply: modalElement.querySelector("[data-ai-apply]"),
    };
    const state = {
        projectId: null,
        exigenciaId: null,
        endpoint: "",
        returnModal: null,
        reopenParent: false,
        applied: false,
    };

    document.addEventListener("click", (event) => {
        const trigger = event.target.closest("[data-exigencia-ai]");
        if (!trigger) return;
        event.preventDefault();
        state.projectId = trigger.dataset.projectId;
        state.exigenciaId = trigger.dataset.exigenciaId;
        state.endpoint = `/api/project/${state.projectId}/exigencia/${state.exigenciaId}/ai-analysis`;
        const visibleProjectModal = document.getElementById(`project-modal-${state.projectId}`);
        state.returnModal = trigger.closest(".modal.show")
            || (visibleProjectModal?.classList.contains("show") ? visibleProjectModal : null);
        state.reopenParent = Boolean(state.returnModal);
        state.applied = false;
        elements.noteName.textContent = trigger.dataset.noteName || "Nota de exigencia";
        resetExigenciaAiDialog(elements);

        const openAiModal = () => {
            elements.modal.show();
            loadExigenciaAiAnalysis(elements, state);
        };
        if (state.returnModal) {
            state.returnModal.addEventListener("hidden.bs.modal", openAiModal, { once: true });
            bootstrap.Modal.getInstance(state.returnModal)?.hide();
        } else {
            openAiModal();
        }
    });

    elements.reanalyze.addEventListener("click", () => analyzeExigenciaNote(elements, state));
    elements.add.addEventListener("click", () => {
        appendExigenciaAiItem(elements, { codigo: "", titulo: "", resumo: "", pagina: 0, trecho_origem: "" }, false);
        updateExigenciaAiCount(elements);
        elements.items.lastElementChild?.querySelector("textarea")?.focus();
    });
    elements.items.addEventListener("click", (event) => {
        const removeButton = event.target.closest("[data-ai-remove-item]");
        if (!removeButton) return;
        removeButton.closest(".exigencia-ai-item")?.remove();
        updateExigenciaAiCount(elements);
    });
    elements.apply.addEventListener("click", () => applyExigenciaAiChecklist(elements, state));

    modalElement.addEventListener("hidden.bs.modal", () => {
        const returnModal = state.returnModal;
        const shouldReopen = state.reopenParent && !state.applied && returnModal?.isConnected;
        state.returnModal = null;
        if (shouldReopen) {
            setTimeout(() => bootstrap.Modal.getOrCreateInstance(returnModal).show(), 100);
        }
    });
}

function resetExigenciaAiDialog(elements) {
    elements.loading.hidden = true;
    elements.error.hidden = true;
    elements.warning.hidden = true;
    elements.review.hidden = true;
    elements.empty.hidden = true;
    elements.items.replaceChildren();
    elements.reanalyze.hidden = true;
    elements.add.hidden = true;
    elements.apply.hidden = true;
    elements.apply.disabled = false;
}

function setExigenciaAiLoading(elements, loading) {
    elements.loading.hidden = !loading;
    if (loading) {
        elements.error.hidden = true;
        elements.warning.hidden = true;
        elements.review.hidden = true;
        elements.empty.hidden = true;
        elements.reanalyze.hidden = true;
        elements.add.hidden = true;
        elements.apply.hidden = true;
    }
}

function showExigenciaAiMessage(elements, message, tone = "danger") {
    const target = tone === "danger" ? elements.error : elements.warning;
    target.classList.toggle("alert-success", tone === "success");
    target.classList.toggle("alert-warning", tone !== "success" && tone !== "danger");
    target.classList.toggle("alert-danger", tone === "danger");
    target.textContent = message;
    target.hidden = false;
}

async function fetchExigenciaAiJson(url, options = {}) {
    const response = await fetch(url, options);
    const data = await response.json().catch(() => ({ ok: false, error: "Resposta invalida do servidor." }));
    if (!response.ok || !data.ok) {
        const error = new Error(data.error || "Nao foi possivel concluir a operacao.");
        error.payload = data;
        throw error;
    }
    return data;
}

async function loadExigenciaAiAnalysis(elements, state) {
    setExigenciaAiLoading(elements, true);
    try {
        const data = await fetchExigenciaAiJson(state.endpoint);
        if (data.analysis) {
            renderExigenciaAiAnalysis(elements, data.analysis);
            return;
        }
        // Sem analise salva ainda (ou sem Groq configurada): tenta analisar, e o
        // proprio POST ja libera o cadastro manual caso a IA nao esteja disponivel.
        await analyzeExigenciaNote(elements, state);
    } catch (error) {
        renderExigenciaAiAnalysis(elements, { items: [] });
        showExigenciaAiMessage(elements, error.message);
    }
}

async function analyzeExigenciaNote(elements, state) {
    setExigenciaAiLoading(elements, true);
    try {
        const data = await fetchExigenciaAiJson(state.endpoint, { method: "POST" });
        renderExigenciaAiAnalysis(elements, data.analysis);
        if (data.message) {
            showExigenciaAiMessage(elements, data.message, "success");
        }
    } catch (error) {
        // A IA pode falhar (Groq fora do ar, limite atingido etc.): mesmo assim libera
        // o cadastro manual em vez de deixar o checklist travado.
        renderExigenciaAiAnalysis(elements, error.payload?.analysis || { items: [] });
        showExigenciaAiMessage(elements, error.message);
    }
}

function renderExigenciaAiAnalysis(elements, analysis) {
    setExigenciaAiLoading(elements, false);
    elements.items.replaceChildren();
    const applied = analysis.status === "aplicado";
    (analysis.items || []).forEach((item) => appendExigenciaAiItem(elements, item, applied));
    elements.review.hidden = false;
    elements.empty.hidden = (analysis.items || []).length > 0;
    elements.reanalyze.hidden = applied;
    elements.add.hidden = applied;
    elements.apply.hidden = applied;
    updateExigenciaAiCount(elements);
    if (analysis.warning) showExigenciaAiMessage(elements, analysis.warning, "warning");
    if (applied) showExigenciaAiMessage(elements, "Este rascunho ja foi transformado em checklist.", "success");
}

function makeExigenciaAiField(labelText, className, control) {
    const label = document.createElement("label");
    label.className = className;
    const caption = document.createElement("span");
    caption.textContent = labelText;
    label.append(caption, control);
    return label;
}

function appendExigenciaAiItem(elements, item, readOnly) {
    const row = document.createElement("div");
    row.className = "exigencia-ai-item";
    row.dataset.page = String(item.pagina || 0);
    row.dataset.source = item.trecho_origem || "";

    const codeInput = document.createElement("input");
    codeInput.className = "form-control form-control-sm";
    codeInput.type = "text";
    codeInput.maxLength = 40;
    codeInput.placeholder = "2.1";
    codeInput.value = item.codigo || "";
    codeInput.readOnly = readOnly;

    const titleInput = document.createElement("textarea");
    titleInput.className = "form-control form-control-sm";
    titleInput.maxLength = 600;
    titleInput.rows = 1;
    titleInput.placeholder = "Acao exigida";
    titleInput.value = item.titulo || "";
    titleInput.readOnly = readOnly;

    const removeButton = document.createElement("button");
    removeButton.className = "btn btn-outline-danger btn-sm exigencia-ai-item-remove";
    removeButton.type = "button";
    removeButton.title = "Remover item";
    removeButton.setAttribute("aria-label", "Remover item");
    removeButton.dataset.aiRemoveItem = "";
    removeButton.textContent = "x";
    removeButton.hidden = readOnly;

    row.append(
        makeExigenciaAiField("Numero", "exigencia-ai-item-code", codeInput),
        makeExigenciaAiField("Item do checklist", "exigencia-ai-item-title", titleInput),
        removeButton,
    );
    if (item.pagina || item.trecho_origem) {
        const source = document.createElement("small");
        source.className = "exigencia-ai-item-source";
        const pageLabel = item.pagina ? `Pagina ${item.pagina}` : "Pagina nao identificada";
        source.textContent = item.trecho_origem ? `${pageLabel}: ${item.trecho_origem}` : pageLabel;
        row.appendChild(source);
    }
    elements.items.appendChild(row);
}

function updateExigenciaAiCount(elements) {
    const count = elements.items.querySelectorAll(".exigencia-ai-item").length;
    elements.count.textContent = `${count} ${count === 1 ? "item" : "itens"}`;
    elements.empty.hidden = count > 0;
}

function collectExigenciaAiItems(elements) {
    return Array.from(elements.items.querySelectorAll(".exigencia-ai-item")).map((row) => ({
        codigo: row.querySelector(".exigencia-ai-item-code input")?.value.trim() || "",
        titulo: row.querySelector(".exigencia-ai-item-title textarea")?.value.trim() || "",
        resumo: "",
        pagina: Number(row.dataset.page || 0),
        trecho_origem: row.dataset.source || "",
    })).filter((item) => item.titulo);
}

async function applyExigenciaAiChecklist(elements, state) {
    const items = collectExigenciaAiItems(elements);
    if (!items.length) {
        showExigenciaAiMessage(elements, "Mantenha pelo menos um item no checklist.");
        return;
    }
    elements.apply.disabled = true;
    const originalText = elements.apply.textContent;
    elements.apply.textContent = "Criando...";
    try {
        const data = await fetchExigenciaAiJson(`${state.endpoint}/apply`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ items }),
        });
        state.applied = true;
        state.reopenParent = false;
        showExigenciaAiMessage(elements, data.message, "success");
        elements.reanalyze.hidden = true;
        elements.add.hidden = true;
        elements.apply.hidden = true;
        document.querySelectorAll(`[data-exigencia-ai][data-exigencia-id="${state.exigenciaId}"]`).forEach((button) => {
            button.textContent = "Checklist criado";
            button.disabled = true;
        });
        const projectId = state.projectId;
        setTimeout(() => {
            elements.modalElement.addEventListener("hidden.bs.modal", () => {
                if (typeof window.refreshProjectMatrixUi === "function") {
                    window.refreshProjectMatrixUi(projectId, { reopenModal: true }).catch(() => {});
                }
            }, { once: true });
            elements.modal.hide();
        }, 650);
    } catch (error) {
        showExigenciaAiMessage(elements, error.message);
        elements.apply.disabled = false;
        elements.apply.textContent = originalText;
    }
}

function showProjectDetailFeedback(message, tone = "success") {
    if (!message) return;
    let stack = document.querySelector("[data-project-detail-feedback]");
    if (!stack) {
        stack = document.createElement("div");
        stack.className = "matrix-action-feedback-stack";
        stack.dataset.projectDetailFeedback = "1";
        document.body.appendChild(stack);
    }
    const alert = document.createElement("div");
    alert.className = `alert alert-${tone === "danger" ? "danger" : tone} alert-dismissible fade show`;
    alert.setAttribute("role", "status");
    const text = document.createElement("span");
    text.textContent = message;
    const close = document.createElement("button");
    close.type = "button";
    close.className = "btn-close";
    close.setAttribute("aria-label", "Fechar");
    close.addEventListener("click", () => alert.remove());
    alert.append(text, close);
    stack.replaceChildren(alert);
    window.setTimeout(() => alert.remove(), tone === "danger" ? 9000 : 6500);
}

function projectDetailFeedbackFromDocument(doc) {
    const alert = doc?.querySelector(".alert");
    if (!alert) return null;
    let tone = "success";
    if (alert.classList.contains("alert-danger")) tone = "danger";
    else if (alert.classList.contains("alert-warning")) tone = "warning";
    else if (alert.classList.contains("alert-info")) tone = "info";
    return { message: alert.textContent.trim(), tone };
}

async function fetchFreshProjectDetailDocument() {
    const response = await fetch(`${window.location.pathname}${window.location.search}`, {
        credentials: "same-origin",
        cache: "no-store",
        headers: { "X-Requested-With": "XMLHttpRequest" },
    });
    if (response.redirected && new URL(response.url, window.location.origin).pathname === "/login") {
        window.location.assign(response.url);
        throw new Error("Sessao expirada.");
    }
    if (!response.ok) throw new Error("A alteracao foi salva, mas nao foi possivel atualizar a tela.");
    return new DOMParser().parseFromString(await response.text(), "text/html");
}

function refreshProjectDetailFromDocument(doc, paneId, scrollPosition) {
    const currentPane = document.getElementById(paneId);
    const freshPane = doc.getElementById(paneId);
    if (!currentPane || !freshPane) {
        throw new Error("A alteracao foi salva, mas a aba atual nao pode ser atualizada.");
    }

    freshPane.classList.add("show", "active");
    currentPane.replaceWith(freshPane);

    const currentHeading = document.querySelector(".page-heading");
    const freshHeading = doc.querySelector(".page-heading");
    if (currentHeading && freshHeading) {
        const currentTitle = currentHeading.querySelector("h1");
        const freshTitle = freshHeading.querySelector("h1");
        const currentSubtitle = currentHeading.querySelector("p");
        const freshSubtitle = freshHeading.querySelector("p");
        if (currentTitle && freshTitle) currentTitle.textContent = freshTitle.textContent;
        if (currentSubtitle && freshSubtitle) currentSubtitle.textContent = freshSubtitle.textContent;
    }

    const currentStrip = document.querySelector(".page-heading + .project-strip");
    const freshStrip = doc.querySelector(".page-heading + .project-strip");
    if (currentStrip && freshStrip) currentStrip.replaceChildren(...freshStrip.cloneNode(true).childNodes);

    initProjectClientAutocompletes(freshPane);
    initProjectOwnerManagers();
    initProjectDetailAsyncForms(freshPane);
    window.requestAnimationFrame(() => window.scrollTo({ top: scrollPosition, behavior: "auto" }));
}

function initProjectDetailAsyncForms(root = document) {
    const scope = root.matches?.("[data-project-detail-tabs]")
        ? root
        : (root.querySelector?.("[data-project-detail-tabs]") || root);
    const forms = scope.querySelectorAll?.("form") || [];

    forms.forEach((form) => {
        const actionUrl = form.getAttribute("action") || "";
        const isProjectAction = /\/project\/\d+\/action(?:\?|$)/.test(actionUrl);
        const isStageQuick = /\/stage\/\d+\/quick(?:\?|$)/.test(actionUrl);
        const actionName = form.querySelector('[name="action"]')?.value || "";
        if ((!isProjectAction && !isStageQuick) || actionName === "delete_project") return;
        if (form.dataset.projectDetailAsyncReady === "1") return;
        form.dataset.projectDetailAsyncReady = "1";

        form.addEventListener("submit", async (event) => {
            if (event.defaultPrevented || !window.fetch || !window.DOMParser) return;
            event.preventDefault();
            if (form.dataset.submitting === "1") return;

            const pane = form.closest(".tab-pane");
            if (!pane?.id) return;
            const paneId = pane.id;
            const scrollPosition = window.scrollY;
            const submitter = event.submitter || form.querySelector('button[type="submit"]');
            const originalText = submitter?.textContent || "";
            form.dataset.submitting = "1";
            if (submitter) {
                submitter.disabled = true;
                submitter.textContent = "Salvando...";
            }

            try {
                const body = new FormData(form);
                if (event.submitter?.name && !body.has(event.submitter.name)) {
                    body.append(event.submitter.name, event.submitter.value);
                }
                const response = await fetch(actionUrl, {
                    method: "POST",
                    body,
                    credentials: "same-origin",
                    cache: "no-store",
                    headers: {
                        "Accept": "application/json, text/html;q=0.9",
                        "X-Requested-With": "XMLHttpRequest",
                    },
                });
                if (response.redirected && new URL(response.url, window.location.origin).pathname === "/login") {
                    window.location.assign(response.url);
                    return;
                }

                const contentType = (response.headers.get("Content-Type") || "").toLowerCase();
                let freshDocument = null;
                let feedback = null;
                if (contentType.includes("application/json")) {
                    const data = await response.json().catch(() => ({}));
                    if (!response.ok || !data.ok) {
                        throw new Error(data.error || data.message || "Nao foi possivel salvar a alteracao.");
                    }
                    feedback = {
                        message: data.message || "Alteracao salva.",
                        tone: data.tone || "success",
                    };
                } else {
                    if (!response.ok) throw new Error("Nao foi possivel salvar a alteracao.");
                    freshDocument = new DOMParser().parseFromString(await response.text(), "text/html");
                    feedback = projectDetailFeedbackFromDocument(freshDocument);
                    if (feedback?.tone === "danger") throw new Error(feedback.message);
                }

                freshDocument = freshDocument || await fetchFreshProjectDetailDocument();
                refreshProjectDetailFromDocument(freshDocument, paneId, scrollPosition);
                showProjectDetailFeedback(
                    feedback?.message || "Alteracao salva.",
                    feedback?.tone || "success",
                );
            } catch (error) {
                showProjectDetailFeedback(
                    error.message || "Nao foi possivel salvar a alteracao.",
                    "danger",
                );
            } finally {
                delete form.dataset.submitting;
                if (submitter?.isConnected) {
                    submitter.disabled = false;
                    submitter.textContent = originalText;
                }
            }
        });
    });
}

document.addEventListener("DOMContentLoaded", () => {
    initProjectDetailAsyncForms();
});
