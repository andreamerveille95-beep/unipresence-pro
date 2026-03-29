// dashboard.js — Dashboard UniPresence Pro

// ─────────────────────────────────────────────
// ÉTAT GLOBAL
// ─────────────────────────────────────────────
let statsData        = null;
let refreshInterval  = null;

// ─────────────────────────────────────────────
// INITIALISATION
// ─────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  await loadDashboardStats();
  startAutoRefresh(15000); // Rafraîchissement toutes les 15s
});

// ─────────────────────────────────────────────
// CHARGEMENT DES STATS
// ─────────────────────────────────────────────
async function loadDashboardStats() {
  const mainContent = document.querySelector('.dashboard-content') || document.body;
  showSpinner(mainContent);
  try {
    const data = await api.getDashboardStats();
    statsData = data;

    if (data.kpis) {
      // Enrichir les KPIs avec les champs absents du endpoint get_stats_dashboard()
      const enrichedKpis = {
        ...data.kpis,
        seances_du_jour: data.seances_du_jour ? data.seances_du_jour.length : 0,
        taux_presence:   data.taux_ponctualite != null ? data.taux_ponctualite : 0,
      };
      updateKPIs(enrichedKpis);
    }

    // presences_7_jours → format {label, value} attendu par drawLineChart
    if (data.presences_7_jours && data.presences_7_jours.length > 0) {
      const chartLineData = data.presences_7_jours.map((d) => ({
        label: d.date ? d.date.slice(5).replace('-', '/') : '',
        value: (d.nb_presents || 0) + (d.nb_retards || 0),
      }));
      drawLineChart(chartLineData);
    }

    // par_departement → format {label, value, dept} attendu par drawBarChart
    if (data.par_departement && data.par_departement.length > 0) {
      const chartBarData = data.par_departement.map((d) => ({
        label: d.departement || '—',
        value: d.nb_presents || 0,
        dept:  d.departement || '',
      }));
      drawBarChart(chartBarData);
    }

    if (data.taux_ponctualite != null) drawDonutChart(data.taux_ponctualite);
    if (data.derniers_pointages)       renderDerniersPointages(data.derniers_pointages);
    if (data.seances_du_jour)          renderSeancesDuJour(data.seances_du_jour);

    // Horodatage dernière mise à jour
    const lastUpdate = document.getElementById('last-update');
    if (lastUpdate) {
      const now = new Date();
      lastUpdate.textContent = `Mis à jour à ${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`;
    }
  } catch (err) {
    showToast('Impossible de charger les statistiques : ' + err.message, 'error');
  } finally {
    hideSpinner(mainContent);
  }
}

// ─────────────────────────────────────────────
// KPI CARDS — animation countUp
// ─────────────────────────────────────────────
function updateKPIs(kpis) {
  // kpis : { total_enseignants, presents_aujourd_hui, seances_du_jour, taux_presence }
  const mapping = {
    'kpi-total-enseignants':  { value: kpis.total_enseignants  || 0, decimals: 0 },
    'kpi-presents':           { value: kpis.presents_aujourd_hui || 0, decimals: 0 },
    'kpi-seances':            { value: kpis.seances_du_jour     || 0, decimals: 0 },
    'kpi-taux':               { value: kpis.taux_presence        || 0, decimals: 1, suffix: '%' },
  };

  for (const [id, cfg] of Object.entries(mapping)) {
    const el = document.getElementById(id);
    if (!el) continue;
    const from = parseFloat(el.dataset.current || '0');
    el.dataset.current = cfg.value;
    countUp(el, from, cfg.value, 800, cfg.decimals || 0, cfg.suffix || '');
  }
}

/**
 * Animation fluide d'un compteur numérique
 * @param {HTMLElement} el       élément cible
 * @param {number}      from     valeur de départ
 * @param {number}      to       valeur d'arrivée
 * @param {number}      duration durée en ms
 * @param {number}      decimals décimales à afficher
 * @param {string}      suffix   suffixe ex: '%'
 */
function countUp(el, from, to, duration = 800, decimals = 0, suffix = '') {
  if (!el) return;
  const startTime = performance.now();
  const diff = to - from;

  function step(currentTime) {
    const elapsed  = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);
    // Ease out cubic
    const ease = 1 - Math.pow(1 - progress, 3);
    const current = from + diff * ease;
    el.textContent = current.toFixed(decimals) + suffix;
    if (progress < 1) requestAnimationFrame(step);
  }

  requestAnimationFrame(step);
}

// ─────────────────────────────────────────────
// GRAPHIQUE COURBE SVG (7 derniers jours)
// ─────────────────────────────────────────────
/**
 * @param {Array<{label:string, value:number}>} data
 */
function drawLineChart(data) {
  const container = document.getElementById('chart-line');
  if (!container || !data || data.length === 0) return;

  const W = container.clientWidth  || 560;
  const H = container.clientHeight || 220;
  const padL = 40, padR = 20, padT = 20, padB = 40;
  const innerW = W - padL - padR;
  const innerH = H - padT - padB;

  const values = data.map((d) => d.value);
  const maxVal = Math.max(...values, 1);
  const minVal = 0;

  // Coordonnées des points
  const points = data.map((d, i) => ({
    x: padL + (i / (data.length - 1)) * innerW,
    y: padT + innerH - ((d.value - minVal) / (maxVal - minVal)) * innerH,
    label: d.label,
    value: d.value,
  }));

  // Path principal
  const pathD = points
    .map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`)
    .join(' ');

  // Path aire (gradient)
  const areaD =
    pathD +
    ` L ${points[points.length - 1].x.toFixed(1)} ${(padT + innerH).toFixed(1)}` +
    ` L ${points[0].x.toFixed(1)} ${(padT + innerH).toFixed(1)} Z`;

  // Lignes de grille
  const gridLines = Array.from({ length: 5 }, (_, i) => {
    const y = padT + (i / 4) * innerH;
    const val = Math.round(maxVal - (i / 4) * maxVal);
    return `<line x1="${padL}" y1="${y.toFixed(1)}" x2="${W - padR}" y2="${y.toFixed(1)}"
              stroke="var(--color-border, #e5e7eb)" stroke-width="1" stroke-dasharray="4 3"/>
            <text x="${(padL - 6).toFixed(1)}" y="${(y + 4).toFixed(1)}" text-anchor="end"
              font-size="10" fill="var(--color-text-muted, #9ca3af)">${val}</text>`;
  }).join('');

  // Labels axe X
  const xLabels = points
    .map(
      (p) =>
        `<text x="${p.x.toFixed(1)}" y="${(padT + innerH + 18).toFixed(1)}" text-anchor="middle"
          font-size="10" fill="var(--color-text-muted, #9ca3af)">${p.label}</text>`
    )
    .join('');

  // Cercles de données + zones tooltip
  const circles = points
    .map(
      (p) =>
        `<g class="chart-point" data-value="${p.value}" data-label="${p.label}">
          <circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="5"
            fill="var(--color-primary, #6366f1)" stroke="#fff" stroke-width="2"
            class="chart-dot"/>
          <circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="12"
            fill="transparent" class="chart-hit-area"/>
        </g>`
    )
    .join('');

  // Calcul longueur totale du path pour l'animation
  const totalLength = points.reduce((acc, p, i) => {
    if (i === 0) return 0;
    const prev = points[i - 1];
    return acc + Math.sqrt(Math.pow(p.x - prev.x, 2) + Math.pow(p.y - prev.y, 2));
  }, 0);

  const svgId    = 'line-chart-svg-' + Date.now();
  const gradId   = 'line-grad-' + Date.now();
  const pathId   = 'line-path-' + Date.now();

  container.innerHTML = `
    <svg id="${svgId}" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}"
         style="overflow:visible" aria-label="Graphique présences 7 derniers jours">
      <defs>
        <linearGradient id="${gradId}" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stop-color="var(--color-primary,#6366f1)" stop-opacity="0.3"/>
          <stop offset="100%" stop-color="var(--color-primary,#6366f1)" stop-opacity="0.02"/>
        </linearGradient>
      </defs>

      <!-- Grille -->
      ${gridLines}

      <!-- Aire -->
      <path d="${areaD}" fill="url(#${gradId})"/>

      <!-- Courbe avec animation -->
      <path id="${pathId}" d="${pathD}"
        fill="none" stroke="var(--color-primary,#6366f1)" stroke-width="2.5"
        stroke-linecap="round" stroke-linejoin="round"
        stroke-dasharray="${totalLength.toFixed(0)}"
        stroke-dashoffset="${totalLength.toFixed(0)}">
        <animate attributeName="stroke-dashoffset"
          from="${totalLength.toFixed(0)}" to="0"
          dur="0.8s" fill="freeze" calcMode="spline"
          keySplines="0.4 0 0.2 1" keyTimes="0;1"/>
      </path>

      <!-- Points -->
      ${circles}

      <!-- Labels X -->
      ${xLabels}

      <!-- Tooltip (caché par défaut) -->
      <g id="chart-tooltip-${svgId}" style="display:none; pointer-events:none">
        <rect rx="4" ry="4" fill="var(--color-surface,#1e293b)" width="80" height="32"/>
        <text id="chart-tooltip-text-${svgId}" font-size="11"
          fill="var(--color-text,#f1f5f9)" x="8" y="14"/>
        <text id="chart-tooltip-val-${svgId}"  font-size="13" font-weight="bold"
          fill="var(--color-primary,#6366f1)" x="8" y="28"/>
      </g>
    </svg>
  `;

  // Gestion des tooltips
  const svg = container.querySelector('svg');
  const tooltip     = svg.querySelector(`#chart-tooltip-${svgId}`);
  const tooltipText = svg.querySelector(`#chart-tooltip-text-${svgId}`);
  const tooltipVal  = svg.querySelector(`#chart-tooltip-val-${svgId}`);

  svg.querySelectorAll('.chart-point').forEach((g) => {
    g.addEventListener('mouseenter', (e) => {
      const pt     = svg.createSVGPoint();
      pt.x = e.clientX; pt.y = e.clientY;
      const svgPt  = pt.matrixTransform(svg.getScreenCTM().inverse());
      const cx     = parseFloat(g.querySelector('.chart-dot').getAttribute('cx'));
      const cy     = parseFloat(g.querySelector('.chart-dot').getAttribute('cy'));
      tooltipText.textContent = g.dataset.label;
      tooltipVal.textContent  = g.dataset.value + ' présences';
      tooltip.querySelector('rect').setAttribute('width', '120');
      tooltip.setAttribute('transform', `translate(${(cx - 60).toFixed(0)},${(cy - 44).toFixed(0)})`);
      tooltip.style.display = 'block';
    });
    g.addEventListener('mouseleave', () => { tooltip.style.display = 'none'; });
  });
}

// ─────────────────────────────────────────────
// GRAPHIQUE BARRES SVG (par département)
// ─────────────────────────────────────────────
/**
 * @param {Array<{label:string, value:number, dept:string}>} data
 */
function drawBarChart(data) {
  const container = document.getElementById('chart-bar');
  if (!container || !data || data.length === 0) return;

  const W = container.clientWidth  || 400;
  const H = container.clientHeight || 200;
  const padL = 40, padR = 20, padT = 20, padB = 50;
  const innerW = W - padL - padR;
  const innerH = H - padT - padB;

  const values = data.map((d) => d.value);
  const maxVal = Math.max(...values, 1);

  const barW   = Math.max(20, innerW / data.length * 0.5);
  const spacing = innerW / data.length;

  // Palette de couleurs par département
  const palette = {
    ESIT:  'var(--color-primary, #6366f1)',
    EME:   'var(--color-secondary, #8b5cf6)',
    ADMIN: 'var(--color-warning, #f59e0b)',
    default: 'var(--color-accent, #06b6d4)',
  };

  // Lignes de grille
  const gridLines = Array.from({ length: 4 }, (_, i) => {
    const y   = padT + (i / 3) * innerH;
    const val = Math.round(maxVal - (i / 3) * maxVal);
    return `<line x1="${padL}" y1="${y.toFixed(1)}" x2="${W - padR}" y2="${y.toFixed(1)}"
              stroke="var(--color-border, #e5e7eb)" stroke-width="1" stroke-dasharray="4 3"/>
            <text x="${(padL - 6).toFixed(1)}" y="${(y + 4).toFixed(1)}" text-anchor="end"
              font-size="10" fill="var(--color-text-muted, #9ca3af)">${val}</text>`;
  }).join('');

  // Barres
  const bars = data.map((d, i) => {
    const barH  = ((d.value / maxVal) * innerH) || 0;
    const x     = padL + i * spacing + (spacing - barW) / 2;
    const y     = padT + innerH - barH;
    const color = palette[d.dept] || palette.default;
    const animDur = (0.4 + i * 0.08).toFixed(2);

    return `<g class="bar-group" data-value="${d.value}" data-label="${d.label}">
      <rect x="${x.toFixed(1)}" y="${(padT + innerH).toFixed(1)}"
        width="${barW.toFixed(1)}" height="0" rx="3" fill="${color}" opacity="0.9"
        class="bar-rect">
        <animate attributeName="height" from="0" to="${barH.toFixed(1)}"
          dur="${animDur}s" fill="freeze" calcMode="spline"
          keySplines="0.4 0 0.2 1" keyTimes="0;1"/>
        <animate attributeName="y" from="${(padT + innerH).toFixed(1)}" to="${y.toFixed(1)}"
          dur="${animDur}s" fill="freeze" calcMode="spline"
          keySplines="0.4 0 0.2 1" keyTimes="0;1"/>
      </rect>
      <text x="${(x + barW / 2).toFixed(1)}" y="${(y - 5).toFixed(1)}"
        text-anchor="middle" font-size="11" font-weight="600"
        fill="var(--color-text, #1e293b)">${d.value}</text>
      <text x="${(x + barW / 2).toFixed(1)}" y="${(padT + innerH + 18).toFixed(1)}"
        text-anchor="middle" font-size="11"
        fill="var(--color-text-muted, #9ca3af)">${d.label}</text>
    </g>`;
  }).join('');

  // Légende
  const legend = Object.entries(palette)
    .filter(([k]) => k !== 'default' && data.some((d) => d.dept === k))
    .map(([dept, color], i) => {
      const lx = padL + i * 90;
      return `<g transform="translate(${lx},${H - 12})">
        <rect width="12" height="12" rx="2" fill="${color}"/>
        <text x="16" y="10" font-size="10" fill="var(--color-text-muted,#9ca3af)">${dept}</text>
      </g>`;
    }).join('');

  container.innerHTML = `
    <svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}"
         aria-label="Graphique présences par département">
      ${gridLines}
      ${bars}
      ${legend}
    </svg>
  `;

  // Tooltips barres
  container.querySelectorAll('.bar-group').forEach((g) => {
    g.style.cursor = 'pointer';
    g.addEventListener('mouseenter', () => {
      g.querySelector('.bar-rect').setAttribute('opacity', '1');
    });
    g.addEventListener('mouseleave', () => {
      g.querySelector('.bar-rect').setAttribute('opacity', '0.9');
    });
  });
}

// ─────────────────────────────────────────────
// DONUT SVG (taux de ponctualité)
// ─────────────────────────────────────────────
/**
 * @param {number} percentage  0–100
 */
function drawDonutChart(percentage) {
  const container = document.getElementById('chart-donut');
  if (!container) return;

  const size   = 160;
  const radius = 60;
  const cx     = size / 2;
  const cy     = size / 2;
  const circumference = 2 * Math.PI * radius;
  const filled = (percentage / 100) * circumference;
  const gap    = circumference - filled;

  // Couleur selon valeur
  let color;
  if (percentage >= 80)     color = 'var(--color-success, #22c55e)';
  else if (percentage >= 60) color = 'var(--color-warning, #f59e0b)';
  else                       color = 'var(--color-danger, #ef4444)';

  container.innerHTML = `
    <svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}"
         aria-label="Taux de ponctualité : ${percentage}%">
      <!-- Piste de fond -->
      <circle cx="${cx}" cy="${cy}" r="${radius}"
        fill="none" stroke="var(--color-border, #e5e7eb)" stroke-width="12"/>
      <!-- Arc de valeur -->
      <circle cx="${cx}" cy="${cy}" r="${radius}"
        fill="none" stroke="${color}" stroke-width="12"
        stroke-linecap="round"
        stroke-dasharray="${filled.toFixed(2)} ${gap.toFixed(2)}"
        stroke-dashoffset="${(circumference / 4).toFixed(2)}"
        transform="rotate(-90 ${cx} ${cy})">
        <animate attributeName="stroke-dasharray"
          from="0 ${circumference.toFixed(2)}"
          to="${filled.toFixed(2)} ${gap.toFixed(2)}"
          dur="0.9s" fill="freeze" calcMode="spline"
          keySplines="0.4 0 0.2 1" keyTimes="0;1"/>
      </circle>
      <!-- Texte central -->
      <text x="${cx}" y="${cy - 6}" text-anchor="middle"
        font-size="22" font-weight="700"
        fill="var(--color-text, #1e293b)">${percentage.toFixed(0)}%</text>
      <text x="${cx}" y="${cy + 14}" text-anchor="middle"
        font-size="10" fill="var(--color-text-muted, #9ca3af)">Ponctualité</text>
    </svg>
  `;
}

// ─────────────────────────────────────────────
// DERNIERS POINTAGES
// ─────────────────────────────────────────────
/**
 * @param {Array} pointages [{enseignant_nom, enseignant_prenom, heure_arrivee, statut}]
 */
function renderDerniersPointages(pointages) {
  const container = document.getElementById('derniers-pointages');
  if (!container) return;

  if (!pointages || pointages.length === 0) {
    container.innerHTML = '<p class="empty-state">Aucun pointage récent</p>';
    return;
  }

  const statutBadge = {
    PRESENT:  { cls: 'badge--success', label: 'Présent' },
    RETARD:   { cls: 'badge--warning', label: 'En retard' },
    ABSENT:   { cls: 'badge--danger',  label: 'Absent'  },
  };

  container.innerHTML = pointages.map((p) => {
    const prenom   = p.prenom || p.enseignant_prenom || '';
    const nom      = p.nom   || p.enseignant_nom   || '';
    const initials = `${prenom[0] || '?'}${nom[0] || '?'}`.toUpperCase();
    const heure    = formatTime(p.heure_pointage || p.heure_arrivee);
    const badge    = statutBadge[p.statut] || { cls: 'badge--info', label: p.statut };

    return `<div class="pointage-item" data-reveal>
      <div class="pointage-avatar" aria-hidden="true">${initials}</div>
      <div class="pointage-info">
        <span class="pointage-nom">${prenom} ${nom}</span>
        <span class="pointage-heure">${heure}</span>
      </div>
      <span class="badge ${badge.cls}">${badge.label}</span>
    </div>`;
  }).join('');
}

// ─────────────────────────────────────────────
// SÉANCES DU JOUR
// ─────────────────────────────────────────────
/**
 * @param {Array} seances
 */
function renderSeancesDuJour(seances) {
  const container = document.getElementById('seances-du-jour');
  if (!container) return;

  if (!seances || seances.length === 0) {
    container.innerHTML = '<p class="empty-state">Aucune séance programmée aujourd\'hui</p>';
    return;
  }

  const typeBadge = {
    CM:  'badge--primary',
    TD:  'badge--secondary',
    TP:  'badge--info',
    EXAM:'badge--danger',
  };

  container.innerHTML = seances.map((s) => {
    const typeSeance = s.type_seance || s.type || '—';
    const badgeCls   = typeBadge[typeSeance] || 'badge--default';
    const prenom     = (s.enseignant && s.enseignant.prenom) || s.prenom || '';
    const nom        = (s.enseignant && s.enseignant.nom)    || s.nom    || s.enseignant_nom || '';
    const enseignant = (prenom || nom) ? `${prenom} ${nom}`.trim() : '—';
    return `<div class="seance-item" data-reveal>
      <div class="seance-horaire">
        <span class="seance-heure-debut">${formatTime(s.heure_debut)}</span>
        <span class="seance-heure-sep">–</span>
        <span class="seance-heure-fin">${formatTime(s.heure_fin)}</span>
      </div>
      <div class="seance-details">
        <span class="seance-enseignant">${enseignant}</span>
        <span class="seance-salle">${s.salle || '—'}</span>
      </div>
      <span class="badge ${badgeCls}">${typeSeance}</span>
    </div>`;
  }).join('');
}

// ─────────────────────────────────────────────
// AUTO-REFRESH
// ─────────────────────────────────────────────
function startAutoRefresh(interval) {
  if (refreshInterval) clearInterval(refreshInterval);
  refreshInterval = setInterval(loadDashboardStats, interval);
}

function stopAutoRefresh() {
  if (refreshInterval) {
    clearInterval(refreshInterval);
    refreshInterval = null;
  }
}

// Arrêter le refresh quand l'onglet est masqué (économie réseau)
document.addEventListener('visibilitychange', () => {
  if (document.hidden) {
    stopAutoRefresh();
  } else {
    startAutoRefresh(15000);
  }
});
