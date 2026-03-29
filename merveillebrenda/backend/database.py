# ============================================================
#  UniPresence Pro — IUE Douala
#  database.py — SQLite (intégré Python, zéro installation)
# ============================================================

import sqlite3
import os
import logging
import math
import re
from datetime import datetime

logger = logging.getLogger('unipresence.database')

# Import config
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import SQLITE_DB_PATH

# ── Regex pré-compilées (compilées UNE seule fois au démarrage) ──────────────
_RE_DATE_SUB = re.compile(
    r"DATE_SUB\s*\(\s*([^,]+)\s*,\s*INTERVAL\s+(\d+)\s+DAY\s*\)",
    re.IGNORECASE
)
_RE_DATE_ADD = re.compile(
    r"DATE_ADD\s*\(\s*([^,]+)\s*,\s*INTERVAL\s+(\d+)\s+DAY\s*\)",
    re.IGNORECASE
)
_RE_DATEDIFF = re.compile(
    r"DATEDIFF\s*\(([^,]+),([^)]+)\)",
    re.IGNORECASE
)

# ── WAL activé une seule fois sur le fichier DB ───────────────────────────────
_wal_initialized = False


def get_connection():
    """Retourne une connexion SQLite avec row_factory pour obtenir des dicts."""
    global _wal_initialized
    conn = sqlite3.connect(SQLITE_DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    # WAL persiste dans le fichier DB — on ne l'envoie qu'une fois par process
    if not _wal_initialized:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA cache_size=-8000")   # 8 MB cache SQLite
        conn.execute("PRAGMA temp_store=MEMORY")  # temp tables en RAM
        _wal_initialized = True
    conn.execute("PRAGMA foreign_keys=ON")        # per-connexion obligatoire
    return conn


def row_to_dict(row):
    """Convertir sqlite3.Row en dict Python."""
    if row is None:
        return None
    return dict(row)


def rows_to_list(rows):
    """Convertir liste de sqlite3.Row en liste de dicts."""
    if not rows:
        return []
    return [dict(r) for r in rows]


class DatabaseHelper:
    """Helper CRUD pour SQLite — API identique à l'ancienne version MySQL."""

    def fetch_one(self, sql, params=None):
        """Exécuter une requête et retourner une ligne (dict) ou None."""
        sql = self._adapt_sql(sql)
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(sql, params or [])
            row = cur.fetchone()
            conn.close()
            return row_to_dict(row)
        except Exception as e:
            logger.error(f"fetch_one error: {e} | SQL: {sql}")
            return None

    def fetch_all(self, sql, params=None):
        """Exécuter une requête et retourner toutes les lignes (liste de dicts)."""
        sql = self._adapt_sql(sql)
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(sql, params or [])
            rows = cur.fetchall()
            conn.close()
            return rows_to_list(rows)
        except Exception as e:
            logger.error(f"fetch_all error: {e} | SQL: {sql}")
            return []

    def execute_query(self, sql, params=None, fetch=False):
        """Exécuter une requête INSERT/UPDATE/DELETE."""
        sql = self._adapt_sql(sql)
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(sql, params or [])
            conn.commit()
            result = cur.lastrowid if fetch else cur.rowcount
            conn.close()
            return result
        except Exception as e:
            logger.error(f"execute_query error: {e} | SQL: {sql}")
            return None

    # Alias pour la compatibilité avec les appels db.execute(...)
    def execute(self, sql, params=None):
        """Alias de execute_query pour la compatibilité."""
        return self.execute_query(sql, params, fetch=False)

    def insert(self, table, data_dict):
        """Insérer une ligne dans une table. Retourne le lastrowid."""
        cols = ', '.join(data_dict.keys())
        placeholders = ', '.join(['?' for _ in data_dict])
        sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(sql, list(data_dict.values()))
            conn.commit()
            last_id = cur.lastrowid
            conn.close()
            return last_id
        except Exception as e:
            logger.error(f"insert error: {e} | table: {table}")
            return None

    def update(self, table, data_dict, where_clause, where_params=None):
        """Mettre à jour des lignes. Retourne rowcount."""
        where_clause = self._adapt_sql(where_clause)
        set_clause = ', '.join([f"{k} = ?" for k in data_dict.keys()])
        sql = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"
        params = list(data_dict.values()) + (list(where_params) if where_params else [])
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(sql, params)
            conn.commit()
            count = cur.rowcount
            conn.close()
            return count
        except Exception as e:
            logger.error(f"update error: {e} | table: {table}")
            return 0

    def delete(self, table, where_clause, where_params=None):
        """Supprimer des lignes. Retourne rowcount."""
        where_clause = self._adapt_sql(where_clause)
        sql = f"DELETE FROM {table} WHERE {where_clause}"
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(sql, list(where_params) if where_params else [])
            conn.commit()
            count = cur.rowcount
            conn.close()
            return count
        except Exception as e:
            logger.error(f"delete error: {e} | table: {table}")
            return 0

    def fetch_paginated(self, sql, params=None, page=1, limit=20):
        """Pagination : retourne {rows, total, page, pages}."""
        sql = self._adapt_sql(sql)
        try:
            conn = get_connection()
            cur = conn.cursor()
            # Total
            count_sql = f"SELECT COUNT(*) as cnt FROM ({sql}) t"
            cur.execute(count_sql, params or [])
            total = cur.fetchone()[0]
            # Données paginées
            offset = (page - 1) * limit
            cur.execute(f"{sql} LIMIT ? OFFSET ?", list(params or []) + [limit, offset])
            rows = rows_to_list(cur.fetchall())
            conn.close()
            return {
                'rows': rows,
                'total': total,
                'page': page,
                'pages': math.ceil(total / limit) if total else 1,
            }
        except Exception as e:
            logger.error(f"fetch_paginated error: {e}")
            return {'rows': [], 'total': 0, 'page': 1, 'pages': 1}

    def _adapt_sql(self, sql):
        """Convertir les placeholders MySQL %s → SQLite ? et adapter la syntaxe."""
        if sql is None:
            return sql
        # Remplacer %s par ?
        sql = sql.replace('%s', '?')
        # NOW() → datetime('now','localtime')
        sql = sql.replace('NOW()', "datetime('now','localtime')")
        sql = sql.replace('now()', "datetime('now','localtime')")
        # CURDATE() → date('now','localtime')
        sql = sql.replace('CURDATE()', "date('now','localtime')")
        sql = sql.replace('curdate()', "date('now','localtime')")
        # Regex pré-compilées (évite la recompilation à chaque appel)
        if 'DATE_SUB' in sql.upper():
            sql = _RE_DATE_SUB.sub(
                lambda m: f"date({m.group(1).strip()}, '-{m.group(2)} days')", sql)
        if 'DATE_ADD' in sql.upper():
            sql = _RE_DATE_ADD.sub(
                lambda m: f"date({m.group(1).strip()}, '+{m.group(2)} days')", sql)
        if 'DATEDIFF' in sql.upper():
            sql = _RE_DATEDIFF.sub(
                lambda m: f"(julianday({m.group(1).strip()}) - julianday({m.group(2).strip()}))", sql)
        return sql

    def ping(self):
        """Tester la connexion. Retourne True si OK."""
        try:
            conn = get_connection()
            conn.execute("SELECT 1")
            conn.close()
            return True
        except Exception:
            return False

    # Helpers de compatibilité supplémentaires
    def count(self, table, where_clause='1=1', where_params=None):
        """Compte les lignes d'une table avec un filtre optionnel."""
        where_clause = self._adapt_sql(where_clause)
        sql = f"SELECT COUNT(*) AS cnt FROM {table} WHERE {where_clause}"
        row = self.fetch_one(sql, where_params or [])
        return row['cnt'] if row else 0

    def table_exists(self, table_name):
        """Vérifie qu'une table existe dans la base SQLite."""
        row = self.fetch_one(
            "SELECT COUNT(*) AS cnt FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        )
        return bool(row and row.get('cnt', 0) > 0)


def init_database():
    """Créer toutes les tables et insérer les données de démo si la DB est vide."""
    conn = get_connection()
    cur = conn.cursor()

    # ── Tables ──────────────────────────────────────────────────
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL,
        prenom TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        mot_de_passe TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS enseignants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        matricule TEXT UNIQUE NOT NULL,
        nom TEXT NOT NULL,
        prenom TEXT NOT NULL,
        email TEXT,
        telephone TEXT,
        specialite TEXT,
        departement TEXT,
        grade TEXT,
        photo TEXT DEFAULT '',
        qr_code_path TEXT DEFAULT '',
        qr_code_data TEXT DEFAULT '',
        est_actif INTEGER DEFAULT 1,
        date_inscription TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS seances (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        titre TEXT NOT NULL,
        matiere TEXT,
        enseignant_id INTEGER REFERENCES enseignants(id),
        salle TEXT,
        date_seance TEXT,
        heure_debut TEXT,
        heure_fin TEXT,
        type_seance TEXT CHECK(type_seance IN ('CM','TD','TP','Exam')),
        statut TEXT DEFAULT 'planifiee' CHECK(statut IN ('planifiee','en_cours','terminee','annulee')),
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS presences (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        enseignant_id INTEGER REFERENCES enseignants(id),
        seance_id INTEGER REFERENCES seances(id),
        type_pointage TEXT CHECK(type_pointage IN ('ARRIVEE','DEPART','PAUSE')),
        mode_pointage TEXT CHECK(mode_pointage IN ('QR_CODE','CAMERA','MANUEL')),
        heure_pointage TEXT,
        date_pointage TEXT,
        retard_minutes INTEGER DEFAULT 0,
        statut TEXT CHECK(statut IN ('PRESENT','RETARD','ABSENT','EXCUSE')),
        commentaire TEXT,
        adresse_ip TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS sessions_admin (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id INTEGER REFERENCES admins(id),
        token TEXT UNIQUE NOT NULL,
        created_at TEXT DEFAULT (datetime('now','localtime')),
        expires_at TEXT,
        adresse_ip TEXT
    );

    -- ── Index de performance ──────────────────────────────────────
    -- Requêtes fréquentes : filtre par date + type de pointage
    CREATE INDEX IF NOT EXISTS idx_presences_date
        ON presences(date_pointage);
    CREATE INDEX IF NOT EXISTS idx_presences_ens_date
        ON presences(enseignant_id, date_pointage);
    CREATE INDEX IF NOT EXISTS idx_presences_type
        ON presences(type_pointage);
    -- Tri enseignants
    CREATE INDEX IF NOT EXISTS idx_enseignants_nom
        ON enseignants(nom, prenom);
    CREATE INDEX IF NOT EXISTS idx_enseignants_dept
        ON enseignants(departement);
    CREATE INDEX IF NOT EXISTS idx_enseignants_actif
        ON enseignants(est_actif);
    -- Sessions admin (lookup par token)
    CREATE INDEX IF NOT EXISTS idx_sessions_token
        ON sessions_admin(token);
    """)

    # ── Migration : supprimer les CHECK sur departement/grade si présents ──
    schema_row = cur.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='enseignants'"
    ).fetchone()
    if schema_row and schema_row[0] and 'CHECK' in schema_row[0]:
        logger.info("Migration : suppression des contraintes CHECK sur enseignants…")
        # PRAGMA foreign_keys doit être exécuté HORS executescript (connexion-level)
        cur.execute("PRAGMA foreign_keys = OFF")
        conn.commit()
        # Nettoyer une éventuelle table temporaire laissée par une tentative ratée
        cur.execute("DROP TABLE IF EXISTS enseignants_mig")
        conn.commit()
        cur.execute("""
            CREATE TABLE enseignants_mig (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                matricule TEXT UNIQUE NOT NULL,
                nom TEXT NOT NULL,
                prenom TEXT NOT NULL,
                email TEXT,
                telephone TEXT,
                specialite TEXT,
                departement TEXT,
                grade TEXT,
                photo TEXT DEFAULT '',
                qr_code_path TEXT DEFAULT '',
                qr_code_data TEXT DEFAULT '',
                est_actif INTEGER DEFAULT 1,
                date_inscription TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            )
        """)
        cur.execute("""
            INSERT INTO enseignants_mig
                SELECT id, matricule, nom, prenom, email, telephone,
                       specialite, departement, grade, photo,
                       qr_code_path, qr_code_data, est_actif,
                       date_inscription, created_at
                FROM enseignants
        """)
        cur.execute("DROP TABLE enseignants")
        cur.execute("ALTER TABLE enseignants_mig RENAME TO enseignants")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_enseignants_nom   ON enseignants(nom, prenom)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_enseignants_dept  ON enseignants(departement)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_enseignants_actif ON enseignants(est_actif)")
        conn.commit()
        cur.execute("PRAGMA foreign_keys = ON")
        logger.info("Migration enseignants terminée — CHECK supprimés.")

    # ── Données de démo (seulement si la table admins est vide) ──
    cur.execute("SELECT COUNT(*) FROM admins")
    if cur.fetchone()[0] == 0:
        # Admin : admin@iue.cm / admin123
        import bcrypt
        pwd_hash = bcrypt.hashpw(b'admin123', bcrypt.gensalt(12)).decode('utf-8')
        cur.execute(
            "INSERT INTO admins (nom, prenom, email, mot_de_passe) VALUES (?,?,?,?)",
            ('Admin', 'IUE', 'admin@iue.cm', pwd_hash)
        )

        today = datetime.now().strftime('%Y-%m-%d')
        now_time = datetime.now().strftime('%H:%M:%S')

        # 5 enseignants
        enseignants = [
            ('IUE-2024-0001', 'MBARGA', 'Jean-Paul', 'jp.mbarga@iue.cm', '+237691234567', 'Informatique & Réseaux', 'ESIT', 'Maître', today),
            ('IUE-2024-0002', 'NNOMO', 'Alice', 'a.nnomo@iue.cm', '+237677890123', 'Marketing Digital', 'EME', 'Chargé', today),
            ('IUE-2024-0003', 'BIYONG', 'Stéphane', 's.biyong@iue.cm', '+237655432109', 'Génie Logiciel', 'ESIT', 'Prof', today),
            ('IUE-2024-0004', 'FOUDA', 'Marie-Claire', 'mc.fouda@iue.cm', '+237699876543', 'Finance & Comptabilité', 'EME', 'Assistant', today),
            ('IUE-2025-0005', 'EKANI', 'Robert', 'r.ekani@iue.cm', '+237681234000', 'Administration', 'ADMIN', 'Chargé', today),
        ]
        for e in enseignants:
            cur.execute("""INSERT INTO enseignants
                (matricule,nom,prenom,email,telephone,specialite,departement,grade,date_inscription)
                VALUES (?,?,?,?,?,?,?,?,?)""", e)

        # 3 séances aujourd'hui
        seances = [
            ('Algorithmique avancée', 'Informatique', 1, 'B204', today, '08:00', '10:00', 'CM', 'planifiee'),
            ('Marketing Stratégique', 'Marketing', 2, 'A101', today, '10:30', '12:30', 'TD', 'planifiee'),
            ('Base de données', 'Informatique', 3, 'Labo Info', today, '14:00', '16:00', 'TP', 'planifiee'),
        ]
        for s in seances:
            cur.execute("""INSERT INTO seances
                (titre,matiere,enseignant_id,salle,date_seance,heure_debut,heure_fin,type_seance,statut)
                VALUES (?,?,?,?,?,?,?,?,?)""", s)

        # 3 présences
        presences = [
            (1, 1, 'ARRIVEE', 'MANUEL', '08:05', today, 0, 'PRESENT', '', '127.0.0.1'),
            (2, 2, 'ARRIVEE', 'QR_CODE', '10:45', today, 15, 'RETARD', '', '127.0.0.1'),
            (4, None, 'ARRIVEE', 'MANUEL', now_time, today, 0, 'PRESENT', '', '127.0.0.1'),
        ]
        for p in presences:
            cur.execute("""INSERT INTO presences
                (enseignant_id,seance_id,type_pointage,mode_pointage,heure_pointage,date_pointage,retard_minutes,statut,commentaire,adresse_ip)
                VALUES (?,?,?,?,?,?,?,?,?,?)""", p)

    conn.commit()
    conn.close()
    logger.info(f"Base SQLite initialisée : {SQLITE_DB_PATH}")


# ============================================================
#  Instance globale partagée
# ============================================================
db = DatabaseHelper()
