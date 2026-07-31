import os
from flask import Blueprint, render_template, abort, request, jsonify
from app.models import Torneo, Fase, Grupo, Jornada, Partido, Equipo, Jugador, Noticia, Temporada
from app.services import estadisticas_service, notificacion_service

public_bp = Blueprint("public", "public_routes", template_folder="../templates/public")


def _fase_actual():
    """MVP: toma la primera fase de tipo 'grupos' del primer torneo registrado."""
    fase = Fase.query.filter_by(tipo="grupos").first()
    return fase


@public_bp.route("/")
def home():
    fase = _fase_actual()
    torneo = Torneo.query.first()
    proximos = []
    ultimos = []
    jornada_actual = None
    if fase:
        jornada_actual = (
            Jornada.query.filter_by(fase_id=fase.id, estado="publicada")
            .order_by(Jornada.numero.desc()).first()
        )
        proximos = (
            Partido.query.join(Jornada).filter(
                Jornada.fase_id == fase.id, Jornada.estado == "publicada",
                Partido.estado == "programado",
            ).order_by(Partido.fecha, Partido.hora).limit(5).all()
        )
        ultimos = (
            Partido.query.join(Jornada).filter(
                Jornada.fase_id == fase.id, Jornada.estado == "publicada",
                Partido.estado == "jugado",
            ).order_by(Partido.fecha.desc()).limit(5).all()
        )
    goleadores = estadisticas_service.tabla_goleadores(fase.id if fase else None, limite=5)
    noticias = Noticia.query.order_by(Noticia.fecha_publicacion.desc()).limit(3).all()
    return render_template(
        "public/home.html", torneo=torneo, jornada_actual=jornada_actual,
        proximos=proximos, ultimos=ultimos, goleadores=goleadores, noticias=noticias,
    )


@public_bp.route("/tabla")
def tabla_posiciones():
    fase = _fase_actual()
    if not fase:
        abort(404)
    grupos = Grupo.query.filter_by(fase_id=fase.id).all()
    tablas = {g.nombre: g.tabla_posiciones() for g in grupos}
    return render_template("public/tabla.html", tablas=tablas)


@public_bp.route("/calendario")
def calendario():
    fase = _fase_actual()
    if not fase:
        abort(404)
    from app.services.jornada_grid import construir_grid
    jornadas = (
        Jornada.query.filter_by(fase_id=fase.id, estado="publicada")
        .order_by(Jornada.numero).all()
    )
    jornadas_con_grid = [(j, construir_grid(j)) for j in jornadas]
    return render_template("public/calendario.html", jornadas_con_grid=jornadas_con_grid)


@public_bp.route("/partido/<int:partido_id>")
def partido_detalle(partido_id):
    partido = Partido.query.get_or_404(partido_id)
    if partido.jornada.estado != "publicada":
        abort(404)
    return render_template("public/partido.html", partido=partido)


@public_bp.route("/goleadores")
def goleadores():
    fase = _fase_actual()
    tabla = estadisticas_service.tabla_goleadores(fase.id if fase else None, limite=30)
    return render_template("public/goleadores.html", tabla=tabla)


@public_bp.route("/disciplina")
def disciplina():
    fase = _fase_actual()
    tabla = estadisticas_service.tabla_disciplinaria(fase.id if fase else None, limite=30)
    return render_template("public/disciplina.html", tabla=tabla)


@public_bp.route("/equipos")
def equipos():
    lista = Equipo.query.order_by(Equipo.nombre).all()
    return render_template("public/equipos.html", equipos=lista)


@public_bp.route("/equipos/<int:equipo_id>")
def equipo_detalle(equipo_id):
    equipo = Equipo.query.get_or_404(equipo_id)
    temporada = Temporada.query.first()
    jugadores = equipo.jugadores_temporada(temporada.id) if temporada else []
    partidos = sorted(equipo.partidos(), key=lambda p: p.fecha)
    proximos = [p for p in partidos if p.estado == "programado"]
    jugados = [p for p in partidos if p.estado == "jugado"]
    return render_template(
        "public/equipo.html", equipo=equipo, jugadores=jugadores,
        proximos=proximos, jugados=jugados,
    )


@public_bp.route("/jugadores/<int:jugador_id>")
def jugador_detalle(jugador_id):
    jugador = Jugador.query.get_or_404(jugador_id)
    temporada = Temporada.query.first()
    equipo = jugador.equipo_actual(temporada.id) if temporada else None
    stats = jugador.estadisticas()
    return render_template("public/jugador.html", jugador=jugador, equipo=equipo, stats=stats)


@public_bp.route("/noticias")
def noticias():
    lista = Noticia.query.order_by(Noticia.fecha_publicacion.desc()).all()
    return render_template("public/noticias.html", noticias=lista)


@public_bp.route("/noticias/<int:noticia_id>")
def noticia_detalle(noticia_id):
    noticia = Noticia.query.get_or_404(noticia_id)
    return render_template("public/noticia.html", noticia=noticia)


@public_bp.route("/tareas/recordatorios")
def tarea_recordatorios():
    """Dispara el envío de recordatorios de partido (un día antes / una hora
    antes) por HTTP, protegido con un token secreto. Pensado para llamarse
    desde un servicio externo de 'cron por HTTP' (por ejemplo cron-job.org,
    gratis) cuando el hosting elegido no ofrece tareas programadas propias.

    Configura la variable de entorno CRON_SECRET con un valor largo y
    aleatorio, y llama a esta URL con ?token=ese-valor. Sin CRON_SECRET
    configurado, este endpoint está desactivado por seguridad."""
    secreto_esperado = os.environ.get("CRON_SECRET")
    if not secreto_esperado:
        abort(404)
    if request.args.get("token") != secreto_esperado:
        abort(403)
    enviados_dia, enviados_hora = notificacion_service.ejecutar_recordatorios()
    return jsonify({"recordatorios_dia_antes": enviados_dia, "recordatorios_hora_antes": enviados_hora})
