"""Llaves de la fase final (cuartos, semifinales y final).

Cuando termina la fase regular (liguilla a una vuelta en dos grupos), clasifican
los 4 mejores de cada grupo y los cruces son:

    Lado izquierdo:  1° A vs 4° B   |   3° A vs 2° B
    Lado derecho:    1° B vs 4° A   |   3° B vs 2° A

Los cuartos viven como una Fase (tipo "cuartos") con una sola Jornada en
borrador, para reutilizar todo lo que ya existe: editar fecha/hora/cancha,
capturar resultado, publicar la jornada, PDF, notificaciones.

Semifinales: ganador C1 vs ganador C2 (izq.) y ganador C3 vs ganador C4 (der.).
Final: ganador SF1 vs ganador SF2. Cada ronda es una Fase con una sola Jornada.

No hay columnas nuevas en la base de datos: el lugar de cada partido dentro de
la llave se deduce del orden de creacion (id) de los partidos de la jornada:
    cuartos: 1 = izq. arriba, 2 = izq. abajo, 3 = der. arriba, 4 = der. abajo
Si un partido termina empatado, el organizador elige quien avanzo al generar la
siguiente ronda; despues, el ganador se deduce viendo que equipo aparece en la
siguiente ronda (asi no hace falta guardar penales).
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


# ---------- Rondas ----------

TIPO_SEMIS = "semifinales"
TIPO_FINAL = "final"

RONDAS = {
    "cuartos": {"tipo": TIPO_CUARTOS, "nombre": "Cuartos de final", "n": 4, "paso": 1,
                "slots": SLOTS_CUARTOS, "anterior": None, "siguiente": "semifinales"},
    "semifinales": {"tipo": TIPO_SEMIS, "nombre": "Semifinales", "n": 2, "paso": 2,
                    "slots": [("martes", "10:00"), ("martes", "11:00")],
                    "anterior": "cuartos", "siguiente": "final"},
    "final": {"tipo": TIPO_FINAL, "nombre": "Final", "n": 1, "paso": 3,
              "slots": [("martes", "10:00")], "anterior": "semifinales", "siguiente": None},
}


def _fase_ronda(clave):
    return Fase.query.filter_by(tipo=RONDAS[clave]["tipo"]).first()


def _jornada_ronda(clave):
    fase = _fase_ronda(clave)
    if not fase:
        return None
    return Jornada.query.filter_by(fase_id=fase.id).order_by(Jornada.numero).first()


def _partidos_ronda(clave, publico=False):
    """Partidos de la ronda en orden de llave. Con publico=True, una ronda cuya
    jornada sigue en borrador no existe para el publico."""
    j = _jornada_ronda(clave)
    if not j or (publico and j.estado != "publicada"):
        return []
    return sorted(j.partidos, key=lambda p: p.id)[:RONDAS[clave]["n"]]


def _jugado(p):
    return p.estado == "jugado" and p.resultado_local is not None and p.resultado_visitante is not None


def _es_empate(p):
    return _jugado(p) and p.resultado_local == p.resultado_visitante


def _ganador(p, siguientes):
    """Ganador por marcador; si hubo empate, el equipo que aparece en la
    siguiente ronda (lo que el organizador eligio al generarla)."""
    if not _jugado(p):
        return None
    if p.resultado_local > p.resultado_visitante:
        return p.equipo_local
    if p.resultado_visitante > p.resultado_local:
        return p.equipo_visitante
    ids = set()
    for q in siguientes:
        ids.update([q.equipo_local_id, q.equipo_visitante_id])
    avanzan = [e for e in (p.equipo_local, p.equipo_visitante) if e.id in ids]
    return avanzan[0] if len(avanzan) == 1 else None


def _nombre_partido(p):
    return f"{p.equipo_local.nombre} vs {p.equipo_visitante.nombre}"


def _ultima_fecha(clave):
    j = _jornada_ronda(clave)
    fechas = [p.fecha for p in j.partidos if p.fecha] if j else []
    return max(fechas) if fechas else None


def _vaciar_jornada(jornada):
    for p in list(jornada.partidos):
        EventoPartido.query.filter_by(partido_id=p.id).delete()
        DetallePartidoEquipo.query.filter_by(partido_id=p.id).delete()
        SolicitudCambioHorario.query.filter_by(partido_id=p.id).delete()
        Asistencia.query.filter_by(partido_id=p.id).delete()
        db.session.delete(p)
    db.session.delete(jornada)


def _crear_ronda(clave, cruces, fecha_base):
    """Crea la Fase (si hace falta) y la Jornada en borrador con los cruces,
    en el orden de los slots de la ronda."""
    cfg = RONDAS[clave]
    fase_g = _fase_grupos()
    fase = _fase_ronda(clave)
    if not fase:
        fase = Fase(categoria_id=fase_g.categoria_id, tipo=cfg["tipo"], nombre=cfg["nombre"],
                    orden=(fase_g.orden or 1) + cfg["paso"])
        db.session.add(fase)
        db.session.flush()

    fecha_ref = (fecha_base or date_cls.today()) + timedelta(days=7)
    fechas = fechas_semana(fecha_ref)
    jornada = Jornada(fase_id=fase.id, numero=1, fecha_referencia=fecha_ref, estado="borrador")
    db.session.add(jornada)
    db.session.flush()

    cancha = Cancha.query.first()
    for (local, visitante), (dia, hora) in zip(cruces, cfg["slots"]):
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


def reiniciar_ronda(clave):
    """Borra una ronda para volver a generarla. Solo mientras su jornada siga
    en borrador y no exista ya la ronda siguiente."""
    nombre = RONDAS[clave]["nombre"].lower()
    jornada = _jornada_ronda(clave)
    if not jornada:
        raise LlavesError(f"Todavía no hay {nombre} generadas.")
    if jornada.estado != "borrador":
        raise LlavesError(f"Las {nombre} ya están publicadas y no se pueden regenerar.")
    sig = RONDAS[clave]["siguiente"]
    if sig and _jornada_ronda(sig):
        raise LlavesError(f"Ya existen las {RONDAS[sig]['nombre'].lower()}; elimínalas primero para regenerar las {nombre}.")
    _vaciar_jornada(jornada)
    db.session.commit()


# ---------- Cuartos ----------

def _clasificados(grupo):
    return [fila["equipo"] for fila in grupo.tabla_posiciones()][:CLASIFICAN_POR_GRUPO]


def _validar_para_generar(estado):
    """Solo bloquea si es imposible armar los cruces (no hay 2 grupos o
    alguno tiene menos de 4 equipos). Que la fase regular no haya terminado
    NO bloquea: el organizador decide cuando generar las llaves."""
    if estado["problema"]:
        raise LlavesError(estado["problema"])


def _cruces_cuartos(estado):
    g1, g2 = estado["grupos"]
    a, b = _clasificados(g1), _clasificados(g2)
    # Orden = posicion en la llave: izq. arriba, izq. abajo, der. arriba, der. abajo
    return [
        (a[0], b[3]),  # 1° A vs 4° B
        (a[2], b[1]),  # 3° A vs 2° B
        (b[0], a[3]),  # 1° B vs 4° A
        (b[2], a[1]),  # 3° B vs 2° A
    ]


def _ultima_fecha_regular(fase):
    return (
        db.session.query(db.func.max(Partido.fecha))
        .join(Jornada).filter(Jornada.fase_id == fase.id).scalar()
    )


def generar_cuartos():
    """Crea la jornada de cuartos (en borrador) con los 4 cruces."""
    estado = estado_fase_regular()
    if _jornada_ronda("cuartos"):
        raise LlavesError("Las llaves ya fueron generadas. Si necesitas rehacerlas, usa \"Regenerar llaves\".")
    _validar_para_generar(estado)
    return _crear_ronda("cuartos", _cruces_cuartos(estado), _ultima_fecha_regular(estado["fase"]))


def regenerar_cuartos():
    """Rehace las llaves con la tabla actual. Valida ANTES de borrar, para no
    dejar al organizador sin llaves si algo no cumple."""
    jornada = _jornada_ronda("cuartos")
    if not jornada:
        raise LlavesError("Todavía no hay llaves generadas.")
    if jornada.estado != "borrador":
        raise LlavesError("Las llaves ya están publicadas y no se pueden regenerar.")
    if _jornada_ronda("semifinales"):
        raise LlavesError("Ya existen las semifinales; elimínalas primero para regenerar los cuartos.")
    _validar_para_generar(estado_fase_regular())
    reiniciar_ronda("cuartos")
    return generar_cuartos()


# ---------- Semifinales y final ----------

def _resolver_ganadores(ant, elegidos=None):
    """Lista de equipos que avanzan de la ronda `ant`, en orden de llave.
    Si hubo empate usa lo elegido por el organizador o, en su defecto, lo que
    ya aparece en la ronda siguiente (al regenerar)."""
    elegidos = elegidos or {}
    cfg = RONDAS[ant]
    partidos = _partidos_ronda(ant)
    if len(partidos) < cfg["n"]:
        raise LlavesError(f"Primero genera {cfg['nombre'].lower()}.")
    siguientes = _partidos_ronda(cfg["siguiente"])
    ganadores = []
    for p in partidos:
        if not _jugado(p):
            raise LlavesError(f"Falta el resultado de {_nombre_partido(p)}.")
        g = _ganador(p, [])
        if g is None:  # empate
            eid = elegidos.get(p.id)
            if eid is None:
                g = _ganador(p, siguientes)
            else:
                g = next((e for e in (p.equipo_local, p.equipo_visitante) if e.id == eid), None)
            if g is None:
                raise LlavesError(f"Empate en {_nombre_partido(p)}: elige quién avanzó.")
        ganadores.append(g)
    return ganadores


def _cruces_de(ganadores):
    return [(ganadores[i], ganadores[i + 1]) for i in range(0, len(ganadores), 2)]


def generar_ronda(clave, elegidos=None):
    """Genera semifinales o final (en borrador) con los ganadores de la ronda anterior."""
    cfg = RONDAS[clave]
    if not cfg["anterior"]:
        raise LlavesError("Los cuartos se generan con el botón de llaves.")
    if _jornada_ronda(clave):
        raise LlavesError(f"Las {cfg['nombre'].lower()} ya fueron generadas.")
    ganadores = _resolver_ganadores(cfg["anterior"], elegidos)
    return _crear_ronda(clave, _cruces_de(ganadores), _ultima_fecha(cfg["anterior"]))


def regenerar_ronda(clave, elegidos=None):
    """Rehace semifinales o final. Resuelve los ganadores ANTES de borrar."""
    cfg = RONDAS[clave]
    jornada = _jornada_ronda(clave)
    if not jornada:
        raise LlavesError(f"Todavía no hay {cfg['nombre'].lower()} generadas.")
    if jornada.estado != "borrador":
        raise LlavesError(f"Las {cfg['nombre'].lower()} ya están publicadas y no se pueden regenerar.")
    ganadores = _resolver_ganadores(cfg["anterior"], elegidos)
    reiniciar_ronda(clave)
    return _crear_ronda(clave, _cruces_de(ganadores), _ultima_fecha(cfg["anterior"]))


def estado_ronda(clave):
    """Datos para el panel de admin de semifinales / final."""
    cfg = RONDAS[clave]
    ant = cfg["anterior"]
    info = {
        "clave": clave, "nombre": cfg["nombre"], "jornada": _jornada_ronda(clave),
        "anterior_nombre": RONDAS[ant]["nombre"].lower(),
        "puede": False, "motivo": None, "faltan": [], "empates": [],
        "siguiente_existe": bool(cfg["siguiente"] and _jornada_ronda(cfg["siguiente"])),
    }
    previos = _partidos_ronda(ant)
    if len(previos) < RONDAS[ant]["n"]:
        info["motivo"] = f"Primero genera {RONDAS[ant]['nombre'].lower()}."
        return info
    propios = _partidos_ronda(clave)
    info["faltan"] = [p for p in previos if not _jugado(p)]
    for p in previos:
        if _es_empate(p):
            g = _ganador(p, propios)
            info["empates"].append({"partido": p, "preseleccion": g.id if g else None})
    info["puede"] = not info["faltan"]
    return info


# ---------- Datos para pintar la llave ----------

def _etiquetas_seed():
    """{equipo_id: '1° A'...} segun la tabla actual de cada grupo."""
    fase = _fase_grupos()
    etiquetas = {}
    if not fase:
        return etiquetas
    for g in _grupos_ordenados(fase):
        for i, fila in enumerate(g.tabla_posiciones()[:CLASIFICAN_POR_GRUPO], start=1):
            etiquetas[fila["equipo"].id] = f"{i}° {g.nombre}"
    return etiquetas


def _tarjetas(partidos, siguientes, titulo, lados, etiquetas=None):
    etiquetas = etiquetas or {}
    out = []
    for i, p in enumerate(partidos):
        out.append({
            "num": i + 1,
            "titulo": titulo.format(n=i + 1),
            "lado": lados[i],
            "partido": p,
            "etiqueta_local": etiquetas.get(p.equipo_local_id),
            "etiqueta_visitante": etiquetas.get(p.equipo_visitante_id),
            "ganador": _ganador(p, siguientes),
            "empate": _es_empate(p),
        })
    return out


def armar_llaves(publico=False):
    """Devuelve el cuadro completo o None si no hay cuartos. Con publico=True,
    las rondas cuya jornada sigue en borrador no se incluyen."""
    cuartos_p = _partidos_ronda("cuartos", publico)
    if not cuartos_p:
        return None
    semis_p = _partidos_ronda("semifinales", publico)
    final_p = _partidos_ronda("final", publico)

    cuartos = _tarjetas(cuartos_p, semis_p, "Cuarto {n}", ["izq", "izq", "der", "der"], _etiquetas_seed())
    semis = _tarjetas(semis_p, final_p, "Semifinal {n}", ["izq", "der"])
    final = _tarjetas(final_p, [], "Final", ["centro"])
    final = final[0] if final else None
    return {
        "jornada": _jornada_ronda("cuartos"),
        "jornada_semis": _jornada_ronda("semifinales"),
        "jornada_final": _jornada_ronda("final"),
        "cuartos": cuartos,
        "semis": semis,
        "final": final,
        "campeon": final["ganador"] if final else None,
    }
