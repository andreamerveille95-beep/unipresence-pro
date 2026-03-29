# ============================================================
#  UniPresence Pro — IUE Douala
#  Export PDF (QR Codes, Rapports) et ZIP
# ============================================================

import io
import os
import zipfile
import logging
import unicodedata
from datetime import datetime, date

try:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import cm, mm
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        Image as RLImage, PageBreak, HRFlowable
    )
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
except ImportError:
    raise ImportError(
        "Le module reportlab est requis. "
        "Installez-le avec : pip install reportlab"
    )

try:
    from PIL import Image as PILImage
except ImportError:
    PILImage = None

from config import QR_DIR, IMAGE_DIR, BASE_DIR, PDF_COMPANY_NAME, PDF_APP_NAME, PDF_WATERMARK

# ------------------------------------------------------------
# Logger
# ------------------------------------------------------------
logger = logging.getLogger('pdf_exporter')

# Couleurs IUE
COLOR_PRIMARY   = colors.HexColor('#1a3a6b')   # bleu foncé
COLOR_SECONDARY = colors.HexColor('#e8f0fe')   # bleu très clair
COLOR_ACCENT    = colors.HexColor('#f59e0b')   # ambre
COLOR_DARK      = colors.HexColor('#1f2937')
COLOR_GRAY      = colors.HexColor('#6b7280')
COLOR_LIGHT     = colors.HexColor('#f9fafb')
COLOR_RETARD    = colors.HexColor('#fef3c7')
COLOR_ABSENT    = colors.HexColor('#fee2e2')
COLOR_PRESENT   = colors.HexColor('#d1fae5')


# ============================================================
#  Classe PDFExporter
# ============================================================

class PDFExporter:
    """
    Classe d'export en PDF et ZIP pour UniPresence Pro.

    Méthodes principales :
    - export_qr_codes_pdf(enseignants_list) → bytes (PDF)
    - export_qr_zip(enseignants_list)       → bytes (ZIP)
    - export_rapport_pdf(presences_list, filters_dict) → bytes (PDF)
    """

    # ----------------------------------------------------------
    # 1. Export PDF — QR Codes
    # ----------------------------------------------------------

    def export_qr_codes_pdf(self, enseignants_list: list) -> bytes:
        """
        Génère un PDF avec les QR codes de tous les enseignants.

        Mise en page : grille 2 colonnes × 3 lignes par page (A4 portrait).
        Chaque cellule contient : QR image + nom + matricule + spécialité + dépt.

        Parameters
        ----------
        enseignants_list : list[dict]

        Returns
        -------
        bytes
            Contenu binaire du PDF.
        """
        buffer   = io.BytesIO()
        doc_date = datetime.now().strftime('%d/%m/%Y')
        filename = f"qr_codes_enseignants_{datetime.now().strftime('%Y%m%d')}.pdf"

        # Utiliser canvas directement pour mieux contrôler le layout
        pdf = rl_canvas.Canvas(buffer, pagesize=A4)
        page_w, page_h = A4     # 595.27 × 841.89 points

        COLS        = 2
        ROWS        = 3
        MARGIN_X    = 2.5 * cm
        MARGIN_TOP  = 4.5 * cm
        MARGIN_BOT  = 2.5 * cm
        CELL_W      = (page_w - 2 * MARGIN_X) / COLS
        CELL_H      = (page_h - MARGIN_TOP - MARGIN_BOT) / ROWS
        QR_SIZE     = min(CELL_W, CELL_H) * 0.55

        total_pages = max(1, -(-len(enseignants_list) // (COLS * ROWS)))  # ceil div
        page_num    = 0

        def draw_header(pdf, page_n, total_p):
            """Dessine l'en-tête et le pied de page."""
            # En-tête
            pdf.setFillColor(COLOR_PRIMARY)
            pdf.rect(0, page_h - 3 * cm, page_w, 3 * cm, fill=1, stroke=0)
            pdf.setFillColor(colors.white)
            pdf.setFont('Helvetica-Bold', 16)
            pdf.drawCentredString(page_w / 2, page_h - 1.5 * cm,
                                  f'{PDF_APP_NAME} — QR Codes Enseignants')
            pdf.setFont('Helvetica', 10)
            pdf.drawCentredString(page_w / 2, page_h - 2.3 * cm,
                                  f'{PDF_COMPANY_NAME}  |  Généré le {doc_date}')
            # Filigrane diagonal
            pdf.saveState()
            pdf.setFillColor(colors.Color(0.85, 0.85, 0.85, alpha=0.35))
            pdf.setFont('Helvetica-Bold', 48)
            pdf.translate(page_w / 2, page_h / 2)
            pdf.rotate(35)
            pdf.drawCentredString(0, 0, PDF_WATERMARK)
            pdf.restoreState()
            # Pied de page
            pdf.setFillColor(COLOR_PRIMARY)
            pdf.rect(0, 0, page_w, MARGIN_BOT - 0.3 * cm, fill=1, stroke=0)
            pdf.setFillColor(colors.white)
            pdf.setFont('Helvetica', 9)
            pdf.drawCentredString(page_w / 2, 0.7 * cm,
                                  f'{PDF_COMPANY_NAME} — Page {page_n}/{total_p} — CONFIDENTIEL')

        items_per_page = COLS * ROWS
        for idx, ens in enumerate(enseignants_list):
            pos_in_page = idx % items_per_page

            if pos_in_page == 0:
                if idx > 0:
                    pdf.showPage()
                page_num += 1
                draw_header(pdf, page_num, total_pages)

            col = pos_in_page % COLS
            row = pos_in_page // COLS

            cell_x = MARGIN_X + col * CELL_W
            cell_y = page_h - MARGIN_TOP - (row + 1) * CELL_H

            # Bordure de cellule
            pdf.setStrokeColor(colors.HexColor('#e5e7eb'))
            pdf.setLineWidth(0.5)
            pdf.roundRect(cell_x + 5, cell_y + 5,
                          CELL_W - 10, CELL_H - 10,
                          radius=4, fill=0, stroke=1)

            # QR Code image
            qr_path = self._get_qr_image_path(ens)
            qr_x    = cell_x + (CELL_W - QR_SIZE) / 2
            qr_y    = cell_y + CELL_H - QR_SIZE - 15

            if qr_path and os.path.isfile(qr_path):
                pdf.drawImage(qr_path, qr_x, qr_y, width=QR_SIZE, height=QR_SIZE,
                              preserveAspectRatio=True)
            else:
                # Placeholder si QR absent
                pdf.setFillColor(colors.HexColor('#e5e7eb'))
                pdf.rect(qr_x, qr_y, QR_SIZE, QR_SIZE, fill=1, stroke=0)
                pdf.setFillColor(COLOR_GRAY)
                pdf.setFont('Helvetica', 9)
                pdf.drawCentredString(qr_x + QR_SIZE / 2, qr_y + QR_SIZE / 2 - 5,
                                      'QR non disponible')

            # Texte sous le QR
            text_y = qr_y - 5
            nom    = f"{ens.get('nom', '')} {ens.get('prenom', '')}"
            mat    = ens.get('matricule', '')
            spec   = ens.get('specialite', '')[:35]
            dept   = ens.get('departement', '')

            pdf.setFillColor(COLOR_DARK)
            pdf.setFont('Helvetica-Bold', 9)
            pdf.drawCentredString(cell_x + CELL_W / 2, text_y, nom[:40])

            pdf.setFont('Helvetica', 8)
            pdf.setFillColor(COLOR_GRAY)
            pdf.drawCentredString(cell_x + CELL_W / 2, text_y - 13, mat)

            pdf.setFont('Helvetica', 7.5)
            pdf.drawCentredString(cell_x + CELL_W / 2, text_y - 24,
                                  f'{spec} — {dept}')

        # Dernière page si la liste est vide
        if not enseignants_list:
            page_num = 1
            draw_header(pdf, 1, 1)
            pdf.setFillColor(COLOR_GRAY)
            pdf.setFont('Helvetica', 12)
            pdf.drawCentredString(page_w / 2, page_h / 2, 'Aucun enseignant à afficher.')

        pdf.save()
        buffer.seek(0)
        logger.info("PDF QR codes généré : %d enseignant(s).", len(enseignants_list))
        return buffer.getvalue()

    # ----------------------------------------------------------
    # 2. Export PDF individuel — un seul QR avec logo IUE
    # ----------------------------------------------------------

    def export_single_qr_pdf(self, enseignant: dict) -> bytes:
        """
        Génère un PDF A4 contenant uniquement le QR code d'un enseignant,
        avec le logo IUE, le nom, le matricule et le département.

        Parameters
        ----------
        enseignant : dict  — ligne complète de la table enseignants

        Returns
        -------
        bytes
        """
        buffer = io.BytesIO()
        pdf    = rl_canvas.Canvas(buffer, pagesize=A4)
        pw, ph = A4
        today  = datetime.now().strftime('%d/%m/%Y')

        # ── En-tête bleu ────────────────────────────────────────
        pdf.setFillColor(COLOR_PRIMARY)
        pdf.rect(0, ph - 3.5 * cm, pw, 3.5 * cm, fill=1, stroke=0)

        # Logo (si disponible)
        logo_path = os.path.join(BASE_DIR, '..', 'frontend', 'assets', 'images', 'logo-iue.png')
        logo_path = os.path.normpath(logo_path)
        logo_drawn = False
        if os.path.isfile(logo_path):
            try:
                logo_size = 2.2 * cm
                pdf.drawImage(logo_path, 1.2 * cm, ph - 3.5 * cm + (3.5 * cm - logo_size) / 2,
                              width=logo_size, height=logo_size, preserveAspectRatio=True,
                              mask='auto')
                logo_drawn = True
            except Exception:
                pass

        txt_x = (1.2 * cm + 2.6 * cm) if logo_drawn else pw / 2
        pdf.setFillColor(colors.white)
        pdf.setFont('Helvetica-Bold', 15)
        if logo_drawn:
            pdf.drawString(txt_x, ph - 1.65 * cm, PDF_APP_NAME)
            pdf.setFont('Helvetica', 9)
            pdf.drawString(txt_x, ph - 2.5 * cm, f'{PDF_COMPANY_NAME} — {today}')
        else:
            pdf.drawCentredString(pw / 2, ph - 1.65 * cm, PDF_APP_NAME)
            pdf.setFont('Helvetica', 9)
            pdf.drawCentredString(pw / 2, ph - 2.5 * cm, f'{PDF_COMPANY_NAME} — {today}')

        # ── Zone centrale : QR ───────────────────────────────────
        QR_SIZE = 9 * cm
        qr_path = self._get_qr_image_path(enseignant)
        qr_x    = (pw - QR_SIZE) / 2
        qr_y    = ph / 2 - QR_SIZE / 2 + 1.5 * cm   # légèrement au-dessus du centre

        if qr_path and os.path.isfile(qr_path):
            # Cadre blanc avec ombre légère
            pdf.setFillColor(colors.white)
            pdf.setStrokeColor(colors.HexColor('#e5e7eb'))
            pdf.setLineWidth(1)
            pdf.roundRect(qr_x - 0.6 * cm, qr_y - 0.6 * cm,
                          QR_SIZE + 1.2 * cm, QR_SIZE + 1.2 * cm,
                          radius=6, fill=1, stroke=1)
            pdf.drawImage(qr_path, qr_x, qr_y,
                          width=QR_SIZE, height=QR_SIZE, preserveAspectRatio=True)
        else:
            pdf.setFillColor(colors.HexColor('#f3f4f6'))
            pdf.roundRect(qr_x, qr_y, QR_SIZE, QR_SIZE, radius=4, fill=1, stroke=0)
            pdf.setFillColor(COLOR_GRAY)
            pdf.setFont('Helvetica', 11)
            pdf.drawCentredString(pw / 2, qr_y + QR_SIZE / 2, 'QR code non disponible')

        # ── Infos enseignant sous le QR ──────────────────────────
        nom_complet = f"{enseignant.get('prenom', '')} {enseignant.get('nom', '')}".strip().upper()
        matricule   = enseignant.get('matricule', '—')
        departement = enseignant.get('departement', '')
        specialite  = enseignant.get('specialite', '')
        grade       = enseignant.get('grade', '')

        y_text = qr_y - 2.0 * cm   # 2 cm sous le bas du cadre blanc
        pdf.setFillColor(COLOR_DARK)
        pdf.setFont('Helvetica-Bold', 14)
        pdf.drawCentredString(pw / 2, y_text, nom_complet)

        pdf.setFillColor(COLOR_PRIMARY)
        pdf.setFont('Helvetica-Bold', 11)
        pdf.drawCentredString(pw / 2, y_text - 0.7 * cm, matricule)

        pdf.setFillColor(COLOR_GRAY)
        pdf.setFont('Helvetica', 9)
        detail = ' — '.join(filter(None, [grade, specialite, departement]))
        pdf.drawCentredString(pw / 2, y_text - 1.35 * cm, detail[:70])

        # ── Instructions ─────────────────────────────────────────
        y_inst = qr_y - 3.8 * cm
        pdf.setFillColor(colors.HexColor('#e8f0fe'))
        pdf.roundRect(2 * cm, y_inst - 0.6 * cm, pw - 4 * cm, 1.1 * cm,
                      radius=4, fill=1, stroke=0)
        pdf.setFillColor(COLOR_PRIMARY)
        pdf.setFont('Helvetica', 9)
        pdf.drawCentredString(pw / 2, y_inst - 0.2 * cm,
                              'Présentez ce QR code à l\'entrée de chaque séance pour enregistrer votre présence.')

        # ── Pied de page ─────────────────────────────────────────
        pdf.setFillColor(COLOR_PRIMARY)
        pdf.rect(0, 0, pw, 1.4 * cm, fill=1, stroke=0)
        pdf.setFillColor(colors.white)
        pdf.setFont('Helvetica', 8)
        pdf.drawCentredString(pw / 2, 0.5 * cm,
                              f'{PDF_COMPANY_NAME} — QR Code confidentiel — Ne pas diffuser')

        pdf.save()
        buffer.seek(0)
        return buffer.getvalue()

    # ----------------------------------------------------------
    # 3. Export ZIP — QR Codes PNG
    # ----------------------------------------------------------

    def export_qr_zip(self, enseignants_list: list) -> bytes:
        """
        Crée une archive ZIP contenant les QR codes PNG de tous les enseignants.

        Structure de l'archive :
        ``qr_codes_iue_YYYYMMDD/qr_<matricule>_<nom>_<prenom>.png``

        Parameters
        ----------
        enseignants_list : list[dict]

        Returns
        -------
        bytes
            Contenu binaire du fichier ZIP.
        """
        buffer      = io.BytesIO()
        folder_name = f"qr_codes_iue_{datetime.now().strftime('%Y%m%d')}"

        with zipfile.ZipFile(buffer, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
            count = 0
            for ens in enseignants_list:
                qr_path = self._get_qr_image_path(ens)
                if not qr_path or not os.path.isfile(qr_path):
                    logger.warning(
                        "QR introuvable pour matricule=%s, ignoré dans le ZIP.",
                        ens.get('matricule', '?')
                    )
                    continue

                mat    = self._normalize_filename(ens.get('matricule', 'INCONNU'))
                nom    = self._normalize_filename(ens.get('nom', ''))
                prenom = self._normalize_filename(ens.get('prenom', ''))
                arc_name = f"{folder_name}/qr_{mat}_{nom}_{prenom}.png"

                zf.write(qr_path, arcname=arc_name)
                count += 1

            # Ajouter un fichier README dans le ZIP
            readme_content = (
                f"UniPresence Pro — IUE Douala\n"
                f"Archive QR Codes Enseignants\n"
                f"Générée le : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"Nombre de QR codes : {count}\n\n"
                f"CONFIDENTIEL — Usage interne uniquement.\n"
            ).encode('utf-8')
            zf.writestr(f"{folder_name}/README.txt", readme_content)

        buffer.seek(0)
        logger.info("ZIP QR codes généré : %d fichier(s).", count)
        return buffer.getvalue()

    # ----------------------------------------------------------
    # 3. Export PDF — Rapport de présences
    # ----------------------------------------------------------

    def export_rapport_pdf(self, presences_list: list, filters_dict: dict) -> bytes:
        """
        Génère un PDF rapport des présences avec statistiques.

        Parameters
        ----------
        presences_list : list[dict]
            Chaque dict doit avoir : date_pointage, heure_pointage, nom, prenom,
            matricule, departement, statut, mode_pointage, retard_minutes, seance.
        filters_dict : dict
            Filtres appliqués (date_debut, date_fin, departement, statut…).

        Returns
        -------
        bytes
            Contenu binaire du PDF.
        """
        buffer = io.BytesIO()
        doc    = SimpleDocTemplate(
            buffer,
            pagesize    = A4,
            rightMargin = 2 * cm,
            leftMargin  = 2 * cm,
            topMargin   = 3 * cm,
            bottomMargin= 2.5 * cm,
            title       = f'{PDF_APP_NAME} — Rapport de présences',
            author      = PDF_COMPANY_NAME,
        )

        styles = getSampleStyleSheet()
        story  = []

        # ---- Titre ----
        style_titre = ParagraphStyle(
            'titre_iue',
            fontSize   = 18,
            textColor  = COLOR_PRIMARY,
            alignment  = TA_CENTER,
            fontName   = 'Helvetica-Bold',
            spaceAfter = 6,
        )
        style_sous  = ParagraphStyle(
            'sous_titre',
            fontSize   = 11,
            textColor  = COLOR_GRAY,
            alignment  = TA_CENTER,
            fontName   = 'Helvetica',
            spaceAfter = 4,
        )
        style_normal = ParagraphStyle(
            'normal_iue',
            fontSize   = 9,
            textColor  = COLOR_DARK,
            fontName   = 'Helvetica',
            spaceAfter = 2,
        )
        style_cell = ParagraphStyle(
            'cell_iue',
            fontSize   = 8,
            textColor  = COLOR_DARK,
            fontName   = 'Helvetica',
            leading    = 10,
        )

        story.append(Spacer(1, 0.5 * cm))
        story.append(Paragraph(f'{PDF_APP_NAME}', style_titre))
        story.append(Paragraph(f'Rapport de Présences — {PDF_COMPANY_NAME}', style_sous))
        story.append(Paragraph(
            f'Généré le {datetime.now().strftime("%d/%m/%Y à %H:%M:%S")}',
            style_sous
        ))
        story.append(HRFlowable(width='100%', thickness=1.5, color=COLOR_PRIMARY))
        story.append(Spacer(1, 0.4 * cm))

        # ---- Filtres appliqués ----
        if filters_dict:
            filtres_txt = '  |  '.join(
                f'<b>{k}</b>: {v}'
                for k, v in filters_dict.items()
                if v
            )
            if filtres_txt:
                style_filtres = ParagraphStyle(
                    'filtres',
                    fontSize   = 9,
                    textColor  = COLOR_GRAY,
                    fontName   = 'Helvetica-Oblique',
                    spaceAfter = 6,
                )
                story.append(Paragraph(f'Filtres : {filtres_txt}', style_filtres))

        # ---- Statistiques ----
        total    = len(presences_list)
        presents = sum(1 for p in presences_list if p.get('statut') == 'PRESENT')
        retards  = sum(1 for p in presences_list if p.get('statut') == 'RETARD')
        absents  = sum(1 for p in presences_list if p.get('statut') == 'ABSENT')
        excuses  = sum(1 for p in presences_list if p.get('statut') == 'EXCUSE')

        taux_ponct = round(presents * 100 / total, 1) if total > 0 else 0.0

        stats_data = [
            ['Indicateur', 'Valeur'],
            ['Total pointages',        str(total)],
            ['Présents',               str(presents)],
            ['Retards',                str(retards)],
            ['Absents',                str(absents)],
            ['Excusés',                str(excuses)],
            ['Taux de ponctualité',    f'{taux_ponct} %'],
        ]
        stats_table = Table(stats_data, colWidths=[8 * cm, 6 * cm])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND',  (0, 0), (-1, 0), COLOR_PRIMARY),
            ('TEXTCOLOR',   (0, 0), (-1, 0), colors.white),
            ('FONTNAME',    (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',    (0, 0), (-1, 0), 9),
            ('ALIGN',       (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN',      (0, 0), (-1, -1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [COLOR_LIGHT, COLOR_SECONDARY]),
            ('FONTNAME',    (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE',    (0, 1), (-1, -1), 9),
            ('GRID',        (0, 0), (-1, -1), 0.4, colors.HexColor('#d1d5db')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ]))
        story.append(stats_table)
        story.append(Spacer(1, 0.5 * cm))

        # ---- Tableau des présences ----
        story.append(Paragraph('Détail des pointages', ParagraphStyle(
            'section',
            fontSize   = 12,
            fontName   = 'Helvetica-Bold',
            textColor  = COLOR_PRIMARY,
            spaceAfter = 6,
        )))

        headers = [
            'Date', 'Heure', 'Enseignant', 'Matricule',
            'Dépt', 'Statut', 'Mode', 'Retard (min)'
        ]
        col_widths = [2.2*cm, 1.8*cm, 4*cm, 3.2*cm, 1.8*cm, 2*cm, 2.2*cm, 1.8*cm]

        table_data = [[Paragraph(h, ParagraphStyle(
            'th', fontSize=8, fontName='Helvetica-Bold',
            textColor=colors.white, alignment=TA_CENTER
        )) for h in headers]]

        STATUS_COLORS = {
            'PRESENT': COLOR_PRESENT,
            'RETARD':  COLOR_RETARD,
            'ABSENT':  COLOR_ABSENT,
            'EXCUSE':  colors.HexColor('#e0e7ff'),
        }

        row_styles = []
        for i, p in enumerate(presences_list, start=1):
            date_str   = str(p.get('date_pointage', ''))
            heure_str  = str(p.get('heure_pointage', ''))[:5]
            nom_complet = f"{p.get('nom', '')} {p.get('prenom', '')}"
            mat        = p.get('matricule', '')
            dept       = p.get('departement', '')
            statut     = p.get('statut', '')
            mode       = p.get('mode_pointage', '')
            retard     = str(p.get('retard_minutes', 0))

            row = [
                Paragraph(date_str,   style_cell),
                Paragraph(heure_str,  style_cell),
                Paragraph(nom_complet[:30], style_cell),
                Paragraph(mat,        style_cell),
                Paragraph(dept,       style_cell),
                Paragraph(statut,     style_cell),
                Paragraph(mode,       style_cell),
                Paragraph(retard,     style_cell),
            ]
            table_data.append(row)

            bg = STATUS_COLORS.get(statut, COLOR_LIGHT)
            row_styles.append(('BACKGROUND', (0, i), (-1, i), bg))

        presence_table = Table(table_data, colWidths=col_widths, repeatRows=1)
        base_style = [
            ('BACKGROUND',  (0, 0), (-1, 0), COLOR_PRIMARY),
            ('TEXTCOLOR',   (0, 0), (-1, 0), colors.white),
            ('ALIGN',       (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN',      (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME',    (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE',    (0, 1), (-1, -1), 8),
            ('GRID',        (0, 0), (-1, -1), 0.3, colors.HexColor('#e5e7eb')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING',    (0, 0), (-1, -1), 4),
        ]
        presence_table.setStyle(TableStyle(base_style + row_styles))

        story.append(presence_table)
        story.append(Spacer(1, 1 * cm))

        # ---- Pied de page via onFirstPage / onLaterPages ----
        def add_footer(canvas_obj, doc_obj):
            canvas_obj.saveState()
            canvas_obj.setFont('Helvetica', 8)
            canvas_obj.setFillColor(COLOR_GRAY)
            page_w, _ = A4
            canvas_obj.drawCentredString(
                page_w / 2, 1.5 * cm,
                f'{PDF_COMPANY_NAME} — {PDF_APP_NAME} — '
                f'Page {doc_obj.page} — CONFIDENTIEL'
            )
            # Filigrane
            canvas_obj.setFillColor(colors.Color(0.88, 0.88, 0.88, alpha=0.3))
            canvas_obj.setFont('Helvetica-Bold', 40)
            pw, ph = A4
            canvas_obj.translate(pw / 2, ph / 2)
            canvas_obj.rotate(35)
            canvas_obj.drawCentredString(0, 0, PDF_WATERMARK)
            canvas_obj.restoreState()

        doc.build(
            story,
            onFirstPage  = add_footer,
            onLaterPages = add_footer,
        )

        buffer.seek(0)
        logger.info("PDF rapport généré : %d ligne(s) de présence.", total)
        return buffer.getvalue()

    # ----------------------------------------------------------
    # Helpers privés
    # ----------------------------------------------------------

    def _normalize_filename(self, s: str) -> str:
        """
        Convertit une chaîne en nom de fichier ASCII sûr.

        Supprime les accents, remplace les espaces par des underscores,
        conserve uniquement les caractères alphanumériques et tirets.

        Parameters
        ----------
        s : str

        Returns
        -------
        str
        """
        normalized = unicodedata.normalize('NFKD', s or '')
        ascii_str  = normalized.encode('ascii', errors='ignore').decode('ascii')
        safe       = ''.join(
            c if (c.isalnum() or c in '-_') else '_'
            for c in ascii_str
        )
        # Supprimer les underscores multiples
        while '__' in safe:
            safe = safe.replace('__', '_')
        return safe.strip('_')

    def _get_qr_image_path(self, enseignant: dict) -> str | None:
        """
        Retourne le chemin PNG du QR code d'un enseignant.

        Cherche d'abord ``qr_code_path`` dans le dict, puis calcule
        le chemin attendu à partir du matricule.

        Parameters
        ----------
        enseignant : dict

        Returns
        -------
        str | None
        """
        # 1. Chemin stocké en base
        stored = enseignant.get('qr_code_path', '')
        if stored and os.path.isfile(stored):
            return stored

        # 2. Chemin calculé à partir du matricule
        matricule = enseignant.get('matricule', '')
        if not matricule:
            return None
        safe     = matricule.replace('/', '_').replace('\\', '_').replace(' ', '_')
        expected = os.path.join(QR_DIR, f'qr_{safe}.png')
        return expected if os.path.isfile(expected) else None


# ============================================================
#  Instance globale partagée
# ============================================================
pdf_exporter = PDFExporter()
