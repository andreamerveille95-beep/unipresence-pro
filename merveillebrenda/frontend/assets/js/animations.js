// animations.js — Animations et interactions globales UniPresence Pro

// ─────────────────────────────────────────────
// SCROLL REVEAL (IntersectionObserver)
// ─────────────────────────────────────────────
/**
 * Animer tous les éléments [data-reveal] quand ils entrent dans le viewport.
 * Supporte les attributs optionnels :
 *   data-reveal-delay="200"   → délai fixe en ms
 *   data-reveal="fade"        → animation (classe CSS à appliquer)
 */
function initScrollReveal() {
  const elements = document.querySelectorAll('[data-reveal]');
  if (!elements.length) return;

  const observer = new IntersectionObserver(
    (entries) => {
      // Grouper par ordre d'apparition pour le stagger
      const visible = entries.filter((e) => e.isIntersecting);
      visible.forEach((entry, i) => {
        const el        = entry.target;
        const fixedDelay = parseInt(el.dataset.revealDelay || '0', 10);
        const stagger   = i * 50;
        const totalDelay = fixedDelay + stagger;

        setTimeout(() => {
          el.classList.add('revealed');
        }, totalDelay);

        observer.unobserve(el);
      });
    },
    {
      threshold:   0.1,
      rootMargin:  '0px 0px -40px 0px',
    }
  );

  elements.forEach((el) => {
    // S'assurer que les éléments commencent invisibles (si pas déjà géré en CSS)
    if (!el.classList.contains('revealed')) {
      el.classList.add('reveal-ready');
    }
    observer.observe(el);
  });
}

// ─────────────────────────────────────────────
// ANIMATION STAGGER DES LIGNES DE TABLEAU
// ─────────────────────────────────────────────
/**
 * Animer les lignes d'un tbody avec un délai décalé.
 * @param {HTMLElement|string} tbodyOrSelector  tbody ou sélecteur CSS
 * @param {number}             baseDelay        délai de base en ms (avant le premier)
 * @param {number}             stepDelay        pas entre chaque ligne en ms
 */
function animateTableRows(tbodyOrSelector, baseDelay = 0, stepDelay = 50) {
  let tbody;
  if (typeof tbodyOrSelector === 'string') {
    tbody = document.querySelector(tbodyOrSelector);
  } else if (tbodyOrSelector instanceof HTMLElement) {
    tbody = tbodyOrSelector;
  } else {
    // Fallback : tous les tbody visibles
    tbody = document.querySelector('tbody');
  }

  if (!tbody) return;

  const rows = tbody.querySelectorAll('tr');
  rows.forEach((row, i) => {
    row.style.opacity   = '0';
    row.style.transform = 'translateY(10px)';
    row.style.transition = 'none';

    setTimeout(() => {
      row.style.transition = 'opacity 0.25s ease, transform 0.25s ease';
      row.style.opacity    = '1';
      row.style.transform  = 'translateY(0)';
    }, baseDelay + i * stepDelay);
  });
}

// ─────────────────────────────────────────────
// SIDEBAR BURGER MENU (mobile)
// ─────────────────────────────────────────────
function initBurgerMenu() {
  const burgerBtn = document.querySelector('.burger-btn');
  const sidebar   = document.querySelector('.sidebar');

  if (!burgerBtn || !sidebar) return;

  let overlay = document.querySelector('.sidebar-overlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.className = 'sidebar-overlay';
    overlay.setAttribute('aria-hidden', 'true');
    document.body.appendChild(overlay);
  }

  function openSidebar() {
    sidebar.classList.add('open');
    overlay.classList.add('sidebar-overlay--visible');
    burgerBtn.setAttribute('aria-expanded', 'true');
    document.body.style.overflow = 'hidden'; // Empêcher le scroll en arrière-plan
  }

  function closeSidebar() {
    sidebar.classList.remove('open');
    overlay.classList.remove('sidebar-overlay--visible');
    burgerBtn.setAttribute('aria-expanded', 'false');
    document.body.style.overflow = '';
  }

  burgerBtn.addEventListener('click', () => {
    const isOpen = sidebar.classList.contains('open');
    if (isOpen) closeSidebar(); else openSidebar();
  });

  // Fermer en cliquant sur l'overlay
  overlay.addEventListener('click', closeSidebar);

  // Fermer avec Escape
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && sidebar.classList.contains('open')) closeSidebar();
  });

  // Fermer si le viewport devient plus large que 768px
  const mq = window.matchMedia('(min-width: 768px)');
  mq.addEventListener('change', (e) => {
    if (e.matches) closeSidebar();
  });

  // Fermer quand un lien de navigation est cliqué (mobile UX)
  sidebar.querySelectorAll('.nav-link, a').forEach((link) => {
    link.addEventListener('click', () => {
      if (window.innerWidth < 768) closeSidebar();
    });
  });
}

// ─────────────────────────────────────────────
// LIEN DE NAVIGATION ACTIF
// ─────────────────────────────────────────────
function setActiveNavLink() {
  const currentPath = window.location.pathname;
  const navLinks    = document.querySelectorAll('.nav-link, [data-nav-link]');

  navLinks.forEach((link) => {
    link.classList.remove('active');
    link.removeAttribute('aria-current');
  });

  // Chercher d'abord une correspondance exacte, puis partielle
  let matched = false;

  navLinks.forEach((link) => {
    const href = link.getAttribute('href');
    if (!href || href === '#') return;

    // Correspondance exacte
    if (currentPath === href || currentPath.endsWith(href)) {
      link.classList.add('active');
      link.setAttribute('aria-current', 'page');
      matched = true;
    }
  });

  // Correspondance partielle si rien n'est trouvé
  if (!matched) {
    navLinks.forEach((link) => {
      const href = link.getAttribute('href');
      if (!href || href === '#' || href === '/' || href.endsWith('index.html')) return;

      // Extraire le nom de fichier pour comparaison
      const hrefBase = href.split('/').pop().split('?')[0].split('#')[0];
      const pathBase = currentPath.split('/').pop().split('?')[0];

      if (hrefBase && pathBase && pathBase.includes(hrefBase.replace('.html', ''))) {
        link.classList.add('active');
        link.setAttribute('aria-current', 'page');
      }
    });
  }

  // Gérer les sous-menus : si un lien enfant est actif, ouvrir le parent
  navLinks.forEach((link) => {
    if (link.classList.contains('active')) {
      const submenu = link.closest('.nav-submenu, .nav-group');
      if (submenu) {
        submenu.classList.add('open', 'has-active');
        const toggle = submenu.querySelector('.nav-toggle');
        if (toggle) toggle.setAttribute('aria-expanded', 'true');
      }
    }
  });
}

// ─────────────────────────────────────────────
// SMOOTH SCROLL POUR LES ANCRES
// ─────────────────────────────────────────────
function initSmoothScroll() {
  document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
    anchor.addEventListener('click', (e) => {
      const hash   = anchor.getAttribute('href');
      if (!hash || hash === '#') return;

      const target = document.querySelector(hash);
      if (!target) return;

      e.preventDefault();
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });

      // Mettre à jour l'URL sans recharger
      if (history.pushState) history.pushState(null, null, hash);

      // Focus pour l'accessibilité
      if (!target.hasAttribute('tabindex')) target.setAttribute('tabindex', '-1');
      target.focus({ preventScroll: true });
    });
  });
}

// ─────────────────────────────────────────────
// DROPDOWN MENUS (accessibles au clavier)
// ─────────────────────────────────────────────
function initDropdowns() {
  document.querySelectorAll('[data-dropdown]').forEach((trigger) => {
    const menuId = trigger.dataset.dropdown;
    const menu   = document.getElementById(menuId) || trigger.nextElementSibling;
    if (!menu) return;

    trigger.setAttribute('aria-haspopup', 'true');
    trigger.setAttribute('aria-expanded', 'false');

    function openDropdown() {
      menu.classList.add('dropdown--open');
      trigger.setAttribute('aria-expanded', 'true');
      // Positionner le dropdown si nécessaire
      positionDropdown(trigger, menu);
    }

    function closeDropdown() {
      menu.classList.remove('dropdown--open');
      trigger.setAttribute('aria-expanded', 'false');
    }

    trigger.addEventListener('click', (e) => {
      e.stopPropagation();
      const isOpen = menu.classList.contains('dropdown--open');
      // Fermer tous les autres dropdowns
      closeAllDropdowns();
      if (!isOpen) openDropdown();
    });

    // Navigation clavier
    trigger.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        trigger.click();
      }
      if (e.key === 'Escape') closeDropdown();
    });
  });

  // Fermer les dropdowns en cliquant ailleurs
  document.addEventListener('click', closeAllDropdowns);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeAllDropdowns(); });
}

function closeAllDropdowns() {
  document.querySelectorAll('.dropdown--open').forEach((menu) => {
    menu.classList.remove('dropdown--open');
    const trigger = document.querySelector(`[data-dropdown="${menu.id}"]`);
    if (trigger) trigger.setAttribute('aria-expanded', 'false');
  });
}

function positionDropdown(trigger, menu) {
  const rect    = trigger.getBoundingClientRect();
  const menuH   = menu.offsetHeight;
  const viewH   = window.innerHeight;

  // Placer en bas par défaut, en haut si pas de place
  if (rect.bottom + menuH > viewH && rect.top > menuH) {
    menu.classList.add('dropdown--up');
  } else {
    menu.classList.remove('dropdown--up');
  }
}

// ─────────────────────────────────────────────
// TOOLTIPS ACCESSIBLES
// ─────────────────────────────────────────────
function initTooltips() {
  document.querySelectorAll('[data-tooltip]').forEach((el) => {
    const text = el.dataset.tooltip;
    if (!text) return;

    let tooltip = null;

    function showTooltip() {
      tooltip = document.createElement('div');
      tooltip.className   = 'tooltip';
      tooltip.textContent = text;
      tooltip.setAttribute('role', 'tooltip');
      document.body.appendChild(tooltip);

      const rect   = el.getBoundingClientRect();
      const tW     = tooltip.offsetWidth;
      const tH     = tooltip.offsetHeight;
      const margin = 8;

      // Position par défaut : au-dessus
      let top  = rect.top  - tH - margin + window.scrollY;
      let left = rect.left + rect.width / 2 - tW / 2 + window.scrollX;

      // Rester dans le viewport
      left = Math.max(margin, Math.min(left, window.innerWidth - tW - margin));
      if (top < margin) top = rect.bottom + margin + window.scrollY;

      tooltip.style.top  = `${top}px`;
      tooltip.style.left = `${left}px`;
      tooltip.classList.add('tooltip--visible');
    }

    function hideTooltip() {
      if (tooltip) { tooltip.remove(); tooltip = null; }
    }

    el.addEventListener('mouseenter', showTooltip);
    el.addEventListener('mouseleave', hideTooltip);
    el.addEventListener('focus',      showTooltip);
    el.addEventListener('blur',       hideTooltip);
  });
}

// ─────────────────────────────────────────────
// ANIMATION DES CARDS AU SURVOL
// ─────────────────────────────────────────────
function initCardHovers() {
  // Effet tilt 3D subtil sur les cartes
  document.querySelectorAll('.prof-card, .qr-card, .kpi-card').forEach((card) => {
    card.addEventListener('mousemove', (e) => {
      const rect   = card.getBoundingClientRect();
      const x      = e.clientX - rect.left;
      const y      = e.clientY - rect.top;
      const cx     = rect.width  / 2;
      const cy     = rect.height / 2;
      const tiltX  = ((y - cy) / cy) * 4;   // max 4deg
      const tiltY  = ((cx - x) / cx) * 4;

      card.style.transform = `perspective(600px) rotateX(${tiltX.toFixed(1)}deg) rotateY(${tiltY.toFixed(1)}deg) translateY(-2px)`;
    });
    card.addEventListener('mouseleave', () => {
      card.style.transform = '';
    });
  });
}

// ─────────────────────────────────────────────
// ANIMATION DES NOMBRES (compteurs)
// ─────────────────────────────────────────────
function initCounterAnimations() {
  const counters = document.querySelectorAll('[data-count-to]');
  if (!counters.length) return;

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      const el       = entry.target;
      const target   = parseFloat(el.dataset.countTo || '0');
      const decimals = parseInt(el.dataset.countDecimals || '0', 10);
      const suffix   = el.dataset.countSuffix || '';
      const duration = parseInt(el.dataset.countDuration || '800', 10);

      observer.unobserve(el);

      let start     = null;
      const from    = parseFloat(el.dataset.countFrom || '0');

      function step(timestamp) {
        if (!start) start = timestamp;
        const progress = Math.min((timestamp - start) / duration, 1);
        const ease     = 1 - Math.pow(1 - progress, 3);
        el.textContent = (from + (target - from) * ease).toFixed(decimals) + suffix;
        if (progress < 1) requestAnimationFrame(step);
      }
      requestAnimationFrame(step);
    });
  }, { threshold: 0.3 });

  counters.forEach((el) => observer.observe(el));
}

// ─────────────────────────────────────────────
// BARRE DE PROGRESSION ANIMÉE
// ─────────────────────────────────────────────
function initProgressBars() {
  const bars = document.querySelectorAll('[data-progress]');
  if (!bars.length) return;

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      const bar   = entry.target;
      const value = parseFloat(bar.dataset.progress || '0');
      observer.unobserve(bar);
      setTimeout(() => {
        bar.style.width = `${Math.min(value, 100)}%`;
      }, 100);
    });
  }, { threshold: 0.2 });

  bars.forEach((bar) => {
    bar.style.width     = '0%';
    bar.style.transition = 'width 0.8s cubic-bezier(0.4, 0, 0.2, 1)';
    observer.observe(bar);
  });
}

// ─────────────────────────────────────────────
// FLASH MESSAGE (fermeture automatique)
// ─────────────────────────────────────────────
function initFlashMessages() {
  document.querySelectorAll('.flash-message').forEach((msg) => {
    // Auto-dismiss après 5s
    setTimeout(() => {
      msg.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
      msg.style.opacity    = '0';
      msg.style.transform  = 'translateY(-10px)';
      setTimeout(() => msg.remove(), 400);
    }, 5000);

    const closeBtn = msg.querySelector('.flash-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', () => {
        msg.style.transition = 'opacity 0.2s ease';
        msg.style.opacity    = '0';
        setTimeout(() => msg.remove(), 200);
      });
    }
  });
}

// ─────────────────────────────────────────────
// INITIALISATION GLOBALE
// ─────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initScrollReveal();
  initBurgerMenu();
  setActiveNavLink();
  initSmoothScroll();
  initDropdowns();
  initTooltips();
  initCardHovers();
  initCounterAnimations();
  initProgressBars();
  initFlashMessages();

  // Animer les lignes de tableau déjà présentes au chargement
  setTimeout(() => animateTableRows('tbody'), 200);

  // Observer les nouvelles lignes ajoutées dynamiquement
  const tableObserver = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      mutation.addedNodes.forEach((node) => {
        if (node.nodeName === 'TBODY') {
          setTimeout(() => animateTableRows(node), 50);
        }
        if (node.nodeName === 'TR' && node.closest('tbody')) {
          node.style.opacity   = '0';
          node.style.transform = 'translateX(-8px)';
          setTimeout(() => {
            node.style.transition = 'opacity 0.2s ease, transform 0.2s ease';
            node.style.opacity    = '1';
            node.style.transform  = 'translateX(0)';
          }, 30);
        }
      });
    });
  });

  document.querySelectorAll('table').forEach((table) => {
    tableObserver.observe(table, { childList: true, subtree: true });
  });

  // Ré-appliquer scroll reveal lors d'ajouts de contenu dynamique
  const revealObserver = new MutationObserver(() => {
    const newElements = document.querySelectorAll('[data-reveal]:not(.reveal-ready):not(.revealed)');
    if (newElements.length > 0) initScrollReveal();
  });

  revealObserver.observe(document.body, { childList: true, subtree: true });
});

// Ré-exécuter setActiveNavLink sur les navigations SPA si applicable
window.addEventListener('popstate', setActiveNavLink);
