"""Llaves de la fase final (cuartos de final).

Cuando termina la fase regular (liguilla a una vuelta en dos grupos), clasifican
los 4 mejores de cada grupo y los cruces son:

    Lado izquierdo:  1° A vs 4° B   |   3° A vs 2° B
    Lado derecho:    1° B vs 4° A   |   3° B vs 2° A

Los cuartos viven como una Fase (tipo "cuartos") con una sola Jornada en
borrador, para reutilizar todo lo que ya existe: editar fecha/hora/cancha,
capturar resultado, publicar la jornada, PDF, notificaciones.

No hay columnas nuevas en la base de datos: el lugar de cada partido dentro de
la llave se deduce del orden de creacion (id) de los 4 partidos de la jornada:
    1 = izq. arriba, 2 = izq. abajo, 3 = der. arriba, 4 = der. abajo
"""
from datetime import timedelta, date as date_cls, datetime
from itertools import combinations

from app.extensions import db
from app.models import (
    Fase, Grupo, Jornada, Partido, Cancha, EventoPartido, DetallePartidoEquipo,
    SolicitudCambioHorario, Asistencia,
)
from app.services.jornada_grid import fechas_semana

CLASIFICAN_POR_GRUPO = 4
TIPO_CUARTOS = "cuartos"
# (dia, hora): lado izquierdo el martes, lado derecho el miercoles
SLOTS_CUARTOS = [("martes", "10:00"), ("martes", "11:00"),
                 ("miercoles", "10:00"), ("miercoles", "11:00")]


class LlavesError(Exception):
    pass


def _fase_grupos():
    return Fase.query.filter_by(tipo="grupos").first()


def fase_cuartos():
    return Fase.query.filter_by(tipo=TIPO_CUARTOS).first()


def _grupos_ordenados(fase):
    return Grupo.query.filter_by(fase_id=fase.id).order_by(Grupo.nombre).all()


def _jornada_cuartos():
    fase = fase_cuartos()
    if not fase:
        return None
    return Jornada.query.filter_by(fase_id=fase.id).order_by(Jornada.numero).first()


# ---------- Estado de la fase regular ----------

def estado_fase_regular():
    """Dice si la fase regular ya termino y se pueden generar las llaves.

    - pendientes: partidos de la fase que aun no estan 'jugado'
      (programados, suspendidos, reprogramados).
    - faltantes: cruces de la liguilla que nunca se programaron
      (n*(n-1)/2 por grupo, menos los ya jugados).
    - listo: no hay pendientes ni faltantes.
    Es solo informativo: el boton de generar llaves esta siempre disponible
    y, si no esta 'listo', la interfaz pide confirmacion.
    """
    estado = {
        "fase": None, "grupos": [], "pendientes": [], "faltantes": 0,
        "jugados": 0, "esperados": 0, "problema": None,
        "listo": False,
    }
    fase = _fase_grupos()
    if not fase:
        estado["problema"] = "No hay una fase de grupos configurada."
        return estado
    estado["fase"] = fase

    grupos = _grupos_ordenados(fase)
    estado["grupos"] = grupos
    if len(grupos) != 2:
        estado["problema"] = "Las llaves de cuartos requieren exactamente 2 grupos (A y B)."
        return estado

    partidos = Partido.query.join(Jornada).filter(Jornada.fase_id == fase.id).all()
    estado["pendientes"] = sorted(
        [p for p in partidos if p.estado != "jugado"], key=lambda p: (p.fecha, p.hora)
    )
    pares_jugados = {
        frozenset([p.equipo_local_id, p.equipo_visitante_id])
        for p in partidos if p.estado == "jugado"
    }

    for g in grupos:
        ids = [e.id for e in g.equipos()]
        if len(ids) < CLASIFICAN_POR_GRUPO:
            estado["problema"] = (
                f"El grupo {g.nombre} tiene {len(ids)} equipo(s); se necesitan al menos "
                f"{CLASIFICAN_POR_GRUPO} para armar los cuartos."
            )
            return estado
        esperados = len(ids) * (len(ids) - 1) // 2
        hechos = sum(1 for a, b in combinations(ids, 2) if frozenset([a, b]) in pares_jugados)
        estado["esperados"] += esperados
        estado["jugados"] += hechos
        estado["faltantes"] += esperados - hechos

    estado["listo"] = not estado["pendientes"] and estado["faltantes"] == 0
    return estado


# ---------- Generar / reiniciar ----------

def _clasificados(grupo):
    return [fila["equipo"] for fila in grupo.tabla_posiciones()][:CLASIFICAN_POR_GRUPO]


def _validar_para_generar(estado):
    """Solo bloquea si es imposible armar los cruces (no hay 2 grupos o
    alguno tiene menos de 4 equipos). Que la fase regular no haya terminado
    NO bloquea: el organizador decide cuando generar las llaves."""
    if estado["problema"]:
        raise LlavesError(estado["problema"])


def generar_cuartos():
    """Crea la jornada de cuartos (en borrador) con los 4 cruces."""
    estado = estado_fase_regular()
    if _jornada_cuartos():
        raise LlavesError("Las llaves ya fueron generadas. Si necesitas rehacerlas, usa \"Regenerar llaves\".")
    _validar_para_generar(estado)

    fase = estado["fase"]
    g1, g2 = estado["grupos"]
    a, b = _clasificados(g1), _clasificados(g2)
    # Orden = posicion en la llave: izq. arriba, izq. abajo, der. arriba, der. abajo
    cruces = [
        (a[0], b[3]),  # 1° A vs 4° B
        (a[2], b[1]),  # 3° A vs 2° B
        (b[0], a[3]),  # 1° B vs 4° A
        (b[2], a[1]),  # 3° B vs 2° A
    ]

    fase_c = fase_cuartos()
    if not fase_c:
        fase_c = Fase(
            categoria_id=fase.categoria_id, tipo=TIPO_CUARTOS,
            nombre="Cuartos de final", orden=(fase.orden or 1) + 1,
        )
        db.session.add(fase_c)
        db.session.flush()

    ultimo = (
        db.session.query(db.func.max(Partido.fecha))
        .join(Jornada).filter(Jornada.fase_id == fase.id).scalar()
    )
    fecha_ref = (ultimo or date_cls.today()) + timedelta(days=7)
    fechas = fechas_semana(fecha_ref)

    jornada = Jornada(fase_id=fase_c.id, numero=1, fecha_referencia=fecha_ref, estado="borrador")
    db.session.add(jornada)
    db.session.flush()

    cancha = Cancha.query.first()
    for (local, visitante), (dia, hora) in zip(cruces, SLOTS_CUARTOS):
        db.session.add(Partido(
            jornada_id=jornada.id,
            equipo_local_id=local.id, equipo_visitante_id=visitante.id,
            cancha_id=cancha.id if cancha else None,
            fecha=fechas[dia],
            hora=datetime.strptime(hora, "%H:%M").time(),
            estado="programado",
        ))
    db.session.commit()
    return jornada


def regenerar_cuartos():
    """Rehace las llaves con la tabla actual. Valida ANTES de borrar, para no
    dejar al organizador sin llaves si algo no cumple."""
    jornada = _jornada_cuartos()
    if not jornada:
        raise LlavesError("Todavía no hay llaves generadas.")
    if jornada.estado != "borrador":
        raise LlavesError("Las llaves ya están publicadas y no se pueden regenerar.")
    _validar_para_generar(estado_fase_regular())
    reiniciar_cuartos()
    return generar_cuartos()


def reiniciar_cuartos():
    """Borra las llaves para volver a generarlas. Solo mientras la jornada de
    cuartos siga en borrador (igual que cualquier jornada)."""
    jornada = _jornada_cuartos()
    if not jornada:
        raise LlavesError("Todavía no hay llaves generadas.")
    if jornada.estado != "borrador":
        raise LlavesError("Las llaves ya están publicadas y no se pueden regenerar.")
    for p in list(jornada.partidos):
        EventoPartido.query.filter_by(partido_id=p.id).delete()
        DetallePartidoEquipo.query.filter_by(partido_id=p.id).delete()
        SolicitudCambioHorario.query.filter_by(partido_id=p.id).delete()
        Asistencia.query.filter_by(partido_id=p.id).delete()
        db.session.delete(p)
    db.session.delete(jornada)
    db.session.commit()


# ---------- Datos para pintar la llave ----------

def _etiquetas_seed():
    """{equipo_id: '1A'...} segun la tabla actual de cada grupo."""
    fase = _fase_grupos()
    etiquetas = {}
    if not fase:
        return etiquetas
    for g in _grupos_ordenados(fase):
        for i, fila in enumerate(g.tabla_posiciones()[:CLASIFICAN_POR_GRUPO], start=1):
            etiquetas[fila["equipo"].id] = f"{i}° {g.nombre}"
    return etiquetas


def _ganador(p):
    if p.estado != "jugado" or p.resultado_local is None or p.resultado_visitante is None:
        return None
    if p.resultado_local > p.resultado_visitante:
        return p.equipo_local
    if p.resultado_visitante > p.resultado_local:
        return p.equipo_visitante
    return None  # empate: el sistema aun no guarda penales


def armar_llaves():
    """Devuelve {'jornada': Jornada, 'cuartos': [4 dicts]} o None si no existen."""
    jornada = _jornada_cuartos()
    if not jornada:
        return None
    etiquetas = _etiquetas_seed()
    partidos = sorted(jornada.partidos, key=lambda p: p.id)[:4]
    cuartos = []
    for i, p in enumerate(partidos):
        cuartos.append({
            "num": i + 1,
            "lado": "izq" if i < 2 else "der",
            "partido": p,
            "etiqueta_local": etiquetas.get(p.equipo_local_id),
            "etiqueta_visitante": etiquetas.get(p.equipo_visitante_id),
            "ganador": _ganador(p),
            "empate": (p.estado == "jugado" and p.resultado_local is not None
                       and p.resultado_local == p.resultado_visitante),
        })
    return {"jornada": jornada, "cuartos": cuartos}
