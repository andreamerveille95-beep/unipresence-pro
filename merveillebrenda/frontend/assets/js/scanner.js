// scanner.js — Kiosque QR UniPresence Pro
// Algorithme de scan : frames caméra → Python/OpenCV côté serveur
// Zéro dépendance JavaScript externe pour la détection QR

'use strict';

// ─── CONSTANTES ────────────────────────────────────────────────────
const FRAME_MIN_MS   = 300;   // délai minimum entre deux envois (ms)
const OVERLAY_DELAY  = 4500;  // ms d'affichage du résultat
const FRAME_WIDTH    = 640;   // résolution de capture — 640px pour détecter les QR à distance
const JPEG_QUALITY   = 0.82;  // qualité JPEG — bon compromis taille/fidélité modules QR

// ─── ÉTAT ──────────────────────────────────────────────────────────
let cameraStream = null;
let scanRafId    = null;     // ID du requestAnimationFrame courant
let isSending    = false;    // verrou : on n'envoie pas deux frames en même temps
let overlayTimer = null;
let paused       = false;    // true pendant l'affichage de l'overlay

// ─── INIT ──────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {

  // Vérifier contexte sécurisé (HTTPS ou localhost)
  if (!window.isSecureContext) {
    _placeholderError(
      'HTTPS requis pour accéder à la caméra.',
      'Ouvrez la page via https:// ou via localhost.'
    );
    setStatus('error', 'Contexte non sécurisé — caméra indisponible');
    return;
  }

  // Vérifier API disponible
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    _placeholderError(
      'Caméra non supportée',
      'Utilisez Chrome, Firefox ou Edge récent.'
    );
    setStatus('error', 'getUserMedia non supporté par ce navigateur');
    return;
  }

  startCamera();
});

// ─── CAMÉRA ────────────────────────────────────────────────────────
async function startCamera() {
  const video = document.getElementById('camera-feed');
  if (!video) return;

  setStatus('loading', 'Démarrage de la caméra…');

  try {
    cameraStream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: { ideal: 'environment' }, // caméra arrière sur mobile
        width:  { ideal: 1280 },
        height: { ideal: 720 },
      },
    });

    video.srcObject = cameraStream;
    await video.play();

    // Masquer le placeholder dès que la caméra démarre
    const ph = document.getElementById('cam-placeholder');
    if (ph) ph.style.display = 'none';

    setStatus('active', 'Caméra active — pointage Python/OpenCV en cours');
    _setScanActivity('active');

    // Lancer la boucle de scan dès que la vidéo a ses métadonnées
    video.addEventListener('loadedmetadata', () => _demarrerBoucle(video), { once: true });
    if (video.readyState >= HTMLMediaElement.HAVE_METADATA) _demarrerBoucle(video);

  } catch (err) {
    const msgs = {
      NotAllowedError:  'Permission caméra refusée — autorisez la caméra dans le navigateur.',
      NotFoundError:    'Aucune caméra détectée sur cet appareil.',
      NotReadableError: 'Caméra déjà utilisée par une autre application.',
    };
    const msg = msgs[err.name] || ('Erreur caméra : ' + err.message);
    _placeholderError('Caméra inaccessible', msg);
    setStatus('error', msg);
  }
}

// ─── BOUCLE D'ENVOI DE FRAMES (requestAnimationFrame + throttle) ───
// Même principe que Django : on s'accroche au rythme du navigateur (60fps)
// mais on n'envoie réellement une frame que si FRAME_MIN_MS est écoulé.
// Résultat : réactivité de rAF + économie réseau du throttle.
let _lastSentTs = 0;

function _demarrerBoucle(video) {
  // Annuler toute boucle précédente proprement
  if (scanRafId) { cancelAnimationFrame(scanRafId); scanRafId = null; }

  const canvas = document.getElementById('scan-canvas');
  const ctx    = canvas ? canvas.getContext('2d') : null;
  if (!canvas || !ctx) return;

  function _tick(ts) {
    // Reprogrammer immédiatement pour garder la boucle vivante
    scanRafId = requestAnimationFrame(_tick);

    // Conditions de blocage : on saute cette frame
    if (isSending || paused || !cameraStream) return;
    if (video.readyState < HTMLMediaElement.HAVE_ENOUGH_DATA) return;
    if (!video.videoWidth || !video.videoHeight) return;

    // Throttle : on n'envoie au serveur que toutes les FRAME_MIN_MS ms
    if (ts - _lastSentTs < FRAME_MIN_MS) return;
    _lastSentTs = ts;

    // ── Capturer la frame à FRAME_WIDTH (400px) ────────────────────
    const ratio = video.videoHeight / video.videoWidth;
    canvas.width  = FRAME_WIDTH;
    canvas.height = Math.round(FRAME_WIDTH * ratio);
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    // Convertir en JPEG léger (~12KB)
    const frameB64 = canvas.toDataURL('image/jpeg', JPEG_QUALITY);

    // ── Envoyer au serveur Python ──────────────────────────────────
    _setScanActivity('frame');
    isSending = true;
    _envoyerFrame(frameB64).finally(() => { isSending = false; });
  }

  scanRafId = requestAnimationFrame(_tick);
}

// ─── ENVOI D'UNE FRAME AU SERVEUR ──────────────────────────────────
async function _envoyerFrame(frameB64) {
  let data;
  try {
    data = await api.scanImageQR(frameB64, null);
  } catch (err) {
    // Erreur réseau → log silencieux, on réessaie à la prochaine frame
    console.warn('[Scanner] Erreur réseau :', err.message);
    return;
  }

  // ── Aucun QR détecté dans la frame → continuer à scanner silencieusement
  if (!data || data.qr_detecte === false) {
    _setScanActivity('active');   // retour au pulse normal
    return;
  }

  // ── QR trouvé dans la frame : flash immédiat même avant l'overlay
  _setScanActivity('detected');

  // ── QR détecté et pointage enregistré avec succès
  if (data.succes) {
    playBeep(true);
    _afficherOverlay(true, data);
    _pauserScan(OVERLAY_DELAY + 500);
    return;
  }

  // ── QR détecté MAIS erreur métier (doublon, token invalide, désactivé…)
  playBeep(false);
  _afficherOverlay(false, data);
  _pauserScan(OVERLAY_DELAY + 500);
}

// ─── PAUSE DU SCAN (pendant affichage overlay) ──────────────────────
// La boucle rAF tourne toujours (pour garder l'animation), mais le flag
// `paused` bloque l'envoi de frames pendant toute la durée de l'overlay.
function _pauserScan(ms) {
  paused = true;
  _lastSentTs = 0;          // réinitialiser le throttle pour reprendre vite
  _setScanActivity('paused');
  if (overlayTimer) clearTimeout(overlayTimer);
  overlayTimer = setTimeout(() => {
    paused = false;
    _setScanActivity('active');
    setStatus('active', 'Présentez votre badge QR devant la caméra');
    // Masquer aussi la carte résultat Django
    const card = document.getElementById('result-card');
    if (card) card.style.display = 'none';
  }, ms);
}

// ─── INDICATEUR D'ACTIVITÉ TEMPS RÉEL ──────────────────────────────
/**
 * state : 'active' | 'frame' | 'detected' | 'paused' | 'idle'
 *   active   → caméra active, pulse lente verte
 *   frame    → flash à chaque frame envoyée au serveur
 *   detected → QR trouvé, flash fort vert + coins cadre verts
 *   paused   → overlay affiché, pulse ambre
 *   idle     → point gris (démarrage ou erreur)
 */
function _setScanActivity(state) {
  const dot   = document.getElementById('sli-dot');
  const label = document.getElementById('sli-label');
  const frame = document.querySelector('.scan-frame-box');
  const laser = document.querySelector('.scan-laser');
  if (!dot || !label) return;

  // Retirer tous les états précédents
  dot.classList.remove('sli-active', 'sli-frame', 'sli-detected', 'sli-paused');
  if (frame) frame.classList.remove('qr-found');
  if (laser) laser.classList.remove('qr-found');

  switch (state) {
    case 'active':
      dot.classList.add('sli-active');
      label.textContent = 'Recherche de QR…';
      break;

    case 'frame':
      // Flash sur la frame courante puis retour au pulse normal
      dot.classList.add('sli-active', 'sli-frame');
      label.textContent = 'Analyse en cours…';
      // Retirer sli-frame après l'animation pour retrouver le pulse normal
      setTimeout(() => dot.classList.remove('sli-frame'), 450);
      break;

    case 'detected':
      dot.classList.add('sli-detected');
      label.textContent = 'QR détecté ✓';
      if (frame) frame.classList.add('qr-found');
      if (laser) laser.classList.add('qr-found');
      break;

    case 'paused':
      dot.classList.add('sli-paused');
      label.textContent = 'Traitement…';
      break;

    default: // 'idle'
      label.textContent = 'Démarrage…';
      break;
  }
}

// ─── OVERLAY RÉSULTAT ──────────────────────────────────────────────
function _afficherOverlay(success, data) {
  const overlay = document.getElementById('result-overlay');
  if (!overlay) return;

  // ── Carte résultat Django (sous la vidéo) ──────────────────────
  const card       = document.getElementById('result-card');
  const cardHeader = document.getElementById('result-card-header');
  const cardTitle  = document.getElementById('result-card-title');
  const scanResult = document.getElementById('scan-result');

  if (card && cardHeader && cardTitle && scanResult) {
    if (success) {
      const type      = (data.type_pointage || 'ARRIVEE').toUpperCase();
      const isArrivee = type === 'ARRIVEE';
      const statut    = (data.statut || 'PRESENT').toUpperCase();
      const retard    = parseInt(data.retard || 0, 10);
      const nom       = data.enseignant || '';
      const heure     = data.heure || '';

      cardHeader.style.background = isArrivee ? 'var(--vert-presence)' : 'var(--bleu-iue)';
      cardTitle.innerHTML = `<i class="fas fa-check-circle" style="margin-right:8px;"></i>${isArrivee ? 'Arrivée enregistrée' : 'Départ enregistré'}`;

      let html = `<strong>${nom}</strong><br>
                  <span style="color:var(--text-muted)">${isArrivee ? 'Arrivée' : 'Départ'} enregistré(e) à <strong>${heure}</strong></span>`;

      if (isArrivee && statut === 'RETARD')
        html += `<div style="margin-top:8px;padding:8px 12px;border-radius:var(--radius-sm);background:var(--color-retard-bg);color:var(--color-retard);font-size:.88rem;">
                   <i class="fas fa-exclamation-triangle me-1"></i>
                   En retard de <strong>${retard} min</strong>
                 </div>`;
      else if (isArrivee && statut === 'ABSENT')
        html += `<div style="margin-top:8px;padding:8px 12px;border-radius:var(--radius-sm);background:var(--color-absent-bg);color:var(--color-absent);font-size:.88rem;">
                   <i class="fas fa-times-circle me-1"></i>Très en retard
                 </div>`;
      else if (isArrivee)
        html += `<div style="margin-top:8px;padding:8px 12px;border-radius:var(--radius-sm);background:var(--color-present-bg);color:var(--color-present);font-size:.88rem;">
                   <i class="fas fa-check me-1"></i>À l'heure ✓
                 </div>`;

      scanResult.innerHTML = html;
    } else {
      const msg       = data.message || 'Badge non reconnu';
      const isDoublon = msg.toLowerCase().includes('doublon') || msg.toLowerCase().includes('déjà');
      cardHeader.style.background = isDoublon ? 'var(--orange-retard)' : 'var(--rouge-alerte)';
      cardTitle.innerHTML = `<i class="fas fa-${isDoublon ? 'rotate-left' : 'times-circle'}" style="margin-right:8px;"></i>${isDoublon ? 'Déjà pointé' : 'Badge non reconnu'}`;
      scanResult.innerHTML = `<p style="margin-bottom:0;color:var(--text-muted);">${msg}</p>`;
    }

    card.style.display = 'block';
    card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  let html = '';

  if (success) {
    const type     = (data.type_pointage || 'ARRIVEE').toUpperCase();
    const isArrivee = type === 'ARRIVEE';
    const statut   = (data.statut || 'PRESENT').toUpperCase();
    const retard   = parseInt(data.retard || 0, 10);
    const nom      = data.enseignant || '';
    const heure    = data.heure || '';

    let cardClass = isArrivee ? 'ov-arrivee' : 'ov-depart';
    if (isArrivee && statut === 'RETARD') cardClass = 'ov-retard';
    if (isArrivee && statut === 'ABSENT') cardClass = 'ov-absent';

    const icone = isArrivee ? '✓' : '↩';
    const titre = isArrivee ? 'Bienvenue !' : 'Au revoir !';
    const msgHtml = isArrivee
      ? `Arrivée enregistrée à <strong>${heure}</strong>`
      : `Départ enregistré à <strong>${heure}</strong>`;

    let badge = '';
    if (isArrivee) {
      if (statut === 'RETARD')
        badge = `<div class="ov-badge ov-badge-retard">Retard de ${retard} min</div>`;
      else if (statut === 'ABSENT')
        badge = `<div class="ov-badge ov-badge-absent">Très en retard</div>`;
      else
        badge = `<div class="ov-badge ov-badge-present">À l'heure ✓</div>`;
    }

    html = `
      <div class="ov-card ${cardClass}">
        <div class="ov-icon">${icone}</div>
        <div class="ov-titre">${titre}</div>
        <div class="ov-nom">${nom}</div>
        <div class="ov-msg">${msgHtml}</div>
        ${badge}
        <div class="ov-progress-wrap">
          <div class="ov-progress-bar"
               style="animation: ovProgress ${OVERLAY_DELAY}ms linear forwards;"></div>
        </div>
      </div>`;
  } else {
    const msg       = data.message || 'Badge non reconnu';
    const isDoublon = msg.toLowerCase().includes('double') || msg.toLowerCase().includes('doublon');
    html = `
      <div class="ov-card ${isDoublon ? 'ov-retard' : 'ov-error'}">
        <div class="ov-icon ${isDoublon ? '' : 'ov-icon-error'}">${isDoublon ? '⟳' : '✕'}</div>
        <div class="ov-titre">${isDoublon ? 'Déjà pointé' : 'Badge non reconnu'}</div>
        <div class="ov-msg">${msg}</div>
        <div class="ov-progress-wrap">
          <div class="ov-progress-bar"
               style="animation: ovProgress ${OVERLAY_DELAY}ms linear forwards;"></div>
        </div>
      </div>`;
  }

  overlay.innerHTML = html;
  overlay.classList.add('visible');

  setTimeout(() => {
    overlay.classList.remove('visible');
    setTimeout(() => { overlay.innerHTML = ''; }, 300);
  }, OVERLAY_DELAY);
}

// ─── BARRE DE STATUT ───────────────────────────────────────────────
function setStatus(state, message) {
  const el  = document.getElementById('scanner-status-text');
  const dot = document.getElementById('status-dot');
  if (el)  el.textContent  = message;
  if (dot) {
    dot.className = 'status-dot';
    if (state === 'active')  dot.classList.add('dot-active');
    if (state === 'error')   dot.classList.add('dot-error');
    if (state === 'loading') dot.classList.add('dot-loading');
  }
}

// ─── PLACEHOLDER D'ERREUR ──────────────────────────────────────────
function _placeholderError(titre, detail) {
  const ph = document.getElementById('cam-placeholder');
  if (!ph) return;
  ph.querySelector('.cam-placeholder-icon').innerHTML = `
    <svg width="56" height="56" viewBox="0 0 24 24" fill="none"
         stroke="#DC2626" stroke-width="1.5">
      <circle cx="12" cy="12" r="10"/>
      <line x1="12" y1="8" x2="12" y2="13"/>
      <line x1="12" y1="17" x2="12.01" y2="17"/>
    </svg>`;
  const txt = ph.querySelector('.cam-placeholder-text');
  if (txt) txt.innerHTML =
    `<strong style="color:#DC2626;">${titre}</strong><br>
     <span style="font-size:.82rem;opacity:.8;">${detail}</span>`;
}

// ─── BIP SONORE ────────────────────────────────────────────────────
function playBeep(success) {
  try {
    const ctx  = new (window.AudioContext || window.webkitAudioContext)();
    const osc  = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.type = 'sine';
    osc.frequency.setValueAtTime(success ? 880 : 300, ctx.currentTime);
    gain.gain.setValueAtTime(0.3, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.2);
    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + 0.2);
    osc.onended = () => ctx.close();
  } catch (_) {}
}
