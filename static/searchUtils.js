(function (window) {
    function normalizeSearchText(value) {
        return String(value || "")
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .toLowerCase()
            .replace(/\s+/g, " ")
            .trim();
    }

    function normalizeDigits(value) {
        return String(value || "").replace(/\D+/g, "");
    }

    function matchesSearch(fields, query) {
        const normalizedQuery = normalizeSearchText(query);
        const queryDigits = normalizeDigits(query);
        if (!normalizedQuery && !queryDigits) return true;

        return fields.some((field) => {
            const text = normalizeSearchText(field);
            const digits = normalizeDigits(field);
            return (
                (normalizedQuery && text.includes(normalizedQuery)) ||
                (queryDigits && digits.includes(queryDigits))
            );
        });
    }

    function debounce(callback, delay) {
        let timer = null;
        return function debounced(...args) {
            clearTimeout(timer);
            timer = setTimeout(() => callback.apply(this, args), delay);
        };
    }

    window.SearchUtils = {
        normalizeSearchText,
        normalizeDigits,
        matchesSearch,
        debounce,
    };
})(window);
