from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db


class Usuario(UserMixin, db.Model):
    __tablename__ = "usuarios"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.String(30), nullable=False)  # organizador, ayudante, capitan

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def es_staff(self):
        return self.rol in ("organizador", "ayudante")


class Disponibilidad(db.Model):
    __tablename__ = "disponibilidades"
    id = db.Column(db.Integer, primary_key=True)
    equipo_id = db.Column(db.Integer, db.ForeignKey("equipos.id"), nullable=False)
    temporada_id = db.Column(db.Integer, db.ForeignKey("temporadas.id"), nullable=False)
    semana = db.Column(db.Date, nullable=False)  # lunes de la semana a la que aplica
    dia_semana = db.Column(db.String(20), nullable=False)  # martes, miercoles...
    hora_inicio = db.Column(db.Time, nullable=False)
    hora_fin = db.Column(db.Time, nullable=False)

    equipo = db.relationship("Equipo")


class SolicitudCambioHorario(db.Model):
    __tablename__ = "solicitudes_cambio_horario"
    id = db.Column(db.Integer, primary_key=True)
    partido_id = db.Column(db.Integer, db.ForeignKey("partidos.id"), nullable=False)
    solicitado_por_equipo_id = db.Column(db.Integer, db.ForeignKey("equipos.id"), nullable=False)
    nueva_fecha = db.Column(db.Date)  # se llena cuando el rival elige una de las opciones
    nueva_hora = db.Column(db.Time)
    estado = db.Column(db.String(30), default="pendiente_rival")
    # pendiente_rival, pendiente_organizador, aprobado, rechazado
    comentario = db.Column(db.String(300))

    partido = db.relationship("Partido")
    equipo_solicitante = db.relationship("Equipo")
    opciones = db.relationship("OpcionCambioHorario", backref="solicitud", lazy=True, cascade="all, delete-orphan")


class OpcionCambioHorario(db.Model):
    """Cada horario disponible que el capitan que solicita propuso como
    alternativa. El capitan rival elige cual de estas opciones le sirve."""
    __tablename__ = "opciones_cambio_horario"
    id = db.Column(db.Integer, primary_key=True)
    solicitud_id = db.Column(db.Integer, db.ForeignKey("solicitudes_cambio_horario.id"), nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    hora = db.Column(db.Time, nullable=False)
