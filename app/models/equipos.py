from app.extensions import db


class Equipo(db.Model):
    __tablename__ = "equipos"
    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey("organizaciones.id"), nullable=False)
    nombre = db.Column(db.String(120), nullable=False)
    escudo_url = db.Column(db.String(300))
    capitan_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"))

    inscripciones = db.relationship("Inscripcion", backref="equipo", lazy=True)
    rosters = db.relationship("Roster", backref="equipo", lazy=True)

    def jugadores_temporada(self, temporada_id):
        return [r.jugador for r in self.rosters if r.temporada_id == temporada_id]

    def partidos(self):
        from app.models.partidos import Partido
        return Partido.query.filter(
            db.or_(Partido.equipo_local_id == self.id, Partido.equipo_visitante_id == self.id)
        ).all()


class Inscripcion(db.Model):
    """Une un equipo a un grupo/temporada. Permite que un mismo equipo
    participe en varios torneos o temporadas sin duplicarse."""
    __tablename__ = "inscripciones"
    id = db.Column(db.Integer, primary_key=True)
    equipo_id = db.Column(db.Integer, db.ForeignKey("equipos.id"), nullable=False)
    grupo_id = db.Column(db.Integer, db.ForeignKey("grupos.id"), nullable=False)
    temporada_id = db.Column(db.Integer, db.ForeignKey("temporadas.id"), nullable=False)
    estado = db.Column(db.String(20), default="activo")  # activo, retirado


class PagoCancha(db.Model):
    """Los 4 pagos de renta de cancha que cada equipo debe cubrir en la
    temporada. Se manejan como 4 casillas simples (no ligadas a un partido
    en particular) porque asi es como los organizadores llevan el control."""
    __tablename__ = "pagos_cancha"
    id = db.Column(db.Integer, primary_key=True)
    equipo_id = db.Column(db.Integer, db.ForeignKey("equipos.id"), nullable=False)
    temporada_id = db.Column(db.Integer, db.ForeignKey("temporadas.id"), nullable=False)
    pago_1 = db.Column(db.Boolean, default=False)
    pago_2 = db.Column(db.Boolean, default=False)
    pago_3 = db.Column(db.Boolean, default=False)
    pago_4 = db.Column(db.Boolean, default=False)

    equipo = db.relationship("Equipo")

    def completados(self):
        return sum([self.pago_1, self.pago_2, self.pago_3, self.pago_4])


class Jugador(db.Model):
    __tablename__ = "jugadores"
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"))
    nombre = db.Column(db.String(120), nullable=False)
    foto_url = db.Column(db.String(300))
    fecha_nacimiento = db.Column(db.Date)

    rosters = db.relationship("Roster", backref="jugador", lazy=True)

    def equipo_actual(self, temporada_id):
        r = next((r for r in self.rosters if r.temporada_id == temporada_id), None)
        return r.equipo if r else None

    def estadisticas(self, temporada_id=None):
        from app.models.partidos import EventoPartido, Partido
        q = EventoPartido.query.filter_by(jugador_id=self.id)
        eventos = q.all()
        goles = sum(1 for e in eventos if e.tipo_evento == "gol")
        asistencias = sum(1 for e in eventos if e.tipo_evento == "asistencia")
        amarillas = sum(1 for e in eventos if e.tipo_evento == "tarjeta_amarilla")
        rojas = sum(1 for e in eventos if e.tipo_evento == "tarjeta_roja")
        partido_ids = {e.partido_id for e in eventos}
        partidos_jugados = Partido.query.filter(
            Partido.id.in_(partido_ids), Partido.estado == "jugado"
        ).count() if partido_ids else 0
        return {
            "goles": goles, "asistencias": asistencias,
            "amarillas": amarillas, "rojas": rojas,
            "partidos_jugados": partidos_jugados,
        }


class Roster(db.Model):
    """Un jugador pertenece a un equipo durante una temporada especifica."""
    __tablename__ = "rosters"
    id = db.Column(db.Integer, primary_key=True)
    jugador_id = db.Column(db.Integer, db.ForeignKey("jugadores.id"), nullable=False)
    equipo_id = db.Column(db.Integer, db.ForeignKey("equipos.id"), nullable=False)
    temporada_id = db.Column(db.Integer, db.ForeignKey("temporadas.id"), nullable=False)
    numero_playera = db.Column(db.Integer)
    posicion = db.Column(db.String(50))
    inscripcion_pagada = db.Column(db.Boolean, default=False)
    seguro_pagado = db.Column(db.Boolean, default=False)

    def documentacion_completa(self):
        return bool(self.inscripcion_pagada and self.seguro_pagado)
