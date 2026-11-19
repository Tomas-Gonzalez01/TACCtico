/* Transiciones de la interfaz propia; no se accede al documento del dashboard. */
(() => {
  const registration = Symbol.for("tacctico.navigation");
  window[registration]?.dispose();
  const root = document.documentElement;
  const sections = {
    "Catálogo": "contenido_catalogo",
    "Arma tu presupuesto": "contenido_presupuesto",
    "Dashboard": "contenido_dashboard",
  };
  let pending = null;
  let timeout;
  let firstFrame;
  let secondFrame;
  root.dataset.taccticoInput = "keyboard";

  function finish() {
    pending = null;
    clearTimeout(timeout);
    cancelAnimationFrame(firstFrame);
    cancelAnimationFrame(secondFrame);
    root.classList.remove("tacctico-switching");
  }

  function pointer() { root.dataset.taccticoInput = "pointer"; }
  function keyboard() {
    root.dataset.taccticoInput = "keyboard";
    finish();
  }

  function ready() {
    if (!pending) return;
    const block = document.querySelector(`.st-key-${pending}`);
    if (!block?.querySelector(`.tacctico-section-ready[data-section="${pending}"]`)) return;
    // Espera el pintado del bloque nuevo antes de recuperar su opacidad.
    if (firstFrame || secondFrame) return;
    firstFrame = requestAnimationFrame(() => {
      firstFrame = null;
      secondFrame = requestAnimationFrame(() => {
        secondFrame = null;
        finish();
      });
    });
  }

  function navigate(event) {
    const label = event.target.closest?.(".st-key-seccion label");
    if (!label || root.dataset.taccticoInput !== "pointer") return;
    const target = sections[label.textContent.trim()];
    if (!target) return;
    const current = document.querySelector(".tacctico-section-ready")?.dataset.section;
    if (target === (pending || current)) return;
    cancelAnimationFrame(firstFrame);
    cancelAnimationFrame(secondFrame);
    firstFrame = secondFrame = null;
    pending = target;
    root.classList.add("tacctico-switching");
    clearTimeout(timeout);
    // Ante una respuesta fallida o lenta, el contenido siempre queda visible.
    timeout = setTimeout(finish, 1500);
  }

  const observer = new MutationObserver(ready);
  observer.observe(document.querySelector('[data-testid="stMainBlockContainer"]') || document.body, {
    childList: true, subtree: true, attributes: true, attributeFilter: ["class", "data-section"],
  });
  document.addEventListener("pointerdown", pointer, true);
  document.addEventListener("keydown", keyboard, true);
  document.addEventListener("click", navigate, true);
  window[registration] = {
    dispose() {
      observer.disconnect();
      document.removeEventListener("pointerdown", pointer, true);
      document.removeEventListener("keydown", keyboard, true);
      document.removeEventListener("click", navigate, true);
      finish();
    },
  };
})();
