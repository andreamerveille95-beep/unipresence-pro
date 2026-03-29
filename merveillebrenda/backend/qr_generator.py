# ============================================================
#  UniPresence Pro — IUE Douala
#  Générateur de QR Codes pour les enseignants
# ============================================================

import os
import json
import uuid
import base64
import logging
import unicodedata

try:
    import qrcode
    from qrcode.constants import ERROR_CORRECT_H
except ImportError:
    raise ImportError(
        "Le module qrcode est requis. "
        "Installez-le avec : pip install qrcode[pil]"
    )

try:
    from PIL import Image
except ImportError:
    raise ImportError(
        "Le module Pillow est requis. "
        "Installez-le avec : pip install Pillow"
    )

from config import QR_DIR, BASE_DIR, QR_VERSION, QR_BOX_SIZE, QR_BORDER, QR_IMAGE_SIZE

# ------------------------------------------------------------
# Logger
# ------------------------------------------------------------
logger = logging.getLogger('qr_generator')

# S'assurer que le dossier QR existe
os.makedirs(QR_DIR, exist_ok=True)


# ============================================================
#  Classe QRGenerator
# ============================================================

class QRGenerator:
    """
    Génère, enregistre et décode les QR codes des enseignants.

    Chaque QR code encapsule un JSON :
    ``{ "id": int, "matricule": str, "nom": str, "prenom": str, "token": str }``

    Le token est un UUID4 servant d'identifiant unique et sécurisé pour le
    pointage — il est stocké dans ``enseignants.qr_code_data`` en base.
    """

    # ----------------------------------------------------------
    # Méthode principale : générer un QR code
    # ----------------------------------------------------------

    def generate(self, enseignant_dict: dict) -> str:
        """
        Génère et sauvegarde le QR code PNG d'un enseignant.

        Parameters
        ----------
        enseignant_dict : dict
            Doit contenir au minimum : ``id``, ``matricule``, ``nom``, ``prenom``.

        Returns
        -------
        str
            Chemin absolu du fichier PNG généré.
        """
        token = str(uuid.uuid4())

        payload = {
            'id':        enseignant_dict.get('id'),
            'matricule': enseignant_dict.get('matricule', ''),
            'nom':       enseignant_dict.get('nom', ''),
            'prenom':    enseignant_dict.get('prenom', ''),
            'token':     token,
        }

        qr_data_string = json.dumps(payload, ensure_ascii=False)

        # Créer l'objet QRCode
        qr = qrcode.QRCode(
            version           = QR_VERSION,
            error_correction  = ERROR_CORRECT_H,
            box_size          = QR_BOX_SIZE,
            border            = QR_BORDER,
        )
        qr.add_data(qr_data_string)
        qr.make(fit=True)

        # Générer l'image PIL
        img = qr.make_image(fill_color='black', back_color='white')

        # Assurer la taille minimale de 500×500 px
        img_width, img_height = img.size
        if img_width < QR_IMAGE_SIZE or img_height < QR_IMAGE_SIZE:
            img = img.resize(
                (QR_IMAGE_SIZE, QR_IMAGE_SIZE),
                Image.NEAREST
            )

        # Chemin de sauvegarde
        png_path = self.get_qr_path(enseignant_dict.get('matricule', 'unknown'))
        img.save(png_path, format='PNG')

        logger.info(
            "QR code généré : enseignant_id=%s matricule=%s → %s",
            payload['id'], payload['matricule'], png_path
        )

        # Stocker le token dans l'objet retourné (le caller peut l'enregistrer)
        # On retourne le chemin ; le token est accessible via decode() si besoin.
        # On l'attache aussi à l'objet pour faciliter le travail du caller :
        self._last_token    = token
        self._last_qr_data  = qr_data_string

        return png_path

    # ----------------------------------------------------------
    # Propriétés pratiques après generate()
    # ----------------------------------------------------------

    @property
    def last_token(self) -> str:
        """Token UUID4 du dernier QR généré."""
        return getattr(self, '_last_token', '')

    @property
    def last_qr_data(self) -> str:
        """Données JSON encodées dans le dernier QR généré."""
        return getattr(self, '_last_qr_data', '')

    # ----------------------------------------------------------
    # Conversion en base64
    # ----------------------------------------------------------

    def to_base64(self, png_path: str) -> str:
        """
        Lit un fichier PNG et le convertit en Data URI base64.

        Parameters
        ----------
        png_path : str  — Chemin absolu du fichier PNG.

        Returns
        -------
        str
            ``data:image/png;base64,<données>``
            Retourne une chaîne vide si le fichier n'existe pas.
        """
        if not png_path or not os.path.isfile(png_path):
            logger.warning("to_base64 : fichier introuvable → %s", png_path)
            return ''

        try:
            with open(png_path, 'rb') as f:
                raw = f.read()
            b64 = base64.b64encode(raw).decode('ascii')
            return f'data:image/png;base64,{b64}'
        except Exception as exc:
            logger.error("to_base64 erreur (%s) : %s", png_path, exc)
            return ''

    # ----------------------------------------------------------
    # Décodage
    # ----------------------------------------------------------

    def decode(self, qr_data_string: str) -> dict | None:
        """
        Décode une chaîne JSON issue d'un QR code.

        Parameters
        ----------
        qr_data_string : str  — Données brutes lues par le scanner.

        Returns
        -------
        dict | None
            Dictionnaire ``{id, matricule, nom, prenom, token}``
            ou None si le JSON est invalide.
        """
        if not qr_data_string:
            return None

        try:
            data = json.loads(qr_data_string)
            if not isinstance(data, dict):
                return None
            # Vérifier les champs obligatoires
            required = {'id', 'matricule', 'token'}
            if not required.issubset(data.keys()):
                logger.warning(
                    "decode : champs manquants dans le QR data. "
                    "Reçu : %s", list(data.keys())
                )
                return None
            return data
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error("decode : JSON invalide — %s", exc)
            return None

    # ----------------------------------------------------------
    # Régénération
    # ----------------------------------------------------------

    def regenerate(self, enseignant_dict: dict) -> tuple[str, str]:
        """
        Supprime l'ancien QR code et en génère un nouveau.

        Parameters
        ----------
        enseignant_dict : dict
            Doit contenir ``matricule`` (et idéalement ``qr_code_path``).

        Returns
        -------
        tuple[str, str]
            ``(chemin_png, nouveau_token)``
        """
        # Supprimer l'ancien fichier s'il existe
        old_path = enseignant_dict.get('qr_code_path', '')
        if old_path and os.path.isfile(old_path):
            try:
                os.remove(old_path)
                logger.info("Ancien QR supprimé : %s", old_path)
            except OSError as exc:
                logger.warning("Impossible de supprimer %s : %s", old_path, exc)

        # Vérifier aussi le chemin calculé
        expected = self.get_qr_path(enseignant_dict.get('matricule', ''))
        if expected and os.path.isfile(expected) and expected != old_path:
            try:
                os.remove(expected)
            except OSError:
                pass

        # Générer le nouveau QR
        png_path = self.generate(enseignant_dict)
        return png_path, self.last_token

    # ----------------------------------------------------------
    # Chemin attendu
    # ----------------------------------------------------------

    def get_qr_path(self, matricule: str) -> str:
        """
        Retourne le chemin absolu attendu pour le QR code d'un matricule.

        Parameters
        ----------
        matricule : str  — Ex. ``IUE-2024-0001``.

        Returns
        -------
        str
            ``<QR_DIR>/qr_<matricule_safe>.png``
        """
        # Normaliser le matricule pour un nom de fichier sûr
        safe = matricule.replace('/', '_').replace('\\', '_').replace(' ', '_')
        return os.path.join(QR_DIR, f'qr_{safe}.png')

    # ----------------------------------------------------------
    # Helper interne : normalisation unicode → ASCII
    # ----------------------------------------------------------

    @staticmethod
    def _to_ascii(text: str) -> str:
        """
        Convertit une chaîne unicode en ASCII en supprimant les accents.

        Parameters
        ----------
        text : str

        Returns
        -------
        str
        """
        normalized = unicodedata.normalize('NFKD', text)
        return normalized.encode('ascii', errors='ignore').decode('ascii')

    # ----------------------------------------------------------
    # Génération groupée
    # ----------------------------------------------------------

    def generate_all(self, enseignants_list: list) -> dict:
        """
        Génère les QR codes pour une liste d'enseignants.

        Parameters
        ----------
        enseignants_list : list[dict]

        Returns
        -------
        dict
            ``{matricule: {'path': str, 'token': str, 'base64': str}}``
        """
        results = {}
        for ens in enseignants_list:
            matricule = ens.get('matricule', 'INCONNU')
            try:
                path  = self.generate(ens)
                token = self.last_token
                b64   = self.to_base64(path)
                results[matricule] = {
                    'path':   path,
                    'token':  token,
                    'base64': b64,
                }
            except Exception as exc:
                logger.error(
                    "generate_all : erreur pour matricule=%s — %s",
                    matricule, exc
                )
                results[matricule] = {'error': str(exc)}

        logger.info(
            "generate_all terminé : %d QR code(s) généré(s).",
            sum(1 for v in results.values() if 'error' not in v)
        )
        return results


# ============================================================
#  Instance globale partagée
# ============================================================
qr_gen = QRGenerator()
