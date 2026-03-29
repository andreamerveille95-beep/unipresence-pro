# ============================================================
#  UniPresence Pro — IUE Douala
#  Logique métier : gestion des présences et statistiques
# ============================================================

import logging
from datetime import datetime, date, timedelta, time

from database import DatabaseHelper
from qr_generator import QRGenerator
from config import ANTI_DOUBLON_MINUTES, RETARD_MAX_MINUTES

# ------------------------------------------------------------
# Logger
# ------------------------------------------------------------
logger = logging.getLogger('presence_handler')


# ============================================================
#  Classe PresenceHandler
# ============================================================

class PresenceHandler:
    """
    Couche métier pour la gestion des présences des enseignants.

    Dépend de :
    - DatabaseHelper  (accès MySQL)
    - QRGenerator     (décodage des données QR)
    """

    def __init__(self):
        self.db  = DatabaseHelper()
        self.qrg = QRGenerator()

    # ----------------------------------------------------------
    # Helpers internes
    # ----------------------------------------------------------

    def _time_to_minutes(self, t) -> int:
        """Convertit un objet time ou une chaîne HH:MM:SS en minutes depuis minuit."""
        if isinstance(t, time):
            return t.hour * 60 + t.minute
        if isinstance(t, str):
            parts = t.split(':')
            try:
                return int(parts[0]) * 60 + int(parts[1])
            except (IndexError, ValueError):
                return 0
        if isinstance(t, timedelta):
            total = int(t.total_seconds())
            return total // 60
        return 0

    def _current_time(self) -> time:
        return datetime.now().time()

    def _current_date(self) -> date:
        return date.today()

    def _fmt_time(self, t) -> str:
        """Formate un objet time / timedelta / str en HH:MM."""
        if isinstance(t, time):
            return t.strftime('%H:%M')
        if isinstance(t, timedelta):
            total  = int(t.total_seconds())
            h, rem = divmod(total, 3600)
            m      = rem // 60
            return f'{h:02d}:{m:02d}'
        if isinstance(t, str):
            return t[:5]
        return str(t)[:5] if t else '00:00'

    # ----------------------------------------------------------
    # 1. Enregistrer un pointage
    # ----------------------------------------------------------

    def enregistrer_pointage(
        self,
        enseignant_id: int,
        seance_id,
        type_pointage: str,
        mode: str,
        ip: str,
        commentaire: str = '',
    ) -> dict:
        """
        Enregistre un pointage de présence.

        Règles métier :
        - Anti-doublon : si un pointage du même type existe dans les N dernières
          minutes pour cet enseignant, refuse l'enregistrement.
        - Calcul du retard : si seance_id fourni, compare l'heure de pointage
          avec l'heure de début de la séance.
        - Statut automatique :
            * retard = 0             → PRESENT
            * 0 < retard ≤ 30 min   → RETARD
            * retard > 30 min        → ABSENT

        Parameters
        ----------
        enseignant_id : int
        seance_id     : int | None
        type_pointage : str   — 'ARRIVEE' | 'DEPART' | 'PAUSE'
        mode          : str   — 'QR_CODE' | 'CAMERA' | 'MANUEL'
        ip            : str   — Adresse IP du client
        commentaire   : str

        Returns
        -------
        dict
            {succes, message, presence_id, statut, retard_minutes}
        """
        now_time = self._current_time()
        now_date = self._current_date()

        # ---- Vérification enseignant ----
        ens = self.db.fetch_one(
            "SELECT id, nom, prenom, matricule, est_actif "
            "FROM enseignants WHERE id = %s",
            (enseignant_id,)
        )
        if not ens:
            return {
                'succes': False,
                'message': f'Enseignant introuvable (id={enseignant_id}).',
                'presence_id': None, 'statut': None, 'retard_minutes': 0,
            }
        if not ens.get('est_actif', 0):
            return {
                'succes': False,
                'message': 'Cet enseignant est désactivé.',
                'presence_id': None, 'statut': None, 'retard_minutes': 0,
            }

        # ---- Anti-doublon ----
        # On ne bloque que si le DERNIER pointage de la journée est du
        # même type ET date de moins de ANTI_DOUBLON_MINUTES minutes.
        # Ainsi ARRIVEE → DEPART → ARRIVEE fonctionne même en moins de
        # 15 minutes : le dernier pointage est DEPART, donc aucun doublon.
        dernier_pointage = self.db.fetch_one(
            """
            SELECT id, type_pointage, heure_pointage FROM presences
            WHERE enseignant_id = %s
              AND date_pointage  = %s
            ORDER BY heure_pointage DESC, id DESC
            LIMIT 1
            """,
            (enseignant_id, str(now_date))
        )
        if dernier_pointage and dernier_pointage['type_pointage'] == type_pointage:
            cutoff_minutes = self._time_to_minutes(now_time) - ANTI_DOUBLON_MINUTES
            cutoff_time    = (
                f"{cutoff_minutes // 60:02d}:{cutoff_minutes % 60:02d}:00"
                if cutoff_minutes >= 0 else '00:00:00'
            )
            if dernier_pointage['heure_pointage'] >= cutoff_time:
                return {
                    'succes': False,
                    'message': (
                        f'Pointage en double ignoré : le dernier pointage '
                        f'{type_pointage} date de moins de '
                        f'{ANTI_DOUBLON_MINUTES} minutes.'
                    ),
                    'presence_id': dernier_pointage['id'],
                    'statut': None,
                    'retard_minutes': 0,
                }

        # ---- Calcul du retard ----
        retard_minutes = 0
        statut         = 'PRESENT'

        if seance_id:
            seance = self.db.fetch_one(
                "SELECT heure_debut FROM seances WHERE id = %s",
                (seance_id,)
            )
            if seance:
                heure_debut    = seance.get('heure_debut')
                debut_minutes  = self._time_to_minutes(heure_debut)
                arrive_minutes = self._time_to_minutes(now_time)
                retard_minutes = max(0, arrive_minutes - debut_minutes)

        # Déterminer statut
        if retard_minutes == 0:
            statut = 'PRESENT'
        elif retard_minutes <= RETARD_MAX_MINUTES:
            statut = 'RETARD'
        else:
            statut = 'ABSENT'

        # ---- Insertion ----
        data = {
            'enseignant_id':  enseignant_id,
            'seance_id':      seance_id if seance_id else None,
            'type_pointage':  type_pointage,
            'mode_pointage':  mode,
            'heure_pointage': str(now_time)[:8],
            'date_pointage':  str(now_date),
            'retard_minutes': retard_minutes,
            'statut':         statut,
            'commentaire':    commentaire or '',
            'adresse_ip':     ip or '',
        }
        presence_id = self.db.insert('presences', data)

        logger.info(
            "Pointage enregistré : enseignant_id=%s type=%s statut=%s retard=%d min "
            "(id=%s mode=%s ip=%s)",
            enseignant_id, type_pointage, statut, retard_minutes,
            presence_id, mode, ip
        )

        return {
            'succes':          True,
            'message':         f'Pointage {type_pointage} enregistré avec succès.',
            'presence_id':     presence_id,
            'statut':          statut,
            'retard_minutes':  retard_minutes,
            'enseignant_nom':  f"{ens['nom']} {ens['prenom']}",
            'heure':           self._fmt_time(now_time),
        }

    # ----------------------------------------------------------
    # 2. Scanner un QR Code
    # ----------------------------------------------------------

    def scan_qr(
        self,
        qr_data_string: str,
        seance_id,
        mode: str,
        ip: str,
    ) -> dict:
        """
        Traite un scan de QR code et enregistre le pointage correspondant.

        Parameters
        ----------
        qr_data_string : str   — Données JSON brutes du QR code.
        seance_id      : int | None
        mode           : str   — 'QR_CODE' | 'CAMERA'
        ip             : str

        Returns
        -------
        dict
            {succes, enseignant, heure, statut, message}
        """
        # Décoder les données QR
        qr_payload = self.qrg.decode(qr_data_string)
        if not qr_payload:
            return {
                'succes':     False,
                'message':    'QR code invalide ou illisible.',
                'enseignant': None,
                'heure':      None,
                'statut':     None,
            }

        enseignant_id = qr_payload.get('id')
        matricule     = qr_payload.get('matricule', '')
        token_qr      = qr_payload.get('token', '')

        if not enseignant_id:
            return {
                'succes':     False,
                'message':    'QR code ne contient pas d\'identifiant enseignant.',
                'enseignant': None, 'heure': None, 'statut': None,
            }

        # Vérifier le token en base de données
        ens_db = self.db.fetch_one(
            "SELECT id, nom, prenom, matricule, qr_code_data, est_actif "
            "FROM enseignants WHERE id = %s",
            (enseignant_id,)
        )
        if not ens_db:
            return {
                'succes':     False,
                'message':    f'Enseignant introuvable (id={enseignant_id}).',
                'enseignant': None, 'heure': None, 'statut': None,
            }

        if not ens_db.get('est_actif', 0):
            return {
                'succes':     False,
                'message':    'Cet enseignant est désactivé.',
                'enseignant': None, 'heure': None, 'statut': None,
            }

        # Valider le token (le champ qr_code_data contient le JSON encodé dans le QR)
        stored_data = ens_db.get('qr_code_data', '')
        token_valid = False
        if stored_data:
            decoded_stored = self.qrg.decode(stored_data)
            if decoded_stored and decoded_stored.get('token') == token_qr:
                token_valid = True

        if not token_valid:
            # Fallback : si qr_code_data est vide (ancien enseignant sans token),
            # on valide quand même par matricule pour ne pas bloquer le kiosque.
            matricule_db = ens_db.get('matricule', '')
            if not stored_data and matricule and matricule_db == matricule:
                logger.warning(
                    "scan_qr : pas de qr_code_data pour enseignant_id=%s — "
                    "validation par matricule (token absent). Régénérer le QR.",
                    enseignant_id
                )
                token_valid = True  # tolère l'absence de token (QR ancien)
            else:
                logger.warning(
                    "scan_qr : token QR invalide pour enseignant_id=%s "
                    "(matricule=%s ip=%s)",
                    enseignant_id, matricule, ip
                )
                return {
                    'succes':     False,
                    'message':    (
                        'QR code révoqué ou régénéré. '
                        'Veuillez utiliser le nouveau QR code de cet enseignant.'
                    ),
                    'enseignant': f"{ens_db.get('prenom','')} {ens_db.get('nom','')}",
                    'heure': None, 'statut': None,
                }

        # Déterminer automatiquement ARRIVEE ou DEPART
        today = str(self._current_date())
        dernier = self.db.fetch_one(
            """SELECT type_pointage FROM presences
               WHERE enseignant_id = %s AND date_pointage = %s
               ORDER BY heure_pointage DESC, id DESC LIMIT 1""",
            (enseignant_id, today)
        )
        if dernier is None or dernier['type_pointage'] == 'DEPART':
            type_pointage = 'ARRIVEE'
        else:
            type_pointage = 'DEPART'

        # Enregistrer le pointage
        result = self.enregistrer_pointage(
            enseignant_id = enseignant_id,
            seance_id     = seance_id,
            type_pointage = type_pointage,
            mode          = mode,
            ip            = ip,
        )

        return {
            'succes':          result['succes'],
            'message':         result['message'],
            'enseignant':      f"{ens_db['prenom']} {ens_db['nom']}",
            'matricule':       ens_db['matricule'],
            'heure':           result.get('heure'),
            'statut':          result.get('statut'),
            'retard':          result.get('retard_minutes', 0),
            'type_pointage':   type_pointage,
        }

    # ----------------------------------------------------------
    # 3. Statistiques Dashboard
    # ----------------------------------------------------------

    def get_stats_dashboard(self) -> dict:
        """
        Retourne les KPI principaux pour le tableau de bord.

        Returns
        -------
        dict
            {total_enseignants, presents_aujourd_hui, retards_mois, absences_semaine}
        """
        today      = str(date.today())
        first_day_month = date.today().replace(day=1)
        week_start  = date.today() - timedelta(days=date.today().weekday())

        # Total enseignants actifs
        total_row = self.db.fetch_one(
            "SELECT COUNT(*) AS cnt FROM enseignants WHERE est_actif = 1"
        )
        total_enseignants = total_row['cnt'] if total_row else 0

        # Présents aujourd'hui (PRESENT + RETARD)
        pres_row = self.db.fetch_one(
            """
            SELECT COUNT(DISTINCT enseignant_id) AS cnt
            FROM presences
            WHERE date_pointage = %s
              AND type_pointage = 'ARRIVEE'
              AND statut IN ('PRESENT', 'RETARD')
            """,
            (today,)
        )
        presents_aujourd_hui = pres_row['cnt'] if pres_row else 0

        # Retards ce mois
        ret_row = self.db.fetch_one(
            """
            SELECT COUNT(*) AS cnt FROM presences
            WHERE statut = 'RETARD'
              AND date_pointage >= %s
            """,
            (str(first_day_month),)
        )
        retards_mois = ret_row['cnt'] if ret_row else 0

        # Absences cette semaine
        abs_row = self.db.fetch_one(
            """
            SELECT COUNT(*) AS cnt FROM presences
            WHERE statut = 'ABSENT'
              AND date_pointage >= %s
            """,
            (str(week_start),)
        )
        absences_semaine = abs_row['cnt'] if abs_row else 0

        return {
            'total_enseignants':    total_enseignants,
            'presents_aujourd_hui': presents_aujourd_hui,
            'retards_mois':         retards_mois,
            'absences_semaine':     absences_semaine,
        }

    # ----------------------------------------------------------
    # 4. Présences sur 7 jours
    # ----------------------------------------------------------

    def get_presences_7_jours(self) -> list:
        """
        Retourne les statistiques de présence pour les 7 derniers jours.

        Returns
        -------
        list[dict]
            [{date, nb_presents, nb_retards, nb_absents}]
            Classé du plus ancien au plus récent.
        """
        date_debut = str(date.today() - timedelta(days=6))
        rows = self.db.fetch_all(
            """
            SELECT
                date_pointage                                              AS date,
                SUM(CASE WHEN statut = 'PRESENT' THEN 1 ELSE 0 END)      AS nb_presents,
                SUM(CASE WHEN statut = 'RETARD'  THEN 1 ELSE 0 END)      AS nb_retards,
                SUM(CASE WHEN statut = 'ABSENT'  THEN 1 ELSE 0 END)      AS nb_absents
            FROM presences
            WHERE date_pointage >= %s
              AND type_pointage = 'ARRIVEE'
            GROUP BY date_pointage
            ORDER BY date_pointage ASC
            """,
            (date_debut,)
        )
        # Normaliser les valeurs en int et les dates en str
        result = []
        for r in rows:
            result.append({
                'date':        str(r.get('date', '')),
                'nb_presents': int(r.get('nb_presents') or 0),
                'nb_retards':  int(r.get('nb_retards')  or 0),
                'nb_absents':  int(r.get('nb_absents')  or 0),
            })
        return result

    # ----------------------------------------------------------
    # 5. Présences par département
    # ----------------------------------------------------------

    def get_presences_par_departement(self) -> list:
        """
        Retourne le taux de présence par département pour aujourd'hui.

        Returns
        -------
        list[dict]
            [{departement, nb_presents, total}]
        """
        today = str(date.today())
        rows  = self.db.fetch_all(
            """
            SELECT
                e.departement,
                COUNT(DISTINCT e.id)                      AS total,
                COUNT(DISTINCT CASE
                    WHEN p.statut IN ('PRESENT','RETARD')
                     AND p.date_pointage = %s
                    THEN p.enseignant_id END
                )                                          AS nb_presents
            FROM enseignants e
            LEFT JOIN presences p ON p.enseignant_id = e.id
            WHERE e.est_actif = 1
            GROUP BY e.departement
            ORDER BY e.departement
            """,
            (today,)
        )
        return [
            {
                'departement': r.get('departement', ''),
                'nb_presents': int(r.get('nb_presents') or 0),
                'total':       int(r.get('total') or 0),
            }
            for r in rows
        ]

    # ----------------------------------------------------------
    # 6. Taux de ponctualité global
    # ----------------------------------------------------------

    def get_taux_ponctualite(self) -> float:
        """
        Calcule le taux de ponctualité global (présents / total × 100).

        Returns
        -------
        float
            Taux en pourcentage, arrondi à 1 décimale.
        """
        row = self.db.fetch_one(
            """
            SELECT
                COUNT(*)                                              AS total,
                SUM(CASE WHEN statut = 'PRESENT' THEN 1 ELSE 0 END)  AS presents
            FROM presences
            WHERE type_pointage = 'ARRIVEE'
            """
        )
        if not row or not row.get('total'):
            return 0.0
        total    = int(row['total'])
        presents = int(row.get('presents') or 0)
        return round(presents * 100 / total, 1) if total > 0 else 0.0

    # ----------------------------------------------------------
    # 7. Derniers pointages
    # ----------------------------------------------------------

    def get_derniers_pointages(self, limit: int = 5) -> list:
        """
        Retourne les N derniers pointages toutes dates confondues.

        Parameters
        ----------
        limit : int (défaut 5)

        Returns
        -------
        list[dict]
        """
        rows = self.db.fetch_all(
            """
            SELECT
                p.id,
                p.date_pointage,
                p.heure_pointage,
                p.type_pointage,
                p.mode_pointage,
                p.statut,
                p.retard_minutes,
                e.nom,
                e.prenom,
                e.matricule,
                e.departement,
                s.titre  AS seance
            FROM presences p
            JOIN enseignants e ON e.id = p.enseignant_id
            LEFT JOIN seances s ON s.id = p.seance_id
            ORDER BY p.date_pointage DESC, p.heure_pointage DESC
            LIMIT %s
            """,
            (limit,)
        )
        return [
            {
                **r,
                'date_pointage':  str(r.get('date_pointage', '')),
                'heure_pointage': self._fmt_time(r.get('heure_pointage')),
            }
            for r in rows
        ]

    # ----------------------------------------------------------
    # 8. Séances du jour
    # ----------------------------------------------------------

    def get_seances_du_jour(self) -> list:
        """
        Retourne les séances planifiées pour aujourd'hui.

        Returns
        -------
        list[dict]
        """
        today = str(date.today())
        rows  = self.db.fetch_all(
            """
            SELECT
                s.id,
                s.titre,
                s.matiere,
                s.salle,
                s.heure_debut,
                s.heure_fin,
                s.type_seance,
                s.statut,
                e.nom,
                e.prenom,
                e.matricule,
                e.departement
            FROM seances s
            JOIN enseignants e ON e.id = s.enseignant_id
            WHERE s.date_seance = %s
            ORDER BY s.heure_debut ASC
            """,
            (today,)
        )
        return [
            {
                **r,
                'heure_debut': self._fmt_time(r.get('heure_debut')),
                'heure_fin':   self._fmt_time(r.get('heure_fin')),
            }
            for r in rows
        ]

    # ----------------------------------------------------------
    # 9. Liste paginée des présences avec filtres
    # ----------------------------------------------------------

    def get_presences_filtrees(
        self,
        enseignant_id=None,
        date_debut=None,
        date_fin=None,
        departement=None,
        statut=None,
        page: int = 1,
        limit: int = 20,
    ) -> dict:
        """
        Retourne les présences filtrées avec pagination.

        Returns
        -------
        dict
            {presences: list[dict], total: int, page: int, pages: int}
        """
        conditions = ['1=1']
        params     = []

        if enseignant_id:
            conditions.append('p.enseignant_id = %s')
            params.append(int(enseignant_id))

        if date_debut:
            conditions.append('p.date_pointage >= %s')
            params.append(date_debut)

        if date_fin:
            conditions.append('p.date_pointage <= %s')
            params.append(date_fin)

        if departement:
            conditions.append('e.departement = %s')
            params.append(departement)

        if statut:
            conditions.append('p.statut = %s')
            params.append(statut)

        where = ' AND '.join(conditions)

        base_sql = f"""
            SELECT
                p.id,
                p.date_pointage,
                p.heure_pointage,
                p.type_pointage,
                p.mode_pointage,
                p.statut,
                p.retard_minutes,
                p.commentaire,
                e.nom,
                e.prenom,
                e.matricule,
                e.departement,
                s.titre AS seance
            FROM presences p
            JOIN enseignants e ON e.id = p.enseignant_id
            LEFT JOIN seances s ON s.id = p.seance_id
            WHERE {where}
            ORDER BY p.date_pointage DESC, p.heure_pointage DESC
        """

        # Compter le total
        count_sql = (
            f"SELECT COUNT(*) AS cnt FROM presences p "
            f"JOIN enseignants e ON e.id = p.enseignant_id "
            f"WHERE {where}"
        )
        count_row = self.db.fetch_one(count_sql, params)
        total     = int(count_row['cnt']) if count_row else 0

        # Pagination
        page   = max(1, page)
        limit  = max(1, min(limit, 100))
        offset = (page - 1) * limit
        pages  = max(1, -(-total // limit))

        paginated_sql = f"{base_sql} LIMIT %s OFFSET %s"
        rows = self.db.fetch_all(paginated_sql, params + [limit, offset])

        presences = [
            {
                **r,
                'date_pointage':  str(r.get('date_pointage', '')),
                'heure_pointage': self._fmt_time(r.get('heure_pointage')),
            }
            for r in rows
        ]

        return {
            'presences': presences,
            'total':     total,
            'page':      page,
            'pages':     pages,
        }


# ============================================================
#  Instance globale partagée
# ============================================================
presence_handler = PresenceHandler()
