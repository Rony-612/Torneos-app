from datetime import datetime
from app.extensions import db


class Organizacion(db.Model):
    __tablename__ = "organizaciones"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    logo_url = db.Column(db.String(300))

    torneos = db.relationship("Torneo", backref="organizacion", lazy=True)
    equipos = db.relationship("Equipo", backref="organizacion", lazy=True)
    canchas = db.relationship("Cancha", backref="organizacion", lazy=True)
    arbitros = db.relationship("Arbitro", backref="organizacion", lazy=True)
    noticias = db.relationship("Noticia", backref="organizacion", lazy=True)


class Deporte(db.Model):
    __tablename__ = "deportes"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(80), nullable=False)
    # reglas flexibles por deporte: nombres de eventos, duracion, etc.
    reglas = db.Column(db.JSON, default=dict)

    torneos = db.relationship("Torneo", backref="deporte", lazy=True)


class Torneo(db.Model):
    __tablename__ = "torneos"
    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey("organizaciones.id"), nullable=False)
    deporte_id = db.Column(db.Integer, db.ForeignKey("deportes.id"), nullable=False)
    nombre = db.Column(db.String(150), nullable=False)
    formato = db.Column(db.String(50), default="grupos")  # grupos, liga, eliminacion_directa

    temporadas = db.relationship("Temporada", backref="torneo", lazy=True)


class Temporada(db.Model):
    __tablename__ = "temporadas"
    id = db.Column(db.Integer, primary_key=True)
    torneo_id = db.Column(db.Integer, db.ForeignKey("torneos.id"), nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    fecha_inicio = db.Column(db.Date)
    fecha_fin = db.Column(db.Date)
    estado = db.Column(db.String(30), default="planeacion")  # planeacion, en_curso, finalizada

    categorias = db.relationship("Categoria", backref="temporada", lazy=True)
    rosters = db.relationship("Roster", backref="temporada", lazy=True)
    inscripciones = db.relationship("Inscripcion", backref="temporada", lazy=True)


class Categoria(db.Model):
    __tablename__ = "categorias"
    id = db.Column(db.Integer, primary_key=True)
    temporada_id = db.Column(db.Integer, db.ForeignKey("temporadas.id"), nullable=False)
    nombre = db.Column(db.String(80), nullable=False)  # Varonil, Femenil, Libre...

    fases = db.relationship("Fase", backref="categoria", lazy=True)


class Fase(db.Model):
    __tablename__ = "fases"
    id = db.Column(db.Integer, primary_key=True)
    categoria_id = db.Column(db.Integer, db.ForeignKey("categorias.id"), nullable=False)
    tipo = db.Column(db.String(30), nullable=False)  # grupos, cuartos, semifinal, final
    nombre = db.Column(db.String(80), nullable=False)
    orden = db.Column(db.Integer, default=1)

    grupos = db.relationship("Grupo", backref="fase", lazy=True)
    jornadas = db.relationship("Jornada", backref="fase", lazy=True)


class Grupo(db.Model):
    __tablename__ = "grupos"
    id = db.Column(db.Integer, primary_key=True)
    fase_id = db.Column(db.Integer, db.ForeignKey("fases.id"), nullable=False)
    nombre = db.Column(db.String(50), nullable=False)  # A, B...

    inscripciones = db.relationship("Inscripcion", backref="grupo", lazy=True)

    def equipos(self):
        return [i.equipo for i in self.inscripciones if i.estado == "activo"]

    def tabla_posiciones(self):
        """Calcula PJ, PG, PE, PP, GF, GC, DG, Pts para cada equipo del grupo."""
        from app.models.partidos import Partido
        filas = {}
        for equipo in self.equipos():
            filas[equipo.id] = {
                "equipo": equipo, "pj": 0, "pg": 0, "pe": 0, "pp": 0,
                "gf": 0, "gc": 0, "dg": 0, "pts": 0,
            }
        equipo_ids = list(filas.keys())
        partidos = Partido.query.filter(
            Partido.jornada.has(fase_id=self.fase_id),
            Partido.estado == "jugado",
            Partido.equipo_local_id.in_(equipo_ids),
            Partido.equipo_visitante_id.in_(equipo_ids),
        ).all()
        for p in partidos:
            if p.resultado_local is None or p.resultado_visitante is None:
                continue
            fl, fv = filas.get(p.equipo_local_id), filas.get(p.equipo_visitante_id)
            if not fl or not fv:
                continue
            fl["pj"] += 1; fv["pj"] += 1
            fl["gf"] += p.resultado_local; fl["gc"] += p.resultado_visitante
            fv["gf"] += p.resultado_visitante; fv["gc"] += p.resultado_local
            if p.resultado_local > p.resultado_visitante:
                fl["pg"] += 1; fl["pts"] += 3; fv["pp"] += 1
            elif p.resultado_local < p.resultado_visitante:
                fv["pg"] += 1; fv["pts"] += 3; fl["pp"] += 1
            else:
                fl["pe"] += 1; fv["pe"] += 1; fl["pts"] += 1; fv["pts"] += 1
        for f in filas.values():
            f["dg"] = f["gf"] - f["gc"]
        return sorted(filas.values(), key=lambda x: (-x["pts"], -x["dg"], -x["gf"]))


class Cancha(db.Model):
    __tablename__ = "canchas"
    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey("organizaciones.id"), nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    ubicacion = db.Column(db.String(200))

    partidos = db.relationship("Partido", backref="cancha", lazy=True)


class Arbitro(db.Model):
    __tablename__ = "arbitros"
    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey("organizaciones.id"), nullable=False)
    nombre = db.Column(db.String(120), nullable=False)
    contacto = db.Column(db.String(120))

    partidos = db.relationship("Partido", backref="arbitro", lazy=True)


class Noticia(db.Model):
    __tablename__ = "noticias"
    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey("organizaciones.id"), nullable=False)
    titulo = db.Column(db.String(200), nullable=False)
    contenido = db.Column(db.Text, nullable=False)
    fecha_publicacion = db.Column(db.DateTime, default=datetime.utcnow)
    autor_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"))


class ObjetoPerdido(db.Model):
    __tablename__ = "objetos_perdidos"
    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey("organizaciones.id"), nullable=False)
    titulo = db.Column(db.String(150), nullable=False)
    descripcion = db.Column(db.String(400))
    ubicacion = db.Column(db.String(100))
    reportado_por_equipo_id = db.Column(db.Integer, db.ForeignKey("equipos.id"))
    fecha_reporte = db.Column(db.DateTime, default=datetime.utcnow)
    resuelto = db.Column(db.Boolean, default=False)

    reportado_por_equipo = db.relationship("Equipo")
