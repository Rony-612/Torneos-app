"""Prepara la base de datos para un torneo REAL: crea la organización, el
torneo, la temporada, los 2 grupos, una cancha, un árbitro y la cuenta de
la organizadora — sin ningún equipo, jugador ni partido de mentiras.

A diferencia de seed.py, este script:
- NO borra la base de datos existente (usa create_all, no drop_all).
- Es seguro de correr más de una vez: si ya existe una Organización, no
  duplica nada y simplemente te avisa.
- Pide los datos reales por consola en vez de traerlos ya inventados.

Uso:
    python init_produccion.py

Después de correrlo, entra al panel de organización y desde ahí registra
los equipos reales, sus jugadores, y crea la cuenta de cada capitán (botón
"Crear cuenta" en Equipos) — ya no hace falta tocar la base de datos a mano
ni volver a correr ningún script para eso.
"""
import getpass
from datetime import date
from app import create_app
from app.extensions import db
from app.models import Organizacion, Deporte, Torneo, Temporada, Categoria, Fase, Grupo, Cancha, Arbitro, Usuario

app = create_app()


def preguntar(etiqueta, default=None):
    sufijo = f" [{default}]" if default else ""
    valor = input(f"{etiqueta}{sufijo}: ").strip()
    return valor or default


with app.app_context():
    db.create_all()

    if Organizacion.query.first():
        print("Ya hay datos en esta base de datos (existe una Organización).")
        print("Este script no borra nada, así que no hace falta correrlo de nuevo.")
        print("Si de verdad quieres empezar desde cero, borra el archivo .db y vuelve a correr este script.")
        raise SystemExit(0)

    print("=== Inicialización del torneo (datos reales) ===\n")
    nombre_org = preguntar("Nombre de la organización", "DCEA - Universidad de Guanajuato")
    nombre_torneo = preguntar("Nombre del torneo", "Torneo Interno DCEA")
    nombre_temporada = preguntar("Nombre de la temporada", "2026-A")
    nombre_categoria = preguntar("Categoría", "Varonil libre")
    nombre_cancha = preguntar("Nombre de la cancha", "Cancha Central - Campus Marfil")
    nombre_arbitro = preguntar("Nombre del árbitro", "Por asignar")

    print("\n=== Cuenta de la organizadora (para entrar al panel) ===")
    email_admin = preguntar("Correo de la organizadora")
    while not email_admin:
        email_admin = preguntar("Correo de la organizadora (obligatorio)")
    nombre_admin = preguntar("Nombre de la organizadora", "Organizadora")
    password_admin = getpass.getpass("Contraseña para esa cuenta (no se muestra al escribir): ")
    while len(password_admin) < 6:
        print("La contraseña debe tener al menos 6 caracteres.")
        password_admin = getpass.getpass("Contraseña para esa cuenta: ")

    org = Organizacion(nombre=nombre_org)
    db.session.add(org)
    db.session.flush()

    deporte = Deporte(nombre="Fútbol", reglas={"duracion_min": 60})
    db.session.add(deporte)
    db.session.flush()

    torneo = Torneo(organizacion_id=org.id, deporte_id=deporte.id, nombre=nombre_torneo, formato="grupos")
    db.session.add(torneo)
    db.session.flush()

    temporada = Temporada(torneo_id=torneo.id, nombre=nombre_temporada, fecha_inicio=date.today(), estado="en_curso")
    db.session.add(temporada)
    db.session.flush()

    categoria = Categoria(temporada_id=temporada.id, nombre=nombre_categoria)
    db.session.add(categoria)
    db.session.flush()

    fase = Fase(categoria_id=categoria.id, tipo="grupos", nombre="Fase de grupos", orden=1)
    db.session.add(fase)
    db.session.flush()

    db.session.add_all([
        Grupo(fase_id=fase.id, nombre="A"),
        Grupo(fase_id=fase.id, nombre="B"),
    ])

    db.session.add(Cancha(organizacion_id=org.id, nombre=nombre_cancha))
    db.session.add(Arbitro(organizacion_id=org.id, nombre=nombre_arbitro))

    admin_user = Usuario(nombre=nombre_admin, email=email_admin, rol="organizador")
    admin_user.set_password(password_admin)
    db.session.add(admin_user)

    db.session.commit()

    print("\n¡Listo! Ya puedes entrar al panel de organización con:")
    print(f"  Correo:     {email_admin}")
    print("  Contraseña: la que acabas de escribir")
    print("\nDesde ahí registra los equipos reales, sus jugadores, y crea la cuenta de cada")
    print("capitán (Equipos → 'Crear cuenta'). No hace falta correr ningún otro script.")
