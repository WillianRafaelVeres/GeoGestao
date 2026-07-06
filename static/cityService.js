// Seletor de cidade por UF: escolha a UF primeiro e a cidade vira um
// autocomplete com a lista oficial de municipios do IBGE, filtrada conforme
// o usuario digita. Pares sao ligados por data-city-uf="grupo" (select de UF)
// e data-city-input="grupo" (input de cidade) dentro do mesmo <form>.
(function () {
    "use strict";

    const API_BASE = "https://servicodados.ibge.gov.br/api/v1/localidades/estados/";
    const CACHE_PREFIX = "geogestao:cities:";
    const CACHE_TTL_MS = 30 * 24 * 60 * 60 * 1000; // municipios quase nao mudam
    const MAX_ITEMS = 60;
    const memoryCache = new Map();
    const pendingFetches = new Map();

    function normalize(value) {
        return (value || "")
            .normalize("NFD")
            .replace(/[̀-ͯ]/g, "")
            .toLowerCase()
            .trim();
    }

    function readLocalCache(uf) {
        try {
            const raw = localStorage.getItem(CACHE_PREFIX + uf);
            if (!raw) return null;
            const parsed = JSON.parse(raw);
            if (!parsed || !Array.isArray(parsed.cities) || !parsed.cities.length) return null;
            if (Date.now() - (parsed.ts || 0) > CACHE_TTL_MS) return null;
            return parsed.cities;
        } catch {
            return null;
        }
    }

    function writeLocalCache(uf, cities) {
        try {
            localStorage.setItem(CACHE_PREFIX + uf, JSON.stringify({ ts: Date.now(), cities }));
        } catch {
            // sem espaco no localStorage: segue funcionando sem cache
        }
    }

    function getCities(uf) {
        uf = (uf || "").toUpperCase().trim();
        if (!/^[A-Z]{2}$/.test(uf)) return Promise.resolve([]);
        if (memoryCache.has(uf)) return Promise.resolve(memoryCache.get(uf));
        const cached = readLocalCache(uf);
        if (cached) {
            memoryCache.set(uf, cached);
            return Promise.resolve(cached);
        }
        if (pendingFetches.has(uf)) return pendingFetches.get(uf);
        const request = fetch(`${API_BASE}${uf}/municipios?orderBy=nome`)
            .then((response) => {
                if (!response.ok) throw new Error("IBGE indisponivel");
                return response.json();
            })
            .then((data) => {
                const cities = (Array.isArray(data) ? data : []).map((m) => m && m.nome).filter(Boolean);
                pendingFetches.delete(uf);
                if (cities.length) {
                    memoryCache.set(uf, cities);
                    writeLocalCache(uf, cities);
                }
                return cities;
            })
            .catch(() => {
                // Offline ou API fora: sem lista, o campo continua texto livre.
                pendingFetches.delete(uf);
                return [];
            });
        pendingFetches.set(uf, request);
        return request;
    }

    function filterCities(cities, term) {
        if (!term) return cities.slice(0, MAX_ITEMS);
        const needle = normalize(term);
        const starts = [];
        const contains = [];
        for (const city of cities) {
            const haystack = normalize(city);
            if (haystack.startsWith(needle)) {
                starts.push(city);
                if (starts.length >= MAX_ITEMS) break;
            } else if (haystack.includes(needle)) {
                contains.push(city);
            }
        }
        return starts.concat(contains).slice(0, MAX_ITEMS);
    }

    function findUfField(cityInput) {
        const form = cityInput.closest("form") || document;
        const group = cityInput.getAttribute("data-city-input") || "";
        const candidates = form.querySelectorAll("[data-city-uf]");
        for (const field of candidates) {
            if ((field.getAttribute("data-city-uf") || "") === group) return field;
        }
        return candidates.length === 1 ? candidates[0] : null;
    }

    function findWarning(cityInput) {
        const form = cityInput.closest("form") || document;
        const group = cityInput.getAttribute("data-city-input") || "";
        const withGroup = form.querySelector(`[data-city-warning="${group}"]`);
        if (withGroup) return withGroup;
        const section = cityInput.closest(".client-section");
        return section ? section.querySelector(".city-warning") : null;
    }

    function setupPicker(cityInput) {
        if (cityInput.dataset.cityPickerReady) return;
        const ufField = findUfField(cityInput);
        if (!ufField) return;
        cityInput.dataset.cityPickerReady = "1";
        cityInput.setAttribute("autocomplete", "off");

        const wrapper = document.createElement("div");
        wrapper.className = "ac-wrapper city-picker";
        cityInput.parentNode.insertBefore(wrapper, cityInput);
        wrapper.appendChild(cityInput);
        const list = document.createElement("div");
        list.className = "ac-list";
        wrapper.appendChild(list);
        let activeIndex = -1;

        function currentUf() {
            const uf = (ufField.value || "").toUpperCase().trim();
            return /^[A-Z]{2}$/.test(uf) ? uf : "";
        }

        function close() {
            list.classList.remove("open");
            list.innerHTML = "";
            activeIndex = -1;
        }

        function renderMessage(message) {
            list.innerHTML = "";
            activeIndex = -1;
            const empty = document.createElement("div");
            empty.className = "ac-empty";
            empty.textContent = message;
            list.appendChild(empty);
            list.classList.add("open");
        }

        function renderItems(items) {
            list.innerHTML = "";
            activeIndex = -1;
            items.forEach((city) => {
                const item = document.createElement("div");
                item.className = "ac-item";
                item.textContent = city;
                item.addEventListener("mousedown", (event) => {
                    event.preventDefault(); // roda antes do blur do input
                    choose(city);
                });
                list.appendChild(item);
            });
            list.classList.add("open");
        }

        function choose(city) {
            cityInput.value = city;
            close();
            applyWarning();
            cityInput.dispatchEvent(new Event("change", { bubbles: true }));
        }

        function applyWarning() {
            const warning = findWarning(cityInput);
            if (!warning) return;
            const uf = currentUf();
            const city = cityInput.value.trim();
            const cities = memoryCache.get(uf);
            if (!uf || !city || !cities || !cities.length) {
                warning.classList.remove("is-visible");
                return;
            }
            const known = cities.some((item) => normalize(item) === normalize(city));
            warning.classList.toggle("is-visible", !known);
        }

        async function update() {
            const uf = currentUf();
            if (!uf) {
                renderMessage("Selecione primeiro a UF.");
                return;
            }
            const term = cityInput.value;
            const cities = await getCities(uf);
            if (document.activeElement !== cityInput) return;
            if (!cities.length) {
                close();
                return;
            }
            const matches = filterCities(cities, term);
            if (!matches.length) {
                renderMessage("Nenhuma cidade encontrada nesta UF.");
                return;
            }
            renderItems(matches);
        }

        cityInput.addEventListener("focus", update);
        cityInput.addEventListener("input", () => {
            update();
            applyWarning();
        });
        cityInput.addEventListener("blur", () => {
            setTimeout(close, 120);
            applyWarning();
        });
        cityInput.addEventListener("keydown", (event) => {
            const items = Array.from(list.querySelectorAll(".ac-item"));
            if (!list.classList.contains("open") || !items.length) return;
            if (event.key === "ArrowDown" || event.key === "ArrowUp") {
                event.preventDefault();
                const delta = event.key === "ArrowDown" ? 1 : -1;
                activeIndex = (activeIndex + delta + items.length) % items.length;
                items.forEach((el, index) => el.classList.toggle("is-active", index === activeIndex));
                items[activeIndex].scrollIntoView({ block: "nearest" });
            } else if (event.key === "Enter" && activeIndex >= 0) {
                event.preventDefault();
                choose(items[activeIndex].textContent);
            } else if (event.key === "Escape") {
                close();
            }
        });

        ufField.addEventListener("change", async () => {
            const uf = currentUf();
            if (!uf) {
                applyWarning();
                return;
            }
            const cities = await getCities(uf);
            const city = cityInput.value.trim();
            if (city && cities.length && !cities.some((item) => normalize(item) === normalize(city))) {
                // Cidade era de outro estado: limpa para evitar cadastro errado.
                cityInput.value = "";
            }
            applyWarning();
            if (document.activeElement === cityInput) update();
        });

        cityInput.__cityValidate = applyWarning;

        // Valida dados ja existentes ao abrir a tela (ex.: edicao de cadastro).
        if (currentUf() && cityInput.value.trim()) {
            getCities(currentUf()).then(applyWarning);
        }
    }

    function initPickers(root) {
        (root || document).querySelectorAll("[data-city-input]").forEach(setupPicker);
    }

    function refreshWarnings(root) {
        (root || document).querySelectorAll("[data-city-input]").forEach((input) => {
            if (typeof input.__cityValidate !== "function") return;
            const ufField = findUfField(input);
            const uf = ufField ? (ufField.value || "").toUpperCase().trim() : "";
            if (/^[A-Z]{2}$/.test(uf) && input.value.trim()) {
                getCities(uf).then(() => input.__cityValidate());
            } else {
                input.__cityValidate();
            }
        });
    }

    window.CityService = { getCities, normalize, initPickers, refreshWarnings };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", () => initPickers(document));
    } else {
        initPickers(document);
    }
})();
