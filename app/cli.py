"""Comando de consola para mandar los recordatorios de partido.

Este proyecto es un servidor web normal (no tiene un 'reloj' interno
corriendo en segundo plano), así que los recordatorios por tiempo no se
pueden disparar solos desde una vista como el resto de notificaciones.
Lo que se necesita es que algo externo llame este comando periódicamente:
un cron job del servidor, un 'Scheduled Job' de Railway/Render, o una tarea
programada de Windows si se corre en una máquina local.

Uso manual:
    flask enviar-recordatorios

Uso típico en cron (correr cada hora, todos los días):
    0 * * * * cd /ruta/al/proyecto && /ruta/al/venv/bin/flask enviar-recordatorios

El comando es seguro de correr varias veces: cada partido solo manda su
recordatorio de 'un día antes' una vez, y el de 'una hora antes' una vez
(se marca con una bandera en la base de datos apenas se manda).
"""
import click
from flask.cli import with_appcontext
from app.services import notificacion_service


@click.command("enviar-recordatorios")
@with_appcontext
def enviar_recordatorios():
    """Manda el recordatorio de 'un día antes' y el de 'una hora antes' a
    los partidos programados que ya les toca, y marca cuáles ya se enviaron
    para no duplicarlos si el comando se corre varias veces."""
    enviados_dia, enviados_hora = notificacion_service.ejecutar_recordatorios()
    click.echo(f"Recordatorios enviados: {enviados_dia} de 'un día antes', {enviados_hora} de 'una hora antes'.")


def registrar_comandos_cli(app):
    app.cli.add_command(enviar_recordatorios)
