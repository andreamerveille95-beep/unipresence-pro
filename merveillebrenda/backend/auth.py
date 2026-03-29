# ============================================================
#  UniPresence Pro — IUE Douala
#  Module d'authentification : sessions + bcrypt + rate-limit
# ============================================================

import uuid
import logging
import threading
from datetime import datetime, timedelta, timezone

try:
    import bcrypt
except ImportError:
    raise ImportError(
        "Le module bcrypt est requis. "
        "Installez-le avec : pip install bcrypt"
    )

from config import (
    BCRYPT_COST,
    SESSION_DURATION_HOURS,
    MAX_LOGIN_ATTEMPTS,
    LOGIN_BLOCK_MINUTES,
)

# ------------------------------------------------------------
# Logger
# ------------------------------------------------------------
logger = logging.getLogger('auth')

# ------------------------------------------------------------
# Stockage en mémoire (thread-safe via Lock)
# ------------------------------------------------------------

# { token: { admin_id, email, nom, expires_at (datetime), ip } }
SESSIONS: dict = {}
_sessions_lock = threading.Lock()

# { ip: { count: int, first_attempt: datetime, blocked_until: datetime|None } }
LOGIN_ATTEMPTS: dict = {}
_attempts_lock = threading.Lock()


# ============================================================
#  Hachage mot de passe
# ============================================================

def hash_password(password: str) -> str:
    """
    Hache un mot de passe en clair avec bcrypt.

    Parameters
    ----------
    password : str

    Returns
    -------
    str
        Hachage bcrypt (préfixe $2b$…).
    """
    salt   = bcrypt.gensalt(rounds=BCRYPT_COST)
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(password: str, hashed: str) -> bool:
    """
    Vérifie qu'un mot de passe en clair correspond à son hachage bcrypt.

    Parameters
    ----------
    password : str  — Mot de passe à tester.
    hashed   : str  — Hachage stocké en base.

    Returns
    -------
    bool
    """
    try:
        return bcrypt.checkpw(
            password.encode('utf-8'),
            hashed.encode('utf-8')
        )
    except Exception as exc:
        logger.error("verify_password erreur : %s", exc)
        return False


# ============================================================
#  Gestion des sessions
# ============================================================

def _now_utc() -> datetime:
    """Retourne l'heure UTC actuelle avec timezone."""
    return datetime.now(timezone.utc)


def _purge_expired_sessions():
    """Supprime les sessions expirées du dictionnaire en mémoire."""
    now = _now_utc()
    expired = [t for t, s in SESSIONS.items() if s['expires_at'] <= now]
    for t in expired:
        SESSIONS.pop(t, None)
    if expired:
        logger.debug("Purge : %d session(s) expirée(s) supprimée(s).", len(expired))


def create_session(admin_id: int, email: str, nom: str, ip: str) -> str:
    """
    Crée une nouvelle session authentifiée pour un administrateur.

    Parameters
    ----------
    admin_id : int
    email    : str
    nom      : str
    ip       : str  — Adresse IP du client.

    Returns
    -------
    str
        Token de session (UUID4 hexadécimal).
    """
    token      = str(uuid.uuid4())
    expires_at = _now_utc() + timedelta(hours=SESSION_DURATION_HOURS)

    with _sessions_lock:
        _purge_expired_sessions()
        SESSIONS[token] = {
            'admin_id':  admin_id,
            'email':     email,
            'nom':       nom,
            'expires_at': expires_at,
            'ip':        ip,
            'created_at': _now_utc(),
        }

    logger.info(
        "Session créée pour admin_id=%s email=%s depuis ip=%s (expire %s)",
        admin_id, email, ip,
        expires_at.strftime('%Y-%m-%d %H:%M:%S UTC')
    )
    return token


def get_session(token: str):
    """
    Récupère une session valide (non expirée).
    Vérifie d'abord le cache mémoire, puis la base de données
    (permet la persistance des sessions après redémarrage du serveur).

    Parameters
    ----------
    token : str

    Returns
    -------
    dict | None
        Données de la session, ou None si absente / expirée.
    """
    if not token:
        return None

    # 1. Vérifier le cache mémoire
    with _sessions_lock:
        session = SESSIONS.get(token)
        if session is not None:
            if session['expires_at'] <= _now_utc():
                SESSIONS.pop(token, None)
                logger.debug("Session expirée supprimée (token=%.8s…).", token)
                return None
            return dict(session)   # copie défensive

    # 2. Fallback : chercher en base de données (après redémarrage serveur)
    try:
        from database import DatabaseHelper
        db = DatabaseHelper()
        row = db.fetch_one(
            """SELECT sa.token, sa.admin_id, sa.expires_at, sa.adresse_ip,
                      a.email, a.nom, a.prenom
               FROM sessions_admin sa
               JOIN admins a ON a.id = sa.admin_id
               WHERE sa.token = %s""",
            (token,)
        )
        if row is None:
            return None

        # Analyser la date d'expiration stockée en base
        expires_raw = row.get('expires_at', '')
        try:
            expires_at = datetime.strptime(
                str(expires_raw)[:19], '%Y-%m-%d %H:%M:%S'
            ).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            return None

        if expires_at <= _now_utc():
            logger.debug("Session DB expirée (token=%.8s…).", token)
            return None

        # Reconstruire la session en mémoire pour les prochains appels
        session_data = {
            'admin_id':   row['admin_id'],
            'email':      row.get('email', ''),
            'nom':        row.get('nom', ''),
            'prenom':     row.get('prenom', ''),
            'expires_at': expires_at,
            'ip':         row.get('adresse_ip', ''),
            'created_at': _now_utc(),
        }
        with _sessions_lock:
            SESSIONS[token] = session_data
        logger.info(
            "Session restaurée depuis DB pour admin_id=%s (token=%.8s…).",
            row['admin_id'], token
        )
        return dict(session_data)

    except Exception as exc:
        logger.error("get_session DB fallback erreur : %s", exc)
        return None


def delete_session(token: str) -> None:
    """
    Invalide une session (déconnexion).

    Parameters
    ----------
    token : str
    """
    if not token:
        return
    with _sessions_lock:
        removed = SESSIONS.pop(token, None)
    if removed:
        logger.info(
            "Session supprimée pour admin_id=%s (token=%.8s…).",
            removed.get('admin_id'), token
        )


def list_active_sessions() -> list:
    """Retourne la liste de toutes les sessions actives (pour debug)."""
    now = _now_utc()
    with _sessions_lock:
        return [
            {**s, 'token': t}
            for t, s in SESSIONS.items()
            if s['expires_at'] > now
        ]


# ============================================================
#  Rate Limiting (anti-brute-force)
# ============================================================

def check_rate_limit(ip: str) -> bool:
    """
    Vérifie si une IP est autorisée à tenter une connexion.

    Returns
    -------
    bool
        True  → connexion autorisée.
        False → IP bloquée (trop de tentatives).
    """
    now = _now_utc()

    with _attempts_lock:
        record = LOGIN_ATTEMPTS.get(ip)

        if record is None:
            return True  # première tentative

        # Vérifier si le blocage a expiré
        blocked_until = record.get('blocked_until')
        if blocked_until and now >= blocked_until:
            # Réinitialiser après expiration du blocage
            LOGIN_ATTEMPTS.pop(ip, None)
            return True

        # Bloqué
        if blocked_until and now < blocked_until:
            remaining = int((blocked_until - now).total_seconds() / 60)
            logger.warning(
                "IP %s bloquée — encore %d min avant déblocage.", ip, remaining
            )
            return False

        # Vérifier le nombre de tentatives
        if record['count'] >= MAX_LOGIN_ATTEMPTS:
            # Appliquer le blocage
            record['blocked_until'] = now + timedelta(minutes=LOGIN_BLOCK_MINUTES)
            logger.warning(
                "IP %s bloquée pour %d min après %d tentatives.",
                ip, LOGIN_BLOCK_MINUTES, record['count']
            )
            return False

        return True


def record_failed_attempt(ip: str) -> None:
    """
    Enregistre une tentative de connexion échouée pour une IP.

    Parameters
    ----------
    ip : str
    """
    now = _now_utc()

    with _attempts_lock:
        record = LOGIN_ATTEMPTS.get(ip)

        if record is None:
            LOGIN_ATTEMPTS[ip] = {
                'count':         1,
                'first_attempt': now,
                'blocked_until': None,
            }
        else:
            record['count'] += 1
            # Fenêtre glissante : si la première tentative est vieille,
            # remettre à zéro
            age = (now - record['first_attempt']).total_seconds() / 60
            if age > LOGIN_BLOCK_MINUTES and record.get('blocked_until') is None:
                record['count']         = 1
                record['first_attempt'] = now
            elif record['count'] >= MAX_LOGIN_ATTEMPTS and not record.get('blocked_until'):
                record['blocked_until'] = now + timedelta(minutes=LOGIN_BLOCK_MINUTES)

        logger.info(
            "Tentative échouée depuis ip=%s (count=%d).",
            ip, LOGIN_ATTEMPTS[ip]['count']
        )


def reset_attempts(ip: str) -> None:
    """
    Réinitialise le compteur de tentatives pour une IP (après succès).

    Parameters
    ----------
    ip : str
    """
    with _attempts_lock:
        if ip in LOGIN_ATTEMPTS:
            LOGIN_ATTEMPTS.pop(ip)
            logger.debug("Compteur réinitialisé pour ip=%s.", ip)


# ============================================================
#  Helpers pour le handler HTTP
# ============================================================

def get_token_from_request(handler) -> str | None:
    """
    Extrait le token de session depuis le cookie ``session_token``.

    Parameters
    ----------
    handler : BaseHTTPRequestHandler (ou sous-classe)

    Returns
    -------
    str | None
    """
    cookie_header = handler.headers.get('Cookie', '')
    if not cookie_header:
        return None

    for part in cookie_header.split(';'):
        part = part.strip()
        if part.startswith('session_token='):
            token = part[len('session_token='):].strip()
            return token if token else None

    return None


def require_auth(handler):
    """
    Vérifie l'authentification d'une requête HTTP.

    Lit le cookie ``session_token``, valide la session et la retourne.
    Si la session est absente ou expirée, retourne None.

    Parameters
    ----------
    handler : BaseHTTPRequestHandler (ou sous-classe)

    Returns
    -------
    dict | None
        Données de la session si authentifié, None sinon.
    """
    token = get_token_from_request(handler)
    if not token:
        return None
    session = get_session(token)
    if session is None:
        logger.debug(
            "require_auth : session invalide ou expirée "
            "(token=%.8s… ip=%s).",
            token, handler.client_address[0] if handler.client_address else '?'
        )
    return session
