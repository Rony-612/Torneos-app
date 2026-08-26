"""Genera datos de ejemplo para el Torneo Interno de Fútbol DCEA.
Uso: python seed.py
"""
from datetime import date, time, timedelta
from app import create_app
from app.extensions import db
from app.models import (
    Organizacion, Deporte, Torneo, Temporada, Categoria, Fase, Grupo,
    Cancha, Arbitro, Equipo, Inscripcion, Jugador, Roster, Usuario,
    Jornada, Partido, EventoPartido, Noticia, Disponibilidad,
)

app = create_app()

EQUIPOS_A = ["Contadores FC", "Mercadotecnia United", "Finanzas FC", "Economía Real", "Gestión Deportivo", "Negocios United"]
EQUIPOS_B = ["Aduanas FC", "Recursos Humanos", "Impuestos United", "Comercio Real", "Innovación FC", "Emprende United"]

with app.app_context():
    db.drop_all()
    db.create_all()

    org = Organizacion(nombre="DCEA - Universidad de Guanajuato")
    db.session.add(org)
    db.session.flush()

    deporte = Deporte(nombre="Fútbol", reglas={"duracion_min": 60, "eventos": ["gol", "asistencia", "tarjeta_amarilla", "tarjeta_roja"]})
    db.session.add(deporte)
    db.session.flush()

    torneo = Torneo(organizacion_id=org.id, deporte_id=deporte.id, nombre="Torneo Interno DCEA 2026", formato="grupos")
    db.session.add(torneo)
    db.session.flush()

    temporada = Temporada(torneo_id=torneo.id, nombre="2026-A", fecha_inicio=date(2026, 8, 1), fecha_fin=date(2026, 12, 1), estado="en_curso")
    db.session.add(temporada)
    db.session.flush()

    categoria = Categoria(temporada_id=temporada.id, nombre="Varonil libre")
    db.session.add(categoria)
    db.session.flush()

    fase = Fase(categoria_id=categoria.id, tipo="grupos", nombre="Fase de grupos", orden=1)
    db.session.add(fase)
    db.session.flush()

    grupo_a = Grupo(fase_id=fase.id, nombre="A")
    grupo_b = Grupo(fase_id=fase.id, nombre="B")
    db.session.add_all([grupo_a, grupo_b])
    db.session.flush()

    # Este torneo solo cuenta con una cancha y un arbitro disponibles,
    # por eso los partidos se juegan unicamente martes/miercoles/jueves
    # de 10:00 a 14:00 (un partido a la vez).
    cancha1 = Cancha(organizacion_id=org.id, nombre="Cancha Central - Campus Marfil", ubicacion="Marfil")
    db.session.add(cancha1)
    db.session.flush()

    arbitro1 = Arbitro(organizacion_id=org.id, nombre="Juan Pérez", contacto="juan.perez@example.com")
    db.session.add(arbitro1)
    db.session.flush()

    # --- Usuarios ---
    organizadora = Usuario(nombre="Organizadora DCEA", email="organizadora@dcea.ugto.mx", rol="organizador")
    organizadora.set_password("admin123")
    db.session.add(organizadora)

    # --- Equipos y jugadores ---
    LICENCIATURAS = ["LCI", "LRI", "LMKT", "LCF", "LNI", "LAE", "LTUR", "LGE"]

    def crear_equipo(nombre, grupo, idx_base):
        equipo = Equipo(organizacion_id=org.id, nombre=nombre)
        db.session.add(equipo)
        db.session.flush()
        db.session.add(Inscripcion(equipo_id=equipo.id, grupo_id=grupo.id, temporada_id=temporada.id))
        for i in range(1, 9):
            jugador = Jugador(nombre=f"Jugador {idx_base}-{i}")
            db.session.add(jugador)
            db.session.flush()
            db.session.add(Roster(
                jugador_id=jugador.id, equipo_id=equipo.id, temporada_id=temporada.id,
                nua=f"{idx_base}{i:02d}{idx_base}45",
                licenciatura=LICENCIATURAS[(idx_base + i) % len(LICENCIATURAS)],
            ))
        return equipo

    equipos_a = [crear_equipo(n, grupo_a, i + 1) for i, n in enumerate(EQUIPOS_A)]
    equipos_b = [crear_equipo(n, grupo_b, i + 7) for i, n in enumerate(EQUIPOS_B)]
    db.session.flush()

    # un capitan por cada equipo (los 12), mismo password para todos,
    # para poder entrar y probar con el equipo que quieras
    equipos_todos = equipos_a + equipos_b
    capitanes_creados = []
    for i, equipo in enumerate(equipos_todos, start=1):
        email = f"capitan{i}@dcea.ugto.mx"
        capitan_user = Usuario(nombre=f"Capitán {equipo.nombre}", email=email, rol="capitan")
        capitan_user.set_password("capitan123")
        db.session.add(capitan_user)
        db.session.flush()
        equipo.capitan_id = capitan_user.id
        capitanes_creados.append((equipo.nombre, email))

    # --- Jornada 1: publicada, completa. Los 6 equipos de cada grupo ya
    # jugaron su primer partido de la ronda, salvo uno que quedo suspendido. ---
    # semana del lunes 10 de agosto -> martes 11, miercoles 12, jueves 13
    lunes_j1 = date(2026, 8, 10)
    martes_j1, miercoles_j1, jueves_j1 = lunes_j1 + timedelta(days=1), lunes_j1 + timedelta(days=2), lunes_j1 + timedelta(days=3)

    jornada1 = Jornada(fase_id=fase.id, numero=1, fecha_referencia=lunes_j1, estado="borrador")
    db.session.add(jornada1)
    db.session.flush()

    partidos_j1 = [
        # Grupo A
        Partido(jornada_id=jornada1.id, equipo_local_id=equipos_a[0].id, equipo_visitante_id=equipos_a[1].id,
                cancha_id=cancha1.id, arbitro_id=arbitro1.id, fecha=martes_j1, hora=time(10, 0),
                estado="jugado", resultado_local=3, resultado_visitante=1),
        Partido(jornada_id=jornada1.id, equipo_local_id=equipos_a[2].id, equipo_visitante_id=equipos_a[3].id,
                cancha_id=cancha1.id, arbitro_id=arbitro1.id, fecha=miercoles_j1, hora=time(10, 0),
                estado="jugado", resultado_local=1, resultado_visitante=1),
        Partido(jornada_id=jornada1.id, equipo_local_id=equipos_a[4].id, equipo_visitante_id=equipos_a[5].id,
                cancha_id=cancha1.id, arbitro_id=arbitro1.id, fecha=jueves_j1, hora=time(10, 0),
                estado="suspendido", nota="Suspendido por lluvia, pendiente de reprogramar"),
        # Grupo B
        Partido(jornada_id=jornada1.id, equipo_local_id=equipos_b[0].id, equipo_visitante_id=equipos_b[1].id,
                cancha_id=cancha1.id, arbitro_id=arbitro1.id, fecha=martes_j1, hora=time(11, 0),
                estado="jugado", resultado_local=2, resultado_visitante=0),
        Partido(jornada_id=jornada1.id, equipo_local_id=equipos_b[2].id, equipo_visitante_id=equipos_b[3].id,
                cancha_id=cancha1.id, arbitro_id=arbitro1.id, fecha=miercoles_j1, hora=time(11, 0),
                estado="jugado", resultado_local=2, resultado_visitante=1),
        Partido(jornada_id=jornada1.id, equipo_local_id=equipos_b[4].id, equipo_visitante_id=equipos_b[5].id,
                cancha_id=cancha1.id, arbitro_id=arbitro1.id, fecha=jueves_j1, hora=time(11, 0),
                estado="jugado", resultado_local=0, resultado_visitante=0),
    ]
    db.session.add_all(partidos_j1)
    db.session.flush()
    p_contadores_mercadotecnia, p_finanzas_economia, p_gestion_negocios, \
        p_aduanas_rrhh, p_impuestos_comercio, p_innovacion_emprende = partidos_j1

    def jugadores_de(equipo):
        return Jugador.query.join(Roster).filter(Roster.equipo_id == equipo.id).all()

    j_contadores = jugadores_de(equipos_a[0])
    j_mercadotecnia = jugadores_de(equipos_a[1])
    j_finanzas = jugadores_de(equipos_a[2])
    j_economia = jugadores_de(equipos_a[3])
    j_aduanas = jugadores_de(equipos_b[0])
    j_rrhh = jugadores_de(equipos_b[1])
    j_impuestos = jugadores_de(equipos_b[2])
    j_comercio = jugadores_de(equipos_b[3])

    eventos = [
        # Contadores 3-1 Mercadotecnia
        EventoPartido(partido_id=p_contadores_mercadotecnia.id, jugador_id=j_contadores[0].id, equipo_id=equipos_a[0].id, tipo_evento="gol", minuto=12),
        EventoPartido(partido_id=p_contadores_mercadotecnia.id, jugador_id=j_contadores[0].id, equipo_id=equipos_a[0].id, tipo_evento="gol", minuto=34),
        EventoPartido(partido_id=p_contadores_mercadotecnia.id, jugador_id=j_contadores[1].id, equipo_id=equipos_a[0].id, tipo_evento="gol", minuto=50),
        EventoPartido(partido_id=p_contadores_mercadotecnia.id, jugador_id=j_mercadotecnia[0].id, equipo_id=equipos_a[1].id, tipo_evento="gol", minuto=40),
        EventoPartido(partido_id=p_contadores_mercadotecnia.id, jugador_id=j_mercadotecnia[2].id, equipo_id=equipos_a[1].id, tipo_evento="tarjeta_amarilla", minuto=45),
        # Finanzas 1-1 Economia
        EventoPartido(partido_id=p_finanzas_economia.id, jugador_id=j_finanzas[3].id, equipo_id=equipos_a[2].id, tipo_evento="gol", minuto=22),
        EventoPartido(partido_id=p_finanzas_economia.id, jugador_id=j_economia[1].id, equipo_id=equipos_a[3].id, tipo_evento="gol", minuto=58),
        # Aduanas 2-0 RRHH
        EventoPartido(partido_id=p_aduanas_rrhh.id, jugador_id=j_aduanas[0].id, equipo_id=equipos_b[0].id, tipo_evento="gol", minuto=15),
        EventoPartido(partido_id=p_aduanas_rrhh.id, jugador_id=j_aduanas[0].id, equipo_id=equipos_b[0].id, tipo_evento="gol", minuto=61),
        EventoPartido(partido_id=p_aduanas_rrhh.id, jugador_id=j_rrhh[4].id, equipo_id=equipos_b[1].id, tipo_evento="tarjeta_roja", minuto=70),
        # Impuestos 2-1 Comercio
        EventoPartido(partido_id=p_impuestos_comercio.id, jugador_id=j_impuestos[2].id, equipo_id=equipos_b[2].id, tipo_evento="gol", minuto=18),
        EventoPartido(partido_id=p_impuestos_comercio.id, jugador_id=j_impuestos[2].id, equipo_id=equipos_b[2].id, tipo_evento="gol", minuto=44),
        EventoPartido(partido_id=p_impuestos_comercio.id, jugador_id=j_comercio[0].id, equipo_id=equipos_b[3].id, tipo_evento="gol", minuto=80),
    ]
    db.session.add_all(eventos)

    jornada1.estado = "publicada"
    jornada1.publicada_por_id = organizadora.id

    # --- Disponibilidad de ejemplo (martes/miercoles/jueves, 10:00-14:00) ---
    # de la semana siguiente, para poder probar "Generar calendario"
    semana_ejemplo = lunes_j1 + timedelta(days=7)
    disponibilidades = [
        Disponibilidad(equipo_id=equipos_a[0].id, temporada_id=temporada.id, semana=semana_ejemplo, dia_semana="martes", hora_inicio=time(10, 0), hora_fin=time(11, 0)),
        Disponibilidad(equipo_id=equipos_a[0].id, temporada_id=temporada.id, semana=semana_ejemplo, dia_semana="jueves", hora_inicio=time(11, 0), hora_fin=time(12, 0)),
        Disponibilidad(equipo_id=equipos_a[1].id, temporada_id=temporada.id, semana=semana_ejemplo, dia_semana="martes", hora_inicio=time(10, 0), hora_fin=time(11, 0)),
        Disponibilidad(equipo_id=equipos_a[1].id, temporada_id=temporada.id, semana=semana_ejemplo, dia_semana="jueves", hora_inicio=time(11, 0), hora_fin=time(12, 0)),
        Disponibilidad(equipo_id=equipos_a[2].id, temporada_id=temporada.id, semana=semana_ejemplo, dia_semana="miercoles", hora_inicio=time(10, 0), hora_fin=time(11, 0)),
        Disponibilidad(equipo_id=equipos_a[3].id, temporada_id=temporada.id, semana=semana_ejemplo, dia_semana="miercoles", hora_inicio=time(10, 0), hora_fin=time(11, 0)),
        Disponibilidad(equipo_id=equipos_a[4].id, temporada_id=temporada.id, semana=semana_ejemplo, dia_semana="martes", hora_inicio=time(12, 0), hora_fin=time(13, 0)),
        Disponibilidad(equipo_id=equipos_a[5].id, temporada_id=temporada.id, semana=semana_ejemplo, dia_semana="martes", hora_inicio=time(12, 0), hora_fin=time(13, 0)),
        Disponibilidad(equipo_id=equipos_b[0].id, temporada_id=temporada.id, semana=semana_ejemplo, dia_semana="jueves", hora_inicio=time(10, 0), hora_fin=time(11, 0)),
        Disponibilidad(equipo_id=equipos_b[1].id, temporada_id=temporada.id, semana=semana_ejemplo, dia_semana="jueves", hora_inicio=time(10, 0), hora_fin=time(11, 0)),
        Disponibilidad(equipo_id=equipos_b[2].id, temporada_id=temporada.id, semana=semana_ejemplo, dia_semana="miercoles", hora_inicio=time(11, 0), hora_fin=time(12, 0)),
        Disponibilidad(equipo_id=equipos_b[3].id, temporada_id=temporada.id, semana=semana_ejemplo, dia_semana="miercoles", hora_inicio=time(11, 0), hora_fin=time(12, 0)),
    ]
    db.session.add_all(disponibilidades)

    # --- Pagos de cancha de ejemplo (algunos equipos completos, otros a medias) ---
    from app.models import PagoCancha
    pagos_cancha = [
        PagoCancha(equipo_id=equipos_a[0].id, temporada_id=temporada.id, pago_1=True, pago_2=True, pago_3=True, pago_4=True),
        PagoCancha(equipo_id=equipos_a[1].id, temporada_id=temporada.id, pago_1=True, pago_2=True),
        PagoCancha(equipo_id=equipos_a[2].id, temporada_id=temporada.id, pago_1=True),
        PagoCancha(equipo_id=equipos_b[0].id, temporada_id=temporada.id, pago_1=True, pago_2=True, pago_3=True),
    ]
    db.session.add_all(pagos_cancha)

    # --- Noticia de ejemplo ---
    noticia = Noticia(
        organizacion_id=org.id, titulo="Inicia el Torneo Interno DCEA 2026",
        contenido="Arrancamos la temporada 2026-A con 12 equipos divididos en dos grupos. ¡Mucho éxito a todos los participantes!",
        autor_id=organizadora.id,
    )
    db.session.add(noticia)

    db.session.commit()

    print("Datos de ejemplo creados correctamente.")
    print("Organizadora -> organizadora@dcea.ugto.mx / admin123")
    print()
    print("Capitanes (mismo password para todos: capitan123):")
    for nombre_equipo, email in capitanes_creados:
        print(f"  {email:30s} -> {nombre_equipo}")
