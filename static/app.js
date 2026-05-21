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
});
