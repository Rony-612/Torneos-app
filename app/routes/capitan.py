from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_user, logout_user, login_required, current_user

from app.extensions import db
from app.models import (
    Usuario, Equipo, Temporada, Disponibilidad, SolicitudCambioHorario, Partido,
    Grupo, Jugador, EventoPartido, DetallePartidoEquipo, PagoCancha,
)
from app.services import estadisticas_service, notificacion_service
from app.utils import requiere_rol

capitan_bp = Blueprint("capitan", "capitan_routes", template_folder="../templates/capitan")


@capitan_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        user = Usuario.query.filter_by(email=email).first()
        if user and user.check_password(password) and user.rol == "capitan":
            login_user(user)
            return redirect(url_for("capitan.panel"))
        flash("Credenciales inválidas.", "error")
    return render_template("capitan/login.html")


@capitan_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("capitan.login"))


def _mi_equipo():
    return Equipo.query.filter_by(capitan_id=current_user.id).first()


@capitan_bp.route("/")
@login_required
@requiere_rol("capitan")
def panel():
    equipo = _mi_equipo()
    if not equipo:
        abort(404)
    from app.models import Inscripcion
    partidos = sorted(equipo.partidos(), key=lambda p: p.fecha)
    proximos = [p for p in partidos if p.estado == "programado"]
    proximo = proximos[0] if proximos else None

    inscripcion = Inscripcion.query.filter_by(equipo_id=equipo.id, estado="activo").first()
    grupo = Grupo.query.get(inscripcion.grupo_id) if inscripcion else None
    posicion, pts = None, None
    if grupo:
        tabla = grupo.tabla_posiciones()
        for i, fila in enumerate(tabla, start=1):
            if fila["equipo"].id == equipo.id:
                posicion, pts = i, fila["pts"]
                break

    temporada = Temporada.query.first()
    hoy = datetime.utcnow().date()
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    disp_count = Disponibilidad.query.filter_by(equipo_id=equipo.id, temporada_id=temporada.id, semana=inicio_semana).count() if temporada else 0
    pendientes_pago = [p for p in partidos if p.estado != "suspendido" and not p.arbitraje_pagado_de(equipo.id)]

    from app.models import ObjetoPerdido
    avisos = ObjetoPerdido.query.filter_by(resuelto=False).order_by(ObjetoPerdido.fecha_reporte.desc()).limit(2).all()

    return render_template(
        "capitan/panel.html", equipo=equipo, proximos=proximos, proximo=proximo,
        grupo=grupo, posicion=posicion, pts=pts, disp_count=disp_count,
        pendientes_pago=pendientes_pago, avisos=avisos,
    )


from app.services.jornada_grid import DIAS_GRID as DIAS_GRID_DISP, HORAS_GRID as HORAS_GRID_DISP


@capitan_bp.route("/disponibilidad", methods=["GET", "POST"])
@login_required
@requiere_rol("capitan")
def disponibilidad():
    equipo = _mi_equipo()
    temporada = Temporada.query.first()

    hoy = datetime.utcnow().date()
    semana_param = request.values.get("semana")
    if semana_param:
        semana = datetime.strptime(semana_param, "%Y-%m-%d").date()
    else:
        semana = hoy - timedelta(days=hoy.weekday())

    if request.method == "POST":
        # reemplaza toda la disponibilidad de esta semana con lo que llego marcado
        Disponibilidad.query.filter_by(equipo_id=equipo.id, temporada_id=temporada.id, semana=semana).delete()
        for slot in request.form.getlist("slot"):
            dia, hora_str = slot.split("|")
            hora_inicio = datetime.strptime(hora_str, "%H:%M").time()
            hora_fin_dt = datetime.combine(hoy, hora_inicio) + timedelta(hours=1)
            db.session.add(Disponibilidad(
                equipo_id=equipo.id, temporada_id=temporada.id, semana=semana,
                dia_semana=dia, hora_inicio=hora_inicio, hora_fin=hora_fin_dt.time(),
            ))
        db.session.commit()
        flash(f"Disponibilidad de la semana del {semana.strftime('%d/%m/%Y')} guardada.", "success")
        return redirect(url_for("capitan.disponibilidad", semana=semana.isoformat()))

    registrados = Disponibilidad.query.filter_by(equipo_id=equipo.id, temporada_id=temporada.id, semana=semana).all()
    marcados = {f"{d.dia_semana}|{d.hora_inicio.strftime('%H:%M')}" for d in registrados}

    return render_template(
        "capitan/disponibilidad.html", dias=DIAS_GRID_DISP, horas=HORAS_GRID_DISP, marcados=marcados,
        semana=semana, semana_anterior=semana - timedelta(days=7), semana_siguiente=semana + timedelta(days=7),
    )


@capitan_bp.route("/partidos/<int:partido_id>/solicitar-cambio", methods=["GET", "POST"])
@login_required
@requiere_rol("capitan")
def solicitar_cambio(partido_id):
    from app.models import OpcionCambioHorario
    from app.services.jornada_grid import construir_grid

    equipo = _mi_equipo()
    partido = Partido.query.get_or_404(partido_id)
    if equipo.id not in (partido.equipo_local_id, partido.equipo_visitante_id):
        abort(403)

    if request.method == "POST":
        slots = request.form.getlist("slot")
        if not slots:
            flash("Selecciona al menos un horario disponible para proponer.", "error")
            return redirect(url_for("capitan.solicitar_cambio", partido_id=partido_id))

        solicitud = SolicitudCambioHorario(
            partido_id=partido.id, solicitado_por_equipo_id=equipo.id,
            comentario=request.form.get("comentario"), estado="pendiente_rival",
        )
        db.session.add(solicitud)
        db.session.flush()
        fechas = construir_grid(partido.jornada)["dias"]
        fechas_dict = dict(fechas)
        for slot in slots:
            dia, hora_str = slot.split("|")
            db.session.add(OpcionCambioHorario(
                solicitud_id=solicitud.id, fecha=fechas_dict[dia],
                hora=datetime.strptime(hora_str, "%H:%M").time(),
            ))
        db.session.commit()
        notificacion_service.notificar_solicitud_cambio(solicitud)
        flash("Propuesta enviada al equipo rival con los horarios que seleccionaste.", "success")
        return redirect(url_for("capitan.solicitudes"))

    grid = construir_grid(partido.jornada, excluir_partido_id=partido.id)
    return render_template("capitan/solicitar_cambio.html", partido=partido, grid=grid)


def _equipo_rival(partido, mi_equipo_id):
    if partido.equipo_local_id == mi_equipo_id:
        return partido.equipo_visitante
    return partido.equipo_local


@capitan_bp.route("/solicitudes")
@login_required
@requiere_rol("capitan")
def solicitudes():
    from app.services.jornada_grid import construir_grid
    equipo = _mi_equipo()
    todas = SolicitudCambioHorario.query.all()
    por_responder = [
        s for s in todas
        if s.estado == "pendiente_rival"
        and s.solicitado_por_equipo_id != equipo.id
        and _equipo_rival(s.partido, s.solicitado_por_equipo_id).id == equipo.id
    ]
    grids_por_responder = {}
    for s in por_responder:
        grid = construir_grid(s.partido.jornada, excluir_partido_id=s.partido.id)
        opciones_dict = {}
        for op in s.opciones:
            dia_label = next((d for d, f in grid["dias"] if f == op.fecha), None)
            hora_str = op.hora.strftime("%H:%M")
            if dia_label:
                opciones_dict[(dia_label, hora_str)] = op
        grids_por_responder[s.id] = (grid, opciones_dict)

    mis_solicitudes = [s for s in todas if s.solicitado_por_equipo_id == equipo.id]
    return render_template(
        "capitan/solicitudes.html", por_responder=por_responder, mis_solicitudes=mis_solicitudes,
        grids_por_responder=grids_por_responder,
    )


@capitan_bp.route("/solicitudes/<int:solicitud_id>/responder", methods=["POST"])
@login_required
@requiere_rol("capitan")
def responder_solicitud(solicitud_id):
    equipo = _mi_equipo()
    solicitud = SolicitudCambioHorario.query.get_or_404(solicitud_id)
    rival = _equipo_rival(solicitud.partido, solicitud.solicitado_por_equipo_id)
    if rival.id != equipo.id or solicitud.estado != "pendiente_rival":
        abort(403)

    decision = request.form["decision"]
    if decision == "aceptar":
        from app.models import OpcionCambioHorario
        opcion_id = request.form.get("opcion_id")
        if not opcion_id:
            flash("Elige cuál de los horarios propuestos te funciona.", "error")
            return redirect(url_for("capitan.solicitudes"))
        opcion = OpcionCambioHorario.query.get_or_404(opcion_id)
        solicitud.nueva_fecha = opcion.fecha
        solicitud.nueva_hora = opcion.hora
        solicitud.estado = "pendiente_organizador"
        db.session.commit()
        notificacion_service.notificar_cambio_pendiente_aprobacion(solicitud)
        flash("Aceptaste el cambio. Ahora espera la aprobación final de la organizadora.", "success")
    else:
        solicitud.estado = "rechazado_por_rival"
        db.session.commit()
        notificacion_service.notificar_rechazo_cambio(solicitud)
        flash("Rechazaste la propuesta. La organizadora decidirá si el partido se queda igual o pasa a pendientes.", "success")
    return redirect(url_for("capitan.solicitudes"))


# ---------- Mi equipo (documentacion) ----------

@capitan_bp.route("/mi-equipo")
@login_required
@requiere_rol("capitan")
def mi_equipo():
    equipo = _mi_equipo()
    temporada = Temporada.query.first()
    rosters = equipo.rosters
    return render_template("capitan/mi_equipo.html", equipo=equipo, rosters=rosters)


# ---------- Arbitrajes (solo lectura: el pago lo controla la organizacion) ----------

@capitan_bp.route("/arbitrajes")
@login_required
@requiere_rol("capitan")
def arbitrajes():
    equipo = _mi_equipo()
    partidos = sorted(equipo.partidos(), key=lambda p: p.fecha)
    return render_template("capitan/arbitrajes.html", equipo=equipo, partidos=partidos)


# ---------- Pagos de cancha (solo lectura) ----------

@capitan_bp.route("/pagos-cancha")
@login_required
@requiere_rol("capitan")
def pagos_cancha():
    equipo = _mi_equipo()
    temporada = Temporada.query.first()
    pago = PagoCancha.query.filter_by(equipo_id=equipo.id, temporada_id=temporada.id).first() if temporada else None
    return render_template("capitan/pagos_cancha.html", equipo=equipo, pago=pago)


# ---------- Detalles del partido (uniforme / casacas) ----------

@capitan_bp.route("/partidos/<int:partido_id>/detalles", methods=["POST"])
@login_required
@requiere_rol("capitan")
def guardar_detalles_partido(partido_id):
    equipo = _mi_equipo()
    partido = Partido.query.get_or_404(partido_id)
    detalle = partido.detalle_de(equipo.id)
    if not detalle:
        detalle = DetallePartidoEquipo(partido_id=partido.id, equipo_id=equipo.id)
        db.session.add(detalle)
    detalle.color_uniforme = request.form.get("color_uniforme")
    detalle.lleva_casacas = request.form.get("lleva_casacas") == "si"
    db.session.commit()
    flash("Detalles del partido guardados.", "success")
    return redirect(url_for("capitan.panel"))


# ---------- Mi grupo y goleadores ----------

@capitan_bp.route("/mi-grupo")
@login_required
@requiere_rol("capitan")
def mi_grupo():
    equipo = _mi_equipo()
    from app.models import Inscripcion
    inscripcion = Inscripcion.query.filter_by(equipo_id=equipo.id, estado="activo").first()
    grupo = Grupo.query.get(inscripcion.grupo_id) if inscripcion else None
    tabla = grupo.tabla_posiciones() if grupo else []
    return render_template("capitan/mi_grupo.html", grupo=grupo, tabla=tabla, mi_equipo_id=equipo.id)


@capitan_bp.route("/goleadores")
@login_required
@requiere_rol("capitan")
def goleadores():
    equipo = _mi_equipo()
    from app.models import Inscripcion
    inscripcion = Inscripcion.query.filter_by(equipo_id=equipo.id, estado="activo").first()
    grupo = Grupo.query.get(inscripcion.grupo_id) if inscripcion else None
    fase_id = grupo.fase_id if grupo else None
    tabla = estadisticas_service.tabla_goleadores(fase_id, limite=15)
    return render_template("capitan/goleadores.html", tabla=tabla)


# ---------- Avisos (objetos perdidos) ----------

@capitan_bp.route("/avisos", methods=["GET", "POST"])
@login_required
@requiere_rol("capitan")
def avisos():
    from app.models import ObjetoPerdido, Organizacion
    equipo = _mi_equipo()
    if request.method == "POST":
        org = Organizacion.query.first()
        objeto = ObjetoPerdido(
            organizacion_id=org.id, titulo=request.form["titulo"],
            descripcion=request.form.get("descripcion"), ubicacion=request.form.get("ubicacion"),
            reportado_por_equipo_id=equipo.id,
        )
        db.session.add(objeto)
        db.session.commit()
        flash("Aviso publicado. Los demás capitanes podrán verlo.", "success")
        return redirect(url_for("capitan.avisos"))
    lista = ObjetoPerdido.query.filter_by(resuelto=False).order_by(ObjetoPerdido.fecha_reporte.desc()).all()
    return render_template("capitan/avisos.html", objetos=lista)
