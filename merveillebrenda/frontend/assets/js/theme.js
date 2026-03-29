// theme.js — Dark/Light mode UniPresence Pro
// Initialisation immédiate pour éviter le flash de mauvais thème
(function () {
  const saved = localStorage.getItem('theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const theme = saved || (prefersDark ? 'dark' : 'light');
  if (theme === 'dark') document.documentElement.classList.add('dark');

  window.ThemeManager = {
    current: theme,

    /**
     * Basculer entre dark et light
     */
    toggle() {
      const next = this.current === 'dark' ? 'light' : 'dark';
      this.set(next);
    },

    /**
     * Forcer un thème ('dark' ou 'light')
     * @param {string} t
     */
    set(t) {
      if (t !== 'dark' && t !== 'light') return;

      // Transition douce : ajouter la classe pendant 300ms
      document.documentElement.classList.add('theme-transitioning');

      if (t === 'dark') {
        document.documentElement.classList.add('dark');
      } else {
        document.documentElement.classList.remove('dark');
      }

      this.current = t;
      localStorage.setItem('theme', t);
      this._updateIcons();

      setTimeout(() => {
        document.documentElement.classList.remove('theme-transitioning');
      }, 300);
    },

    /**
     * Mettre à jour toutes les icônes des boutons toggle
     */
    _updateIcons() {
      const isDark = this.current === 'dark';
      document.querySelectorAll('.theme-toggle').forEach((btn) => {
        // Icône soleil si mode sombre, lune si mode clair
        const iconSun = btn.querySelector('.icon-sun');
        const iconMoon = btn.querySelector('.icon-moon');
        if (iconSun) iconSun.style.display = isDark ? 'inline-block' : 'none';
        if (iconMoon) iconMoon.style.display = isDark ? 'none' : 'inline-block';

        // Fallback : texte ou aria-label
        btn.setAttribute('aria-label', isDark ? 'Activer le mode clair' : 'Activer le mode sombre');
        btn.setAttribute('title', isDark ? 'Mode clair' : 'Mode sombre');

        // Si le bouton contient du texte brut sans icônes SVG
        if (!iconSun && !iconMoon) {
          btn.textContent = isDark ? '☀️' : '🌙';
        }
      });
    },

    /**
     * Lier tous les .theme-toggle au toggle()
     */
    init() {
      this._updateIcons();
      document.querySelectorAll('.theme-toggle').forEach((btn) => {
        btn.addEventListener('click', () => this.toggle());
      });

      // Écouter les changements de préférence système
      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
        // Ne pas écraser si l'utilisateur a fait un choix manuel
        if (!localStorage.getItem('theme')) {
          this.set(e.matches ? 'dark' : 'light');
        }
      });
    },
  };

  document.addEventListener('DOMContentLoaded', () => window.ThemeManager.init());
})();
