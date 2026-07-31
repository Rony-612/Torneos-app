"""Generación de calendario por reglas simples (v1, sin optimización).

El torneo DCEA solo juega martes, miércoles y jueves de 10:00 a 14:00
(bloques de una hora) porque solo hay una cancha y un árbitro disponibles.
Ese patrón vive en app.services.jornada_grid y es la misma rejilla que usan
la disponibilidad de los capitanes y la tabla visual de cada jornada.

Cuando ya no quedan enfrentamientos nuevos por programar (la ronda regular
se agotó) pero todavía hay partidos suspendidos/pendientes de la fase, esta
misma función arma una última jornada juntando esos pendientes en vez de
crear partidos nuevos.

Punto de extensión para el futuro: cuando se agregue un algoritmo de
optimización, este módulo es el único que cambia.
"""
from itertools import combinations
from datetime import datetime, timedelta
from app.extensions import db
from app.models import Grupo, Disponibilidad, Partido, Cancha, Arbitro
from app.services.jornada_grid import DIAS_GRID, HORAS_GRID, fechas_semana


def _partidos_ya_jugados_o_programados(fase_id):
    pares = set()
    partidos = Partido.query.join(Partido.jornada).filter_by(fase_id=fase_id).all()
    for p in partidos:
        pares.add(frozenset([p.equipo_local_id, p.equipo_visitante_id]))
    return pares


def _ronda_pendiente(equipos, ya_jugados):
    """Arma el mayor numero posible de enfrentamientos (un partido por equipo
    como maximo) sin repetir partidos ya jugados o ya programados en la fase.

    Un emparejamiento 'codicioso' (tomar la primera pareja disponible en
    orden) puede dejar equipos sueltos por error, aunque exista una
    combinacion que los acomode a todos: por ejemplo, si A ya jugo con B,
    emparejar primero C-D puede dejar a A y a otro equipo sin pareja, cuando
    A-C y algo mas si hubiera cabido. Por eso aqui se prueban combinaciones
    con backtracking (con poda) para encontrar la ronda mas completa posible.
    Los grupos de un torneo tipico (varios equipos) son chicos, asi que esto
    es instantaneo.
    """
    equipos = list(equipos)
    mejor = []

    def backtrack(disponibles, actual):
        nonlocal mejor
        if len(actual) > len(mejor):
            mejor = list(actual)
        # poda: si ni emparejando a todos los que quedan se supera lo mejor, no sigas
        cota_superior = len(actual) + len(disponibles) // 2
        if cota_superior <= len(mejor) or not disponibles:
            return
        primero, resto = disponibles[0], disponibles[1:]
        # opcion A: intenta parear "primero" con cada posible rival valido
        for i, otro in enumerate(resto):
            if frozenset([primero.id, otro.id]) in ya_jugados:
                continue
            nuevo_resto = resto[:i] + resto[i + 1:]
            backtrack(nuevo_resto, actual + [(primero, otro)])
        # opcion B: "primero" se queda sin pareja esta ronda
        backtrack(resto, actual)

    backtrack(equipos, [])
    return mejor


def _disponibilidad_equipo(equipo_id, temporada_id, semana):
    filas = Disponibilidad.query.filter_by(equipo_id=equipo_id, temporada_id=temporada_id, semana=semana).all()
    return {(d.dia_semana, d.hora_inicio.strftime("%H:%M")) for d in filas}


def generar_propuesta_jornada(fase_id, temporada_id, fecha_base=None, numero=None):
    """Genera una jornada BORRADOR acomodando partidos en los slots fijos del
    torneo (martes/miércoles/jueves, 10:00-14:00), priorizando los horarios
    donde ambos capitanes marcaron disponibilidad. Como solo hay una cancha,
    cada slot se usa una sola vez.

    Primero intenta armar una ronda nueva (un enfrentamiento pendiente por
    equipo). Si ya no hay enfrentamientos nuevos pero existen partidos
    suspendidos/pendientes en la fase, arma la jornada final reacomodando
    esos partidos pendientes en vez de crear unos nuevos.

    Regresa (jornada, partidos, usando_pendientes). Si no hay absolutamente
    nada que programar, regresa (None, [], False).
    """
    from app.models import Jornada

    fecha_base = fecha_base or datetime.utcnow().date()
    lunes_semana = fecha_base - timedelta(days=fecha_base.weekday())
    fechas = fechas_semana(fecha_base)
    ya_jugados = _partidos_ya_jugados_o_programados(fase_id)
    grupos = Grupo.query.filter_by(fase_id=fase_id).all()
    cancha = Cancha.query.first()
    arbitro = Arbitro.query.first()

    # 1. intenta armar una ronda nueva de enfrentamientos que no se hayan jugado
    pendientes_nuevos = []
    for grupo in grupos:
        ronda = _ronda_pendiente(grupo.equipos(), ya_jugados)
        pendientes_nuevos.extend(ronda)
        for a, b in ronda:
            ya_jugados.add(frozenset([a.id, b.id]))

    usando_pendientes = False
    partidos_a_reprogramar = []
    if not pendientes_nuevos:
        # 2. ya no hay enfrentamientos nuevos: junta los que quedaron suspendidos
        from app.models import Jornada as JornadaModel
        partidos_a_reprogramar = (
            Partido.query.join(JornadaModel, Partido.jornada_id == JornadaModel.id)
            .filter(JornadaModel.fase_id == fase_id, Partido.estado == "suspendido")
            .all()
        )
        if not partidos_a_reprogramar:
            return None, [], False
        usando_pendientes = True

    if numero is None:
        ultimo = Jornada.query.filter_by(fase_id=fase_id).order_by(Jornada.numero.desc()).first()
        numero = (ultimo.numero + 1) if ultimo else 1

    jornada = Jornada(fase_id=fase_id, numero=numero, fecha_referencia=fecha_base, estado="borrador")
    db.session.add(jornada)
    db.session.flush()

    # todos los slots fijos disponibles esta semana (una cancha = un partido por slot)
    slots_libres = [(dia, hora) for dia in DIAS_GRID for hora in HORAS_GRID]
    partidos_creados = []

    if usando_pendientes:
        pares = [(p.equipo_local, p.equipo_visitante, p) for p in partidos_a_reprogramar]
    else:
        pares = [(a, b, None) for a, b in pendientes_nuevos]

    # 1a pasada: prioriza slots donde ambos equipos marcaron disponibilidad
    asignaciones = {}
    restantes = []
    for equipo_a, equipo_b, partido_existente in pares:
        disp_a = _disponibilidad_equipo(equipo_a.id, temporada_id, lunes_semana)
        disp_b = _disponibilidad_equipo(equipo_b.id, temporada_id, lunes_semana)
        comunes = disp_a & disp_b
        elegido = next((s for s in slots_libres if s in comunes), None)
        if elegido:
            slots_libres.remove(elegido)
            asignaciones[elegido] = (equipo_a, equipo_b, partido_existente, False)
        else:
            restantes.append((equipo_a, equipo_b, partido_existente))

    # 2a pasada: lo que no tuvo coincidencia, se acomoda en lo que vaya quedando
    for equipo_a, equipo_b, partido_existente in restantes:
        if not slots_libres:
            break
        elegido = slots_libres.pop(0)
        asignaciones[elegido] = (equipo_a, equipo_b, partido_existente, True)

    for (dia, hora), (equipo_a, equipo_b, partido_existente, sin_coincidencia) in asignaciones.items():
        nota = "Sin coincidencia de disponibilidad: horario por confirmar" if sin_coincidencia else None
        if partido_existente:
            # reprograma el partido pendiente en vez de crear uno nuevo
            partido_existente.jornada_id = jornada.id
            partido_existente.fecha = fechas[dia]
            partido_existente.hora = datetime.strptime(hora, "%H:%M").time()
            partido_existente.estado = "programado"
            partido_existente.nota = nota
            partidos_creados.append(partido_existente)
        else:
            partido = Partido(
                jornada_id=jornada.id, equipo_local_id=equipo_a.id, equipo_visitante_id=equipo_b.id,
                cancha_id=cancha.id if cancha else None, arbitro_id=arbitro.id if arbitro else None,
                fecha=fechas[dia], hora=datetime.strptime(hora, "%H:%M").time(),
                estado="programado", nota=nota,
            )
            db.session.add(partido)
            partidos_creados.append(partido)

    db.session.commit()
    return jornada, partidos_creados, usando_pendientes
