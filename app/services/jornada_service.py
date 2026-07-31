from app.extensions import db
from app.models import Jornada
from app.services import notificacion_service


class JornadaYaPublicadaError(Exception):
    pass


def publicar_jornada(jornada_id, usuario):
    jornada = Jornada.query.get_or_404(jornada_id)
    if jornada.estado == "publicada":
        raise JornadaYaPublicadaError("Esta jornada ya fue publicada.")
    jornada.publicar(usuario)
    db.session.commit()
    notificacion_service.notificar_publicacion_jornada(jornada)
    return jornada


def crear_jornada(fase_id, numero, fecha_referencia=None):
    jornada = Jornada(fase_id=fase_id, numero=numero, fecha_referencia=fecha_referencia, estado="borrador")
    db.session.add(jornada)
    db.session.commit()
    return jornada
