// professeurs.js — CRUD enseignants UniPresence Pro

// ─────────────────────────────────────────────
// ÉTAT GLOBAL
// ─────────────────────────────────────────────
let allProfesseurs      = [];
let filteredProfesseurs = [];
let currentPage         = 1;
const PAGE_SIZE         = 12;
let activeView          = 'grid'; // 'grid' | 'list'
let searchQuery         = '';
let activeFilters       = { departement: '', statut: '', grade: '' };

// ─────────────────────────────────────────────
// INITIALISATION
// ─────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  await loadProfesseurs();
  initSearchBar();
  initFilters();
  initViewToggle();
  initModalListeners();
  initExportButtons();
  initCreateButton();
});

// ─────────────────────────────────────────────
// CHARGEMENT
// ─────────────────────────────────────────────
async function loadProfesseurs() {
  const grid = document.getElementById('professeurs-grid') || document.querySelector('.professeurs-container');
  if (grid) showSpinner(grid);
  try {
    const data = await api.getEnseignants();
    allProfesseurs      = Array.isArray(data) ? data : (data.data || data.enseignants || []);
    filteredProfesseurs = [...allProfesseurs];
    currentPage         = 1;
    renderProfesseurs(filteredProfesseurs);
  } catch (err) {
    showToast('Erreur lors du chargement des enseignants : ' + err.message, 'error');
  } finally {
    if (grid) hideSpinner(grid);
  }
}

// ─────────────────────────────────────────────
// RENDU PRINCIPAL
// ─────────────────────────────────────────────
function renderProfesseurs(profs) {
  const container = document.getElementById('professeurs-grid') || document.querySelector('.professeurs-container');
  if (!container) return;

  const start   = (currentPage - 1) * PAGE_SIZE;
  const end     = start + PAGE_SIZE;
  const page    = profs.slice(start, end);

  if (profs.length === 0) {
    container.innerHTML = `<div class="empty-state">
      <svg viewBox="0 0 64 64" width="64" height="64" fill="none" aria-hidden="true">
        <circle cx="32" cy="32" r="30" stroke="var(--color-border,#e5e7eb)" stroke-width="2"/>
        <path d="M20 44c0-6.627 5.373-12 12-12s12 5.373 12 12" stroke="var(--color-text-muted,#9ca3af)" stroke-width="2" stroke-linecap="round"/>
        <circle cx="32" cy="24" r="8" stroke="var(--color-text-muted,#9ca3af)" stroke-width="2"/>
      </svg>
      <p>Aucun enseignant trouvé</p>
    </div>`;
    renderPagination(0, 1, PAGE_SIZE);
    return;
  }

  if (activeView === 'grid') {
    container.className = container.className.replace(/\blist-view\b/, '') + ' grid-view';
    container.innerHTML = page.map(renderProfCard).join('');
  } else {
    container.className = container.className.replace(/\bgrid-view\b/, '') + ' list-view';
    container.innerHTML = renderProfTable(page);
  }

  // Attacher les événements aux boutons d'action
  container.querySelectorAll('[data-action]').forEach((btn) => {
    btn.addEventListener('click', handleCardAction);
  });

  renderPagination(profs.length, currentPage, PAGE_SIZE);

  // Animations reveal
  if (window.initScrollReveal) window.initScrollReveal();
}

// ─────────────────────────────────────────────
// CARD ENSEIGNANT
// ─────────────────────────────────────────────
function renderProfCard(prof) {
  const initials   = getInitials(prof.prenom, prof.nom);
  const deptBadge  = getDeptBadge(prof.departement);
  const gradeBadge = getGradeBadge(prof.grade);
  const activeNow  = prof.present_aujourd_hui
    ? '<span class="status-dot status-dot--online" title="Présent aujourd\'hui"></span>'
    : '<span class="status-dot status-dot--offline" title="Absent aujourd\'hui"></span>';
  const photoHTML = prof.photo
    ? `<img src="${prof.photo}" alt="${prof.prenom} ${prof.nom}" class="prof-avatar__img" loading="lazy">`
    : `<span class="prof-avatar__initials" aria-hidden="true">${initials}</span>`;

  return `<article class="prof-card" data-id="${prof.id}" data-reveal>
    <div class="prof-card__header">
      <div class="prof-avatar" aria-label="${prof.prenom} ${prof.nom}">
        ${photoHTML}
        ${activeNow}
      </div>
      <div class="prof-card__meta">
        <h3 class="prof-card__name">${prof.prenom || ''} ${prof.nom || ''}</h3>
        <p class="prof-card__matricule">${prof.matricule || '—'}</p>
      </div>
    </div>
    <div class="prof-card__body">
      <p class="prof-card__email" title="${prof.email || ''}">${prof.email || '—'}</p>
      <p class="prof-card__specialite">${prof.specialite || '—'}</p>
      <div class="prof-card__badges">
        ${deptBadge}
        ${gradeBadge}
      </div>
    </div>
    <div class="prof-card__actions">
      <button class="btn btn--icon" data-action="detail"    data-id="${prof.id}" title="Voir le détail">
        <svg viewBox="0 0 20 20" fill="currentColor" width="16" height="16"><path d="M10 12a2 2 0 100-4 2 2 0 000 4z"/><path fill-rule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clip-rule="evenodd"/></svg>
      </button>
      <button class="btn btn--icon" data-action="modifier"  data-id="${prof.id}" title="Modifier">
        <svg viewBox="0 0 20 20" fill="currentColor" width="16" height="16"><path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z"/></svg>
      </button>
      <button class="btn btn--icon" data-action="qr"        data-id="${prof.id}" title="QR Code">
        <svg viewBox="0 0 20 20" fill="currentColor" width="16" height="16"><path fill-rule="evenodd" d="M3 4a1 1 0 011-1h3a1 1 0 010 2H5v2a1 1 0 01-2 0V4zm2 6a1 1 0 011-1h.01a1 1 0 010 2H6a1 1 0 01-1-1zm5-1a1 1 0 000 2h.01a1 1 0 000-2H10zm4 1a1 1 0 011-1h.01a1 1 0 010 2H15a1 1 0 01-1-1zm-4 4a1 1 0 011-1h.01a1 1 0 010 2H11a1 1 0 01-1-1zm5-1a1 1 0 000 2h.01a1 1 0 000-2H16zm-9 1a1 1 0 011-1h.01a1 1 0 010 2H8a1 1 0 01-1-1zM3 13a1 1 0 011-1h3a1 1 0 010 2H5v1a1 1 0 01-2 0v-2zm10-3a1 1 0 011-1h3a1 1 0 010 2h-1v2a1 1 0 01-2 0v-1h-.01a1 1 0 010-2H13zm2-4a1 1 0 011-1h.01a1 1 0 010 2H16a1 1 0 01-1-1zm-5 0a1 1 0 000 2h3a1 1 0 000-2h-3z" clip-rule="evenodd"/></svg>
      </button>
      <button class="btn btn--icon btn--danger" data-action="desactiver" data-id="${prof.id}" title="Désactiver">
        <svg viewBox="0 0 20 20" fill="currentColor" width="16" height="16"><path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd"/></svg>
      </button>
    </div>
  </article>`;
}

// ─────────────────────────────────────────────
// VUE TABLEAU
// ─────────────────────────────────────────────
function renderProfTable(profs) {
  const rows = profs.map((prof) => {
    const initials  = getInitials(prof.prenom, prof.nom);
    const deptBadge = getDeptBadge(prof.departement);
    const dot = prof.present_aujourd_hui
      ? '<span class="status-dot status-dot--online"></span>'
      : '<span class="status-dot status-dot--offline"></span>';
    return `<tr data-id="${prof.id}">
      <td>
        <div class="table-avatar-cell">
          ${prof.photo
            ? `<img src="${prof.photo}" class="table-avatar__img" alt="">`
            : `<span class="table-avatar__initials">${initials}</span>`}
          ${dot}
        </div>
      </td>
      <td>${prof.nom || '—'} ${prof.prenom || ''}</td>
      <td>${prof.matricule || '—'}</td>
      <td>${prof.email || '—'}</td>
      <td>${deptBadge}</td>
      <td>${prof.grade || '—'}</td>
      <td>
        <div class="table-actions">
          <button class="btn btn--icon" data-action="detail"    data-id="${prof.id}" title="Détail">&#128065;</button>
          <button class="btn btn--icon" data-action="modifier"  data-id="${prof.id}" title="Modifier">&#9998;</button>
          <button class="btn btn--icon" data-action="qr"        data-id="${prof.id}" title="QR Code">&#9638;</button>
          <button class="btn btn--icon btn--danger" data-action="desactiver" data-id="${prof.id}" title="Supprimer">&#128465;</button>
        </div>
      </td>
    </tr>`;
  }).join('');

  return `<table class="data-table">
    <thead>
      <tr>
        <th></th>
        <th>Nom</th>
        <th>Matricule</th>
        <th>Email</th>
        <th>Département</th>
        <th>Grade</th>
        <th>Actions</th>
      </tr>
    </thead>
    <tbody>${rows}</tbody>
  </table>`;
}

// ─────────────────────────────────────────────
// DISPATCH DES ACTIONS DE CARD
// ─────────────────────────────────────────────
function handleCardAction(e) {
  const btn    = e.currentTarget;
  const action = btn.dataset.action;
  const id     = parseInt(btn.dataset.id, 10);
  switch (action) {
    case 'detail':    voirDetail(id);    break;
    case 'modifier':  modifierProf(id);  break;
    case 'qr':        genererQR(id);     break;
    case 'desactiver':desactiverProf(id);break;
  }
}

// ─────────────────────────────────────────────
// RECHERCHE EN TEMPS RÉEL
// ─────────────────────────────────────────────
function initSearchBar() {
  const input = document.getElementById('search-professeurs') || document.querySelector('.search-bar input');
  if (!input) return;
  input.addEventListener('input', debounce((e) => {
    searchQuery = e.target.value.trim().toLowerCase();
    currentPage = 1;
    applyFilters();
  }, 200));
}

// ─────────────────────────────────────────────
// FILTRES
// ─────────────────────────────────────────────
function initFilters() {
  const selectors = {
    departement: document.getElementById('filter-dept'),
    statut:      document.getElementById('filter-statut'),
    grade:       document.getElementById('filter-grade'),
  };
  for (const [key, el] of Object.entries(selectors)) {
    if (el) {
      el.addEventListener('change', (e) => {
        activeFilters[key] = e.target.value;
        currentPage = 1;
        applyFilters();
      });
    }
  }
}

function applyFilters() {
  filteredProfesseurs = allProfesseurs.filter((prof) => {
    // Filtre texte
    if (searchQuery) {
      const haystack = `${prof.nom} ${prof.prenom} ${prof.matricule} ${prof.email}`.toLowerCase();
      if (!haystack.includes(searchQuery)) return false;
    }
    // Filtre département
    if (activeFilters.departement && prof.departement !== activeFilters.departement) return false;
    // Filtre grade
    if (activeFilters.grade && prof.grade !== activeFilters.grade) return false;
    // Filtre statut
    if (activeFilters.statut === 'actif'   && prof.actif === false) return false;
    if (activeFilters.statut === 'inactif' && prof.actif !== false) return false;
    return true;
  });
  renderProfesseurs(filteredProfesseurs);
}

// ─────────────────────────────────────────────
// TOGGLE VUE
// ─────────────────────────────────────────────
function initViewToggle() {
  const btnGrid = document.getElementById('view-grid');
  const btnList = document.getElementById('view-list');
  if (btnGrid) btnGrid.addEventListener('click', () => { activeView = 'grid'; renderProfesseurs(filteredProfesseurs); });
  if (btnList) btnList.addEventListener('click', () => { activeView = 'list'; renderProfesseurs(filteredProfesseurs); });
}

// ─────────────────────────────────────────────
// ACTIONS CRUD
// ─────────────────────────────────────────────
async function voirDetail(id) {
  const prof = allProfesseurs.find((p) => p.id === id);
  if (!prof) {
    try { const data = await api.getEnseignant(id); openDetailModal(data); } catch(e) { showToast(e.message, 'error'); }
    return;
  }
  openDetailModal(prof);
}

function openDetailModal(prof) {
  const initials = getInitials(prof.prenom, prof.nom);
  const content = `
    <div class="detail-modal">
      <div class="detail-modal__avatar">
        ${prof.photo ? `<img src="${prof.photo}" alt="${prof.prenom} ${prof.nom}">` : `<span class="avatar-lg">${initials}</span>`}
      </div>
      <table class="detail-table">
        <tr><th>Nom complet</th><td>${prof.prenom || ''} ${prof.nom || ''}</td></tr>
        <tr><th>Matricule</th><td>${prof.matricule || '—'}</td></tr>
        <tr><th>Email</th><td><a href="mailto:${prof.email}">${prof.email || '—'}</a></td></tr>
        <tr><th>Téléphone</th><td>${prof.telephone || '—'}</td></tr>
        <tr><th>Département</th><td>${getDeptBadge(prof.departement)}</td></tr>
        <tr><th>Grade</th><td>${prof.grade || '—'}</td></tr>
        <tr><th>Spécialité</th><td>${prof.specialite || '—'}</td></tr>
        <tr><th>Date création</th><td>${formatDate(prof.created_at)}</td></tr>
      </table>
    </div>`;
  openModal(`${prof.prenom || ''} ${prof.nom || ''}`, content);
}

async function modifierProf(id) {
  let prof = allProfesseurs.find((p) => p.id === id);
  if (!prof) {
    try { prof = await api.getEnseignant(id); } catch(e) { showToast(e.message, 'error'); return; }
  }
  openFormModal('Modifier l\'enseignant', prof, async (formData) => {
    try {
      await api.updateEnseignant(id, formData);
      showToast('Enseignant mis à jour avec succès', 'success');
      closeModal();
      await loadProfesseurs();
    } catch (err) {
      showToast('Erreur : ' + err.message, 'error');
    }
  });
}

async function creerProf(formData) {
  try {
    await api.createEnseignant(formData);
    showToast('Enseignant créé avec succès', 'success');
    closeModal();
    await loadProfesseurs();
  } catch (err) {
    showToast('Erreur : ' + err.message, 'error');
  }
}

async function genererQR(id) {
  const modal = openModal('QR Code', '<div class="qr-loading">Génération en cours…</div>');
  try {
    const data = await api.getQRCode(id);
    const prof = allProfesseurs.find((p) => p.id === id);
    const nom  = prof ? `${prof.prenom || ''} ${prof.nom || ''}` : `Enseignant #${id}`;
    const qrSrc = data.qr_base64 || data.qr_code || data.image || '';
    document.querySelector('.modal-body').innerHTML = `
      <div class="qr-display">
        ${qrSrc
          ? `<img src="${qrSrc.startsWith('data:') ? qrSrc : 'data:image/png;base64,' + qrSrc}"
               alt="QR Code ${nom}" class="qr-image" style="max-width:220px">`
          : '<p>QR non disponible</p>'}
        <p class="qr-nom">${nom}</p>
        <p class="qr-matricule">${prof ? prof.matricule : ''}</p>
        <div class="qr-actions">
          <button class="btn btn--primary" onclick="downloadQRFromModal(${id})">Télécharger PNG</button>
          <button class="btn btn--secondary" onclick="regenererQRModal(${id})">Régénérer</button>
        </div>
      </div>`;
  } catch (err) {
    document.querySelector('.modal-body').innerHTML = `<p class="error-msg">${err.message}</p>`;
  }
}

async function downloadQRFromModal(id) {
  const prof = allProfesseurs.find((p) => p.id === id);
  try {
    const data  = await api.getQRCode(id);
    const b64   = data.qr_base64 || data.qr_code || data.image || '';
    if (!b64) { showToast('Image QR introuvable', 'error'); return; }
    const src   = b64.startsWith('data:') ? b64 : 'data:image/png;base64,' + b64;
    const link  = document.createElement('a');
    link.href   = src;
    link.download = `qr_${prof ? prof.matricule : id}_${prof ? prof.nom : ''}.png`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  } catch (err) { showToast(err.message, 'error'); }
}

async function regenererQRModal(id) {
  if (!confirm('Régénérer le QR code ? L\'ancien sera invalidé.')) return;
  try {
    await api.regenerateQR(id);
    showToast('QR code régénéré', 'success');
    genererQR(id);
  } catch (err) { showToast(err.message, 'error'); }
}

async function desactiverProf(id) {
  const prof = allProfesseurs.find((p) => p.id === id);
  const nom  = prof ? `${prof.prenom || ''} ${prof.nom || ''}` : `cet enseignant`;
  if (!confirm(`Supprimer/désactiver ${nom} ? Cette action est irréversible.`)) return;
  try {
    await api.deleteEnseignant(id);
    showToast(`${nom} a été supprimé`, 'success');
    await loadProfesseurs();
  } catch (err) {
    showToast('Erreur : ' + err.message, 'error');
  }
}

// ─────────────────────────────────────────────
// MODAL GÉNÉRIQUE
// ─────────────────────────────────────────────
function openModal(title, content) {
  let overlay = document.getElementById('modal-overlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'modal-overlay';
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
      <div class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">
        <div class="modal-header">
          <h2 class="modal-title" id="modal-title"></h2>
          <button class="modal-close btn btn--icon" aria-label="Fermer la modale">
            <svg viewBox="0 0 20 20" fill="currentColor" width="20" height="20">
              <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"/>
            </svg>
          </button>
        </div>
        <div class="modal-body"></div>
      </div>`;
    document.body.appendChild(overlay);
    overlay.querySelector('.modal-close').addEventListener('click', closeModal);
    overlay.addEventListener('click', (e) => { if (e.target === overlay) closeModal(); });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeModal(); });
  }

  overlay.querySelector('.modal-title').textContent = title;
  overlay.querySelector('.modal-body').innerHTML = typeof content === 'string' ? content : '';
  overlay.classList.add('modal-overlay--open');
  document.body.style.overflow = 'hidden';
  return overlay;
}

function closeModal() {
  const overlay = document.getElementById('modal-overlay');
  if (overlay) {
    overlay.classList.remove('modal-overlay--open');
    document.body.style.overflow = '';
  }
}

// ─────────────────────────────────────────────
// FORMULAIRE CRÉATION / MODIFICATION
// ─────────────────────────────────────────────
function openFormModal(title, prof = null, onSubmit) {
  const isEdit = !!prof;
  const formHTML = `
    <form id="prof-form" class="form-grid" novalidate>
      <div class="form-group">
        <label for="f-prenom">Prénom *</label>
        <input id="f-prenom" name="prenom" type="text" required value="${isEdit ? (prof.prenom || '') : ''}">
      </div>
      <div class="form-group">
        <label for="f-nom">Nom *</label>
        <input id="f-nom" name="nom" type="text" required value="${isEdit ? (prof.nom || '') : ''}">
      </div>
      <div class="form-group">
        <label for="f-matricule">Matricule *</label>
        <input id="f-matricule" name="matricule" type="text" required value="${isEdit ? (prof.matricule || '') : ''}">
      </div>
      <div class="form-group">
        <label for="f-email">Email *</label>
        <input id="f-email" name="email" type="email" required value="${isEdit ? (prof.email || '') : ''}">
      </div>
      <div class="form-group">
        <label for="f-telephone">Téléphone</label>
        <input id="f-telephone" name="telephone" type="tel" value="${isEdit ? (prof.telephone || '') : ''}">
      </div>
      <div class="form-group">
        <label for="f-dept">Département *</label>
        <select id="f-dept" name="departement" required>
          <option value="">— Choisir —</option>
          <option value="ESIT" ${isEdit && prof.departement === 'ESIT' ? 'selected' : ''}>ESIT</option>
          <option value="EME"  ${isEdit && prof.departement === 'EME'  ? 'selected' : ''}>EME</option>
          <option value="ADMIN"${isEdit && prof.departement === 'ADMIN'? 'selected' : ''}>ADMIN</option>
        </select>
      </div>
      <div class="form-group">
        <label for="f-grade">Grade</label>
        <select id="f-grade" name="grade">
          <option value="">— Choisir —</option>
          <option value="Professeur"       ${isEdit && prof.grade === 'Professeur'        ? 'selected' : ''}>Professeur</option>
          <option value="Maître de conf."  ${isEdit && prof.grade === 'Maître de conf.'  ? 'selected' : ''}>Maître de conférences</option>
          <option value="Assistant"        ${isEdit && prof.grade === 'Assistant'         ? 'selected' : ''}>Assistant</option>
          <option value="Chargé de cours"  ${isEdit && prof.grade === 'Chargé de cours'  ? 'selected' : ''}>Chargé de cours</option>
          <option value="Vacataire"        ${isEdit && prof.grade === 'Vacataire'         ? 'selected' : ''}>Vacataire</option>
        </select>
      </div>
      <div class="form-group form-group--full">
        <label for="f-specialite">Spécialité</label>
        <input id="f-specialite" name="specialite" type="text" value="${isEdit ? (prof.specialite || '') : ''}">
      </div>
      <div class="form-group form-group--full form-actions">
        <button type="button" class="btn btn--secondary" onclick="closeModal()">Annuler</button>
        <button type="submit" class="btn btn--primary">${isEdit ? 'Enregistrer' : 'Créer'}</button>
      </div>
    </form>`;

  openModal(title, formHTML);

  document.getElementById('prof-form').addEventListener('submit', (e) => {
    e.preventDefault();
    const form = e.target;
    if (!form.checkValidity()) { form.reportValidity(); return; }
    const formData = Object.fromEntries(new FormData(form).entries());
    onSubmit(formData);
  });
}

function initCreateButton() {
  const btn = document.getElementById('btn-create-prof') || document.querySelector('[data-create-prof]');
  if (btn) {
    btn.addEventListener('click', () => {
      openFormModal('Nouvel enseignant', null, creerProf);
    });
  }
}

function initModalListeners() {
  // Fermeture par touche Escape (déjà géré dans openModal au premier appel)
}

// ─────────────────────────────────────────────
// EXPORT
// ─────────────────────────────────────────────
function initExportButtons() {
  const btnPDF = document.getElementById('export-qr-pdf');
  const btnZIP = document.getElementById('export-qr-zip');
  if (btnPDF) btnPDF.addEventListener('click', exporterPDF);
  if (btnZIP) btnZIP.addEventListener('click', exporterZIP);
}

async function exporterPDF() {
  try {
    showToast('Génération du PDF en cours…', 'info');
    await api.exportQRPDF();
    showToast('PDF téléchargé', 'success');
  } catch (err) { showToast(err.message, 'error'); }
}

async function exporterZIP() {
  try {
    showToast('Génération du ZIP en cours…', 'info');
    await api.exportQRZip();
    showToast('ZIP téléchargé', 'success');
  } catch (err) { showToast(err.message, 'error'); }
}

// ─────────────────────────────────────────────
// PAGINATION
// ─────────────────────────────────────────────
function renderPagination(total, page, pageSize) {
  const container = document.getElementById('pagination') || document.querySelector('.pagination');
  if (!container) return;

  const totalPages = Math.ceil(total / pageSize);
  if (totalPages <= 1) { container.innerHTML = ''; return; }

  const pages = [];
  // Toujours page 1
  pages.push(1);
  // Pages autour de la page courante
  for (let p = Math.max(2, page - 2); p <= Math.min(totalPages - 1, page + 2); p++) pages.push(p);
  // Toujours dernière page
  if (totalPages > 1) pages.push(totalPages);

  // Dédupliquer et trier
  const uniquePages = [...new Set(pages)].sort((a, b) => a - b);

  let html = `<button class="pagination__btn" ${page <= 1 ? 'disabled' : ''} data-page="${page - 1}"
    aria-label="Page précédente">&#8592; Préc.</button>`;

  let prev = 0;
  for (const p of uniquePages) {
    if (p - prev > 1) html += `<span class="pagination__ellipsis">…</span>`;
    html += `<button class="pagination__btn ${p === page ? 'pagination__btn--active' : ''}"
      data-page="${p}" aria-current="${p === page ? 'page' : 'false'}">${p}</button>`;
    prev = p;
  }

  html += `<button class="pagination__btn" ${page >= totalPages ? 'disabled' : ''} data-page="${page + 1}"
    aria-label="Page suivante">Suiv. &#8594;</button>`;

  html += `<span class="pagination__info">${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, total)} sur ${total}</span>`;

  container.innerHTML = html;

  container.querySelectorAll('.pagination__btn:not([disabled])').forEach((btn) => {
    btn.addEventListener('click', () => {
      currentPage = parseInt(btn.dataset.page, 10);
      renderProfesseurs(filteredProfesseurs);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  });
}

// ─────────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────────
function getInitials(prenom, nom) {
  return `${(prenom || '')[0] || ''}${(nom || '')[0] || ''}`.toUpperCase() || '??';
}

function getDeptBadge(dept) {
  const cls = { ESIT: 'badge--primary', EME: 'badge--secondary', ADMIN: 'badge--warning' }[dept] || 'badge--default';
  return dept ? `<span class="badge ${cls}">${dept}</span>` : '';
}

function getGradeBadge(grade) {
  return grade ? `<span class="badge badge--outline">${grade}</span>` : '';
}
