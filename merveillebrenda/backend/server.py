# ============================================================
#  UniPresence Pro — IUE Douala
#  Serveur HTTP natif Python — point d'entrée principal
# ============================================================

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from http.server import HTTPServer, BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import urllib.parse
import mimetypes
import traceback
import io
import csv
import zipfile
from datetime import datetime, date, timedelta
from math import ceil

from config import SERVER_HOST, SERVER_PORT, FRONTEND_DIR, IMAGE_DIR, QR_DIR
from database import DatabaseHelper
from auth import (
    create_session, get_session, delete_session,
    check_rate_limit, record_failed_attempt, reset_attempts,
    get_token_from_request, verify_password, hash_password
)
from qr_generator import QRGenerator
from pdf_exporter import PDFExporter
from presence_handler import PresenceHandler


# ============================================================
#  Handler principal
# ============================================================

class UniPresenceHandler(BaseHTTPRequestHandler):

    # ----------------------------------------------------------
    # Méthodes utilitaires
    # ----------------------------------------------------------

    def log_message(self, format, *args):
        # Loguer uniquement les appels API (POST/PUT/DELETE) — pas le bruit des assets
        if self.command in ('POST', 'PUT', 'DELETE'):
            code = args[1] if len(args) > 1 else '---'
            try:
                msg = f'[{self.log_date_time_string()}] {self.command} {self.path} -> {code}'
                print(msg, flush=True)
            except Exception:
                pass  # Ne jamais laisser un log crasher la réponse HTTP

    def add_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin',
                         self.headers.get('Origin', '*'))
        self.send_header('Access-Control-Allow-Credentials', 'true')
        self.send_header('Access-Control-Allow-Methods',
                         'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers',
                         'Content-Type, Cookie')

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False,
                          default=str).encode('utf-8')
        self.send_response(status)
        self.add_cors_headers()
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, message, status=400):
        self.send_json({'erreur': message, 'succes': False}, status)

    def send_bytes(self, data, content_type, filename=None):
        self.send_response(200)
        self.add_cors_headers()
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', len(data))
        if filename:
            self.send_header('Content-Disposition',
                             f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(data)

    def send_html_file(self, filepath):
        try:
            with open(filepath, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.add_cors_headers()
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'404 Not Found')

    def send_static_file(self, filepath):
        try:
            mime_type, _ = mimetypes.guess_type(filepath)
            mime_type = mime_type or 'application/octet-stream'
            with open(filepath, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.add_cors_headers()
            self.send_header('Content-Type', mime_type)
            self.send_header('Content-Length', len(content))
            self.send_header('Cache-Control', 'public, max-age=3600')
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()

    def read_body(self):
        length = int(self.headers.get('Content-Length', 0))
        if length == 0:
            return {}
        body = self.rfile.read(length)
        try:
            return json.loads(body.decode('utf-8'))
        except Exception:
            return {}

    def get_query_params(self):
        parsed = urllib.parse.urlparse(self.path)
        return dict(urllib.parse.parse_qsl(parsed.query))

    def get_client_ip(self):
        return self.headers.get('X-Forwarded-For',
                                self.client_address[0])

    def require_auth(self):
        token = get_token_from_request(self)
        if not token:
            return None
        return get_session(token)

    def redirect(self, location):
        self.send_response(302)
        self.send_header('Location', location)
        self.end_headers()

    def get_path(self):
        return urllib.parse.urlparse(self.path).path

    # ----------------------------------------------------------
    # OPTIONS (preflight CORS)
    # ----------------------------------------------------------

    def do_OPTIONS(self):
        self.send_response(204)
        self.add_cors_headers()
        self.end_headers()

    # ----------------------------------------------------------
    # GET
    # ----------------------------------------------------------

    def do_GET(self):
        path = self.get_path()

        try:
            # Pages HTML publiques
            if path == '/':
                self.send_html_file(
                    os.path.join(FRONTEND_DIR, 'index.html'))
            elif path == '/connexion':
                self.send_html_file(
                    os.path.join(FRONTEND_DIR, 'connexion.html'))
            elif path == '/a_propos':
                self.send_html_file(
                    os.path.join(FRONTEND_DIR, 'a_propos.html'))
            elif path == '/scanner':
                self.send_html_file(
                    os.path.join(FRONTEND_DIR, 'scanner.html'))

            # Pages protégées
            elif path in ['/dashboard', '/professeurs', '/formulaire',
                          '/seances', '/rapport', '/qr_codes']:
                session = self.require_auth()
                if not session:
                    self.redirect('/connexion')
                    return
                page_map = {
                    '/dashboard':   'dashboard.html',
                    '/professeurs': 'professeurs.html',
                    '/formulaire':  'formulaire.html',
                    '/seances':     'seances.html',
                    '/rapport':     'rapport.html',
                    '/qr_codes':    'qr_codes.html',
                }
                self.send_html_file(
                    os.path.join(FRONTEND_DIR, page_map[path]))

            # Assets statiques
            elif path.startswith('/assets/'):
                filepath = os.path.join(FRONTEND_DIR, path.lstrip('/'))
                self.send_static_file(filepath)
            elif path.startswith('/image/'):
                filepath = os.path.join(IMAGE_DIR, path[7:])
                self.send_static_file(filepath)

            # API
            elif path == '/api/me':
                self._api_me()
            elif path == '/api/enseignants':
                self._api_get_enseignants()
            elif (path.startswith('/api/enseignants/')
                  and path.endswith('/qr/pdf')):
                parts = path.split('/')
                if len(parts) >= 4 and parts[3].isdigit():
                    self._api_get_qr_pdf(int(parts[3]))
                else:
                    self.send_error_json('ID invalide')
            elif (path.startswith('/api/enseignants/')
                  and path.endswith('/qr')
                  and '/qr/' not in path):
                parts = path.split('/')
                if len(parts) >= 4 and parts[3].isdigit():
                    self._api_get_qr(int(parts[3]))
                else:
                    self.send_error_json('ID invalide')
            elif path == '/api/enseignants/qr/export':
                self._api_export_qr_pdf()
            elif path == '/api/enseignants/qr/zip':
                self._api_export_qr_zip()
            elif (path.startswith('/api/enseignants/')
                  and path.count('/') == 3):
                eid = path.split('/')[3]
                if eid.isdigit():
                    self._api_get_enseignant(int(eid))
                else:
                    self.send_error_json('ID invalide')
            elif path == '/api/seances':
                self._api_get_seances()
            elif (path.startswith('/api/seances/')
                  and path.count('/') == 3):
                try:
                    self._api_get_seance(int(path.split('/')[3]))
                except ValueError:
                    self.send_error_json('ID invalide')
            elif path == '/api/presences':
                self._api_get_presences()
            elif path == '/api/presences/stats':
                self._api_presences_stats()
            elif path == '/api/rapport':
                self._api_rapport()
            elif path == '/api/rapport/pdf':
                self._api_rapport_pdf()
            elif path == '/api/rapport/csv':
                self._api_rapport_csv()
            elif path == '/api/dashboard/stats':
                self._api_dashboard_stats()
            else:
                self.send_error_json('Route non trouvée', 404)

        except Exception:
            traceback.print_exc()
            self.send_error_json('Erreur interne du serveur', 500)

    # ----------------------------------------------------------
    # POST
    # ----------------------------------------------------------

    def do_POST(self):
        path = self.get_path()
        try:
            if path == '/api/login':
                self._api_login()
            elif path == '/api/logout':
                self._api_logout()
            elif path == '/api/enseignants':
                self._api_create_enseignant()
            elif (path.startswith('/api/enseignants/')
                  and path.endswith('/qr')):
                parts = path.split('/')
                if len(parts) >= 4 and parts[3].isdigit():
                    self._api_regenerer_qr(int(parts[3]))
                else:
                    self.send_error_json('ID invalide')
            elif path == '/api/seances':
                self._api_create_seance()
            elif path in ('/api/presences/scan',
                          '/api/presences/camera'):
                self._api_scan()
            elif path == '/api/presences/scan_image':
                self._api_scan_image()
            elif path == '/api/presences/manuel':
                self._api_pointage_manuel()
            else:
                self.send_error_json('Route non trouvée', 404)
        except Exception:
            traceback.print_exc()
            self.send_error_json('Erreur interne du serveur', 500)

    # ----------------------------------------------------------
    # PUT
    # ----------------------------------------------------------

    def do_PUT(self):
        path = self.get_path()
        try:
            if (path.startswith('/api/enseignants/')
                    and path.count('/') == 3):
                eid = path.split('/')[3]
                if eid.isdigit():
                    self._api_update_enseignant(int(eid))
                else:
                    self.send_error_json('ID invalide')
            elif (path.startswith('/api/seances/')
                  and path.count('/') == 3):
                sid = path.split('/')[3]
                if sid.isdigit():
                    self._api_update_seance(int(sid))
                else:
                    self.send_error_json('ID invalide')
            else:
                self.send_error_json('Route non trouvée', 404)
        except Exception:
            traceback.print_exc()
            self.send_error_json('Erreur interne du serveur', 500)

    # ----------------------------------------------------------
    # DELETE
    # ----------------------------------------------------------

    def do_DELETE(self):
        path = self.get_path()
        try:
            if (path.startswith('/api/enseignants/')
                    and path.count('/') == 3):
                eid = path.split('/')[3]
                if eid.isdigit():
                    self._api_delete_enseignant(int(eid))
                else:
                    self.send_error_json('ID invalide')
            elif (path.startswith('/api/seances/')
                  and path.count('/') == 3):
                sid = path.split('/')[3]
                if sid.isdigit():
                    self._api_delete_seance(int(sid))
                else:
                    self.send_error_json('ID invalide')
            else:
                self.send_error_json('Route non trouvée', 404)
        except Exception:
            traceback.print_exc()
            self.send_error_json('Erreur interne du serveur', 500)

    # ==========================================================
    #  Implémentations des routes API
    # ==========================================================

    # ----------------------------------------------------------
    # AUTH
    # ----------------------------------------------------------

    def _api_login(self):
        ip = self.get_client_ip()
        if not check_rate_limit(ip):
            self.send_error_json(
                'Trop de tentatives. Réessayez dans 10 minutes.', 429)
            return

        data = self.read_body()
        email = data.get('email', '').strip().lower()
        mot_de_passe = data.get('mot_de_passe', '')

        db = DatabaseHelper()
        admin = db.fetch_one(
            'SELECT * FROM admins WHERE email = %s', (email,))

        if not admin or not verify_password(mot_de_passe,
                                            admin['mot_de_passe']):
            record_failed_attempt(ip)
            self.send_error_json('Email ou mot de passe incorrect', 401)
            return

        reset_attempts(ip)
        token = create_session(
            admin['id'], admin['email'], admin['nom'], ip)

        # Persister la session en base
        expires = (datetime.now() + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')
        try:
            db.insert('sessions_admin', {
                'admin_id':   admin['id'],
                'token':      token,
                'expires_at': expires,
                'adresse_ip': ip,
            })
        except Exception:
            pass  # La session en mémoire suffit si la table n'existe pas

        body = json.dumps({
            'succes': True,
            'admin': {
                'id':     admin['id'],
                'nom':    admin.get('nom', ''),
                'prenom': admin.get('prenom', ''),
                'email':  admin['email'],
            },
        }, ensure_ascii=False).encode('utf-8')

        self.send_response(200)
        self.add_cors_headers()
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Set-Cookie',
                         f'session_token={token}; HttpOnly; Path=/; SameSite=Lax; Max-Age=28800')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def _api_logout(self):
        token = get_token_from_request(self)
        if token:
            delete_session(token)
            try:
                db = DatabaseHelper()
                db.execute(
                    'DELETE FROM sessions_admin WHERE token = %s',
                    (token,))
            except Exception:
                pass

        self.send_response(200)
        self.add_cors_headers()
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header(
            'Set-Cookie',
            'session_token=; HttpOnly; Path=/; SameSite=Lax; Max-Age=0')
        body = json.dumps(
            {'succes': True}, ensure_ascii=False).encode('utf-8')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def _api_me(self):
        session = self.require_auth()
        if not session:
            self.send_error_json('Non authentifié', 401)
            return
        self.send_json({'admin': session})

    # ----------------------------------------------------------
    # ENSEIGNANTS
    # ----------------------------------------------------------

    def _api_get_enseignants(self):
        session = self.require_auth()
        if not session:
            self.send_error_json('Non authentifié', 401)
            return

        params = self.get_query_params()
        departement = params.get('departement', '').strip()
        actif       = params.get('actif', '').strip()
        grade       = params.get('grade', '').strip()
        search      = params.get('search', '').strip()

        conditions = []
        values = []

        # Par défaut : n'afficher que les enseignants actifs
        # sauf si le paramètre actif est explicitement passé (ex: actif=0 pour l'archive)
        if actif != '':
            conditions.append('est_actif = %s')
            values.append(int(actif))
        else:
            conditions.append('est_actif = 1')

        if departement:
            conditions.append('departement = %s')
            values.append(departement)
        if grade:
            conditions.append('grade = %s')
            values.append(grade)
        if search:
            conditions.append(
                '(nom LIKE %s OR prenom LIKE %s OR email LIKE %s OR matricule LIKE %s)')
            like = f'%{search}%'
            values.extend([like, like, like, like])

        today = date.today().isoformat()

        # Préfixer les conditions WHERE avec 'e.' pour lever les ambiguïtés
        prefixed = []
        for c in conditions:
            c = c.replace('departement', 'e.departement')
            c = c.replace('est_actif',   'e.est_actif')
            c = c.replace('grade',       'e.grade')
            c = c.replace('nom',         'e.nom')
            c = c.replace('prenom',      'e.prenom')
            c = c.replace('email',       'e.email')
            c = c.replace('matricule',   'e.matricule')
            prefixed.append(c)
        where = ('WHERE ' + ' AND '.join(prefixed)) if prefixed else ''

        db = DatabaseHelper()
        # UNE seule requête avec LEFT JOIN → 1 connexion au lieu de 2
        # La photo (base64 volumineux) est exclue — retournée uniquement sur GET /id
        enseignants = db.fetch_all(
            f"""SELECT e.id, e.nom, e.prenom, e.email, e.telephone, e.departement,
                       e.specialite, e.grade, e.date_inscription, e.est_actif,
                       e.matricule, e.qr_code_path,
                       CASE WHEN p.enseignant_id IS NOT NULL THEN 1 ELSE 0 END
                            AS present_aujourd_hui
                FROM enseignants e
                LEFT JOIN (
                    SELECT DISTINCT enseignant_id
                    FROM presences
                    WHERE date_pointage = %s AND type_pointage = 'ARRIVEE'
                ) p ON p.enseignant_id = e.id
                {where} ORDER BY e.nom, e.prenom""",
            (today,) + tuple(values))

        self.send_json({'enseignants': enseignants, 'total': len(enseignants)})

    def _api_get_enseignant(self, eid):
        session = self.require_auth()
        if not session:
            self.send_error_json('Non authentifié', 401)
            return
        db = DatabaseHelper()
        enseignant = db.fetch_one(
            'SELECT * FROM enseignants WHERE id = %s', (eid,))
        if not enseignant:
            self.send_error_json('Enseignant introuvable', 404)
            return
        self.send_json({'enseignant': enseignant})

    def _api_create_enseignant(self):
        session = self.require_auth()
        if not session:
            self.send_error_json('Non authentifié', 401)
            return

        data = self.read_body()
        db   = DatabaseHelper()

        # Générer le matricule à partir du prochain id SQLite réel
        # sqlite_sequence garde la dernière valeur auto-increment utilisée
        seq_row = db.fetch_one(
            "SELECT seq FROM sqlite_sequence WHERE name='enseignants'")
        next_id = (seq_row['seq'] if seq_row else 0) + 1
        matricule = f"IUE-{datetime.now().year}-{next_id:04d}"
        # Vérifier que ce matricule n'existe pas déjà (sécurité anti-collision)
        while db.fetch_one('SELECT id FROM enseignants WHERE matricule = %s', (matricule,)):
            next_id += 1
            matricule = f"IUE-{datetime.now().year}-{next_id:04d}"

        record = {
            'matricule':       matricule,
            'nom':             data.get('nom', ''),
            'prenom':          data.get('prenom', ''),
            'email':           data.get('email', ''),
            'telephone':       data.get('telephone', ''),
            'specialite':      data.get('specialite', ''),
            'departement':     data.get('departement', ''),
            'grade':           data.get('grade', ''),
            'date_inscription': data.get(
                'date_inscription', date.today().isoformat()),
            'est_actif':       1,
        }
        # Inclure la photo si fournie (base64)
        photo_b64 = data.get('photo_base64', '')
        if photo_b64:
            record['photo'] = photo_b64

        eid = db.insert('enseignants', record)
        if not eid:
            self.send_error_json(
                'Échec de l\'enregistrement — vérifiez que le département '
                '(ESIT / EME / ADMIN) et le grade sont valides.', 400)
            return
        record['id'] = eid

        # Générer le QR code
        qr_base64 = None
        try:
            qr_gen  = QRGenerator()
            qr_path = qr_gen.generate({
                'id':        eid,
                'matricule': matricule,
                'nom':       record['nom'],
                'prenom':    record['prenom'],
            })
            db.execute(
                'UPDATE enseignants SET qr_code_path=%s, qr_code_data=%s WHERE id=%s',
                (qr_path, qr_gen.last_qr_data, eid))
            qr_base64 = qr_gen.to_base64(qr_path)
            record['qr_code_path'] = qr_path
        except Exception:
            traceback.print_exc()

        self.send_json({
            'succes':      True,
            'enseignant':  record,
            'qr_base64':   qr_base64,
        })

    def _api_update_enseignant(self, eid):
        session = self.require_auth()
        if not session:
            self.send_error_json('Non authentifié', 401)
            return
        data = self.read_body()
        allowed = ['nom', 'prenom', 'email', 'telephone',
                   'specialite', 'departement', 'grade',
                   'date_inscription', 'est_actif', 'photo']
        updates = {k: v for k, v in data.items() if k in allowed}
        if not updates:
            self.send_error_json('Aucune donnée à mettre à jour')
            return
        db = DatabaseHelper()
        db.update('enseignants', updates, 'id = %s', (eid,))
        enseignant = db.fetch_one(
            'SELECT * FROM enseignants WHERE id = %s', (eid,))
        self.send_json({'succes': True, 'enseignant': enseignant})

    def _api_delete_enseignant(self, eid):
        session = self.require_auth()
        if not session:
            self.send_error_json('Non authentifié', 401)
            return
        db = DatabaseHelper()
        db.update('enseignants', {'est_actif': 0}, 'id = %s', (eid,))
        self.send_json({'succes': True, 'message': 'Enseignant désactivé'})

    # ----------------------------------------------------------
    # QR CODES
    # ----------------------------------------------------------

    def _api_get_qr(self, eid):
        session = self.require_auth()
        if not session:
            self.send_error_json('Non authentifié', 401)
            return
        db = DatabaseHelper()
        enseignant = db.fetch_one(
            'SELECT * FROM enseignants WHERE id = %s', (eid,))
        if not enseignant:
            self.send_error_json('Enseignant introuvable', 404)
            return

        qr_gen = QRGenerator()
        qr_path = qr_gen.get_qr_path(enseignant['matricule'])

        if not os.path.exists(qr_path):
            qr_path = qr_gen.generate({
                'id':        eid,
                'matricule': enseignant['matricule'],
                'nom':       enseignant['nom'],
                'prenom':    enseignant['prenom'],
            })
            db.execute(
                'UPDATE enseignants SET qr_code_path=%s, qr_code_data=%s WHERE id=%s',
                (qr_path, qr_gen.last_qr_data, eid))

        qr_base64 = qr_gen.to_base64(qr_path)
        self.send_json({
            'qr_base64': qr_base64,
            'matricule': enseignant['matricule'],
            'nom':       enseignant['nom'],
            'prenom':    enseignant['prenom'],
        })

    def _api_get_qr_pdf(self, eid):
        """Retourne un PDF A4 du QR code individuel avec logo IUE."""
        session = self.require_auth()
        if not session:
            self.send_error_json('Non authentifié', 401)
            return
        db  = DatabaseHelper()
        ens = db.fetch_one('SELECT * FROM enseignants WHERE id = %s', (eid,))
        if not ens:
            self.send_error_json('Enseignant introuvable', 404)
            return
        # Générer le QR s'il n'existe pas
        qr_gen  = QRGenerator()
        qr_path = qr_gen.get_qr_path(ens['matricule'])
        if not os.path.exists(qr_path):
            qr_path = qr_gen.generate({'id': eid, 'matricule': ens['matricule'],
                                       'nom': ens['nom'], 'prenom': ens['prenom']})
            db.execute('UPDATE enseignants SET qr_code_path=%s, qr_code_data=%s WHERE id=%s',
                       (qr_path, qr_gen.last_qr_data, eid))
        pdf_bytes = PDFExporter().export_single_qr_pdf(ens)
        safe_nom  = (ens.get('nom', '') + '_' + ens.get('prenom', '')).replace(' ', '_')
        filename  = f"qr_{ens.get('matricule','IUE')}_{safe_nom}.pdf"
        self.send_bytes(pdf_bytes, 'application/pdf', filename)

    def _api_regenerer_qr(self, eid):
        session = self.require_auth()
        if not session:
            self.send_error_json('Non authentifié', 401)
            return
        db = DatabaseHelper()
        enseignant = db.fetch_one(
            'SELECT * FROM enseignants WHERE id = %s', (eid,))
        if not enseignant:
            self.send_error_json('Enseignant introuvable', 404)
            return

        qr_gen  = QRGenerator()
        qr_path = qr_gen.generate({
            'id':        eid,
            'matricule': enseignant['matricule'],
            'nom':       enseignant['nom'],
            'prenom':    enseignant['prenom'],
        })
        db.execute(
            'UPDATE enseignants SET qr_code_path=%s, qr_code_data=%s WHERE id=%s',
            (qr_path, qr_gen.last_qr_data, eid))
        qr_base64 = qr_gen.to_base64(qr_path)
        self.send_json({'succes': True, 'qr_base64': qr_base64})

    def _api_export_qr_pdf(self):
        session = self.require_auth()
        if not session:
            self.send_error_json('Non authentifié', 401)
            return
        db  = DatabaseHelper()
        qrg = QRGenerator()
        enseignants = db.fetch_all(
            'SELECT * FROM enseignants WHERE est_actif=1 ORDER BY nom')
        # Auto-générer les QR codes manquants avant d'inclure dans le PDF
        for ens in enseignants:
            qr_path = qrg.get_qr_path(ens['matricule'])
            if not os.path.isfile(qr_path):
                try:
                    qr_path = qrg.generate({
                        'id':        ens['id'],
                        'matricule': ens['matricule'],
                        'nom':       ens['nom'],
                        'prenom':    ens['prenom'],
                    })
                    db.execute(
                        'UPDATE enseignants SET qr_code_path=?, qr_code_data=? WHERE id=?',
                        (qr_path, qrg.last_qr_data, ens['id'])
                    )
                    ens['qr_code_path'] = qr_path
                except Exception:
                    traceback.print_exc()
        pdf_bytes = PDFExporter().export_qr_codes_pdf(enseignants)
        filename = f'qr_codes_enseignants_{date.today().strftime("%Y%m%d")}.pdf'
        self.send_bytes(pdf_bytes, 'application/pdf', filename)

    def _api_export_qr_zip(self):
        session = self.require_auth()
        if not session:
            self.send_error_json('Non authentifié', 401)
            return
        db  = DatabaseHelper()
        qrg = QRGenerator()
        enseignants = db.fetch_all(
            'SELECT * FROM enseignants WHERE est_actif=1 ORDER BY nom')
        # Auto-générer les QR codes manquants avant de zipper
        for ens in enseignants:
            qr_path = qrg.get_qr_path(ens['matricule'])
            if not os.path.isfile(qr_path):
                try:
                    qr_path = qrg.generate({
                        'id':        ens['id'],
                        'matricule': ens['matricule'],
                        'nom':       ens['nom'],
                        'prenom':    ens['prenom'],
                    })
                    db.execute(
                        'UPDATE enseignants SET qr_code_path=?, qr_code_data=? WHERE id=?',
                        (qr_path, qrg.last_qr_data, ens['id'])
                    )
                    ens['qr_code_path'] = qr_path
                except Exception:
                    traceback.print_exc()
        zip_bytes = PDFExporter().export_qr_zip(enseignants)
        filename = f'qr_codes_iue_{date.today().strftime("%Y%m%d")}.zip'
        self.send_bytes(zip_bytes, 'application/zip', filename)

    # ----------------------------------------------------------
    # SÉANCES
    # ----------------------------------------------------------

    def _api_get_seances(self):
        # Lecture publique des séances (nécessaire pour le scanner kiosque)
        params        = self.get_query_params()
        date_filtre   = params.get('date', '').strip()
        ens_id        = params.get('enseignant_id', '').strip()
        statut        = params.get('statut', '').strip()

        conditions = []
        values     = []

        if date_filtre:
            conditions.append('s.date_seance = %s')
            values.append(date_filtre)
        if ens_id:
            conditions.append('s.enseignant_id = %s')
            values.append(int(ens_id))
        if statut:
            conditions.append('s.statut = %s')
            values.append(statut)

        where = ('WHERE ' + ' AND '.join(conditions)) if conditions else ''
        sql = f"""
            SELECT s.*, e.nom AS enseignant_nom, e.prenom AS enseignant_prenom,
                   e.departement, e.matricule
            FROM seances s
            LEFT JOIN enseignants e ON s.enseignant_id = e.id
            {where}
            ORDER BY s.date_seance DESC, s.heure_debut DESC
        """
        db      = DatabaseHelper()
        seances = db.fetch_all(sql, tuple(values))
        self.send_json({'seances': seances})

    def _api_get_seance(self, sid):
        session = self.require_auth()
        if not session:
            self.send_error_json('Non authentifié', 401)
            return
        db = DatabaseHelper()
        seance = db.fetch_one(
            """SELECT s.*, e.nom AS enseignant_nom, e.prenom AS enseignant_prenom
               FROM seances s
               LEFT JOIN enseignants e ON s.enseignant_id = e.id
               WHERE s.id = %s""", (sid,))
        if not seance:
            self.send_error_json('Séance introuvable', 404)
            return
        self.send_json({'seance': seance})

    def _api_create_seance(self):
        session = self.require_auth()
        if not session:
            self.send_error_json('Non authentifié', 401)
            return
        data = self.read_body()
        allowed = ['titre', 'matiere', 'enseignant_id', 'salle',
                   'date_seance', 'heure_debut', 'heure_fin',
                   'type_seance', 'statut']
        record = {k: v for k, v in data.items() if k in allowed}
        if 'statut' not in record:
            record['statut'] = 'planifiee'
        db  = DatabaseHelper()
        sid = db.insert('seances', record)
        record['id'] = sid
        self.send_json({'succes': True, 'seance': record})

    def _api_update_seance(self, sid):
        session = self.require_auth()
        if not session:
            self.send_error_json('Non authentifié', 401)
            return
        data = self.read_body()
        allowed = ['titre', 'matiere', 'enseignant_id', 'salle',
                   'date_seance', 'heure_debut', 'heure_fin',
                   'type_seance', 'statut']
        updates = {k: v for k, v in data.items() if k in allowed}
        if not updates:
            self.send_error_json('Aucune donnée à mettre à jour')
            return
        db = DatabaseHelper()
        db.update('seances', updates, 'id = %s', (sid,))
        seance = db.fetch_one('SELECT * FROM seances WHERE id = %s', (sid,))
        self.send_json({'succes': True, 'seance': seance})

    def _api_delete_seance(self, sid):
        session = self.require_auth()
        if not session:
            self.send_error_json('Non authentifié', 401)
            return
        db = DatabaseHelper()
        db.execute('DELETE FROM seances WHERE id = %s', (sid,))
        self.send_json({'succes': True, 'message': 'Séance supprimée'})

    # ----------------------------------------------------------
    # PRÉSENCES / SCAN
    # ----------------------------------------------------------

    def _api_scan(self):
        data     = self.read_body()
        qr_data  = data.get('qr_data')
        seance_id = data.get('seance_id')
        mode     = data.get('mode', 'QR_CODE')
        ip       = self.get_client_ip()
        result   = PresenceHandler().scan_qr(qr_data, seance_id, mode, ip)
        self.send_json(result)

    def _api_scan_image(self):
        """
        Décode un QR code depuis une image uploadée (base64 JSON).
        Détection multi-stratégies : fonctionne quelle que soit la distance,
        l'éclairage ou la taille du QR dans le frame (page entière ou gros plan).
        Corps attendu : { "image_base64": "data:image/jpeg;base64,..." , "seance_id": null }
        """
        import base64
        try:
            import numpy as np
            import cv2 as _cv2
        except ImportError:
            self.send_error_json(
                'OpenCV et NumPy sont requis pour le scan caméra. '
                'Installez-les avec : pip install opencv-python numpy', 503)
            return

        data      = self.read_body()
        image_b64 = data.get('image_base64', '')
        seance_id = data.get('seance_id')
        ip        = self.get_client_ip()

        if not image_b64:
            self.send_error_json('Aucune image reçue (image_base64 manquant)', 400)
            return

        if ',' in image_b64:
            image_b64 = image_b64.split(',', 1)[1]

        try:
            img_bytes = base64.b64decode(image_b64)
            nparr     = np.frombuffer(img_bytes, np.uint8)
            img       = _cv2.imdecode(nparr, _cv2.IMREAD_COLOR)
        except Exception as exc:
            self.send_error_json(f'Image illisible : {exc}', 400)
            return

        if img is None:
            self.send_error_json('Format image non supporté', 400)
            return

        # ── Moteur de détection 2 phases : locate → crop → decode ────
        #
        # Principe : detect() est ~4× plus rapide que detectAndDecode().
        # On l'utilise pour LOCALISER le QR sur une image agrandie, puis on
        # ne lance detectAndDecode() que sur le petit crop recadré — quelques
        # centaines de pixels au lieu de megapixels. Gain : ×5 à ×20.
        #
        detector = _cv2.QRCodeDetector()

        def _crop_and_decode(image, points):
            """
            Recadre la zone QR détectée (avec marge), l'agrandit si besoin
            à 400px minimum, et lance detectAndDecode sur ce petit crop.
            """
            if points is None:
                return ''
            pts = np.array(points[0], dtype=np.int32)
            h_img, w_img = image.shape[:2]
            x0, y0 = pts.min(axis=0)
            x1, y1 = pts.max(axis=0)
            margin = max(20, int(max(x1 - x0, y1 - y0) * 0.25))
            x0 = max(0, x0 - margin)
            y0 = max(0, y0 - margin)
            x1 = min(w_img, x1 + margin)
            y1 = min(h_img, y1 + margin)
            crop = image[y0:y1, x0:x1]
            if crop.size == 0:
                return ''
            # Garantir au moins 400px sur le grand côté pour que le décodeur
            # puisse lire les modules du QR code sans ambiguïté
            cw, ch = crop.shape[1], crop.shape[0]
            if max(cw, ch) < 400:
                sc   = 400 / max(cw, ch)
                crop = _cv2.resize(crop,
                                   (int(cw * sc), int(ch * sc)),
                                   interpolation=_cv2.INTER_CUBIC)
            try:
                text, _, _ = detector.detectAndDecode(crop)
                return text or ''
            except Exception:
                return ''

        def _try_on(image):
            """
            Stratégie 2 temps :
            1. detect() rapide pour savoir si un QR est présent (78ms vs 192ms)
            2a. Si trouvé → crop + decode (quelques ms sur la petite région)
            2b. Si le crop échoue → detectAndDecode sur toute l'image (robuste)
            3. Si detect() ne trouve rien → on ne perd pas de temps à décoder
            """
            try:
                gray = (_cv2.cvtColor(image, _cv2.COLOR_BGR2GRAY)
                        if len(image.shape) == 3 else image)
                found, points = detector.detect(gray)
                if found and points is not None:
                    # Essai rapide : decode sur le crop recadré
                    text = _crop_and_decode(image, points)
                    if text:
                        return text
                    # Le crop a échoué (contexte insuffisant) — fallback direct
                    try:
                        text, _, _ = detector.detectAndDecode(image)
                        return text or ''
                    except Exception:
                        return ''
            except Exception:
                pass
            return ''

        h0, w0  = img.shape[:2]
        gray0   = _cv2.cvtColor(img, _cv2.COLOR_BGR2GRAY)
        kernel  = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
        mh, mw  = h0 // 2, w0 // 2
        regions = [                              # quadrants : bas-droite en 1er
            (mh, h0, mw, w0), (0, mh, 0, mw),   # bas-droite, haut-gauche
            (mh, h0, 0, mw),  (0, mh, mw, w0),  # bas-gauche, haut-droite
        ]
        qr_data = ''

        # ── ÉTAPE 1 : original 640px ──────────────────────────────
        # detect() 78ms + crop-decode ~20ms  ≈ 100ms (QR ≥ ~200px)
        qr_data = _try_on(img)

        # ── ÉTAPE 2 : upscale ×2 CUBIC (QR mi-distance) ──────────
        if not qr_data:
            qr_data = _try_on(
                _cv2.resize(img, (w0 * 2, h0 * 2),
                            interpolation=_cv2.INTER_CUBIC))

        # ── ÉTAPE 3 : sharpen ×2 (image floue / artefacts JPEG) ──
        if not qr_data:
            qr_data = _try_on(
                _cv2.resize(_cv2.filter2D(gray0, -1, kernel),
                            (w0 * 2, h0 * 2),
                            interpolation=_cv2.INTER_CUBIC))

        # ── ÉTAPES 4-7 : quadrants ×2 CUBIC (QR dans un coin) ────
        # Quadrant 320×240 → ×2 → 640×480 : même taille qu'un frame
        # normal, donc detect+crop rapide. Couvre les QR de ~150px.
        if not qr_data:
            for r0, r1, c0, c1 in regions:
                quad    = img[r0:r1, c0:c1]
                qr_data = _try_on(
                    _cv2.resize(quad,
                                (quad.shape[1] * 2, quad.shape[0] * 2),
                                interpolation=_cv2.INTER_CUBIC))
                if qr_data:
                    break

        # ── ÉTAPES 8-11 : quadrants ×4 CUBIC — detectAndDecode direct
        # Pour les QR de ~96px (page PDF entière face caméra).
        # A cette échelle, detect() seul est insuffisant ; on lance
        # detectAndDecode directement sur le quadrant ×4 CUBIC.
        # Coût : ~360ms/quadrant, mais on s'arrête dès la 1re réussite.
        if not qr_data:
            for r0, r1, c0, c1 in regions:
                quad = img[r0:r1, c0:c1]
                qup4 = _cv2.resize(quad,
                                   (quad.shape[1] * 4, quad.shape[0] * 4),
                                   interpolation=_cv2.INTER_CUBIC)
                try:
                    text, _, _ = detector.detectAndDecode(qup4)
                    if text:
                        qr_data = text
                        break
                except Exception:
                    pass

        # ── ÉTAPE 12 : OTSU ×2 (fond non uniforme, faible contraste) ─
        if not qr_data:
            _, otsu = _cv2.threshold(gray0, 0, 255,
                                     _cv2.THRESH_BINARY + _cv2.THRESH_OTSU)
            qr_data = _try_on(
                _cv2.resize(otsu, (w0 * 2, h0 * 2),
                            interpolation=_cv2.INTER_CUBIC))

        # ── ÉTAPE 13 : fallback detectAndDecode brut ─────────────
        if not qr_data:
            for variant in [
                gray0,
                _cv2.equalizeHist(gray0),
            ]:
                try:
                    text, _, _ = detector.detectAndDecode(variant)
                    if text:
                        qr_data = text
                        break
                except Exception:
                    pass

        # ── ÉTAPE 9 : WeChatQRCode (OpenCV contrib) si disponible ──
        if not qr_data:
            try:
                wechat   = _cv2.wechat_qrcode_WeChatQRCode()
                texts, _ = wechat.detectAndDecode(img)
                if texts:
                    qr_data = texts[0]
            except Exception:
                pass

        if not qr_data:
            self.send_json({
                'succes':      False,
                'qr_detecte':  False,
                'message':     'Aucun QR code détecté dans l\'image.',
                'enseignant':  None,
                'heure':       None,
                'statut':      None,
            })
            return

        # ── Pipeline de pointage ───────────────────────────────────
        result = PresenceHandler().scan_qr(qr_data, seance_id, 'QR_CODE', ip)
        result['qr_detecte'] = True
        self.send_json(result)

    def _api_pointage_manuel(self):
        session = self.require_auth()
        if not session:
            self.send_error_json('Non authentifié', 401)
            return
        data   = self.read_body()
        result = PresenceHandler().enregistrer_pointage(
            enseignant_id=data.get('enseignant_id'),
            seance_id=data.get('seance_id'),
            type_pointage=data.get('type_pointage', 'ARRIVEE'),
            mode='MANUEL',
            ip=self.get_client_ip(),
            commentaire=data.get('commentaire', ''),
        )
        self.send_json(result)

    def _api_get_presences(self):
        session = self.require_auth()
        if not session:
            self.send_error_json('Non authentifié', 401)
            return

        params       = self.get_query_params()
        ens_id       = params.get('enseignant_id', '').strip()
        date_debut   = params.get('date_debut', '').strip()
        date_fin     = params.get('date_fin', '').strip()
        departement  = params.get('departement', '').strip()
        statut       = params.get('statut', '').strip()
        page         = max(1, int(params.get('page', 1)))
        limit        = max(1, min(100, int(params.get('limit', 20))))

        conditions = []
        values     = []

        if ens_id:
            conditions.append('p.enseignant_id = %s')
            values.append(int(ens_id))
        if date_debut:
            conditions.append('DATE(p.date_pointage) >= %s')
            values.append(date_debut)
        if date_fin:
            conditions.append('DATE(p.date_pointage) <= %s')
            values.append(date_fin)
        if departement:
            conditions.append('e.departement = %s')
            values.append(departement)
        if statut:
            conditions.append('p.statut = %s')
            values.append(statut)

        where = ('WHERE ' + ' AND '.join(conditions)) if conditions else ''

        db = DatabaseHelper()
        count_row = db.fetch_one(
            f"""SELECT COUNT(*) as cnt
                FROM presences p
                LEFT JOIN enseignants e ON p.enseignant_id = e.id
                LEFT JOIN seances s ON p.seance_id = s.id
                {where}""",
            tuple(values))
        total = count_row['cnt'] if count_row else 0
        pages = ceil(total / limit) if total else 1

        offset = (page - 1) * limit
        presences = db.fetch_all(
            f"""SELECT p.*, e.nom, e.prenom, e.matricule, e.departement,
                       s.titre AS seance_titre, s.matiere
                FROM presences p
                LEFT JOIN enseignants e ON p.enseignant_id = e.id
                LEFT JOIN seances s ON p.seance_id = s.id
                {where}
                ORDER BY p.date_pointage DESC, p.heure_pointage DESC
                LIMIT %s OFFSET %s""",
            tuple(values) + (limit, offset))

        self.send_json({
            'presences': presences,
            'total':     total,
            'page':      page,
            'pages':     pages,
        })

    def _api_presences_stats(self):
        session = self.require_auth()
        if not session:
            self.send_error_json('Non authentifié', 401)
            return
        stats = PresenceHandler().get_stats_dashboard()
        self.send_json(stats)

    def _api_dashboard_stats(self):
        session = self.require_auth()
        if not session:
            self.send_error_json('Non authentifié', 401)
            return
        handler = PresenceHandler()
        self.send_json({
            'kpis':              handler.get_stats_dashboard(),
            'presences_7_jours': handler.get_presences_7_jours(),
            'par_departement':   handler.get_presences_par_departement(),
            'taux_ponctualite':  handler.get_taux_ponctualite(),
            'derniers_pointages': handler.get_derniers_pointages(),
            'seances_du_jour':   handler.get_seances_du_jour(),
        })

    # ----------------------------------------------------------
    # RAPPORT
    # ----------------------------------------------------------

    def _api_rapport(self):
        session = self.require_auth()
        if not session:
            self.send_error_json('Non authentifié', 401)
            return

        params      = self.get_query_params()
        ens_id      = params.get('enseignant_id', '').strip()
        departement = params.get('departement', '').strip()
        statut      = params.get('statut', '').strip()
        date_debut  = params.get('date_debut', '').strip()
        date_fin    = params.get('date_fin', '').strip()
        search      = params.get('search', '').strip()

        conditions = []
        values     = []

        if ens_id:
            conditions.append('p.enseignant_id = %s')
            values.append(int(ens_id))
        if departement:
            conditions.append('e.departement = %s')
            values.append(departement)
        if statut:
            conditions.append('p.statut = %s')
            values.append(statut)
        if date_debut:
            conditions.append('DATE(p.date_pointage) >= %s')
            values.append(date_debut)
        if date_fin:
            conditions.append('DATE(p.date_pointage) <= %s')
            values.append(date_fin)
        if search:
            conditions.append(
                '(e.nom LIKE %s OR e.prenom LIKE %s OR e.matricule LIKE %s OR e.departement LIKE %s)')
            like = f'%{search}%'
            values.extend([like, like, like, like])

        where = ('WHERE ' + ' AND '.join(conditions)) if conditions else ''
        db = DatabaseHelper()
        presences = db.fetch_all(
            f"""SELECT p.*, e.nom, e.prenom, e.matricule, e.departement,
                       s.titre AS seance_titre, s.matiere, s.salle
                FROM presences p
                LEFT JOIN enseignants e ON p.enseignant_id = e.id
                LEFT JOIN seances s ON p.seance_id = s.id
                {where}
                ORDER BY p.date_pointage DESC, p.heure_pointage DESC""",
            tuple(values))

        total    = len(presences)
        presents = sum(1 for p in presences if p.get('statut') == 'PRESENT')
        retards  = sum(1 for p in presences if p.get('statut') == 'RETARD')
        absents  = sum(1 for p in presences if p.get('statut') == 'ABSENT')
        taux     = round((presents / total * 100), 1) if total else 0

        self.send_json({
            'presences': presences,
            'stats': {
                'total':    total,
                'presents': presents,
                'retards':  retards,
                'absents':  absents,
                'taux_presence': taux,
            },
        })

    def _api_rapport_pdf(self):
        session = self.require_auth()
        if not session:
            self.send_error_json('Non authentifié', 401)
            return

        # Réutiliser _api_rapport mais capturer les données
        params      = self.get_query_params()
        ens_id      = params.get('enseignant_id', '').strip()
        departement = params.get('departement', '').strip()
        statut      = params.get('statut', '').strip()
        date_debut  = params.get('date_debut', '').strip()
        date_fin    = params.get('date_fin', '').strip()

        conditions = []
        values     = []
        if ens_id:
            conditions.append('p.enseignant_id = %s')
            values.append(int(ens_id))
        if departement:
            conditions.append('e.departement = %s')
            values.append(departement)
        if statut:
            conditions.append('p.statut = %s')
            values.append(statut)
        if date_debut:
            conditions.append('DATE(p.date_pointage) >= %s')
            values.append(date_debut)
        if date_fin:
            conditions.append('DATE(p.date_pointage) <= %s')
            values.append(date_fin)

        where = ('WHERE ' + ' AND '.join(conditions)) if conditions else ''
        db = DatabaseHelper()
        presences = db.fetch_all(
            f"""SELECT p.*, e.nom, e.prenom, e.matricule, e.departement,
                       s.titre AS seance_titre, s.matiere
                FROM presences p
                LEFT JOIN enseignants e ON p.enseignant_id = e.id
                LEFT JOIN seances s ON p.seance_id = s.id
                {where}
                ORDER BY p.date_pointage DESC, p.heure_pointage DESC""",
            tuple(values))

        filtres   = params
        pdf_bytes = PDFExporter().export_rapport_pdf(presences, filtres)
        self.send_bytes(pdf_bytes, 'application/pdf', 'rapport_presences.pdf')

    def _api_rapport_csv(self):
        session = self.require_auth()
        if not session:
            self.send_error_json('Non authentifié', 401)
            return

        params      = self.get_query_params()
        ens_id      = params.get('enseignant_id', '').strip()
        departement = params.get('departement', '').strip()
        statut      = params.get('statut', '').strip()
        date_debut  = params.get('date_debut', '').strip()
        date_fin    = params.get('date_fin', '').strip()

        conditions = []
        values     = []
        if ens_id:
            conditions.append('p.enseignant_id = %s')
            values.append(int(ens_id))
        if departement:
            conditions.append('e.departement = %s')
            values.append(departement)
        if statut:
            conditions.append('p.statut = %s')
            values.append(statut)
        if date_debut:
            conditions.append('DATE(p.date_pointage) >= %s')
            values.append(date_debut)
        if date_fin:
            conditions.append('DATE(p.date_pointage) <= %s')
            values.append(date_fin)

        where = ('WHERE ' + ' AND '.join(conditions)) if conditions else ''
        db = DatabaseHelper()
        presences = db.fetch_all(
            f"""SELECT p.*, e.nom, e.prenom, e.matricule, e.departement,
                       s.titre AS seance_titre, s.matiere
                FROM presences p
                LEFT JOIN enseignants e ON p.enseignant_id = e.id
                LEFT JOIN seances s ON p.seance_id = s.id
                {where}
                ORDER BY p.date_pointage DESC, p.heure_pointage DESC""",
            tuple(values))

        output = io.StringIO()
        # BOM UTF-8 pour Excel
        output.write('\ufeff')
        writer = csv.writer(output)
        writer.writerow([
            'Date', 'Heure', 'Enseignant', 'Matricule',
            'Département', 'Séance', 'Mode', 'Retard(min)',
            'Statut', 'Commentaire',
        ])
        for p in presences:
            dp = p.get('date_pointage') or ''
            if hasattr(dp, 'strftime'):
                date_str = dp.strftime('%d/%m/%Y')
                heure_str = dp.strftime('%H:%M')
            else:
                parts = str(dp).split(' ')
                date_str  = parts[0] if parts else ''
                heure_str = parts[1][:5] if len(parts) > 1 else ''

            writer.writerow([
                date_str,
                heure_str,
                f"{p.get('prenom', '')} {p.get('nom', '')}".strip(),
                p.get('matricule', ''),
                p.get('departement', ''),
                p.get('seance_titre') or p.get('matiere', ''),
                p.get('mode_pointage', ''),
                p.get('retard_minutes', 0),
                p.get('statut', ''),
                p.get('commentaire', ''),
            ])

        csv_bytes = output.getvalue().encode('utf-8-sig')
        filename  = f'rapport_presences_{date.today().strftime("%Y%m%d")}.csv'
        self.send_bytes(csv_bytes, 'text/csv; charset=utf-8', filename)


# ============================================================
#  Point d'entrée
# ============================================================

if __name__ == '__main__':
    import logging
    logging.basicConfig(
        level   = logging.INFO,
        format  = '%(asctime)s [%(name)s] %(levelname)s : %(message)s',
        datefmt = '%H:%M:%S',
        force   = True,
    )

    os.makedirs(QR_DIR, exist_ok=True)

    # Initialiser la base SQLite (crée le fichier + tables + démo si nécessaire)
    from database import init_database
    init_database()

    # Générer les QR codes manquants pour les enseignants de démo
    _db_init  = DatabaseHelper()
    _qr_init  = QRGenerator()
    _ens_list = _db_init.fetch_all(
        "SELECT id, matricule, nom, prenom, qr_code_path, qr_code_data "
        "FROM enseignants WHERE est_actif = 1"
    )
    _fixed = 0
    for _e in _ens_list:
        _path = _qr_init.get_qr_path(_e['matricule'])
        if not os.path.isfile(_path) or not _e.get('qr_code_data'):
            try:
                _new_path = _qr_init.generate({
                    'id':        _e['id'],
                    'matricule': _e['matricule'],
                    'nom':       _e['nom'],
                    'prenom':    _e['prenom'],
                })
                _db_init.execute(
                    'UPDATE enseignants SET qr_code_path=?, qr_code_data=? WHERE id=?',
                    (_new_path, _qr_init.last_qr_data, _e['id'])
                )
                _fixed += 1
            except Exception as _ex:
                print(f'  ⚠  QR génération échouée pour {_e["matricule"]} : {_ex}', flush=True)
    if _fixed:
        print(f'  ✔  {_fixed} QR code(s) de démo générés/régénérés.', flush=True)

    # Utiliser sys.stdout avec encodage UTF-8 pour eviter les erreurs cp1252 sur Windows
    import io
    out = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace') if hasattr(sys.stdout, 'buffer') else sys.stdout
    def p(s):
        try: print(s)
        except UnicodeEncodeError: print(s.encode('utf-8').decode('ascii', errors='replace'))

    p('\n' + '=' * 55)
    p('  UniPresence Pro')
    p('  Institut Universitaire de lEntrepreneuriat')
    p('  IUE Douala, Cameroun')
    p('=' * 55)
    p(f'  URL    : http://localhost:{SERVER_PORT}/')
    p(f'  Admin  : admin@iue.cm')
    p(f'  MDP    : admin123')
    p('=' * 55 + '\n')

    try:
        # Activer TCP_NODELAY pour supprimer l'algorithme de Nagle
        # et éviter les délais de ~200ms sur les petites réponses HTTP
        import socket as _socket
        class _FastServer(ThreadingHTTPServer):
            allow_reuse_address = True
            def server_bind(self):
                self.socket.setsockopt(
                    _socket.IPPROTO_TCP, _socket.TCP_NODELAY, 1)
                super().server_bind()
        server = _FastServer((SERVER_HOST, SERVER_PORT), UniPresenceHandler)
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nServeur arrete.')
