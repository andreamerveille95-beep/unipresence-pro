# UniPresence Pro

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-3-003B57?style=flat-square&logo=sqlite&logoColor=white)
![OpenCV](https://img.shields.io/badge/OpenCV-4.x-5C3EE8?style=flat-square&logo=opencv&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-ES6%2B-F7DF1E?style=flat-square&logo=javascript&logoColor=black)
![License](https://img.shields.io/badge/Licence-MIT-16A34A?style=flat-square)

**Système de gestion des présences des enseignants par QR Code**
Institut Universitaire de l'Entrepreneuriat (IUE) — Douala, Cameroun

</div>

---

## Présentation

**UniPresence Pro** est une application web complète de suivi des présences, conçue sur mesure pour l'IUE Douala.
Elle couvre la gestion des enseignants, la génération de QR codes, le scanner en temps réel (via caméra), la planification des séances et l'export de rapports PDF/CSV.

**Zéro framework** — serveur HTTP natif Python, base SQLite embarquée, frontend 100 % Vanilla JS.

---

## Fonctionnalités

| Domaine | Détail |
|---|---|
| **Enseignants** | Création, modification, désactivation — matricule automatique `IUE-YYYY-NNNN` |
| **QR Codes** | Génération automatique, régénération, export PDF groupé et ZIP |
| **Scanner** | Lecture QR via caméra — décodage OpenCV côté serveur (aucune lib JS externe) |
| **Séances** | Création et suivi des séances CM / TD / TP / Examens |
| **Pointage** | Détection ARRIVÉE / DÉPART, calcul du retard, anti-doublon (15 min) |
| **Rapports** | Filtres multi-critères, export PDF (ReportLab) et CSV compatible Excel |
| **Tableau de bord** | KPIs, graphiques SVG, derniers pointages, séances du jour |
| **Authentification** | Sessions cookie HttpOnly, bcrypt cost 12, rate limiting (5 essais / 10 min) |
| **Interface** | Mode sombre / clair (préférence système), responsive mobile / tablette / bureau |

---

## Stack technique

| Couche | Technologie |
|---|---|
| Serveur | Python 3.10+ `http.server` — stdlib, aucun framework |
| Base de données | SQLite 3 via `sqlite3` — intégré Python, mode WAL, zéro installation |
| Authentification | Sessions UUID4 · bcrypt cost 12 · Cookies HttpOnly |
| QR — génération | `qrcode[pil]` + Pillow |
| QR — lecture | OpenCV `cv2.QRCodeDetector` — côté serveur Python |
| Export PDF | ReportLab 4.x |
| Frontend | HTML5 · CSS3 Variables · JavaScript ES6+ Vanilla — zéro framework |
| Typographie | Playfair Display · DM Sans · JetBrains Mono |
| Icônes | Font Awesome 6.5 |

---

## Structure du projet

```
merveillebrenda/
│
├── demarrer.bat                  ← Lancement rapide Windows (double-clic)
├── requirements.txt              ← Dépendances Python
├── README.md
│
├── backend/
│   ├── server.py                 ← Point d'entrée — routes HTTP, dispatch GET/POST
│   ├── config.py                 ← Configuration centralisée (ports, chemins, règles métier)
│   ├── database.py               ← Helper SQLite — fetch_one / fetch_all / insert / update
│   ├── auth.py                   ← Sessions UUID4, bcrypt, rate limiting
│   ├── presence_handler.py       ← Logique métier : pointage, scan QR, stats, rapports
│   ├── qr_generator.py           ← Génération QR (qrcode + Pillow)
│   ├── pdf_exporter.py           ← Export PDF (ReportLab)
│   ├── database.sql              ← Schéma SQLite complet (tables + données démo)
│   ├── data/
│   │   └── unipresencepro.db     ← Base SQLite (créée automatiquement au 1er lancement)
│   └── image/
│       └── qr/                   ← QR codes générés (PNG, un par enseignant)
│
└── frontend/
    ├── index.html                ← Page d'accueil publique
    ├── connexion.html            ← Formulaire de connexion
    ├── dashboard.html            ← Tableau de bord (KPIs, graphiques, séances du jour)
    ├── professeurs.html          ← Gestion des enseignants (liste, création, QR)
    ├── formulaire.html           ← Formulaire d'inscription enseignant
    ├── seances.html              ← Planning des séances
    ├── scanner.html              ← Kiosque scanner QR (caméra → OpenCV)
    ├── rapport.html              ← Rapports de présences (filtres, export)
    ├── qr_codes.html             ← Galerie QR codes (visualisation, téléchargement)
    ├── a_propos.html             ← À propos du projet
    └── assets/
        ├── css/
        │   ├── variables.css     ← Variables CSS (couleurs, typographie, thème)
        │   ├── base.css          ← Reset, layout global, mode sombre
        │   ├── navbar.css        ← Barre de navigation
        │   ├── dashboard.css     ← Styles tableau de bord
        │   ├── scanner.css       ← Styles kiosque scanner
        │   ├── forms.css         ← Formulaires et modales
        │   ├── tables.css        ← Tableaux de données
        │   ├── qr_codes.css      ← Galerie QR
        │   └── animations.css    ← Animations et transitions
        ├── js/
        │   ├── api.js            ← Client HTTP — toutes les requêtes vers le backend
        │   ├── theme.js          ← Basculement mode sombre / clair
        │   ├── scanner.js        ← Boucle caméra → frame JPEG → OpenCV
        │   ├── dashboard.js      ← Graphiques SVG, KPIs, séances du jour
        │   ├── professeurs.js    ← Gestion enseignants (CRUD, pagination)
        │   ├── qr_codes.js       ← Galerie QR, régénération, export
        │   ├── rapport.js        ← Filtres rapport, export PDF/CSV
        │   └── animations.js     ← Animations d'interface
        └── images/
            ├── logo-iue.png
            ├── logo-iue.webp
            ├── logo-iue.svg
            └── logo-iue.ico
```

---

## Prérequis

| Outil | Version minimale |
|---|---|
| Python | 3.10+ |
| pip | inclus avec Python |
| Navigateur | Chrome / Firefox / Edge — API caméra requise pour le scanner |

> SQLite est **intégré dans Python** — aucune installation de base de données externe nécessaire.

---

## Installation

### 1. Cloner / placer le projet

```bash
cd D:\RYDI_Group\IUE\merveillebrenda
```

### 2. Créer l'environnement virtuel

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 3. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 4. Lancer le serveur

**Windows — double-clic (recommandé)**
> Double-cliquer sur `demarrer.bat` à la racine du projet.
> Une fenêtre de terminal s'ouvre — **ne pas la fermer** pendant que l'application tourne.

**Windows / Linux / macOS — terminal**
```bash
# depuis la racine du projet
python backend/server.py
```

Ouvrir le navigateur : **[http://localhost:5000](http://localhost:5000)**

---

## Compte administrateur par défaut

| Champ | Valeur |
|---|---|
| Email | `admin@iue.cm` |
| Mot de passe | `admin123` |

> **Important :** modifiez ce mot de passe après la première connexion.

---

## Comment fonctionne le scan QR

```
Caméra navigateur
      │
      │  frame JPEG 400 px  (toutes les 350 ms)
      │  encodée base64  →  POST /api/presences/scan_image
      ▼
Python / OpenCV  (serveur)
      │  cv2.QRCodeDetector().detectAndDecode()
      │  Fallback 1 : niveaux de gris + equalizeHist
      │  Fallback 2 : redimensionnement si image > 1200 px
      ▼
Logique métier  (presence_handler.py)
      │  Validation token QR + anti-doublon 15 min
      │  Détermination ARRIVÉE / DÉPART
      │  Calcul retard / statut (PRESENT · RETARD · ABSENT)
      ▼
Réponse JSON  →  overlay résultat + bip sonore navigateur
```

> Toute la détection QR se fait **côté serveur Python** via OpenCV — aucune librairie JavaScript de scan n'est requise.

---

## Routes API

| Méthode | Route | Description | Auth |
|---|---|---|---|
| `POST` | `/api/login` | Authentification | — |
| `POST` | `/api/logout` | Déconnexion | ✓ |
| `GET` | `/api/me` | Session courante | ✓ |
| `GET` | `/api/enseignants` | Liste enseignants | ✓ |
| `POST` | `/api/enseignants` | Créer enseignant | ✓ |
| `GET` | `/api/enseignants/:id` | Détail enseignant | ✓ |
| `PUT` | `/api/enseignants/:id` | Modifier enseignant | ✓ |
| `DELETE` | `/api/enseignants/:id` | Désactiver enseignant | ✓ |
| `GET` | `/api/enseignants/:id/qr` | QR code base64 | ✓ |
| `POST` | `/api/enseignants/:id/qr` | Régénérer QR | ✓ |
| `GET` | `/api/enseignants/qr/export` | Export PDF tous QR | ✓ |
| `GET` | `/api/enseignants/qr/zip` | Export ZIP tous QR | ✓ |
| `GET` | `/api/seances` | Liste séances | ✓ |
| `POST` | `/api/seances` | Créer séance | ✓ |
| `GET` | `/api/seances/:id` | Détail séance | ✓ |
| `PUT` | `/api/seances/:id` | Modifier séance | ✓ |
| `DELETE` | `/api/seances/:id` | Supprimer séance | ✓ |
| `GET` | `/api/presences` | Liste présences (filtres + pages) | ✓ |
| `POST` | `/api/presences/scan` | Scan QR texte | — |
| `POST` | `/api/presences/scan_image` | **Scan QR via image OpenCV** | — |
| `POST` | `/api/presences/manuel` | Pointage manuel | ✓ |
| `GET` | `/api/presences/stats` | Stats présences | ✓ |
| `GET` | `/api/dashboard/stats` | Stats complètes tableau de bord | ✓ |
| `GET` | `/api/rapport` | Rapport filtré | ✓ |
| `GET` | `/api/rapport/pdf` | Export rapport PDF | ✓ |
| `GET` | `/api/rapport/csv` | Export rapport CSV | ✓ |

---

## Configuration

Toutes les valeurs sont centralisées dans `backend/config.py` :

| Paramètre | Défaut | Description |
|---|---|---|
| `SERVER_PORT` | `5000` | Port HTTP (surcharge via variable d'env `PORT`) |
| `SQLITE_DB_PATH` | `backend/data/unipresencepro.db` | Chemin base de données |
| `ANTI_DOUBLON_MINUTES` | `15` | Délai minimum entre deux pointages |
| `RETARD_MAX_MINUTES` | `30` | Au-delà de cette limite → statut ABSENT |
| `SESSION_DURATION_HOURS` | `8` | Durée de session administrateur |
| `MAX_LOGIN_ATTEMPTS` | `5` | Tentatives avant blocage |
| `LOGIN_BLOCK_MINUTES` | `10` | Durée du blocage après échecs |
| `QR_IMAGE_SIZE` | `500 px` | Taille des QR codes générés |

---

## Dépendances Python

```
bcrypt==4.3.0          # Hachage des mots de passe
qrcode[pil]==7.4.2     # Génération des QR codes
Pillow==10.4.0         # Traitement d'images (QR + export)
reportlab==4.2.5       # Export des rapports en PDF
opencv-python          # Décodage QR codes côté serveur
numpy                  # Tableaux numériques (requis par OpenCV)
```

---

## Licence

MIT License — © 2025 Institut Universitaire de l'Entrepreneuriat — IUE Douala, Cameroun
