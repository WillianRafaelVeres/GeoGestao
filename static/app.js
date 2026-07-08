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
    btn.disabled = true;
    try {
        const resp = await fetch(`/api/checklist/${itemId}/toggle`, { method: "POST" });
        if (!resp.ok) throw new Error("Falha");
        const data = await resp.json();
        const label = document.getElementById(`check-label-${itemId}`);
        if (data.concluido) {
            btn.classList.add("checked");
            btn.innerHTML = "&#10003;";
            if (label) { label.style.color = "#9ca3af"; label.style.textDecoration = "line-through"; }
        } else {
            btn.classList.remove("checked");
            btn.innerHTML = "";
            if (label) { label.style.color = ""; label.style.textDecoration = ""; }
        }
        const counter = document.querySelector(`.checklist-counter-${stageId}`);
        if (counter) counter.textContent = `${data.done}/${data.total}`;
    } catch {
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
    initClientLiveSearch();
    initProjectClientAutocompletes();
    initCartorioLookup();
    initSingleSubmitForms();
    initMatrixLiveFilters();
});

function initSingleSubmitForms() {
    document.querySelectorAll("form[data-single-submit]").forEach((form) => {
        form.addEventListener("submit", (event) => {
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

function initCartorioLookup() {
    const catalog = Array.isArray(window.cartorioCatalog) ? window.cartorioCatalog : [];
    document.querySelectorAll("[data-cartorio-lookup]").forEach((lookup) => {
        const form = lookup.closest("[data-cartorio-form]") || lookup.closest("form");
        if (!form) return;
        const ufSelect = lookup.querySelector("[data-cartorio-lookup-uf]");
        const citySelect = lookup.querySelector("[data-cartorio-lookup-city]");
        const officeSelect = lookup.querySelector("[data-cartorio-lookup-office]");
        const cnsInput = lookup.querySelector("[data-cartorio-lookup-cns]");

        const normalize = (value) => String(value || "").trim().toLowerCase();
        const uniqueSorted = (values) => Array.from(new Set(values.filter(Boolean))).sort((a, b) => a.localeCompare(b, "pt-BR"));
        const setOptions = (select, values, placeholder) => {
            if (!select) return;
            select.innerHTML = "";
            const first = document.createElement("option");
            first.value = "";
            first.textContent = placeholder;
            select.appendChild(first);
            values.forEach((value) => {
                const option = document.createElement("option");
                option.value = value;
                option.textContent = value;
                select.appendChild(option);
            });
            select.disabled = values.length === 0;
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
            ["nome", "cns", "cidade", "uf", "contato", "email", "telefone", "whatsapp", "oficial", "observacoes"].forEach((field) => {
                setField(field, item[field] || "");
            });
            if (ufSelect) ufSelect.value = item.uf || "";
            refreshCities();
            if (citySelect) citySelect.value = item.cidade || "";
            refreshOffices();
            if (officeSelect) officeSelect.value = String(item.id || "");
            if (cnsInput) cnsInput.value = item.cns || "";
        };
        const refreshCities = () => {
            const uf = ufSelect?.value || "";
            const cities = uniqueSorted(catalog.filter((item) => !uf || item.uf === uf).map((item) => item.cidade));
            setOptions(citySelect, cities, uf ? "Selecione a cidade" : "Escolha a UF");
            setOptions(officeSelect, [], "Escolha a cidade");
        };
        const refreshOffices = () => {
            const uf = ufSelect?.value || "";
            const city = citySelect?.value || "";
            const offices = catalog
                .filter((item) => (!uf || item.uf === uf) && (!city || item.cidade === city))
                .sort((a, b) => a.nome.localeCompare(b.nome, "pt-BR"));
            if (!officeSelect) return;
            officeSelect.innerHTML = "";
            const first = document.createElement("option");
            first.value = "";
            first.textContent = offices.length ? "Selecione o cartorio" : "Nenhum cartorio cadastrado";
            officeSelect.appendChild(first);
            offices.forEach((item) => {
                const option = document.createElement("option");
                option.value = String(item.id);
                option.textContent = item.cns ? `${item.nome} - CNS ${item.cns}` : item.nome;
                officeSelect.appendChild(option);
            });
            officeSelect.disabled = offices.length === 0;
        };

        ufSelect?.addEventListener("change", refreshCities);
        citySelect?.addEventListener("change", refreshOffices);
        officeSelect?.addEventListener("change", () => {
            const item = catalog.find((entry) => String(entry.id) === officeSelect.value);
            fillForm(item);
        });
        cnsInput?.addEventListener("input", () => {
            const cns = normalize(cnsInput.value).replace(/\D/g, "");
            if (cns.length < 4) return;
            const item = catalog.find((entry) => normalize(entry.cns).replace(/\D/g, "") === cns);
            if (item) fillForm(item);
        });

        refreshCities();
    });
}

function initMatrixLiveFilters() {
    const input = document.querySelector("[data-live-filter-input]");
    if (!input || !input.form) return;
    let timer = null;
    input.addEventListener("input", () => {
        clearTimeout(timer);
        timer = setTimeout(() => {
            input.form.requestSubmit();
        }, 450);
    });
}

function initRepresentativeManagers() {
    document.querySelectorAll("[data-representative-manager]").forEach((manager) => {
        const list = manager.querySelector("[data-rep-list]");
        const empty = manager.querySelector("[data-rep-empty]");
        const addButton = manager.querySelector("[data-rep-add]");
        const popout = manager.querySelector("[data-rep-popout]");
        const template = manager.querySelector("[data-rep-template]");
        const title = manager.querySelector("[data-rep-popout-title]");
        const saveButton = manager.querySelector("[data-rep-save]");
        let editingRow = null;

        if (!list || !popout || !template) return;

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

function initProjectClientAutocompletes() {
    const widgets = Array.from(document.querySelectorAll("[data-client-autocomplete]"));
    if (!widgets.length) return;

    widgets.forEach((widget) => {
        const input = widget.querySelector("[data-client-autocomplete-input]");
        const hidden = widget.querySelector("[data-client-autocomplete-id]");
        const list = widget.querySelector("[data-client-autocomplete-list]");
        const sourceName = widget.dataset.clientSource || "projectClientes";
        if (!input || !hidden || !list || input.disabled || input.readOnly) return;

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

function escapeHtml(value) {
    const element = document.createElement("span");
    element.textContent = String(value || "");
    return element.innerHTML;
}

function initDocumentalClientForm() {
    const forms = document.querySelectorAll(".cliente-form");
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

    initPendingFocusShortcuts();

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

function initPendingFocusShortcuts() {
    document.querySelectorAll("[data-pending-focus]").forEach((button) => {
        button.addEventListener("click", () => {
            const pendingModalEl = button.closest(".modal");
            const editModalEl = document.querySelector(button.dataset.editModal);
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
        aplicarDadosEmpresa(form, empresa, updateCityWarnings);
        setDocStatus(status, "Empresa encontrada. Dados preenchidos automaticamente.", "success");
    } catch {
        setDocStatus(status, "Nao foi possivel consultar o CNPJ agora. Voce pode preencher manualmente.", "warning");
    }
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
