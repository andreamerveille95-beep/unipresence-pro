// qr_codes.js — Galerie et gestion QR codes UniPresence Pro

// ─────────────────────────────────────────────
// ÉTAT GLOBAL
// ─────────────────────────────────────────────
let allQRData    = [];   // [{enseignant, qr_base64}]
let filteredQR   = [];
let searchQuery  = '';

// ─────────────────────────────────────────────
// INITIALISATION
// ─────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  await loadQRCodes();
  initSearch();
  initExportButtons();
  initSortButtons();
});

// ─────────────────────────────────────────────
// CHARGEMENT DES QR CODES
// ─────────────────────────────────────────────
async function loadQRCodes() {
  const container = document.getElementById('qr-grid') || document.querySelector('.qr-container');
  if (container) showSpinner(container);

  try {
    // 1. Récupérer tous les enseignants (qui incluent éventuellement qr_code_path)
    const data = await api.getEnseignants();
    const enseignants = Array.isArray(data) ? data : (data.data || data.enseignants || []);

    // 2. Pour chaque enseignant ayant un QR, charger l'image base64
    allQRData = [];

    await Promise.allSettled(
      enseignants.map(async (ens) => {
        try {
          const qrData = await api.getQRCode(ens.id);
          const b64    = qrData.qr_base64 || qrData.qr_code || qrData.image || '';
          if (b64) {
            allQRData.push({
              enseignant: ens,
              qr_base64:  b64.startsWith('data:') ? b64 : `data:image/png;base64,${b64}`,
            });
          }
        } catch (_) {
          // Enseignant sans QR code — on skip silencieusement
        }
      })
    );

    // Trier par nom par défaut
    allQRData.sort((a, b) => {
      const nA = (a.enseignant.nom || '').toLowerCase();
      const nB = (b.enseignant.nom || '').toLowerCase();
      return nA.localeCompare(nB, 'fr');
    });

    filteredQR = [...allQRData];
    renderQRGrid();

  } catch (err) {
    showToast('Erreur de chargement des QR codes : ' + err.message, 'error');
  } finally {
    if (container) hideSpinner(container);
  }

  // Mettre à jour le compteur
  updateCounter();
}

// ─────────────────────────────────────────────
// RENDU GRILLE
// ─────────────────────────────────────────────
function renderQRGrid(dataOverride) {
  const container = document.getElementById('qr-grid') || document.querySelector('.qr-container');
  if (!container) return;

  // Accepte un tableau optionnel (pour le filtre dept depuis le HTML inline)
  const data = dataOverride !== undefined ? dataOverride : filteredQR;

  const empty = document.getElementById('qr-empty');

  if (data.length === 0) {
    container.style.display = 'none';
    if (empty) empty.style.display = 'block';
    updateCounter(0);
    return;
  }

  if (empty) empty.style.display = 'none';
  container.style.display = 'grid';
  container.innerHTML = data.map(renderQRCard).join('');

  // Attacher les événements
  container.querySelectorAll('[data-action]').forEach((btn) => {
    btn.addEventListener('click', handleQRAction);
  });

  // Animations reveal
  if (window.initScrollReveal) window.initScrollReveal();
  updateCounter(data.length);
}

// ─────────────────────────────────────────────
// CARD QR
// ─────────────────────────────────────────────
function renderQRCard(item) {
  const ens      = item.enseignant;
  const initials = `${(ens.prenom || '')[0] || ''}${(ens.nom || '')[0] || ''}`.toUpperCase();
  const dept     = ens.departement || '';
  const deptStyle = {
    ESIT:  'background:var(--badge-esit-bg);color:var(--badge-esit-color)',
    EME:   'background:var(--badge-eme-bg);color:var(--badge-eme-color)',
    ADMIN: 'background:var(--badge-admin-bg);color:var(--badge-admin-color)',
  }[dept] || 'background:var(--bg-section);color:var(--text-muted)';

  return `<article class="qr-card" data-id="${ens.id}" data-reveal>
    <div class="qr-card-check"><i class="fa-solid fa-check" style="font-size:.65rem;"></i></div>

    <div class="qr-image-wrap">
      <img
        src="${item.qr_base64}"
        alt="QR Code de ${ens.prenom || ''} ${ens.nom || ''}"
        class="qr-image"
        loading="lazy"
        onerror="this.parentElement.innerHTML='<div class=qr-image-placeholder><i class=fa-solid\ fa-qrcode></i></div>';"
      >
    </div>

    <div class="qr-name">
      <span class="qr-prenom">${ens.prenom || ''}</span> ${ens.nom || ''}
    </div>
    <div class="qr-matricule">${ens.matricule || '—'}</div>

    <div class="qr-dept-badge">
      ${dept ? `<span style="display:inline-block;padding:2px 10px;border-radius:999px;font-size:.7rem;font-weight:700;${deptStyle}">${dept}</span>` : ''}
      ${ens.grade ? `<span style="display:inline-block;padding:2px 8px;border-radius:999px;font-size:.68rem;background:var(--bg-section);color:var(--text-muted);border:1px solid var(--border-color);margin-left:4px;">${ens.grade}</span>` : ''}
    </div>

    <div class="qr-actions">
      <button class="qr-action-btn qr-action-btn--download"
        data-action="download"
        data-id="${ens.id}"
        data-matricule="${ens.matricule || ''}"
        data-nom="${ens.nom || ''}"
        data-prenom="${ens.prenom || ''}"
        title="Télécharger l'image PNG">
        <i class="fa-solid fa-image"></i> PNG
      </button>
      <button class="qr-action-btn qr-action-btn--pdf"
        data-action="download-pdf"
        data-id="${ens.id}"
        data-matricule="${ens.matricule || ''}"
        data-nom="${ens.nom || ''}"
        data-prenom="${ens.prenom || ''}"
        title="Télécharger le PDF avec logo IUE">
        <i class="fa-solid fa-file-pdf"></i> PDF
      </button>
      <button class="qr-action-btn qr-action-btn--regen"
        data-action="regenerer"
        data-id="${ens.id}"
        title="Régénérer le QR code">
        <i class="fa-solid fa-rotate"></i>
      </button>
    </div>
  </article>`;
}

// ─────────────────────────────────────────────
// DISPATCH DES ACTIONS
// ─────────────────────────────────────────────
function handleQRAction(e) {
  const btn = e.currentTarget;
  const action = btn.dataset.action;
  const id     = parseInt(btn.dataset.id, 10);

  switch (action) {
    case 'download':
      downloadQR(id, btn.dataset.matricule, btn.dataset.nom, btn.dataset.prenom);
      break;
    case 'download-pdf':
      downloadQRPDF(id, btn.dataset.matricule, btn.dataset.nom, btn.dataset.prenom);
      break;
    case 'regenerer':
      regenererQR(id);
      break;
  }
}

// ─────────────────────────────────────────────
// RECHERCHE
// ─────────────────────────────────────────────
function initSearch() {
  const input = document.getElementById('search-qr') || document.getElementById('qr-search') || document.querySelector('.qr-search input');
  if (!input) return;

  input.addEventListener('input', debounce((e) => {
    searchQuery = e.target.value.trim().toLowerCase();
    applySearch();
  }, 200));
}

function applySearch() {
  if (!searchQuery) {
    filteredQR = [...allQRData];
  } else {
    filteredQR = allQRData.filter((item) => {
      const ens = item.enseignant;
      const str = `${ens.prenom || ''} ${ens.nom || ''} ${ens.matricule || ''} ${ens.email || ''}`.toLowerCase();
      return str.includes(searchQuery);
    });
  }
  renderQRGrid();
}

// ─────────────────────────────────────────────
// TÉLÉCHARGEMENT PNG INDIVIDUEL
// ─────────────────────────────────────────────
async function downloadQR(id, matricule, nom, prenom) {
  // D'abord essayer depuis le cache local
  const cached = allQRData.find((d) => d.enseignant.id === id);

  if (cached && cached.qr_base64) {
    triggerDownload(cached.qr_base64, buildFilename(matricule, nom, prenom));
    return;
  }

  // Sinon refetch
  try {
    const data = await api.getQRCode(id);
    const b64  = data.qr_base64 || data.qr_code || data.image || '';
    if (!b64) { showToast('Image QR introuvable', 'error'); return; }
    const src  = b64.startsWith('data:') ? b64 : `data:image/png;base64,${b64}`;
    triggerDownload(src, buildFilename(matricule, nom, prenom));
  } catch (err) {
    showToast('Erreur téléchargement : ' + err.message, 'error');
  }
}

function buildFilename(matricule, nom, prenom) {
  const mat   = (matricule || 'XXXX').replace(/[^a-zA-Z0-9-_]/g, '_');
  const n     = (nom    || '').toUpperCase().replace(/\s+/g, '_');
  const p     = (prenom || '').replace(/\s+/g, '_');
  return `qr_${mat}_${n}_${p}.png`;
}

function triggerDownload(dataURL, filename) {
  const a       = document.createElement('a');
  a.href        = dataURL;
  a.download    = filename;
  a.style.display = 'none';
  document.body.appendChild(a);
  a.click();
  setTimeout(() => document.body.removeChild(a), 200);
}

// ─────────────────────────────────────────────
// TÉLÉCHARGEMENT PDF INDIVIDUEL (avec logo)
// ─────────────────────────────────────────────
async function downloadQRPDF(id, matricule, nom, prenom) {
  const btn = document.querySelector(`[data-action="download-pdf"][data-id="${id}"]`);
  const originalHTML = btn ? btn.innerHTML : '';
  if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>'; }

  try {
    // Le serveur retourne directement le PDF en binaire
    const response = await fetch(`/api/enseignants/${id}/qr/pdf`, {
      method: 'GET',
      credentials: 'include',
    });
    if (!response.ok) throw new Error(`Erreur ${response.status}`);

    const blob = await response.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    const mat  = (matricule || 'IUE').replace(/[^a-zA-Z0-9-_]/g, '_');
    const n    = (nom    || '').toUpperCase().replace(/\s+/g, '_');
    const p    = (prenom || '').replace(/\s+/g, '_');
    a.href     = url;
    a.download = `qr_${mat}_${n}_${p}.pdf`;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { document.body.removeChild(a); URL.revokeObjectURL(url); }, 300);
    showToast('PDF téléchargé', 'success');
  } catch (err) {
    showToast('Erreur PDF : ' + err.message, 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = originalHTML; }
  }
}

// ─────────────────────────────────────────────
// RÉGÉNÉRATION QR
// ─────────────────────────────────────────────
async function regenererQR(id) {
  const item = allQRData.find((d) => d.enseignant.id === id);
  const nom  = item ? `${item.enseignant.prenom || ''} ${item.enseignant.nom || ''}` : `Enseignant #${id}`;

  if (!confirm(`Régénérer le QR code de ${nom.trim()} ?\nL'ancien code sera invalidé et tous les pointages futurs devront utiliser le nouveau.`)) return;

  // Feedback visuel sur la card
  const card = document.querySelector(`.qr-card[data-id="${id}"]`);
  if (card) showSpinner(card);

  try {
    const data = await api.regenerateQR(id);
    const b64  = data.qr_base64 || data.qr_code || data.image || '';

    if (b64 && item) {
      item.qr_base64 = b64.startsWith('data:') ? b64 : `data:image/png;base64,${b64}`;

      // Mettre à jour l'image dans la card existante sans re-render complet
      if (card) {
        const img = card.querySelector('.qr-card__image');
        if (img) img.src = item.qr_base64;
      }
    } else {
      // Recharger toute la grille
      await loadQRCodes();
    }

    showToast(`QR de ${nom.trim()} régénéré avec succès`, 'success');
  } catch (err) {
    showToast('Erreur régénération : ' + err.message, 'error');
  } finally {
    if (card) hideSpinner(card);
  }
}

// ─────────────────────────────────────────────
// EXPORT GLOBAL
// ─────────────────────────────────────────────
function initExportButtons() {
  const btnPDF = document.getElementById('export-pdf');
  const btnZIP = document.getElementById('export-zip');
  if (btnPDF) btnPDF.addEventListener('click', exporterPDF);
  if (btnZIP) btnZIP.addEventListener('click', exporterZIP);
}

async function exporterPDF() {
  try {
    showToast('Génération du PDF de tous les QR codes…', 'info');
    await api.exportQRPDF();
    showToast('PDF téléchargé', 'success');
  } catch (err) {
    showToast('Erreur export PDF : ' + err.message, 'error');
  }
}

async function exporterZIP() {
  try {
    showToast('Génération du ZIP de tous les QR codes…', 'info');
    await api.exportQRZip();
    showToast('ZIP téléchargé', 'success');
  } catch (err) {
    showToast('Erreur export ZIP : ' + err.message, 'error');
  }
}

// ─────────────────────────────────────────────
// TRI
// ─────────────────────────────────────────────
function initSortButtons() {
  const btnNom  = document.getElementById('sort-nom');
  const btnDept = document.getElementById('sort-dept');

  if (btnNom) {
    btnNom.addEventListener('click', () => {
      filteredQR.sort((a, b) =>
        (a.enseignant.nom || '').localeCompare(b.enseignant.nom || '', 'fr')
      );
      renderQRGrid();
    });
  }

  if (btnDept) {
    btnDept.addEventListener('click', () => {
      filteredQR.sort((a, b) => {
        const dA = a.enseignant.departement || '';
        const dB = b.enseignant.departement || '';
        return dA.localeCompare(dB, 'fr') || (a.enseignant.nom || '').localeCompare(b.enseignant.nom || '', 'fr');
      });
      renderQRGrid();
    });
  }
}

// ─────────────────────────────────────────────
// COMPTEUR
// ─────────────────────────────────────────────
function updateCounter(count) {
  const n  = count !== undefined ? count : filteredQR.length;
  const el = document.getElementById('qr-count');
  if (el) {
    const total = allQRData.length;
    if (n === total) {
      el.textContent = `${total} QR code${total > 1 ? 's' : ''} disponible${total > 1 ? 's' : ''}`;
    } else {
      el.textContent = `${n} sur ${total} QR code${total > 1 ? 's' : ''}`;
    }
  }
}
