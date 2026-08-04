"""Estructura fija de horarios del torneo DCEA: los partidos solo se juegan
martes, miércoles y jueves, de 10:00 a 14:00 (bloques de una hora), porque
solo hay una cancha y un árbitro disponibles. Este módulo centraliza esa
regla para que la disponibilidad de capitanes, la generación automática de
calendario y la tabla visual de cada jornada usen siempre la misma rejilla.
"""
from datetime import timedelta, date as date_cls

DIAS_GRID = ["martes", "miercoles", "jueves"]
HORAS_GRID = ["10:00", "11:00", "12:00", "13:00", "14:00"]  # hora de inicio de cada juego (dura 1 hora)
DIA_INDEX = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4, "sabado": 5, "domingo": 6}
DIA_LABEL = {"martes": "Martes", "miercoles": "Miércoles", "jueves": "Jueves"}


def hora_fin(hora_str):
    h = int(hora_str.split(":")[0])
    return f"{h + 1:02d}:00"


def fechas_semana(fecha_referencia):
    """Regresa {dia_semana: fecha} para martes/miércoles/jueves de la semana
    que contiene fecha_referencia."""
    lunes = fecha_referencia - timedelta(days=fecha_referencia.weekday())
    return {dia: lunes + timedelta(days=DIA_INDEX[dia]) for dia in DIAS_GRID}


def construir_grid(jornada, excluir_partido_id=None):
    """Arma la tabla de una jornada: que partido (si hay) cae en cada
    combinacion de dia fijo x hora fija. excluir_partido_id permite marcar
    un partido en particular como 'no ocupa la celda' (usado cuando un
    capitan esta reprogramando ese mismo partido)."""
    partidos = list(jornada.partidos)
    fecha_ref = jornada.fecha_referencia
    if not fecha_ref and partidos:
        fecha_ref = partidos[0].fecha
    fecha_ref = fecha_ref or date_cls.today()
    fechas = fechas_semana(fecha_ref)

    celdas = {}
    otros = []
    for p in partidos:
        if excluir_partido_id and p.id == excluir_partido_id:
            continue
        hora_str = p.hora.strftime("%H:%M")
        dia_label = next((dia for dia, f in fechas.items() if f == p.fecha), None)
        if dia_label and hora_str in HORAS_GRID:
            celdas[(dia_label, hora_str)] = p
        else:
            otros.append(p)

    dias = [(dia, fechas[dia]) for dia in DIAS_GRID]
    horas = [(h, hora_fin(h)) for h in HORAS_GRID]
    return {"dias": dias, "horas": horas, "celdas": celdas, "otros": otros}
