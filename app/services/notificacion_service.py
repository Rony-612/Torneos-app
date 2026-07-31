"""Notificaciones por correo electrónico.

En desarrollo (sin variables de entorno de SMTP configuradas) los correos NO
se envían de verdad: se registran en `correos_enviados.log` en la raíz del
proyecto, para poder revisar exactamente qué se hubiera mandado y a quién sin
necesitar credenciales reales ni acceso a internet.

En producción, basta con definir las variables de entorno MAIL_SERVER,
MAIL_PORT, MAIL_USERNAME, MAIL_PASSWORD (y opcionalmente MAIL_FROM,
MAIL_USE_TLS) para que empiece a mandar correos de verdad por SMTP, sin
cambiar una sola línea de código de las funciones de abajo.
"""
import os
import json
from datetime import datetime
from email.mime.text import MIMEText
import urllib.request
import urllib.error

_PROYECTO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_PATH = os.path.join(_PROYECTO_ROOT, "correos_enviados.log")


def _registrar_en_log(destinatarios, asunto, cuerpo):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"\n{'=' * 72}\n")
            f.write(f"Fecha:     {datetime.utcnow().isoformat(timespec='seconds')} UTC\n")
            f.write(f"Para:      {', '.join(destinatarios)}\n")
            f.write(f"Asunto:    {asunto}\n\n{cuerpo}\n")
    except OSError:
        pass


def _enviar_smtp(destinatarios, asunto, cuerpo, servidor):
    api_key = os.environ.get("BREVO_API_KEY")
    if not api_key:
        raise Exception("Falta configurar la variable de entorno BREVO_API_KEY en Render")

    remitente = os.environ.get("MAIL_FROM") or "Torneo DCEA <tusistema@gmail.com>"
    
    # Extraer el email limpio si viene en formato "Nombre <correo@domain.com>"
    email_remitente = remitente.split("<")[-1].replace(">", "").strip()
    nombre_remitente = remitente.split("<")[0].strip() if "<" in remitente else "Torneo DCEA"

    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "TorneoDCEA-App/1.0"
    }

    # Brevo requiere que los destinatarios vayan en una lista de diccionarios [{"email": "..."}]
    lista_to = [{"email": d} for d in destinatarios if d]

    payload = {
        "sender": {"name": nombre_remitente, "email": email_remitente},
        "to": lista_to,
        "subject": asunto,
        "textContent": cuerpo
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status not in (200, 201, 202):
                raise Exception(f"Brevo API error status: {response.status}")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise Exception(f"HTTPError {e.code}: {error_body}")

def enviar_correo(destinatarios, asunto, cuerpo):
    destinatarios = sorted({d for d in destinatarios if d})
    if not destinatarios:
        return
    
    api_key = os.environ.get("BREVO_API_KEY")
    servidor = os.environ.get("MAIL_SERVER") or (True if api_key else None)

    try:
        if servidor:
            _enviar_smtp(destinatarios, asunto, cuerpo, servidor)
        else:
            _registrar_en_log(destinatarios, asunto, cuerpo)
    except Exception as e:
        print(f"CRITICAL MAIL ERROR: {e}", flush=True)
        _registrar_en_log(destinatarios, f"[ERROR AL ENVIAR] {asunto}", f"{cuerpo}\n\nError: {e}")

def _correos_organizacion():
    from app.models import Usuario
    return [u.email for u in Usuario.query.filter(Usuario.rol.in_(["organizador", "ayudante"])).all()]


def _correo_capitan(equipo):
    if equipo and equipo.capitan_id:
        from app.models import Usuario
        capitan = Usuario.query.get(equipo.capitan_id)
        return capitan.email if capitan else None
    return None


# ---------- Publicación de jornada ----------

def notificar_publicacion_jornada(jornada):
    for partido in jornada.partidos:
        destinatarios = [_correo_capitan(partido.equipo_local), _correo_capitan(partido.equipo_visitante)]
        asunto = f"Jornada {jornada.numero} publicada: {partido.equipo_local.nombre} vs {partido.equipo_visitante.nombre}"
        cuerpo = (
            f"Se publicó la Jornada {jornada.numero} del torneo.\n\n"
            f"Tu partido: {partido.equipo_local.nombre} vs {partido.equipo_visitante.nombre}\n"
            f"Fecha: {partido.fecha.strftime('%d/%m/%Y')}\n"
            f"Hora: {partido.hora.strftime('%H:%M')}\n"
            f"Cancha: {partido.cancha.nombre if partido.cancha else 'por confirmar'}\n"
            f"Árbitro: {partido.arbitro.nombre if partido.arbitro else 'por confirmar'}\n"
        )
        enviar_correo(destinatarios, asunto, cuerpo)


# ---------- Cambios de horario ----------

def notificar_solicitud_cambio(solicitud):
    from app.services.jornada_grid import construir_grid
    partido = solicitud.partido
    rival = partido.equipo_visitante if partido.equipo_local_id == solicitud.solicitado_por_equipo_id else partido.equipo_local
    opciones_txt = "\n".join(
        f"  - {op.fecha.strftime('%d/%m/%Y')} {op.hora.strftime('%H:%M')}" for op in solicitud.opciones
    )
    asunto = f"{solicitud.equipo_solicitante.nombre} propone cambiar el horario de su partido"
    cuerpo = (
        f"{solicitud.equipo_solicitante.nombre} propuso cambiar el horario del partido contra tu equipo "
        f"({partido.equipo_local.nombre} vs {partido.equipo_visitante.nombre}), "
        f"actualmente programado el {partido.fecha.strftime('%d/%m/%Y')} a las {partido.hora.strftime('%H:%M')}.\n\n"
        f"Horarios que propuso como alternativa:\n{opciones_txt}\n\n"
        f"{'Comentario: ' + solicitud.comentario if solicitud.comentario else ''}\n\n"
        "Entra al portal de capitanes, sección Cambios de horario, para responder."
    )
    enviar_correo([_correo_capitan(rival)], asunto, cuerpo)


def notificar_cambio_pendiente_aprobacion(solicitud):
    asunto = f"Cambio de horario aceptado, pendiente tu aprobación: {solicitud.partido.equipo_local.nombre} vs {solicitud.partido.equipo_visitante.nombre}"
    cuerpo = (
        f"Ambos equipos ya están de acuerdo en mover su partido a "
        f"{solicitud.nueva_fecha.strftime('%d/%m/%Y')} {solicitud.nueva_hora.strftime('%H:%M')}.\n"
        "Entra al panel de organización, sección Solicitudes, para dar la aprobación final."
    )
    enviar_correo(_correos_organizacion(), asunto, cuerpo)


def notificar_rechazo_cambio(solicitud):
    asunto = f"El equipo rival rechazó el cambio de horario: {solicitud.partido.equipo_local.nombre} vs {solicitud.partido.equipo_visitante.nombre}"
    cuerpo = (
        f"{solicitud.equipo_solicitante.nombre} había propuesto cambiar el horario de su partido, pero el "
        "equipo rival no aceptó ninguna opción.\n"
        "Entra al panel de organización, sección Solicitudes, para decidir si el partido se queda igual "
        "o pasa a pendientes."
    )
    enviar_correo(_correos_organizacion(), asunto, cuerpo)


def notificar_resolucion_cambio(solicitud, aprobado):
    partido = solicitud.partido
    destinatarios = [_correo_capitan(partido.equipo_local), _correo_capitan(partido.equipo_visitante)]
    if aprobado:
        asunto = f"Cambio de horario aprobado: {partido.equipo_local.nombre} vs {partido.equipo_visitante.nombre}"
        cuerpo = (
            f"La organización aprobó el cambio de horario. Nuevo horario: "
            f"{partido.fecha.strftime('%d/%m/%Y')} {partido.hora.strftime('%H:%M')}."
        )
    else:
        asunto = f"Cambio de horario no aprobado: {partido.equipo_local.nombre} vs {partido.equipo_visitante.nombre}"
        cuerpo = (
            f"La organización no aprobó el cambio de horario propuesto. El partido se mantiene: "
            f"{partido.fecha.strftime('%d/%m/%Y')} {partido.hora.strftime('%H:%M')}."
        )
    enviar_correo(destinatarios, asunto, cuerpo)


def notificar_resolucion_rechazo(solicitud, suspendido):
    partido = solicitud.partido
    destinatarios = [_correo_capitan(partido.equipo_local), _correo_capitan(partido.equipo_visitante)]
    if suspendido:
        asunto = f"Partido pendiente de reprogramar: {partido.equipo_local.nombre} vs {partido.equipo_visitante.nombre}"
        cuerpo = "No se logró acordar un nuevo horario. La organización marcó el partido como pendiente; se les avisará el nuevo horario en cuanto se reprograme."
    else:
        asunto = f"El partido se mantiene en su horario original: {partido.equipo_local.nombre} vs {partido.equipo_visitante.nombre}"
        cuerpo = (
            f"No se logró acordar un cambio de horario. El partido se mantiene: "
            f"{partido.fecha.strftime('%d/%m/%Y')} {partido.hora.strftime('%H:%M')}."
        )
    enviar_correo(destinatarios, asunto, cuerpo)


# ---------- Resultados y suspensiones ----------

def notificar_resultado(partido):
    destinatarios = [_correo_capitan(partido.equipo_local), _correo_capitan(partido.equipo_visitante)]
    asunto = f"Resultado publicado: {partido.equipo_local.nombre} {partido.resultado_local}-{partido.resultado_visitante} {partido.equipo_visitante.nombre}"
    cuerpo = (
        f"Quedó registrado el resultado del partido:\n\n"
        f"{partido.equipo_local.nombre} {partido.resultado_local} - {partido.resultado_visitante} {partido.equipo_visitante.nombre}\n"
        f"Fecha: {partido.fecha.strftime('%d/%m/%Y')}"
    )
    enviar_correo(destinatarios, asunto, cuerpo)


def notificar_suspension(partido):
    destinatarios = [_correo_capitan(partido.equipo_local), _correo_capitan(partido.equipo_visitante)]
    asunto = f"Partido suspendido: {partido.equipo_local.nombre} vs {partido.equipo_visitante.nombre}"
    cuerpo = (
        f"Se marcó como suspendido el partido {partido.equipo_local.nombre} vs {partido.equipo_visitante.nombre} "
        f"que estaba programado el {partido.fecha.strftime('%d/%m/%Y')} a las {partido.hora.strftime('%H:%M')}.\n"
        f"{('Motivo: ' + partido.nota) if partido.nota else ''}\n\n"
        "Quedó en la lista de pendientes; se les avisará por correo en cuanto se reprograme."
    )
    enviar_correo(destinatarios, asunto, cuerpo)


def notificar_reprogramacion(partido):
    destinatarios = [_correo_capitan(partido.equipo_local), _correo_capitan(partido.equipo_visitante)]
    asunto = f"Partido reprogramado: {partido.equipo_local.nombre} vs {partido.equipo_visitante.nombre}"
    cuerpo = (
        f"El partido {partido.equipo_local.nombre} vs {partido.equipo_visitante.nombre}, que estaba pendiente, "
        f"ya tiene nuevo horario:\n\n"
        f"Fecha: {partido.fecha.strftime('%d/%m/%Y')}\n"
        f"Hora: {partido.hora.strftime('%H:%M')}\n"
        f"Jornada: {partido.jornada.numero}"
    )
    enviar_correo(destinatarios, asunto, cuerpo)


# ---------- Recordatorios (requieren un disparador por tiempo, ver mas abajo) ----------

def notificar_recordatorio_dia_antes(partido):
    destinatarios = [_correo_capitan(partido.equipo_local), _correo_capitan(partido.equipo_visitante)]
    asunto = f"Mañana juegas: {partido.equipo_local.nombre} vs {partido.equipo_visitante.nombre}"
    cuerpo = (
        f"Recordatorio: mañana {partido.fecha.strftime('%d/%m/%Y')} a las {partido.hora.strftime('%H:%M')} "
        f"juegan {partido.equipo_local.nombre} vs {partido.equipo_visitante.nombre}"
        f"{' en ' + partido.cancha.nombre if partido.cancha else ''}."
    )
    enviar_correo(destinatarios, asunto, cuerpo)


def notificar_recordatorio_hora_antes(partido):
    destinatarios = [_correo_capitan(partido.equipo_local), _correo_capitan(partido.equipo_visitante)]
    asunto = f"En una hora juegas: {partido.equipo_local.nombre} vs {partido.equipo_visitante.nombre}"
    cuerpo = (
        f"Recordatorio: en aproximadamente una hora ({partido.hora.strftime('%H:%M')}) juegan "
        f"{partido.equipo_local.nombre} vs {partido.equipo_visitante.nombre}"
        f"{' en ' + partido.cancha.nombre if partido.cancha else ''}. ¡No lleguen tarde!"
    )
    enviar_correo(destinatarios, asunto, cuerpo)


def ejecutar_recordatorios():
    """Revisa los partidos programados y manda el recordatorio de 'un dia
    antes' y el de 'una hora antes' a los que les toca, marcando cada uno
    para no duplicarlo. La llaman tanto el comando de consola
    (`flask enviar-recordatorios`) como el endpoint HTTP protegido por token
    (para poder dispararla desde un cron externo gratuito sin depender de
    que el hosting tenga su propio programador de tareas).
    Regresa (enviados_dia, enviados_hora)."""
    from datetime import datetime, timedelta
    from app.extensions import db
    from app.models import Partido, Jornada

    ahora = datetime.now()
    hoy = ahora.date()
    manana = hoy + timedelta(days=1)

    candidatos = (
        Partido.query.join(Jornada)
        .filter(Jornada.estado == "publicada", Partido.estado.in_(["programado", "reprogramado"]))
        .all()
    )

    enviados_dia, enviados_hora = 0, 0
    for partido in candidatos:
        if partido.fecha == manana and not partido.recordatorio_dia_antes_enviado:
            notificar_recordatorio_dia_antes(partido)
            partido.recordatorio_dia_antes_enviado = True
            enviados_dia += 1

        if partido.fecha == hoy and not partido.recordatorio_hora_antes_enviado:
            inicio_partido = datetime.combine(partido.fecha, partido.hora)
            minutos_restantes = (inicio_partido - ahora).total_seconds() / 60
            if 0 <= minutos_restantes <= 90:
                notificar_recordatorio_hora_antes(partido)
                partido.recordatorio_hora_antes_enviado = True
                enviados_hora += 1

    db.session.commit()
    return enviados_dia, enviados_hora
