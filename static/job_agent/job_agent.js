(function () {
  "use strict";

  // =====================================================
  // Utils
  // =====================================================

  function qs(selector, scope) {
    return (scope || document).querySelector(selector);
  }

  function qsa(selector, scope) {
    return Array.prototype.slice.call((scope || document).querySelectorAll(selector));
  }

  function clampText(s) {
    return (s || "").toString().trim();
  }

  function getCookie(name) {
    const cookieStr = document.cookie || "";
    const parts = cookieStr.split(";").map((c) => c.trim());
    for (let i = 0; i < parts.length; i++) {
      const p = parts[i];
      if (p.startsWith(name + "=")) return decodeURIComponent(p.slice(name.length + 1));
    }
    return "";
  }

  function getCSRFToken() {
    // Django default: csrftoken in cookies
    const fromCookie = getCookie("csrftoken");
    if (fromCookie) return fromCookie;

    // Fallback: any csrf input present in DOM
    const el = qs("input[name=csrfmiddlewaretoken]");
    return el ? el.value : "";
  }

  function formUrlEncode(obj) {
    const pairs = [];
    Object.keys(obj || {}).forEach((k) => {
      pairs.push(encodeURIComponent(k) + "=" + encodeURIComponent(obj[k]));
    });
    return pairs.join("&");
  }

  // =====================================================
  // Toast
  // =====================================================

  function ensureToast() {
    return qs(".ja-toast");
  }

  function showToast(message) {
    const toast = ensureToast();
    if (!toast) return;

    const msg = qs(".ja-toast__msg", toast);
    if (msg) msg.textContent = message || "OK";

    toast.classList.add("is-visible");
    window.clearTimeout(showToast._t);
    showToast._t = window.setTimeout(function () {
      toast.classList.remove("is-visible");
    }, 2500);
  }

  function initToastDismiss() {
    qsa("[data-toast-dismiss]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        const toast = ensureToast();
        if (toast) toast.classList.remove("is-visible");
      });
    });
  }

  // =====================================================
  // Copy to clipboard
  // =====================================================

  function initCopyButtons() {
    qsa("[data-copy]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        const explicitText = btn.getAttribute("data-copy-text");
        const targetSelector = btn.getAttribute("data-copy-target");
        const customToast = btn.getAttribute("data-copy-toast");

        let text = "";

        if (explicitText) {
          text = explicitText;
        } else if (targetSelector) {
          const el = qs(targetSelector);
          if (el) text = clampText(el.value !== undefined ? el.value : el.textContent);
        }

        text = clampText(text);
        if (!text) return;

        if (!navigator.clipboard || !navigator.clipboard.writeText) {
          // Ultra fallback
          try {
            const ta = document.createElement("textarea");
            ta.value = text;
            ta.style.position = "fixed";
            ta.style.opacity = "0";
            document.body.appendChild(ta);
            ta.select();
            document.execCommand("copy");
            document.body.removeChild(ta);
            showToast(customToast || "Copié ✅");
          } catch (e) {
            showToast("Erreur copie");
          }
          return;
        }

        navigator.clipboard.writeText(text).then(
          function () {
            showToast(customToast || "Copié ✅");
          },
          function () {
            showToast("Erreur copie");
          }
        );
      });
    });
  }

  // =====================================================
  // Kanban Drag & Drop
  // =====================================================

  let draggedCard = null;
  let dragStarted = false;
  let originList = null;
  let originNextSibling = null;

  function updateColumnCount(listEl) {
    if (!listEl) return;
    const col = listEl.closest(".ja-kanban__col");
    if (!col) return;
    const countEl = qs(".ja-kanban__count", col);
    if (!countEl) return;

    // Count only lead cards
    const n = qsa("[data-draggable-card='true']", listEl).length;
    countEl.textContent = String(n);
  }

  function updateAllCounts(board) {
    qsa("[data-droppable='true']", board).forEach(updateColumnCount);
  }

  function setDropVisual(listEl, isOver) {
    if (!listEl) return;
    if (isOver) listEl.classList.add("is-over");
    else listEl.classList.remove("is-over");
  }

  function getMoveUrl(cardEl) {
    // Prefer per-card URL
    const url = cardEl.getAttribute("data-move-url");
    if (url) return url;

    // Fallback: build from lead id (last resort)
    const leadId = cardEl.getAttribute("data-lead-id");
    return leadId ? "/jobs/kanban/" + leadId + "/move/" : "";
  }

  function onDragStart(e) {
    draggedCard = this;
    dragStarted = true;

    originList = this.parentElement;
    originNextSibling = this.nextElementSibling;

    this.classList.add("is-dragging");

    if (e.dataTransfer) {
      e.dataTransfer.effectAllowed = "move";
      try {
        e.dataTransfer.setData("text/plain", this.getAttribute("data-lead-id") || "");
      } catch (_) {}
    }
  }

  function onDragEnd() {
    this.classList.remove("is-dragging");
    draggedCard = null;

    // allow click again after a tiny delay
    window.setTimeout(function () {
      dragStarted = false;
    }, 0);
  }

  function onDragOver(e) {
    e.preventDefault();
    setDropVisual(this, true);
    if (e.dataTransfer) e.dataTransfer.dropEffect = "move";
  }

  function onDragLeave() {
    setDropVisual(this, false);
  }

  function rollbackCard() {
    if (!draggedCard || !originList) return;

    // Put back where it was
    if (originNextSibling && originNextSibling.parentElement === originList) {
      originList.insertBefore(draggedCard, originNextSibling);
    } else {
      originList.appendChild(draggedCard);
    }
  }

  function persistMove(cardEl, newStatus) {
    const moveUrl = getMoveUrl(cardEl);
    if (!moveUrl) return Promise.reject(new Error("Missing move URL"));

    const csrf = getCSRFToken();
    const body = formUrlEncode({ status: newStatus });

    return fetch(moveUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-CSRFToken": csrf,
        "X-Requested-With": "XMLHttpRequest",
      },
      body: body,
      credentials: "same-origin",
    }).then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return true;
    });
  }

  function onDrop(e) {
    e.preventDefault();
    setDropVisual(this, false);

    if (!draggedCard) return;

    const newStatus = this.getAttribute("data-status");
    const leadId = draggedCard.getAttribute("data-lead-id");
    if (!newStatus || !leadId) return;

    // If dropped in same list, do nothing
    if (originList === this) return;

    // Optimistic UI
    this.appendChild(draggedCard);
    

    // Update counts immediately
    updateColumnCount(originList);
    updateColumnCount(this);

    persistMove(draggedCard, newStatus)
      .then(function () {
        showToast("Statut mis à jour ✅");
      })
      .catch(function () {
        // rollback UI + counts
        rollbackCard();
        updateColumnCount(originList);
        updateColumnCount(qs("[data-droppable='true'][data-status='" + newStatus + "']"));
        showToast("Impossible de mettre à jour");
      });
  }

  function initKanban() {
    const board = qs("[data-kanban]");
    if (!board) return;

    // Cards
    qsa("[data-draggable-card='true']", board).forEach(function (card) {
      card.addEventListener("dragstart", onDragStart);
      card.addEventListener("dragend", onDragEnd);

      // Click opens detail (but not if we are dragging)
      card.addEventListener("click", function (e) {
        if (dragStarted) return;
        // If the click is on a link/button inside, keep default behavior
        const tag = (e.target && e.target.tagName ? e.target.tagName.toLowerCase() : "");
        if (tag === "a" || tag === "button" || tag === "input" || tag === "select" || tag === "textarea") return;

        const leadId = card.getAttribute("data-lead-id");
        if (leadId) window.location.href = "/jobs/offres/" + leadId + "/";
      });
    });

    // Droppable lists
    qsa("[data-droppable='true']", board).forEach(function (list) {
      list.addEventListener("dragover", onDragOver);
      list.addEventListener("dragleave", onDragLeave);
      list.addEventListener("drop", onDrop);

      // Accessibility focus
      list.setAttribute("tabindex", "0");
    });

    // Ensure counts correct on load
    updateAllCounts(board);
  }

  // =====================================================
  // Boot
  // =====================================================

  document.addEventListener("DOMContentLoaded", function () {
    initToastDismiss();
    initCopyButtons();
    initKanban();
  });
})();
