/*
 * Por segurança e privacidade, CPF é validado apenas localmente.
 * Para CNPJ, consultamos dados públicos empresariais via BrasilAPI.
 * Nenhuma consulta de dados pessoais por CPF é realizada neste sistema.
 */
(function (window) {
    const cache = new Map();

    function cleanCnpj(cnpj) {
        return String(cnpj || "").replace(/\D+/g, "").slice(0, 14);
    }

    function isCnpjCompleto(cnpj) {
        return cleanCnpj(cnpj).length === 14;
    }

    function validarCnpj(value) {
        const cnpj = cleanCnpj(value);
        if (cnpj.length !== 14 || /^(\d)\1{13}$/.test(cnpj)) return false;
        const weights = [
            [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2],
            [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2],
        ];
        for (let round = 0; round < weights.length; round += 1) {
            let total = 0;
            for (let i = 0; i < weights[round].length; i += 1) {
                total += Number(cnpj[i]) * weights[round][i];
            }
            let digit = 11 - (total % 11);
            if (digit >= 10) digit = 0;
            if (digit !== Number(cnpj[12 + round])) return false;
        }
        return true;
    }

    async function consultarCnpj(cnpj) {
        const clean = cleanCnpj(cnpj);
        if (!validarCnpj(clean)) return null;
        if (cache.has(clean)) return cache.get(clean);

        const resp = await fetch(`https://brasilapi.com.br/api/cnpj/v1/${clean}`, {
            headers: { Accept: "application/json" },
        });
        if (!resp.ok) {
            if (resp.status === 404) {
                cache.set(clean, null);
                return null;
            }
            throw new Error("brasilapi_unavailable");
        }
        const data = await resp.json();
        cache.set(clean, data);
        return data;
    }

    function mapBrasilApiCnpjToEmpresa(data) {
        if (!data) return null;
        return {
            razao_social: data.razao_social || "",
            nome_fantasia: data.nome_fantasia || "",
            cep: data.cep ? String(data.cep).replace(/\D+/g, "") : "",
            uf: data.uf || "",
            cidade: data.municipio || "",
            bairro: data.bairro || "",
            logradouro: data.logradouro || "",
            numero: data.numero || "",
            telefone: data.ddd_telefone_1 ? String(data.ddd_telefone_1).replace(/\D+/g, "") : "",
            email: typeof data.email === "string" ? data.email : "",
        };
    }

    window.CnpjService = {
        cleanCnpj,
        isCnpjCompleto,
        validarCnpj,
        consultarCnpj,
        mapBrasilApiCnpjToEmpresa,
    };
})(window);
