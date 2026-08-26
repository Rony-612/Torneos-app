"""Genera el PDF de una jornada con la lista de jugadores de cada partido,
para entregarle a los árbitros (formato inspirado en el que ya usa la DCEA:
No. | Nombre | Licenciatura | NUA | Inscripción | Seguro | Asistencia).
"""
import io
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

from app.services.jornada_grid import DIA_LABEL

MESES_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
    7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}

NAVY = colors.HexColor("#002F6C")
GOLD = colors.HexColor("#FFC400")


def _tabla_roster(equipo, temporada_id):
    styles = getSampleStyleSheet()
    encabezado = ["No.", "Nombre", "Licenciatura", "NUA", "Inscripción", "Seguro", "Asistencia"]
    filas = [encabezado]
    jugadores = equipo.jugadores_temporada(temporada_id) if temporada_id else []
    for i, jugador in enumerate(jugadores, start=1):
        roster = next((r for r in jugador.rosters if r.equipo_id == equipo.id), None)
        filas.append([
            str(i),
            jugador.nombre,
            (roster.licenciatura if roster else "") or "",
            (roster.nua if roster else "") or "",
            "SI" if (roster and roster.inscripcion_pagada) else "",
            "SI" if (roster and roster.seguro_pagado) else "",
            "",  # casilla en blanco para que el arbitro marque asistencia a mano
        ])
    if len(filas) == 1:
        filas.append(["-", "Sin jugadores registrados", "", "", "", "", ""])

    tabla = Table(filas, colWidths=[1.1*cm, 5*cm, 3.3*cm, 2.3*cm, 2.3*cm, 2*cm, 2.3*cm], repeatRows=1)
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return tabla


def generar_pdf_jornada(jornada, grid, temporada_id):
    """Regresa un BytesIO con el PDF listo para descargar."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        topMargin=1.5*cm, bottomMargin=1.5*cm, leftMargin=1.5*cm, rightMargin=1.5*cm,
    )
    styles = getSampleStyleSheet()
    titulo_style = ParagraphStyle("titulo", parent=styles["Heading1"], textColor=NAVY, fontSize=16)
    dia_style = ParagraphStyle("dia", parent=styles["Heading2"], textColor=colors.white, backColor=NAVY,
                                fontSize=12, spaceBefore=10, spaceAfter=8, leftIndent=6, borderPadding=6)
    partido_style = ParagraphStyle("partido", parent=styles["Heading3"], fontSize=11, spaceBefore=6, spaceAfter=4)
    equipo_style = ParagraphStyle("equipo", parent=styles["Normal"], fontSize=9, textColor=NAVY,
                                   fontName="Helvetica-Bold", spaceBefore=6, spaceAfter=2)

    elementos = []
    if grid["dias"]:
        mes = MESES_ES[grid["dias"][0][1].month]
        rango = f"del {grid['dias'][0][1].day} al {grid['dias'][-1][1].day} de {mes}"
    else:
        rango = ""
    elementos.append(Paragraph(f"Jornada {jornada.numero} — Lista de asistencia para árbitros", titulo_style))
    elementos.append(Paragraph(rango, styles["Normal"]))
    elementos.append(Spacer(1, 10))

    hubo_algo = False
    for dia_label, fecha in grid["dias"]:
        partidos_del_dia = sorted(
            [grid["celdas"][(dia_label, h)] for h, _ in grid["horas"] if (dia_label, h) in grid["celdas"]],
            key=lambda p: p.hora,
        )
        if not partidos_del_dia:
            continue
        hubo_algo = True
        elementos.append(Paragraph(f"{fecha.day} {DIA_LABEL.get(dia_label, dia_label).upper()}", dia_style))

        for partido in partidos_del_dia:
            info = f"{partido.hora.strftime('%H:%M')} — {partido.equipo_local.nombre} vs {partido.equipo_visitante.nombre}"
            if partido.cancha:
                info += f" — Cancha: {partido.cancha.nombre}"
            info += " — Árbitro: " + (partido.arbitro.nombre if partido.arbitro else "_______________")
            elementos.append(Paragraph(info, partido_style))

            elementos.append(Paragraph(partido.equipo_local.nombre, equipo_style))
            elementos.append(_tabla_roster(partido.equipo_local, temporada_id))
            elementos.append(Spacer(1, 6))
            elementos.append(Paragraph(partido.equipo_visitante.nombre, equipo_style))
            elementos.append(_tabla_roster(partido.equipo_visitante, temporada_id))
            elementos.append(Spacer(1, 14))

    if not hubo_algo:
        elementos.append(Paragraph("Esta jornada todavía no tiene partidos.", styles["Normal"]))

    doc.build(elementos)
    buffer.seek(0)
    return buffer
