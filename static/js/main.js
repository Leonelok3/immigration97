/* =====================================================
   IMMIGRATION97 — main.js (SAFE)
   ✅ Menu mobile .c-navbar fiable (taps OK)
   ✅ Modals / Forms / Newsletter / Tracking conservés
   ✅ Guards partout (rien ne casse si élément absent)
===================================================== */

(function () {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

  document.addEventListener("DOMContentLoaded", () => {
    const y = document.getElementById("year");
    if (y) y.textContent = new Date().getFullYear();
  });

  document.addEventListener("click", (e) => {
    // Legacy burger: #menuToggle + #navMenu (si utilisé sur d’autres pages)
    const burger = e.target.closest("#menuToggle");
    const menu = $("#navMenu");
    if (burger && menu) {
      const open = menu.classList.toggle("is-open");
      burger.setAttribute("aria-expanded", String(open));
    }

    // Modals close
    if (e.target.matches("[data-close-modal], .modal__backdrop")) {
      const modal =
        e.target.closest(".modal") || document.getElementById("modal-demo");
      if (modal) modal.hidden = true;
    }

    // Modals open
    const openBtn = e.target.closest("[data-open-modal]");
    if (openBtn) {
      const id = openBtn.getAttribute("data-open-modal");
      const m = document.getElementById(`modal-${id}`);
      if (m) m.hidden = false;
    }
  });

  document.addEventListener("change", (e) => {
    if (e.target.id === "langSwitch") {
      // SAFE: évite crash si I97_I18N n’est pas chargé
      window.I97_I18N?.applyLang?.(e.target.value);
    }
  });

  // micro-anim cartes (hover desktop)
  $$(".card").forEach((c) => {
    c.addEventListener("mouseenter", () => (c.style.transform = "translateY(-3px)"));
    c.addEventListener("mouseleave", () => (c.style.transform = ""));
  });
})();

/* --- Loader pendant le submit du formulaire photos --- */
document.addEventListener("submit", (e) => {
  const form = e.target;
  if (form.matches("[data-photo-form]")) {
    const btn = form.querySelector('button[type="submit"]');
    const wrap = form.querySelector(".progress-wrap");
    btn?.setAttribute("disabled", "true");
    if (wrap) wrap.style.display = "block";
  }
});

/* --- Empêche la soumission sans fichier --- */
document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("[data-photo-form]");
  if (!form) return;

  const fileInput = form.querySelector('input[type="file"]');
  const submitBtn = form.querySelector('button[type="submit"]');

  if (fileInput && submitBtn) {
    submitBtn.disabled = true;
    fileInput.addEventListener("change", () => {
      submitBtn.disabled = !fileInput.files.length;
    });
  }
});

/* =====================================================
   LEGACY NAV SYSTEMS (SAFE)
   (On garde: utile si certaines pages utilisent .navbar)
===================================================== */
document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.getElementById("navToggle");
  const navbar = document.querySelector(".navbar");

  if (toggle && navbar) {
    toggle.addEventListener("click", () => {
      navbar.classList.toggle("open");
    });
  }
});

document.addEventListener("DOMContentLoaded", () => {
  const navToggle = document.getElementById("navToggle");
  const navMenu = document.querySelector(".navbar__nav");
  const userBtn = document.getElementById("userMenuBtn");
  const userDropdown = document.getElementById("userDropdown");

  if (navToggle && navMenu) {
    navToggle.addEventListener("click", () => {
      navMenu.classList.toggle("is-open");
    });
  }

  if (userBtn && userDropdown) {
    userBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      userDropdown.classList.toggle("is-open");
    });

    document.addEventListener("click", () => {
      userDropdown.classList.remove("is-open");
    });
  }
});

/* =====================================================
   TRACKING (SAFE) — billing
   (fusion gtag + fbq, même comportement)
===================================================== */
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll('a[href*="billing"]').forEach((btn) => {
    btn.addEventListener("click", () => {
      if (window.gtag) {
        window.gtag("event", "cta_click", {
          event_category: "conversion",
          event_label: "billing_access",
        });
      }
      if (window.fbq) {
        window.fbq("track", "InitiateCheckout");
      }
    });
  });
});

/* =====================================================
   ✅ NAVBAR MOBILE TOGGLE — C-SYSTEM (FIXED)
   Cible ton HTML actuel:
   .c-navbar, .c-navbar__toggle, .c-navbar__nav
===================================================== */
document.addEventListener("DOMContentLoaded", () => {
  const navbar = document.querySelector(".c-navbar");
  const toggle = document.querySelector(".c-navbar__toggle");
  const nav = document.querySelector(".c-navbar__nav");

  if (!navbar || !toggle || !nav) return;

  if (!toggle.getAttribute("type")) toggle.setAttribute("type", "button");

  const setOpen = (open) => {
    navbar.classList.toggle("is-open", open);
    nav.classList.toggle("is-open", open);
    document.body.classList.toggle("nav-open", open);
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
  };

  toggle.addEventListener("click", (e) => {
    e.preventDefault();
    setOpen(!nav.classList.contains("is-open"));
  });

  // ferme au clic sur un lien
  nav.addEventListener("click", (e) => {
    const a = e.target.closest("a");
    if (a) setOpen(false);
  });

  // ferme clic dehors
  document.addEventListener(
    "click",
    (e) => {
      if (!nav.classList.contains("is-open")) return;
      if (!navbar.contains(e.target)) setOpen(false);
    },
    { passive: true }
  );

  // ferme ESC
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") setOpen(false);
  });
});

/* =====================================================
   NEWSLETTER GLOBAL (cooldown) — #nl-global
===================================================== */
document.addEventListener("DOMContentLoaded", () => {
  const wrap = document.getElementById("nl-global");
  const closeBtn = document.getElementById("nl-close");
  if (!wrap || !closeBtn) return;

  const KEY = "imm97_newsletter_dismissed_until_v1";
  const COOLDOWN_HOURS = 6;

  const now = Date.now();
  const dismissedUntil = parseInt(localStorage.getItem(KEY) || "0", 10);

  if (dismissedUntil && now < dismissedUntil) {
    wrap.classList.add("is-hidden");
    wrap.setAttribute("aria-hidden", "true");
    return;
  }

  let shown = false;

  const show = () => {
    if (shown) return;
    shown = true;

    wrap.classList.remove("is-hidden");
    wrap.setAttribute("aria-hidden", "false");

    requestAnimationFrame(() => {
      wrap.classList.remove("is-hidden");
    });
  };

  const onScroll = () => {
    const sc = window.scrollY || document.documentElement.scrollTop || 0;
    if (sc > 220) show();
  };
  window.addEventListener("scroll", onScroll, { passive: true });

  setTimeout(() => {
    if (!shown) show();
  }, 4000);

  closeBtn.addEventListener("click", () => {
    const until = Date.now() + COOLDOWN_HOURS * 60 * 60 * 1000;
    localStorage.setItem(KEY, String(until));

    wrap.classList.add("is-closing");
    setTimeout(() => {
      wrap.classList.add("is-hidden");
      wrap.setAttribute("aria-hidden", "true");
    }, 360);
  });
});


/* =====================================================
   USER DROPDOWN (ELITE) — SAFE
===================================================== */
document.addEventListener("DOMContentLoaded", () => {
  const wrap = document.getElementById("userNav");
  const btn = document.getElementById("userNavBtn");
  const menu = document.getElementById("userNavMenu");
  if (!wrap || !btn || !menu) return;

  const setOpen = (open) => {
    wrap.classList.toggle("is-open", open);
    btn.setAttribute("aria-expanded", open ? "true" : "false");
    menu.setAttribute("aria-hidden", open ? "false" : "true");
  };

  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    setOpen(!wrap.classList.contains("is-open"));
  });

  document.addEventListener("click", () => setOpen(false), { passive: true });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") setOpen(false);
  });

  menu.addEventListener("click", (e) => {
    const a = e.target.closest("a");
    if (a) setOpen(false);
  });
});


