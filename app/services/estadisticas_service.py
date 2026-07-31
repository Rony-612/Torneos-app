from app.extensions import db
from app.models import EventoPartido, Jugador, Partido


def tabla_goleadores(fase_id=None, limite=20):
    q = (
        db.session.query(
            EventoPartido.jugador_id,
            db.func.count(EventoPartido.id).label("goles"),
        )
        .filter(EventoPartido.tipo_evento == "gol")
    )
    if fase_id:
        q = q.join(Partido, Partido.id == EventoPartido.partido_id).join(
            Partido.jornada
        ).filter_by(fase_id=fase_id)
    q = q.group_by(EventoPartido.jugador_id).order_by(db.desc("goles")).limit(limite)

    resultados = []
    for jugador_id, goles in q.all():
        jugador = Jugador.query.get(jugador_id)
        if jugador:
            resultados.append({"jugador": jugador, "goles": goles})
    return resultados


def tabla_disciplinaria(fase_id=None, limite=20):
    q = (
        db.session.query(
            EventoPartido.jugador_id,
            db.func.sum(db.case((EventoPartido.tipo_evento == "tarjeta_amarilla", 1), else_=0)).label("amarillas"),
            db.func.sum(db.case((EventoPartido.tipo_evento == "tarjeta_roja", 1), else_=0)).label("rojas"),
        )
        .filter(EventoPartido.tipo_evento.in_(["tarjeta_amarilla", "tarjeta_roja"]))
    )
    if fase_id:
        q = q.join(Partido, Partido.id == EventoPartido.partido_id).join(
            Partido.jornada
        ).filter_by(fase_id=fase_id)
    q = q.group_by(EventoPartido.jugador_id)

    resultados = []
    for jugador_id, amarillas, rojas in q.all():
        jugador = Jugador.query.get(jugador_id)
        if jugador:
            resultados.append({"jugador": jugador, "amarillas": amarillas or 0, "rojas": rojas or 0})
    resultados.sort(key=lambda r: (-r["rojas"], -r["amarillas"]))
    return resultados[:limite]
