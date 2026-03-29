// rapport.js — Rapports et filtres UniPresence Pro

// ─────────────────────────────────────────────
// ÉTAT GLOBAL
// ─────────────────────────────────────────────
let rapportData   = [];
let currentPage   = 1;
const PAGE_SIZE   = 20;

// ─────────────────────────────────────────────
// INITIALISATION
// ─────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  initDateFilters();
  initSelectFilters();
  await loadEnseignantsList();
  await loadRapport();
  initExportButtons();
  initSearchBar();
});

// ─────────────────────────────────────────────
// CHARGEMENT DES DONNÉES
// ─────────────────────────────────────────────
async function loadRapport() {
  const container = document.getElementById('rapport-table-container') || document.querySelector('.rapport-container');
  if (container) showSpinner(container);

  try {
    const filters = getFilters();
    const data    = await api.getRapport(filters);
    rapportData   = Array.isArray(data) ? data : (data.data || data.presences || data.rapport || []);
    currentPage   = 1;
    renderTable();
    updateStats(rapportData);
  } catch (err) {
    showToast('Impossible de charger le rapport : ' + err.message, 'error');
  } finally {
    if (container) hideSpinner(container);
  }
}

// ─────────────────────────────────────────────
// LECTURE DES FILTRES
// ─────────────────────────────────────────────
function getFilters() {
  const val = (id) => {
    const el = document.getElementById(id);
    return el ? el.value.trim() : '';
  };
  return {
    enseignant_id: val('filter-enseignant') || undefined,
    date_debut:    val('filter-date-debut') || val('date-debut') || undefined,
    date_fin:      val('filter-date-fin')   || val('date-fin')   || undefined,
    departement:   val('filter-dept')       || undefined,
    statut:        val('filter-statut')     || undefined,
    search:        val('rapport-search')    || undefined,
  };
}

// ─────────────────────────────────────────────
// RENDU TABLEAU PAGINÉ
// ─────────────────────────────────────────────
function renderTable() {
  const tbody     = document.getElementById('rapport-tbody') || document.querySelector('#rapport-table tbody');
  const container = document.getElementById('rapport-table-container');

  if (!tbody && !container) return;

  const start  = (currentPage - 1) * PAGE_SIZE;
  const end    = start + PAGE_SIZE;
  const page   = rapportData.slice(start, end);

  const statutConfig = {
    PRESENT:  { cls: 'badge-present', label: 'Présent' },
    RETARD:   { cls: 'badge-retard',  label: 'En retard' },
    ABSENT:   { cls: 'badge-absent',  label: 'Absent' },
    EXCUSED:  { cls: 'badge-excuse',  label: 'Excusé' },
  };

  const modeLabel = {
    CAMERA:   'Caméra',
    QR_CODE:  'QR Code',
    MANUEL:   'Manuel',
  };
  const modeCls = {
    QR_CODE: 'badge-blue',
    CAMERA:  'badge-planifiee',
    MANUEL:  'badge-or',
  };

  if (page.length === 0) {
    const emptyRow = `<tr><td colspan="8" class="table-empty">Aucune donnée pour les filtres sélectionnés</td></tr>`;
    if (tbody) {
      tbody.innerHTML = emptyRow;
    } else {
      container.innerHTML = `<table class="data-table"><tbody>${emptyRow}</tbody></table>`;
    }
    renderPagination(0, 1, PAGE_SIZE);
    return;
  }

  const typeLabel = { ARRIVEE: 'Arrivée', DEPART: 'Départ' };
  const typeCls   = { ARRIVEE: 'badge-blue', DEPART: 'badge-or' };

  const rows = page.map((row, idx) => {
    const statut  = statutConfig[row.statut] || { cls: 'badge-planifiee', label: row.statut || '—' };
    // mode_pointage est le champ retourné par l'API
    const modeVal = row.mode_pointage || row.mode || '';
    const mode    = modeLabel[modeVal] || modeVal || '—';
    const retard  = row.retard_minutes
      ? `<span class="retard-badge">${row.retard_minutes} min</span>`
      : '<span class="text-muted">—</span>';
    // Champs plats issus de la jointure SQL
    const prenom  = row.prenom  || (row.enseignant && row.enseignant.prenom) || '';
    const nom     = row.nom     || (row.enseignant && row.enseignant.nom)    || row.enseignant_nom || '';
    const ensNom  = (prenom || nom) ? `${prenom} ${nom}`.trim() : '—';
    // Département (champ plat de la jointure)
    const dept    = row.departement || '—';
    // Date et heure
    const dateAff  = row.date_pointage || row.date || '';
    const heureAff = row.heure_pointage || row.heure_arrivee || '';
    // Type de pointage (ARRIVEE / DEPART)
    const typeVal  = row.type_pointage || '';
    const typeDisp = typeLabel[typeVal] || typeVal || '—';
    const typeBadge = `<span class="badge ${typeCls[typeVal] || 'badge-planifiee'}">${typeDisp}</span>`;

    return `<tr class="${idx % 2 === 0 ? 'row-even' : 'row-odd'}" data-reveal>
      <td>${formatDate(dateAff)}</td>
      <td>
        <span class="table-avatar-inline" aria-hidden="true">
          ${getInitialsSpan(prenom, nom)}
        </span>
        ${ensNom}
      </td>
      <td>${dept}</td>
      <td><span class="badge ${modeCls[modeVal] || 'badge-blue'}">${mode}</span></td>
      <td>${formatTime(heureAff) || '—'}</td>
      <td>${retard}</td>
      <td><span class="badge ${statut.cls}">${statut.label}</span></td>
      <td>${typeBadge}</td>
    </tr>`;
  }).join('');

  if (tbody) {
    tbody.innerHTML = rows;
    // Animer les lignes
    setTimeout(() => animateTableRows(tbody), 50);
  } else {
    container.innerHTML = `
      <table class="data-table" id="rapport-table">
        <thead>
          <tr>
            <th>Date</th>
            <th>Enseignant</th>
            <th>Département</th>
            <th>Mode</th>
            <th>Heure</th>
            <th>Retard</th>
            <th>Statut</th>
            <th>Type</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>`;
  }

  renderPagination(rapportData.length, currentPage, PAGE_SIZE);
}

function getInitialsSpan(prenom, nom) {
  const i = `${(prenom || '')[0] || ''}${(nom || '')[0] || ''}`.toUpperCase();
  return `<span class="avatar-xs">${i || '??'}</span>`;
}

function animateTableRows(tbody) {
  if (!tbody) return;
  const rows = tbody.querySelectorAll('tr');
  rows.forEach((row, i) => {
    row.style.opacity   = '0';
    row.style.transform = 'translateY(8px)';
    setTimeout(() => {
      row.style.transition = 'opacity 0.2s ease, transform 0.2s ease';
      row.style.opacity    = '1';
      row.style.transform  = 'translateY(0)';
    }, i * 40);
  });
}

// ─────────────────────────────────────────────
// STATISTIQUES RÉSUMÉ
// ─────────────────────────────────────────────
function updateStats(data) {
  if (!data || data.length === 0) {
    setStatEl('stat-total',    '0');
    setStatEl('stat-presents', '0');
    setStatEl('stat-absents',  '0');
    setStatEl('stat-retards',  '0');
    setStatEl('stat-taux',     '0%');
    drawProgressBar(0);
    return;
  }

  const total    = data.length;
  const presents = data.filter((r) => r.statut === 'PRESENT').length;
  const retards  = data.filter((r) => r.statut === 'RETARD').length;
  const absents  = data.filter((r) => r.statut === 'ABSENT').length;
  const taux     = total > 0 ? Math.round(((presents + retards) / total) * 100) : 0;

  // Retard moyen
  const retardData    = data.filter((r) => r.retard_minutes && r.retard_minutes > 0);
  const retardMoyen   = retardData.length > 0
    ? Math.round(retardData.reduce((s, r) => s + r.retard_minutes, 0) / retardData.length)
    : 0;

  setStatEl('stat-total',        String(total));
  setStatEl('stat-presents',     String(presents));
  setStatEl('stat-absents',      String(absents));
  setStatEl('stat-retards',      String(retards));
  setStatEl('stat-retard-moyen', retardMoyen > 0 ? `${retardMoyen} min` : '—');
  setStatEl('stat-taux',         `${taux}%`);

  drawProgressBar(taux);
}

function setStatEl(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

// ─────────────────────────────────────────────
// BARRE DE PROGRESSION SVG
// ─────────────────────────────────────────────
function drawProgressBar(percentage) {
  const container = document.getElementById('progress-taux');
  if (!container) return;

  const W    = container.clientWidth || 300;
  const H    = 24;
  const fill = (percentage / 100) * W;

  let color;
  if (percentage >= 80)      color = 'var(--color-success,#22c55e)';
  else if (percentage >= 60) color = 'var(--color-warning,#f59e0b)';
  else                       color = 'var(--color-danger,#ef4444)';

  container.innerHTML = `
    <svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}"
         role="progressbar" aria-valuenow="${percentage}" aria-valuemin="0" aria-valuemax="100">
      <rect x="0" y="4" width="${W}" height="${H - 8}" rx="6"
        fill="var(--color-border,#e5e7eb)"/>
      <rect x="0" y="4" width="0" height="${H - 8}" rx="6" fill="${color}">
        <animate attributeName="width" from="0" to="${fill.toFixed(1)}"
          dur="0.6s" fill="freeze" calcMode="spline"
          keySplines="0.4 0 0.2 1" keyTimes="0;1"/>
      </rect>
      <text x="${Math.min(fill + 6, W - 30)}" y="${H / 2 + 4}"
        font-size="11" font-weight="600" fill="${color}">${percentage}%</text>
    </svg>`;
}

// ─────────────────────────────────────────────
// FILTRES DATES RAPIDES
// ─────────────────────────────────────────────
function initDateFilters() {
  const btnAujourd = document.getElementById('filter-today');
  const btnSemaine = document.getElementById('filter-week');
  const btnMois    = document.getElementById('filter-month');

  const inputDebut = document.getElementById('filter-date-debut') || document.getElementById('date-debut');
  const inputFin   = document.getElementById('filter-date-fin')   || document.getElementById('date-fin');

  function setDates(debut, fin) {
    if (inputDebut) inputDebut.value = debut;
    if (inputFin)   inputFin.value   = fin;
    [btnAujourd, btnSemaine, btnMois].forEach((b) => b && b.classList.remove('btn--active'));
    loadRapport();
  }

  if (btnAujourd) {
    btnAujourd.addEventListener('click', () => {
      btnAujourd.classList.add('btn--active');
      const today = isoToday();
      setDates(today, today);
    });
  }

  if (btnSemaine) {
    btnSemaine.addEventListener('click', () => {
      btnSemaine.classList.add('btn--active');
      const now   = new Date();
      const day   = now.getDay() || 7; // Lundi = 1
      const lundi = new Date(now); lundi.setDate(now.getDate() - day + 1);
      const dim   = new Date(lundi); dim.setDate(lundi.getDate() + 6);
      setDates(toISO(lundi), toISO(dim));
    });
  }

  if (btnMois) {
    btnMois.addEventListener('click', () => {
      btnMois.classList.add('btn--active');
      const now    = new Date();
      const debut  = new Date(now.getFullYear(), now.getMonth(), 1);
      const fin    = new Date(now.getFullYear(), now.getMonth() + 1, 0);
      setDates(toISO(debut), toISO(fin));
    });
  }

  // Écouter les changements des inputs date
  if (inputDebut) inputDebut.addEventListener('change', () => { currentPage = 1; loadRapport(); });
  if (inputFin)   inputFin.addEventListener('change',   () => { currentPage = 1; loadRapport(); });
}

function isoToday() {
  return toISO(new Date());
}

function toISO(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

// ─────────────────────────────────────────────
// FILTRES SELECT
// ─────────────────────────────────────────────
function initSelectFilters() {
  const ids = ['filter-dept', 'filter-statut', 'filter-enseignant'];
  ids.forEach((id) => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener('change', () => { currentPage = 1; loadRapport(); });
    }
  });
}

// ─────────────────────────────────────────────
// LISTE ENSEIGNANTS POUR LE FILTRE
// ─────────────────────────────────────────────
async function loadEnseignantsList() {
  const select = document.getElementById('filter-enseignant');
  if (!select) return;
  try {
    const data = await api.getEnseignants();
    const list = Array.isArray(data) ? data : (data.data || data.enseignants || []);
    select.innerHTML = `<option value="">Tous les enseignants</option>` +
      list.map((p) => `<option value="${p.id}">${p.prenom || ''} ${p.nom || ''} (${p.matricule || ''})</option>`).join('');
  } catch (_) {
    /* Silencieux : le filtre fonctionnera sans la liste */
  }
}

// ─────────────────────────────────────────────
// RECHERCHE DANS LE TABLEAU (côté client)
// ─────────────────────────────────────────────
function initSearchBar() {
  const input = document.getElementById('rapport-search');
  if (!input) return;
  input.addEventListener('input', debounce(() => {
    currentPage = 1;
    loadRapport();
  }, 400));
}

// ─────────────────────────────────────────────
// BOUTONS D'EXPORT
// ─────────────────────────────────────────────
function initExportButtons() {
  const btnPDF = document.getElementById('export-pdf');
  const btnCSV = document.getElementById('export-csv');
  if (btnPDF) btnPDF.addEventListener('click', exportPDF);
  if (btnCSV) btnCSV.addEventListener('click', exportCSV);
}

async function exportPDF() {
  try {
    showToast('Génération du PDF…', 'info');
    await api.downloadPDF(getFilters());
    showToast('PDF téléchargé', 'success');
  } catch (err) {
    showToast('Erreur export PDF : ' + err.message, 'error');
  }
}

async function exportCSV() {
  try {
    showToast('Génération du CSV…', 'info');
    await api.downloadCSV(getFilters());
    showToast('CSV téléchargé', 'success');
  } catch (err) {
    showToast('Erreur export CSV : ' + err.message, 'error');
  }
}

// ─────────────────────────────────────────────
// PAGINATION
// ─────────────────────────────────────────────
function renderPagination(total, page, pageSize) {
  const container = document.getElementById('rapport-pagination') || document.querySelector('.rapport-pagination');
  if (!container) return;

  const totalPages = Math.ceil(total / pageSize);
  if (totalPages <= 1) { container.innerHTML = ''; return; }

  const uniquePages = buildPageRange(page, totalPages);

  let html = `<button class="pagination__btn" ${page <= 1 ? 'disabled' : ''} data-page="${page - 1}"
    aria-label="Page précédente">&#8592; Précédent</button>`;

  let prev = 0;
  for (const p of uniquePages) {
    if (p - prev > 1) html += `<span class="pagination__ellipsis">…</span>`;
    html += `<button class="pagination__btn ${p === page ? 'pagination__btn--active' : ''}"
      data-page="${p}" aria-current="${p === page ? 'page' : 'false'}">${p}</button>`;
    prev = p;
  }

  html += `<button class="pagination__btn" ${page >= totalPages ? 'disabled' : ''} data-page="${page + 1}"
    aria-label="Page suivante">Suivant &#8594;</button>`;

  const from = (page - 1) * pageSize + 1;
  const to   = Math.min(page * pageSize, total);
  html += `<span class="pagination__info">${from}–${to} sur ${total} entrées</span>`;

  container.innerHTML = html;

  container.querySelectorAll('.pagination__btn:not([disabled])').forEach((btn) => {
    btn.addEventListener('click', () => {
      currentPage = parseInt(btn.dataset.page, 10);
      renderTable();
      const tableEl = document.getElementById('rapport-table') || document.querySelector('.rapport-container');
      if (tableEl) tableEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });
}

function buildPageRange(current, total) {
  const pages = new Set([1, total]);
  for (let p = Math.max(2, current - 2); p <= Math.min(total - 1, current + 2); p++) pages.add(p);
  return [...pages].sort((a, b) => a - b);
}
