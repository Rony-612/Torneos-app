from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_user, logout_user, login_required, current_user

from app.extensions import db
from app.models import (
    Usuario, Fase, Grupo, Jornada, Partido, Equipo, Jugador, Roster,
    EventoPartido, Noticia, Cancha, Arbitro, Temporada, Inscripcion,
    Disponibilidad, SolicitudCambioHorario, ObjetoPerdido, PagoCancha,
)
from app.services import jornada_service, calendario_service, notificacion_service
from app.utils import requiere_rol

admin_bp = Blueprint("admin", "admin_routes", template_folder="../templates/admin")


# ---------- Auth ----------

@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        user = Usuario.query.filter_by(email=email).first()
        if user and user.check_password(password) and user.es_staff():
            login_user(user)
            return redirect(url_for("admin.dashboard"))
        flash("Credenciales inválidas o cuenta sin permisos de organización.", "error")
    return render_template("admin/login.html")


@admin_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("admin.login"))


# ---------- Dashboard ----------

@admin_bp.route("/")
@login_required
@requiere_rol("organizador", "ayudante")
def dashboard():
    fase = Fase.query.filter_by(tipo="grupos").first()
    jornadas = Jornada.query.filter_by(fase_id=fase.id).order_by(Jornada.numero).all() if fase else []
    equipos_count = Equipo.query.count()
    jugadores_count = Jugador.query.count()
    return render_template(
        "admin/dashboard.html", jornadas=jornadas,
        equipos_count=equipos_count, jugadores_count=jugadores_count, fase=fase,
    )


# ---------- Jornadas ----------

@admin_bp.route("/jornadas/nueva", methods=["POST"])
@login_required
@requiere_rol("organizador", "ayudante")
def crear_jornada():
    fase = Fase.query.filter_by(tipo="grupos").first()
    ultimo = Jornada.query.filter_by(fase_id=fase.id).order_by(Jornada.numero.desc()).first()
    numero = (ultimo.numero + 1) if ultimo else 1
    jornada_service.crear_jornada(fase.id, numero)
    flash(f"Jornada {numero} creada en estado borrador.", "success")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/jornadas/<int:jornada_id>")
@login_required
@requiere_rol("organizador", "ayudante")
def jornada_detalle(jornada_id):
    jornada = Jornada.query.get_or_404(jornada_id)
    equipos = Equipo.query.order_by(Equipo.nombre).all()
    canchas = Cancha.query.all()
    arbitros = Arbitro.query.all()
    from app.services.jornada_grid import construir_grid
    grid = construir_grid(jornada)

    inscripciones_activas = Inscripcion.query.filter_by(estado="activo").all()
    grupo_por_equipo = {i.equipo_id: i.grupo_id for i in inscripciones_activas}
    equipos_json = [{"id": e.id, "nombre": e.nombre, "grupo_id": grupo_por_equipo.get(e.id)} for e in equipos]

    partidos_fase = Partido.query.join(Jornada).filter_by(fase_id=jornada.fase_id).all()
    partidos_fase_json = [
        {"id": p.id, "equipo_local_id": p.equipo_local_id, "equipo_visitante_id": p.equipo_visitante_id}
        for p in partidos_fase
    ]

    return render_template(
        "admin/jornada_detalle.html", jornada=jornada, equipos=equipos,
        canchas=canchas, arbitros=arbitros, grid=grid,
        equipos_json=equipos_json, partidos_fase_json=partidos_fase_json,
    )


@admin_bp.route("/jornadas/<int:jornada_id>/publicar", methods=["POST"])
@login_required
@requiere_rol("organizador", "ayudante")
def publicar_jornada(jornada_id):
    try:
        jornada_service.publicar_jornada(jornada_id, current_user)
        flash("Jornada publicada. Ya es visible en la página pública.", "success")
    except jornada_service.JornadaYaPublicadaError as e:
        flash(str(e), "error")
    return redirect(url_for("admin.jornada_detalle", jornada_id=jornada_id))


@admin_bp.route("/jornadas/<int:jornada_id>/partidos/nuevo", methods=["POST"])
@login_required
@requiere_rol("organizador", "ayudante")
def crear_partido(jornada_id):
    jornada = Jornada.query.get_or_404(jornada_id)
    partido = Partido(
        jornada_id=jornada.id,
        equipo_local_id=request.form["equipo_local_id"],
        equipo_visitante_id=request.form["equipo_visitante_id"],
        cancha_id=request.form.get("cancha_id") or None,
        arbitro_id=request.form.get("arbitro_id") or None,
        fecha=datetime.strptime(request.form["fecha"], "%Y-%m-%d").date(),
        hora=datetime.strptime(request.form["hora"], "%H:%M").time(),
        estado="programado",
    )
    db.session.add(partido)
    db.session.commit()
    flash("Partido agregado a la jornada.", "success")
    return redirect(url_for("admin.jornada_detalle", jornada_id=jornada_id))


@admin_bp.route("/partidos/<int:partido_id>/editar", methods=["POST"])
@login_required
@requiere_rol("organizador", "ayudante")
def editar_partido(partido_id):
    partido = Partido.query.get_or_404(partido_id)
    partido.equipo_local_id = request.form["equipo_local_id"]
    partido.equipo_visitante_id = request.form["equipo_visitante_id"]
    partido.fecha = datetime.strptime(request.form["fecha"], "%Y-%m-%d").date()
    partido.hora = datetime.strptime(request.form["hora"], "%H:%M").time()
    partido.cancha_id = request.form.get("cancha_id") or None
    partido.arbitro_id = request.form.get("arbitro_id") or None
    partido.estado = request.form.get("estado", partido.estado)
    partido.nota = request.form.get("nota") or None
    db.session.commit()
    flash("Partido actualizado.", "success")
    return redirect(url_for("admin.jornada_detalle", jornada_id=partido.jornada_id))


@admin_bp.route("/partidos/<int:partido_id>/eliminar", methods=["POST"])
@login_required
@requiere_rol("organizador", "ayudante")
def eliminar_partido(partido_id):
    partido = Partido.query.get_or_404(partido_id)
    jornada_id = partido.jornada_id
    db.session.delete(partido)
    db.session.commit()
    flash("Partido eliminado.", "success")
    return redirect(url_for("admin.jornada_detalle", jornada_id=jornada_id))


@admin_bp.route("/partidos/<int:partido_id>/resultado", methods=["GET", "POST"])
@login_required
@requiere_rol("organizador", "ayudante")
def registrar_resultado(partido_id):
    partido = Partido.query.get_or_404(partido_id)
    temporada = Temporada.query.first()
    if request.method == "POST":
        partido.resultado_local = int(request.form["resultado_local"])
        partido.resultado_visitante = int(request.form["resultado_visitante"])
        partido.estado = "jugado"
        db.session.commit()
        notificacion_service.notificar_resultado(partido)
        flash("Resultado guardado.", "success")
        return redirect(url_for("admin.registrar_resultado", partido_id=partido_id))

    jugadores_local = partido.equipo_local.jugadores_temporada(temporada.id) if temporada else []
    jugadores_visitante = partido.equipo_visitante.jugadores_temporada(temporada.id) if temporada else []
    return render_template(
        "admin/resultado.html", partido=partido,
        jugadores_local=jugadores_local, jugadores_visitante=jugadores_visitante,
    )


@admin_bp.route("/partidos/<int:partido_id>/suspender", methods=["POST"])
@login_required
@requiere_rol("organizador", "ayudante")
def suspender_partido(partido_id):
    partido = Partido.query.get_or_404(partido_id)
    partido.estado = "suspendido"
    partido.resultado_local = None
    partido.resultado_visitante = None
    if not partido.nota:
        partido.nota = "Partido suspendido, pendiente de reprogramar."
    db.session.commit()
    notificacion_service.notificar_suspension(partido)
    flash('Partido marcado como pendiente. Podrás reprogramarlo desde "Pendientes".', "success")
    return redirect(url_for("admin.jornada_detalle", jornada_id=partido.jornada_id))


@admin_bp.route("/partidos/<int:partido_id>/evento", methods=["POST"])
@login_required
@requiere_rol("organizador", "ayudante")
def registrar_evento(partido_id):
    partido = Partido.query.get_or_404(partido_id)
    jugador_id = int(request.form["jugador_id"])
    jugador = Jugador.query.get_or_404(jugador_id)
    temporada = Temporada.query.first()
    equipo = jugador.equipo_actual(temporada.id) if temporada else None
    evento = EventoPartido(
        partido_id=partido.id, jugador_id=jugador_id,
        equipo_id=equipo.id if equipo else None,
        tipo_evento=request.form["tipo_evento"],
        minuto=request.form.get("minuto") or None,
    )
    db.session.add(evento)
    db.session.commit()
    flash("Evento registrado.", "success")
    return redirect(url_for("admin.registrar_resultado", partido_id=partido_id))


@admin_bp.route("/eventos/<int:evento_id>/eliminar", methods=["POST"])
@login_required
@requiere_rol("organizador", "ayudante")
def eliminar_evento(evento_id):
    evento = EventoPartido.query.get_or_404(evento_id)
    partido_id = evento.partido_id
    db.session.delete(evento)
    db.session.commit()
    return redirect(url_for("admin.registrar_resultado", partido_id=partido_id))


# ---------- Equipos y jugadores ----------

@admin_bp.route("/equipos")
@login_required
@requiere_rol("organizador", "ayudante")
def equipos():
    lista = Equipo.query.order_by(Equipo.nombre).all()
    capitanes_por_equipo = {}
    for e in lista:
        if e.capitan_id:
            capitan = Usuario.query.get(e.capitan_id)
            capitanes_por_equipo[e.id] = capitan.email if capitan else None
    return render_template("admin/equipos.html", equipos=lista, capitanes_por_equipo=capitanes_por_equipo)


@admin_bp.route("/equipos/nuevo", methods=["POST"])
@login_required
@requiere_rol("organizador", "ayudante")
def crear_equipo():
    from app.models import Organizacion
    org = Organizacion.query.first()
    equipo = Equipo(organizacion_id=org.id, nombre=request.form["nombre"])
    db.session.add(equipo)
    db.session.commit()

    grupo_id = request.form.get("grupo_id")
    temporada = Temporada.query.first()
    if grupo_id and temporada:
        db.session.add(Inscripcion(equipo_id=equipo.id, grupo_id=grupo_id, temporada_id=temporada.id))
        db.session.commit()
    flash("Equipo registrado.", "success")
    return redirect(url_for("admin.equipos"))


@admin_bp.route("/equipos/<int:equipo_id>/capitan", methods=["POST"])
@login_required
@requiere_rol("organizador", "ayudante")
def gestionar_capitan(equipo_id):
    """Crea la cuenta de capitán de un equipo (si no tiene) o le resetea la
    contraseña (si ya tiene). Si no se especifica contraseña, se genera una
    aleatoria que se le muestra UNA sola vez a la organizadora para que se la
    pase al capitán (después queda hasheada, nadie puede volver a verla)."""
    import secrets
    equipo = Equipo.query.get_or_404(equipo_id)
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()
    if not email:
        flash("Escribe el correo del capitán.", "error")
        return redirect(url_for("admin.equipos"))

    password_generada = None
    if not password:
        password = secrets.token_urlsafe(6)  # ej. "hV3xQ2pR1w"
        password_generada = password

    if equipo.capitan_id:
        capitan = Usuario.query.get(equipo.capitan_id)
        capitan.nombre = f"Capitán {equipo.nombre}"
        capitan.email = email
        capitan.set_password(password)
    else:
        # reutiliza la cuenta si ya existe otro equipo con ese correo (poco comun),
        # si no, crea una nueva
        capitan = Usuario.query.filter_by(email=email, rol="capitan").first()
        if not capitan:
            capitan = Usuario(nombre=f"Capitán {equipo.nombre}", email=email, rol="capitan")
            db.session.add(capitan)
        capitan.set_password(password)
        db.session.flush()
        equipo.capitan_id = capitan.id

    db.session.commit()
    if password_generada:
        flash(
            f"Cuenta de capitán lista para {equipo.nombre}. Correo: {email} — "
            f"Contraseña generada (apúntala, no se vuelve a mostrar): {password_generada}",
            "success",
        )
    else:
        flash(f"Cuenta de capitán actualizada para {equipo.nombre} ({email}).", "success")
    return redirect(url_for("admin.equipos"))


@admin_bp.route("/equipos/<int:equipo_id>/jugadores/nuevo", methods=["POST"])
@login_required
@requiere_rol("organizador", "ayudante")
def crear_jugador(equipo_id):
    equipo = Equipo.query.get_or_404(equipo_id)
    temporada = Temporada.query.first()
    jugador = Jugador(nombre=request.form["nombre"])
    db.session.add(jugador)
    db.session.flush()
    roster = Roster(
        jugador_id=jugador.id, equipo_id=equipo.id, temporada_id=temporada.id,
        numero_playera=request.form.get("numero") or None,
        posicion=request.form.get("posicion") or None,
    )
    db.session.add(roster)
    db.session.commit()
    flash("Jugador agregado al equipo.", "success")
    return redirect(url_for("admin.equipos"))


# ---------- Noticias ----------

@admin_bp.route("/noticias", methods=["GET", "POST"])
@login_required
@requiere_rol("organizador", "ayudante")
def noticias():
    if request.method == "POST":
        from app.models import Organizacion
        org = Organizacion.query.first()
        noticia = Noticia(
            organizacion_id=org.id, titulo=request.form["titulo"],
            contenido=request.form["contenido"], autor_id=current_user.id,
        )
        db.session.add(noticia)
        db.session.commit()
        flash("Noticia publicada.", "success")
        return redirect(url_for("admin.noticias"))
    lista = Noticia.query.order_by(Noticia.fecha_publicacion.desc()).all()
    return render_template("admin/noticias.html", noticias=lista)


# ---------- Grupos ----------

@admin_bp.route("/grupos")
@login_required
@requiere_rol("organizador", "ayudante")
def grupos():
    fase = Fase.query.filter_by(tipo="grupos").first()
    grupos_lista = Grupo.query.filter_by(fase_id=fase.id).all() if fase else []
    equipos_con_grupo_activo = {
        i.equipo_id for i in Inscripcion.query.filter_by(estado="activo").all()
    }
    equipos_sin_grupo = [
        e for e in Equipo.query.order_by(Equipo.nombre).all() if e.id not in equipos_con_grupo_activo
    ]
    return render_template("admin/grupos.html", grupos=grupos_lista, equipos_sin_grupo=equipos_sin_grupo)


@admin_bp.route("/grupos/<int:grupo_id>/agregar-equipo", methods=["POST"])
@login_required
@requiere_rol("organizador", "ayudante")
def agregar_equipo_a_grupo(grupo_id):
    grupo = Grupo.query.get_or_404(grupo_id)
    temporada = Temporada.query.first()
    equipo_id = request.form.get("equipo_id")
    if not equipo_id:
        flash("No hay equipos disponibles para agregar a este grupo.", "error")
        return redirect(url_for("admin.grupos"))
    db.session.add(Inscripcion(equipo_id=equipo_id, grupo_id=grupo.id, temporada_id=temporada.id))
    db.session.commit()
    flash("Equipo agregado al grupo.", "success")
    return redirect(url_for("admin.grupos"))


@admin_bp.route("/inscripciones/<int:inscripcion_id>/quitar", methods=["POST"])
@login_required
@requiere_rol("organizador", "ayudante")
def quitar_de_grupo(inscripcion_id):
    inscripcion = Inscripcion.query.get_or_404(inscripcion_id)
    inscripcion.estado = "retirado"
    db.session.commit()
    flash("Equipo retirado del grupo.", "success")
    return redirect(url_for("admin.grupos"))


# ---------- Documentos (inscripcion / seguro por jugador) ----------

@admin_bp.route("/documentos")
@login_required
@requiere_rol("organizador", "ayudante")
def documentos():
    equipos = Equipo.query.order_by(Equipo.nombre).all()
    equipo_id = request.args.get("equipo_id", type=int)
    rosters = []
    if equipo_id:
        equipo = Equipo.query.get_or_404(equipo_id)
        rosters = equipo.rosters
    return render_template("admin/documentos.html", equipos=equipos, rosters=rosters, equipo_id=equipo_id)


@admin_bp.route("/rosters/<int:roster_id>/documentos", methods=["POST"])
@login_required
@requiere_rol("organizador", "ayudante")
def actualizar_documentos(roster_id):
    roster = Roster.query.get_or_404(roster_id)
    roster.inscripcion_pagada = "inscripcion" in request.form
    roster.seguro_pagado = "seguro" in request.form
    db.session.commit()
    flash(f"Documentación actualizada para {roster.jugador.nombre}.", "success")
    return redirect(url_for("admin.documentos", equipo_id=roster.equipo_id))


# ---------- Pagos de cancha (4 pagos por equipo) ----------

def _pago_cancha_de(equipo_id, temporada_id):
    pago = PagoCancha.query.filter_by(equipo_id=equipo_id, temporada_id=temporada_id).first()
    if not pago:
        pago = PagoCancha(equipo_id=equipo_id, temporada_id=temporada_id)
        db.session.add(pago)
        db.session.commit()
    return pago


@admin_bp.route("/pagos-cancha")
@login_required
@requiere_rol("organizador", "ayudante")
def pagos_cancha():
    equipos = Equipo.query.order_by(Equipo.nombre).all()
    temporada = Temporada.query.first()
    pagos_por_equipo = {e.id: _pago_cancha_de(e.id, temporada.id) for e in equipos} if temporada else {}
    return render_template("admin/pagos_cancha.html", equipos=equipos, pagos_por_equipo=pagos_por_equipo)


@admin_bp.route("/pagos-cancha/<int:pago_id>", methods=["POST"])
@login_required
@requiere_rol("organizador", "ayudante")
def actualizar_pago_cancha(pago_id):
    pago = PagoCancha.query.get_or_404(pago_id)
    pago.pago_1 = "pago_1" in request.form
    pago.pago_2 = "pago_2" in request.form
    pago.pago_3 = "pago_3" in request.form
    pago.pago_4 = "pago_4" in request.form
    db.session.commit()
    flash(f"Pagos de cancha actualizados para {pago.equipo.nombre}.", "success")
    return redirect(url_for("admin.pagos_cancha"))


# ---------- Arbitrajes ----------

@admin_bp.route("/arbitrajes")
@login_required
@requiere_rol("organizador", "ayudante")
def arbitrajes():
    equipos = Equipo.query.order_by(Equipo.nombre).all()
    equipo_id = request.args.get("equipo_id", type=int)
    partidos = []
    if equipo_id:
        equipo = Equipo.query.get_or_404(equipo_id)
        partidos = sorted(equipo.partidos(), key=lambda p: p.fecha)
    total = Partido.query.count()
    todos = Partido.query.all()
    pagados = sum(1 for p in todos if p.arbitraje_pagado_local) + sum(1 for p in todos if p.arbitraje_pagado_visitante)
    return render_template(
        "admin/arbitrajes.html", equipos=equipos, partidos=partidos, equipo_id=equipo_id,
        total=total * 2, pagados=pagados,
    )


@admin_bp.route("/partidos/<int:partido_id>/arbitraje", methods=["POST"])
@login_required
@requiere_rol("organizador", "ayudante")
def actualizar_arbitraje(partido_id):
    partido = Partido.query.get_or_404(partido_id)
    partido.arbitraje_pagado_local = "pagado_local" in request.form
    partido.arbitraje_pagado_visitante = "pagado_visitante" in request.form
    if request.form.get("costo"):
        partido.costo_arbitraje = int(request.form["costo"])
    db.session.commit()
    flash("Estado de arbitraje actualizado.", "success")
    equipo_id = request.form.get("equipo_id", type=int)
    return redirect(url_for("admin.arbitrajes", equipo_id=equipo_id))


# ---------- Horarios (disponibilidad de todos + generar calendario) ----------

@admin_bp.route("/horarios")
@login_required
@requiere_rol("organizador", "ayudante")
def horarios():
    from datetime import datetime, timedelta
    equipos = Equipo.query.order_by(Equipo.nombre).all()
    temporada = Temporada.query.first()

    semana_param = request.args.get("semana")
    if semana_param:
        semana = datetime.strptime(semana_param, "%Y-%m-%d").date()
    else:
        hoy = datetime.utcnow().date()
        semana = hoy - timedelta(days=hoy.weekday())

    disponibilidad_por_equipo = {}
    for e in equipos:
        disponibilidad_por_equipo[e.id] = Disponibilidad.query.filter_by(
            equipo_id=e.id, temporada_id=temporada.id, semana=semana
        ).all() if temporada else []

    return render_template(
        "admin/horarios.html", equipos=equipos, disponibilidad_por_equipo=disponibilidad_por_equipo,
        semana=semana, semana_anterior=semana - timedelta(days=7), semana_siguiente=semana + timedelta(days=7),
    )


@admin_bp.route("/horarios/generar-calendario", methods=["POST"])
@login_required
@requiere_rol("organizador", "ayudante")
def generar_calendario():
    from datetime import datetime
    fase = Fase.query.filter_by(tipo="grupos").first()
    temporada = Temporada.query.first()
    if not fase or not temporada:
        flash("No hay fase/temporada configurada.", "error")
        return redirect(url_for("admin.horarios"))
    semana_param = request.form.get("semana")
    fecha_base = datetime.strptime(semana_param, "%Y-%m-%d").date() if semana_param else None
    jornada, partidos, usando_pendientes = calendario_service.generar_propuesta_jornada(
        fase.id, temporada.id, fecha_base=fecha_base
    )
    if jornada is None:
        flash(
            "No hay partidos nuevos ni pendientes por programar: la fase de grupos ya está completa.",
            "error",
        )
        return redirect(url_for("admin.horarios"))
    if usando_pendientes:
        flash(
            f"Ya no quedaban enfrentamientos nuevos, así que se armó la Jornada {jornada.numero} "
            f"con los {len(partidos)} partido(s) que habían quedado pendientes/suspendidos. "
            "Revísala, edítala si hace falta y publícala cuando esté lista.",
            "success",
        )
    else:
        flash(
            f"Se generó la Jornada {jornada.numero} en borrador con {len(partidos)} partido(s), repartidos "
            "en la semana según la disponibilidad declarada por los capitanes. Revísala, edítala si hace "
            "falta y publícala cuando esté lista.",
            "success",
        )
    return redirect(url_for("admin.jornada_detalle", jornada_id=jornada.id))


# ---------- Solicitudes de cambio de horario ----------

@admin_bp.route("/solicitudes")
@login_required
@requiere_rol("organizador", "ayudante")
def solicitudes():
    pendientes = SolicitudCambioHorario.query.filter_by(estado="pendiente_organizador").all()
    rechazadas_por_rival = SolicitudCambioHorario.query.filter_by(estado="rechazado_por_rival").all()
    historial = SolicitudCambioHorario.query.filter(
        SolicitudCambioHorario.estado.in_(["aprobado", "rechazado"])
    ).all()
    return render_template(
        "admin/solicitudes.html", pendientes=pendientes,
        rechazadas_por_rival=rechazadas_por_rival, historial=historial,
    )


@admin_bp.route("/solicitudes/<int:solicitud_id>/resolver", methods=["POST"])
@login_required
@requiere_rol("organizador", "ayudante")
def resolver_solicitud(solicitud_id):
    solicitud = SolicitudCambioHorario.query.get_or_404(solicitud_id)
    decision = request.form["decision"]
    if decision == "aprobar":
        solicitud.partido.fecha = solicitud.nueva_fecha
        solicitud.partido.hora = solicitud.nueva_hora
        solicitud.partido.estado = "reprogramado"
        solicitud.estado = "aprobado"
        db.session.commit()
        notificacion_service.notificar_resolucion_cambio(solicitud, aprobado=True)
        flash("Cambio de horario aprobado y aplicado al partido.", "success")
    else:
        solicitud.estado = "rechazado"
        db.session.commit()
        notificacion_service.notificar_resolucion_cambio(solicitud, aprobado=False)
        flash("Solicitud de cambio de horario rechazada.", "success")
    return redirect(url_for("admin.solicitudes"))


@admin_bp.route("/solicitudes/<int:solicitud_id>/resolver-rechazo", methods=["POST"])
@login_required
@requiere_rol("organizador", "ayudante")
def resolver_rechazo(solicitud_id):
    """Cuando el equipo rival no aceptó ninguna de las opciones propuestas,
    la organizadora decide si el partido se queda en su horario original o
    si se marca como pendiente para reprogramarlo despues."""
    solicitud = SolicitudCambioHorario.query.get_or_404(solicitud_id)
    decision = request.form["decision"]
    suspendido = decision == "suspender"
    if suspendido:
        solicitud.partido.estado = "suspendido"
        solicitud.partido.nota = "No se logró acordar un nuevo horario; partido pendiente de reprogramar."
        flash('Partido marcado como pendiente. Podrás reprogramarlo desde "Pendientes".', "success")
    else:
        flash("El partido se queda en su horario original.", "success")
    solicitud.estado = "rechazado"
    db.session.commit()
    notificacion_service.notificar_resolucion_rechazo(solicitud, suspendido=suspendido)
    return redirect(url_for("admin.solicitudes"))


# ---------- Pendientes (partidos suspendidos por reprogramar) ----------

@admin_bp.route("/pendientes")
@login_required
@requiere_rol("organizador", "ayudante")
def pendientes():
    lista = Partido.query.filter_by(estado="suspendido").order_by(Partido.fecha).all()
    return render_template("admin/pendientes.html", partidos=lista)


@admin_bp.route("/pendientes/<int:partido_id>/eliminar", methods=["POST"])
@login_required
@requiere_rol("organizador", "ayudante")
def eliminar_pendiente(partido_id):
    partido = Partido.query.get_or_404(partido_id)
    db.session.delete(partido)
    db.session.commit()
    flash("Partido pendiente eliminado.", "success")
    return redirect(url_for("admin.pendientes"))


@admin_bp.route("/pendientes/<int:partido_id>/reprogramar")
@login_required
@requiere_rol("organizador", "ayudante")
def reprogramar_pendiente(partido_id):
    from app.services.jornada_grid import construir_grid
    partido = Partido.query.get_or_404(partido_id)
    fase = Fase.query.filter_by(tipo="grupos").first()
    jornadas = Jornada.query.filter_by(fase_id=fase.id).order_by(Jornada.numero).all() if fase else []

    jornada_id = request.args.get("jornada_id", type=int)
    grid = None
    jornada_elegida = None
    if jornada_id:
        jornada_elegida = Jornada.query.get_or_404(jornada_id)
        grid = construir_grid(jornada_elegida, excluir_partido_id=partido.id)

    return render_template(
        "admin/reprogramar_pendiente.html", partido=partido, jornadas=jornadas,
        jornada_elegida=jornada_elegida, grid=grid,
    )


@admin_bp.route("/pendientes/<int:partido_id>/reprogramar", methods=["POST"])
@login_required
@requiere_rol("organizador", "ayudante")
def guardar_reprogramacion(partido_id):
    from app.services.jornada_grid import fechas_semana
    partido = Partido.query.get_or_404(partido_id)
    jornada_id = request.form.get("jornada_id", type=int)
    slot = request.form.get("slot")
    if not jornada_id or not slot:
        flash("Elige una jornada y un horario disponible.", "error")
        return redirect(url_for("admin.reprogramar_pendiente", partido_id=partido_id, jornada_id=jornada_id))

    jornada = Jornada.query.get_or_404(jornada_id)
    dia, hora_str = slot.split("|")
    fechas = fechas_semana(jornada.fecha_referencia)

    partido.jornada_id = jornada.id
    partido.fecha = fechas[dia]
    partido.hora = datetime.strptime(hora_str, "%H:%M").time()
    partido.estado = "programado"
    partido.nota = None
    db.session.commit()
    notificacion_service.notificar_reprogramacion(partido)
    flash(f"Partido reprogramado a la Jornada {jornada.numero}.", "success")
    return redirect(url_for("admin.jornada_detalle", jornada_id=jornada.id))


# ---------- Avisos (objetos perdidos) ----------

@admin_bp.route("/avisos", methods=["GET", "POST"])
@login_required
@requiere_rol("organizador", "ayudante")
def avisos():
    from app.models import Organizacion
    org = Organizacion.query.first()
    if request.method == "POST":
        objeto = ObjetoPerdido(
            organizacion_id=org.id, titulo=request.form["titulo"],
            descripcion=request.form.get("descripcion"), ubicacion=request.form.get("ubicacion"),
        )
        db.session.add(objeto)
        db.session.commit()
        flash("Aviso publicado.", "success")
        return redirect(url_for("admin.avisos"))
    lista = ObjetoPerdido.query.filter_by(resuelto=False).order_by(ObjetoPerdido.fecha_reporte.desc()).all()
    return render_template("admin/avisos.html", objetos=lista)


@admin_bp.route("/avisos/<int:objeto_id>/resolver", methods=["POST"])
@login_required
@requiere_rol("organizador", "ayudante")
def resolver_aviso(objeto_id):
    objeto = ObjetoPerdido.query.get_or_404(objeto_id)
    objeto.resuelto = True
    db.session.commit()
    return redirect(url_for("admin.avisos"))
