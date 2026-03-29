# ============================================================
#  UniPresence Pro — IUE Douala
#  Fichier de configuration centrale
#  Toutes les valeurs peuvent être surchargées par variables
#  d'environnement pour le déploiement en production.
# ============================================================

import os

# ------------------------------------------------------------
# Base de données SQLite (fichier local, zéro installation)
# ------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)
SQLITE_DB_PATH = os.path.join(DATA_DIR, 'unipresencepro.db')

# ------------------------------------------------------------
# Serveur HTTP
# ------------------------------------------------------------
SERVER_HOST = '0.0.0.0'
SERVER_PORT = int(os.environ.get('PORT', 5000))

# ------------------------------------------------------------
# Sécurité
# ------------------------------------------------------------
SESSION_SECRET        = os.environ.get(
    'SESSION_SECRET',
    'iue_unipresence_session_key_2024_douala_cm'
)
BCRYPT_COST           = 12
SESSION_DURATION_HOURS = 8

# Limitation des tentatives de connexion
MAX_LOGIN_ATTEMPTS   = 5
LOGIN_BLOCK_MINUTES  = 10

# ------------------------------------------------------------
# Chemins du projet
# ------------------------------------------------------------
# BASE_DIR est déjà défini dans la section SQLite ci-dessus.

# Répertoire racine du projet  →  merveillebrenda/
ROOT_DIR     = os.path.dirname(BASE_DIR)

# Répertoire frontend  →  merveillebrenda/frontend/
FRONTEND_DIR = os.path.join(ROOT_DIR, 'frontend')

# Répertoires images
IMAGE_DIR    = os.path.join(BASE_DIR, 'image')
QR_DIR       = os.path.join(IMAGE_DIR, 'qr')

# Créer les dossiers s'ils n'existent pas encore
os.makedirs(QR_DIR, exist_ok=True)

# ------------------------------------------------------------
# Upload de fichiers
# ------------------------------------------------------------
MAX_FILE_SIZE         = 5 * 1024 * 1024   # 5 Mo
ALLOWED_IMAGE_TYPES   = [
    'image/jpeg',
    'image/png',
    'image/gif',
    'image/webp',
]
ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}

# ------------------------------------------------------------
# QR Code
# ------------------------------------------------------------
QR_VERSION        = 1
QR_BOX_SIZE       = 10
QR_BORDER         = 4
QR_IMAGE_SIZE     = 500     # pixels (largeur = hauteur)

# ------------------------------------------------------------
# Export PDF
# ------------------------------------------------------------
PDF_COMPANY_NAME  = 'IUE Douala'
PDF_APP_NAME      = 'UniPresence Pro'
PDF_WATERMARK     = 'IUE — CONFIDENTIEL'

# ------------------------------------------------------------
# CORS (pour le développement frontal)
# ------------------------------------------------------------
CORS_ALLOWED_ORIGINS = '*'
CORS_ALLOWED_METHODS = 'GET, POST, PUT, DELETE, OPTIONS'
CORS_ALLOWED_HEADERS = 'Content-Type, Authorization, Cookie'

# ------------------------------------------------------------
# Pointage — règles métier
# ------------------------------------------------------------
ANTI_DOUBLON_MINUTES  = 15    # délai minimal entre deux pointages
RETARD_MAX_MINUTES    = 30    # au-delà → statut ABSENT

# ------------------------------------------------------------
# Numérotation des matricules
# Exemple : IUE-2024-0001
# ------------------------------------------------------------
MATRICULE_PREFIX      = 'IUE'
