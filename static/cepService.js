(function (window) {
    const cache = new Map();

    function cleanCep(cep) {
        return String(cep || "").replace(/\D+/g, "").slice(0, 8);
    }

    function isCepCompleto(cep) {
        return cleanCep(cep).length === 8;
    }

    async function buscarEnderecoPorCep(cep) {
        const clean = cleanCep(cep);
        if (!isCepCompleto(clean)) return null;
        if (cache.has(clean)) return cache.get(clean);

        const response = await fetch(`https://viacep.com.br/ws/${clean}/json/`, {
            headers: { Accept: "application/json" },
        });
        if (!response.ok) {
            throw new Error("via_cep_unavailable");
        }
        const data = await response.json();
        cache.set(clean, data);
        return data;
    }

    function applyReturnedValue(form, name, value) {
        const field = form.querySelector(`[name="${name}"]`);
        if (!field || !String(value || "").trim()) return;
        field.value = value;
        field.dispatchEvent(new Event("change", { bubbles: true }));
    }

    function aplicarEnderecoViaCep(form, prefix, retornoViaCep) {
        if (!retornoViaCep || retornoViaCep.erro) return false;
        applyReturnedValue(form, `${prefix}_logradouro`, retornoViaCep.logradouro);
        applyReturnedValue(form, `${prefix}_bairro`, retornoViaCep.bairro);
        applyReturnedValue(form, `${prefix}_cidade`, retornoViaCep.localidade);
        applyReturnedValue(form, `${prefix}_uf`, retornoViaCep.uf);
        return true;
    }

    window.CepService = {
        cleanCep,
        isCepCompleto,
        buscarEnderecoPorCep,
        aplicarEnderecoViaCep,
    };
})(window);
