// api.js — Client API et utilitaires globaux UniPresence Pro

// ─────────────────────────────────────────────
// CLASSE API CLIENT
// ─────────────────────────────────────────────
class ApiClient {
  constructor(baseURL = '') {
    this.baseURL = baseURL;
  }

  /**
   * Requête HTTP générique
   * @param {string} method  GET | POST | PUT | DELETE
   * @param {string} path    chemin relatif ex: /api/enseignants
   * @param {*}      body    objet JS ou FormData
   * @param {object} options options fetch supplémentaires
   */
  async request(method, path, body = null, options = {}) {
    const url = this.baseURL + path;
    const headers = { ...(options.headers || {}) };
    let fetchBody = undefined;

    if (body !== null && body !== undefined) {
      if (body instanceof FormData) {
        // Ne pas forcer Content-Type — le navigateur gère le boundary
        fetchBody = body;
      } else {
        headers['Content-Type'] = 'application/json';
        fetchBody = JSON.stringify(body);
      }
    }

    const config = {
      method,
      credentials: 'include',  // Envoyer/recevoir les cookies de session
      headers,
      ...options,
    };
    if (fetchBody !== undefined) config.body = fetchBody;

    let response;
    try {
      response = await fetch(url, config);
    } catch (err) {
      throw new Error('Erreur réseau : impossible de joindre le serveur. ' + err.message);
    }

    if (!response.ok) {
      let errorMessage = `Erreur HTTP ${response.status}`;
      try {
        const errData = await response.json();
        errorMessage = errData.erreur || errData.message || errData.error || errorMessage;
      } catch (_) { /* le corps n'est pas du JSON valide */ }
      throw new Error(errorMessage);
    }

    // Certaines réponses DELETE renvoient 204 sans corps
    if (response.status === 204) return null;

    return response.json();
  }

  /**
   * Requête GET avec paramètres query string
   * @param {string} path
   * @param {object} params  ex: {page: 1, departement: 'ESIT'}
   */
  get(path, params = {}) {
    const keys = Object.keys(params).filter(
      (k) => params[k] !== null && params[k] !== undefined && params[k] !== ''
    );
    if (keys.length > 0) {
      const qs = keys.map((k) => `${encodeURIComponent(k)}=${encodeURIComponent(params[k])}`).join('&');
      path = `${path}?${qs}`;
    }
    return this.request('GET', path);
  }

  post(path, body) {
    return this.request('POST', path, body);
  }

  put(path, body) {
    return this.request('PUT', path, body);
  }

  delete(path) {
    return this.request('DELETE', path);
  }

  // ── Authentification ──────────────────────────────────────
  async login(email, motDePasse) {
    return this.post('/api/login', { email, mot_de_passe: motDePasse });
  }

  async logout() {
    return this.post('/api/logout');
  }

  async getMe() {
    return this.get('/api/me');
  }

  // ── Enseignants ───────────────────────────────────────────
  async getEnseignants(filters = {}) {
    return this.get('/api/enseignants', filters);
  }

  async getEnseignant(id) {
    return this.get(`/api/enseignants/${id}`);
  }

  async createEnseignant(data) {
    return this.post('/api/enseignants', data);
  }

  async updateEnseignant(id, data) {
    return this.put(`/api/enseignants/${id}`, data);
  }

  async deleteEnseignant(id) {
    return this.delete(`/api/enseignants/${id}`);
  }

  // ── QR Codes ──────────────────────────────────────────────
  async getQRCode(id) {
    return this.get(`/api/enseignants/${id}/qr`);
  }

  async regenerateQR(id) {
    return this.post(`/api/enseignants/${id}/qr`);
  }

  async exportQRPDF() {
    return this._downloadBlob('/api/enseignants/qr/export', 'qr_codes_enseignants.pdf');
  }

  async exportQRZip() {
    return this._downloadBlob('/api/enseignants/qr/zip', 'qr_codes_enseignants.zip');
  }

  // ── Séances ───────────────────────────────────────────────
  async getSeances(filters = {}) {
    return this.get('/api/seances', filters);
  }

  async createSeance(data) {
    return this.post('/api/seances', data);
  }

  async updateSeance(id, data) {
    return this.put(`/api/seances/${id}`, data);
  }

  async deleteSeance(id) {
    return this.delete(`/api/seances/${id}`);
  }

  // ── Présences ─────────────────────────────────────────────
  async scanQR(qrData, seanceId, mode) {
    return this.post('/api/presences/scan', {
      qr_data: qrData,
      seance_id: seanceId,
      mode: mode,
    });
  }

  /**
   * Scanner un QR code depuis une image (base64) — décodage côté serveur via OpenCV Python
   * @param {string} imageBase64  — Data URI ou base64 brut (JPEG/PNG)
   * @param {number|null} seanceId
   */
  async scanImageQR(imageBase64, seanceId = null) {
    return this.post('/api/presences/scan_image', {
      image_base64: imageBase64,
      seance_id: seanceId,
    });
  }

  async scanCamera(imageBlob, seanceId) {
    const fd = new FormData();
    fd.append('image', imageBlob, 'frame.jpg');
    fd.append('seance_id', seanceId);
    return this.post('/api/presences/camera', fd);
  }

  async enregistrerManuel(data) {
    return this.post('/api/presences/manuel', data);
  }

  async getPresences(filters = {}) {
    return this.get('/api/presences', filters);
  }

  async getPresencesStats() {
    return this.get('/api/presences/stats');
  }

  // ── Rapport ───────────────────────────────────────────────
  async getRapport(filters = {}) {
    return this.get('/api/rapport', filters);
  }

  async downloadPDF(filters = {}) {
    const keys = Object.keys(filters).filter(
      (k) => filters[k] !== null && filters[k] !== undefined && filters[k] !== ''
    );
    let path = '/api/rapport/pdf';
    if (keys.length > 0) {
      const qs = keys.map((k) => `${encodeURIComponent(k)}=${encodeURIComponent(filters[k])}`).join('&');
      path = `${path}?${qs}`;
    }
    return this._downloadBlob(path, 'rapport_presences.pdf');
  }

  async downloadCSV(filters = {}) {
    const keys = Object.keys(filters).filter(
      (k) => filters[k] !== null && filters[k] !== undefined && filters[k] !== ''
    );
    let path = '/api/rapport/csv';
    if (keys.length > 0) {
      const qs = keys.map((k) => `${encodeURIComponent(k)}=${encodeURIComponent(filters[k])}`).join('&');
      path = `${path}?${qs}`;
    }
    return this._downloadBlob(path, 'rapport_presences.csv');
  }

  // ── Dashboard ─────────────────────────────────────────────
  async getDashboardStats() {
    return this.get('/api/dashboard/stats');
  }

  // ── Utilitaire téléchargement blob ────────────────────────
  async _downloadBlob(url, filename) {
    let response;
    try {
      response = await fetch(this.baseURL + url, { credentials: 'include' });
    } catch (err) {
      throw new Error('Erreur réseau lors du téléchargement : ' + err.message);
    }
    if (!response.ok) throw new Error(`Erreur HTTP ${response.status} lors du téléchargement`);
    const blob = await response.blob();
    const objectURL = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = objectURL;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
      document.body.removeChild(a);
      URL.revokeObjectURL(objectURL);
    }, 200);
  }
}

// Instance globale
const api = new ApiClient();

// ─────────────────────────────────────────────
// TOAST NOTIFICATIONS
// ─────────────────────────────────────────────
/**
 * Afficher une notification toast
 * @param {string} message
 * @param {'success'|'error'|'info'|'warning'} type
 * @param {number} duration  ms avant fermeture auto
 */
function showToast(message, type = 'success', duration = 4000) {
  // Créer ou récupérer le conteneur
  let container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    container.setAttribute('aria-live', 'polite');
    container.setAttribute('aria-atomic', 'false');
    document.body.appendChild(container);
  }

  // Icônes selon le type
  const icons = {
    success: `<svg viewBox="0 0 20 20" fill="currentColor" width="20" height="20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/></svg>`,
    error:   `<svg viewBox="0 0 20 20" fill="currentColor" width="20" height="20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"/></svg>`,
    warning: `<svg viewBox="0 0 20 20" fill="currentColor" width="20" height="20"><path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/></svg>`,
    info:    `<svg viewBox="0 0 20 20" fill="currentColor" width="20" height="20"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"/></svg>`,
  };

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.setAttribute('role', 'alert');
  toast.innerHTML = `
    <span class="toast-icon">${icons[type] || icons.info}</span>
    <span class="toast-message">${message}</span>
    <button class="toast-close" aria-label="Fermer">
      <svg viewBox="0 0 20 20" fill="currentColor" width="16" height="16">
        <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"/>
      </svg>
    </button>
  `;

  container.appendChild(toast);

  // Fermeture manuelle
  toast.querySelector('.toast-close').addEventListener('click', () => dismissToast(toast));

  // Fermeture automatique
  const timer = setTimeout(() => dismissToast(toast), duration);

  // Stopper le timer au survol
  toast.addEventListener('mouseenter', () => clearTimeout(timer));
  toast.addEventListener('mouseleave', () => {
    setTimeout(() => dismissToast(toast), 1500);
  });
}

function dismissToast(toast) {
  if (!toast || toast.classList.contains('dismissing')) return;
  toast.classList.add('dismissing');
  toast.addEventListener('animationend', () => toast.remove(), { once: true });
  // Fallback si animationend ne se déclenche pas
  setTimeout(() => { if (toast.parentNode) toast.remove(); }, 400);
}

// ─────────────────────────────────────────────
// SPINNER (loading overlay)
// ─────────────────────────────────────────────
/**
 * Afficher un spinner dans l'élément ciblé
 * @param {string|HTMLElement} selector  sélecteur CSS ou élément DOM
 */
function showSpinner(selector) {
  const el = typeof selector === 'string' ? document.querySelector(selector) : selector;
  if (!el) return;

  // Ne pas dupliquer
  if (el.querySelector('.spinner-overlay')) return;

  const overlay = document.createElement('div');
  overlay.className = 'spinner-overlay';
  overlay.innerHTML = `
    <div class="spinner" role="status" aria-label="Chargement en cours">
      <svg viewBox="0 0 50 50" width="40" height="40">
        <circle cx="25" cy="25" r="20" fill="none" stroke-width="4"
          stroke="currentColor" stroke-dasharray="80 20"
          stroke-linecap="round"/>
      </svg>
    </div>
  `;

  // Position relative sur le parent si nécessaire
  const pos = getComputedStyle(el).position;
  if (pos === 'static') el.style.position = 'relative';

  el.appendChild(overlay);
}

/**
 * Masquer le spinner dans l'élément ciblé
 * @param {string|HTMLElement} selector
 */
function hideSpinner(selector) {
  const el = typeof selector === 'string' ? document.querySelector(selector) : selector;
  if (!el) return;
  const overlay = el.querySelector('.spinner-overlay');
  if (overlay) overlay.remove();
}

// ─────────────────────────────────────────────
// FONCTIONS UTILITAIRES DATE / HEURE
// ─────────────────────────────────────────────
/**
 * Formater une date ISO ou YYYY-MM-DD → JJ/MM/AAAA
 * @param {string} dateStr
 * @returns {string}
 */
function formatDate(dateStr) {
  if (!dateStr) return '—';
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    const day   = String(d.getDate()).padStart(2, '0');
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const year  = d.getFullYear();
    return `${day}/${month}/${year}`;
  } catch (_) {
    return dateStr;
  }
}

/**
 * Formater une heure HH:MM:SS ou HH:MM → HH:MM
 * @param {string} timeStr
 * @returns {string}
 */
function formatTime(timeStr) {
  if (!timeStr) return '—';
  const match = String(timeStr).match(/^(\d{2}):(\d{2})/);
  if (!match) return timeStr;
  return `${match[1]}:${match[2]}`;
}

/**
 * Formater date et heure combinées → 'JJ/MM/AAAA à HH:MM'
 * @param {string} dateStr
 * @param {string} timeStr
 * @returns {string}
 */
function formatDateTime(dateStr, timeStr) {
  const d = formatDate(dateStr);
  const t = formatTime(timeStr);
  if (d === '—' && t === '—') return '—';
  if (d === '—') return t;
  if (t === '—') return d;
  return `${d} à ${t}`;
}

/**
 * Obtenir la date d'aujourd'hui au format YYYY-MM-DD
 * @returns {string}
 */
function todayISO() {
  const d = new Date();
  const yyyy = d.getFullYear();
  const mm   = String(d.getMonth() + 1).padStart(2, '0');
  const dd   = String(d.getDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
}

/**
 * Débounce : retarder l'appel d'une fonction
 * @param {Function} fn
 * @param {number}   delay  ms
 * @returns {Function}
 */
function debounce(fn, delay = 300) {
  let timer;
  return function (...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), delay);
  };
}
