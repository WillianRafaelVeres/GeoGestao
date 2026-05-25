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

    initDocumentalClientForm();
    initClientLiveSearch();
});

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

function initDocumentalClientForm() {
    const forms = document.querySelectorAll(".cliente-form");
    if (!forms.length) return;

    const spouseRequiredRegimes = ["COMUNHAO_PARCIAL", "COMUNHAO_UNIVERSAL", "PARTICIPACAO_FINAL_AQUESTOS"];
    const citiesByUf = {
        PR: ["Rio Negro", "Curitiba", "Campo Largo", "Lapa", "Sao Mateus do Sul"],
        SC: ["Mafra", "Joinville", "Florianopolis", "Canoinhas", "Porto Uniao"],
        SP: ["Sao Paulo", "Campinas", "Santos", "Sorocaba", "Jundiai"],
        RS: ["Porto Alegre", "Caxias do Sul", "Pelotas", "Santa Maria"],
        MG: ["Belo Horizonte", "Uberlandia", "Juiz de Fora", "Contagem"],
    };

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

            const isSeparationTotal = hasCivilRegime && regime === "SEPARACAO_TOTAL";
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

        form.querySelectorAll("[data-city-input], [data-city-uf]").forEach((field) => {
            field.addEventListener("change", () => updateCityWarnings(form));
            field.addEventListener("input", () => updateCityWarnings(form));
        });

        setupCepLookup(form, updateCityWarnings);

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
        form.querySelectorAll(".client-section").forEach((section) => {
            const uf = section.querySelector("[data-city-uf]");
            const city = section.querySelector("[data-city-input]");
            const warning = section.querySelector(".city-warning");
            if (!uf || !city || !warning || !uf.value || !city.value) {
                if (warning) warning.classList.remove("is-visible");
                return;
            }
            const allowed = citiesByUf[uf.value];
            const normalized = normalizeCity(city.value);
            const isKnown = !allowed || allowed.map(normalizeCity).includes(normalized);
            warning.classList.toggle("is-visible", !isKnown);
        });
    }

    function normalizeCity(value) {
        return (value || "")
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .toLowerCase()
            .trim();
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
