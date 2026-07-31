from datetime import datetime
from app.extensions import db


class Jornada(db.Model):
    __tablename__ = "jornadas"
    id = db.Column(db.Integer, primary_key=True)
    fase_id = db.Column(db.Integer, db.ForeignKey("fases.id"), nullable=False)
    numero = db.Column(db.Integer, nullable=False)
    fecha_referencia = db.Column(db.Date)
    estado = db.Column(db.String(20), default="borrador")  # borrador, publicada
    publicada_por_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"))
    fecha_publicacion = db.Column(db.DateTime)

    partidos = db.relationship("Partido", backref="jornada", lazy=True, order_by="Partido.fecha")

    def publicar(self, usuario):
        self.estado = "publicada"
        self.publicada_por_id = usuario.id
        self.fecha_publicacion = datetime.utcnow()


class Partido(db.Model):
    __tablename__ = "partidos"
    id = db.Column(db.Integer, primary_key=True)
    jornada_id = db.Column(db.Integer, db.ForeignKey("jornadas.id"), nullable=False)
    equipo_local_id = db.Column(db.Integer, db.ForeignKey("equipos.id"), nullable=False)
    equipo_visitante_id = db.Column(db.Integer, db.ForeignKey("equipos.id"), nullable=False)
    cancha_id = db.Column(db.Integer, db.ForeignKey("canchas.id"))
    arbitro_id = db.Column(db.Integer, db.ForeignKey("arbitros.id"))
    fecha = db.Column(db.Date, nullable=False)
    hora = db.Column(db.Time, nullable=False)
    estado = db.Column(db.String(20), default="programado")
    # programado, jugado, suspendido, reprogramado
    resultado_local = db.Column(db.Integer)
    resultado_visitante = db.Column(db.Integer)
    nota = db.Column(db.String(300))  # motivo de suspension, etc.
    costo_arbitraje = db.Column(db.Integer, default=400)
    arbitraje_pagado_local = db.Column(db.Boolean, default=False)
    arbitraje_pagado_visitante = db.Column(db.Boolean, default=False)
    recordatorio_dia_antes_enviado = db.Column(db.Boolean, default=False)
    recordatorio_hora_antes_enviado = db.Column(db.Boolean, default=False)

    equipo_local = db.relationship("Equipo", foreign_keys=[equipo_local_id])
    equipo_visitante = db.relationship("Equipo", foreign_keys=[equipo_visitante_id])
    eventos = db.relationship("EventoPartido", backref="partido", lazy=True)
    detalles = db.relationship("DetallePartidoEquipo", backref="partido", lazy=True)

    def detalle_de(self, equipo_id):
        return next((d for d in self.detalles if d.equipo_id == equipo_id), None)

    def arbitraje_pagado_de(self, equipo_id):
        if equipo_id == self.equipo_local_id:
            return self.arbitraje_pagado_local
        if equipo_id == self.equipo_visitante_id:
            return self.arbitraje_pagado_visitante
        return None

    def goleadores(self):
        return [e for e in self.eventos if e.tipo_evento == "gol"]

    def tarjetas(self):
        return [e for e in self.eventos if e.tipo_evento in ("tarjeta_amarilla", "tarjeta_roja")]


class EventoPartido(db.Model):
    """Tabla generica de eventos: gol, asistencia, tarjeta amarilla/roja.
    Genérica a propósito para poder soportar otros deportes (puntos, faltas, etc.)
    sin cambiar el esquema."""
    __tablename__ = "eventos_partido"
    id = db.Column(db.Integer, primary_key=True)
    partido_id = db.Column(db.Integer, db.ForeignKey("partidos.id"), nullable=False)
    jugador_id = db.Column(db.Integer, db.ForeignKey("jugadores.id"), nullable=False)
    equipo_id = db.Column(db.Integer, db.ForeignKey("equipos.id"), nullable=False)
    tipo_evento = db.Column(db.String(30), nullable=False)
    minuto = db.Column(db.Integer)

    jugador = db.relationship("Jugador")
    equipo = db.relationship("Equipo")


class DetallePartidoEquipo(db.Model):
    """Detalle que cada equipo declara para un partido: color de uniforme
    y si llevaran casacas numeradas. Un registro por equipo por partido."""
    __tablename__ = "detalles_partido_equipo"
    id = db.Column(db.Integer, primary_key=True)
    partido_id = db.Column(db.Integer, db.ForeignKey("partidos.id"), nullable=False)
    equipo_id = db.Column(db.Integer, db.ForeignKey("equipos.id"), nullable=False)
    color_uniforme = db.Column(db.String(80))
    lleva_casacas = db.Column(db.Boolean)

    equipo = db.relationship("Equipo")


class Sancion(db.Model):
    __tablename__ = "sanciones"
    id = db.Column(db.Integer, primary_key=True)
    jugador_id = db.Column(db.Integer, db.ForeignKey("jugadores.id"), nullable=False)
    motivo = db.Column(db.String(300))
    partidos_suspendido = db.Column(db.Integer, default=1)
    jornada_inicio_id = db.Column(db.Integer, db.ForeignKey("jornadas.id"))
    jornada_fin_id = db.Column(db.Integer, db.ForeignKey("jornadas.id"))

    jugador = db.relationship("Jugador")
