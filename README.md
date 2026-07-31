# Sistema de Gestión de Torneos Deportivos - MVP

MVP funcional para el Torneo Interno de Fútbol de la DCEA (Universidad de Guanajuato),
construido con Flask + SQLAlchemy + SQLite. Arquitectura pensada para escalar a
múltiples torneos, categorías y deportes sin rediseñar la base de datos (ver ERD).

## Instalación

```bash
cd torneos-app
python3 -m venv venv
source venv/bin/activate        # en Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Cargar datos de ejemplo (torneo DCEA)

```bash
python seed.py
```

Esto crea:
- La organización DCEA, el torneo, temporada 2026-A, categoría, fase de grupos y los grupos A y B.
- 12 equipos (6 por grupo) con 8 jugadores cada uno.
- **Una sola cancha y un solo árbitro** (así es este torneo): los partidos solo se
  juegan martes, miércoles y jueves de 10:00 a 14:00, un partido a la vez.
- **Solo la Jornada 1, completa y publicada**: los 6 partidos de la primera ronda
  (3 por grupo) con resultados, goleadores y tarjetas ya registrados, salvo uno
  que quedó **suspendido** (para que pruebes "Pendientes" desde el primer momento).
- Disponibilidad de ejemplo (de la semana siguiente, dentro del horario fijo) para
  varios equipos, para probar la generación automática de calendario.
- Usuarios de prueba:
  - Organizadora: `organizadora@dcea.ugto.mx` / `admin123`
  - **Un capitán por cada uno de los 12 equipos**, mismo password para todos:
    `capitan1@dcea.ugto.mx` hasta `capitan12@dcea.ugto.mx` / `capitan123`
    (el número sigue el orden de equipos que ves al correr `python seed.py`,
    que también los lista en la consola). Así puedes entrar con el equipo
    que quieras para probar cualquier flujo.

No hay una Jornada 2 precargada a propósito: la generas tú mismo desde
Admin → Horarios → "Generar jornada de esta semana" para probar el flujo completo.

## Correr el servidor

```bash
python wsgi.py
```

Abre `http://localhost:5000` en tu navegador.

- **Sitio público:** `http://localhost:5000/`
- **Panel de organización:** `http://localhost:5000/admin/login`
- **Portal de capitanes:** `http://localhost:5000/capitan/login`

## El horario fijo del torneo

Como solo hay una cancha y un árbitro, todo el sistema gira alrededor de una
rejilla fija: **martes, miércoles y jueves, de 10:00 a 14:00** (bloques de una
hora). Esa regla vive en `app/services/jornada_grid.py` y la usan:

- La disponibilidad que registran los capitanes (grid de 3 días x 4 horas).
- La tabla-calendario de cada jornada (mismo diseño en el sitio público, en el
  panel de organización y al proponer/responder cambios de horario), con el
  estilo "JORNADA X (del ... al ...)" que ya usan en la DCEA.
- La generación automática de calendario, que solo agenda un partido por slot
  (al fin y al cabo solo hay una cancha).
- La selección de horarios al pedir un cambio: un capitán puede marcar varios
  horarios libres de esa misma jornada como alternativas, y el rival elige
  cuál le sirve (o dice que ninguno) sobre esa misma tabla.

## Qué incluye este MVP

**Público:** inicio (próximos partidos, resultados, goleadores, noticias), tabla de
posiciones por grupo, calendario con la tabla-calendario tipo "Jornada X" (muestra
resultado o "SUSPENDIDO"/"REPROGRAMADO" según el estado) por jornada publicada,
ficha de partido (goles/tarjetas/árbitro), tabla de goleadores, tabla disciplinaria,
perfiles de equipo y de jugador, noticias.

**Panel de organización** (Tailwind + paleta navy/gold):
- Jornadas: la tabla-calendario de la jornada arriba (se actualiza sola conforme
  editas), y abajo la lista de partidos totalmente editable. Al elegir el equipo
  local, el select de visitante se filtra automáticamente para solo mostrar
  equipos de su mismo grupo que todavía no se hayan enfrentado (en toda la fase,
  no solo en esa jornada) — así no se puede armar un partido repetido por error.
- Grupos: asignar y quitar equipos de cada grupo.
- Documentos: marcar inscripción y seguro pagados por jugador.
- Arbitrajes: costo y estatus de pago **por equipo** (un equipo puede estar
  pagado y el otro no; solo la organización lo marca).
- **Pagos de cancha**: cada equipo tiene 4 casillas (los 4 pagos de renta de
  cancha de la temporada); la organización las marca desde una tabla, igual
  que Documentos.
- Horarios: navegar semana a semana la disponibilidad de cada capitán, y
  **generar automáticamente** una jornada. Si ya no quedan enfrentamientos
  nuevos por jugar pero hay partidos pendientes/suspendidos, arma con esos la
  **jornada final** en automático.
- Solicitudes: aprobar/rechazar los cambios de horario ya aceptados por ambos
  capitanes. Si el rival **rechazó** la propuesta, también aparece aquí para que
  decidas si el partido se queda en su horario original o pasa a "Pendientes".
- **Pendientes**: todos los partidos suspendidos, con opción de eliminarlos o de
  agregarlos a cualquier jornada en un horario libre (incluida la que está en curso).
  Desde "Registrar resultado" también hay un botón para marcar un partido como
  suspendido y mandarlo directo a esta lista.
- Noticias y Avisos (objetos perdidos, también pueden publicarlos los capitanes).

**Portal de capitanes** (mismo lenguaje visual):
- Inicio: próximo partido, posición en el grupo, disponibilidad de esta semana,
  alertas de arbitraje pendiente y objetos perdidos recientes.
- Horarios: grid de martes/miércoles/jueves x 10:00-14:00 para marcar disponibilidad;
  se navega y edita semana por semana.
- Cambios de horario: al pedir un cambio se muestra la tabla-calendario de esa
  jornada; el capitán marca uno o varios horarios libres como propuesta. El rival
  ve esa misma tabla con las opciones resaltadas, elige la que le sirva (o rechaza
  todas), y de ahí pasa a la organizadora para su aprobación final.
- Mi equipo: estatus de inscripción y seguro de cada jugador (solo lectura).
- Arbitrajes: solo lectura del estatus de pago de **su propio equipo**.
- **Pagos de cancha**: solo lectura, mismas 4 casillas que ve la organización,
  con un mensaje de cuántos le faltan por cubrir.
- Líder de goleo: podio + tabla completa.
- Mi grupo: tabla de posiciones con el equipo propio resaltado.
- Detalles de partido: cada capitán registra el uniforme/casacas de su equipo, y
  puede ver el uniforme que registró el equipo rival.
- Avisos: los capitanes también pueden publicar objetos perdidos.

## Cómo queda el flujo de cambio de horario

1. Un capitán solicita un nuevo horario para un partido propio, proponiendo uno o
   varios horarios libres (`pendiente_rival`).
2. El capitán del equipo rival elige cuál de esas opciones le sirve, o rechaza
   todas. Si acepta, pasa a `pendiente_organizador`. Si rechaza, pasa a
   `rechazado_por_rival` — y **también** aparece del lado de la organizadora, para
   que decida si el partido se queda en su horario original o pasa a "Pendientes".
3. La organizadora ve las solicitudes ya aceptadas por ambos equipos en
   **Solicitudes** y da la aprobación final, que es la que efectivamente mueve
   el partido (queda en estado `reprogramado`).

En cada paso de este flujo (propuesta, aceptación pendiente de aprobación, rechazo
pendiente de decisión, aprobación/rechazo final) se manda un correo a quien le
toca actuar — ver la siguiente sección.

## Correos automáticos

El sistema manda correo en dos formas:

**Por acción** (ya conectado, no requiere nada extra): publicación de jornada,
resultado registrado, partido suspendido, partido reprogramado, y en cada paso
del flujo de cambio de horario.

**Por tiempo** (recordatorio un día antes y una hora antes de cada partido):
como este es un servidor web normal y no tiene un "reloj" corriendo en segundo
plano, este tipo de recordatorio necesita que algo externo dispare el comando
`flask enviar-recordatorios` periódicamente (ver más abajo). El comando ya
existe y ya está probado — lo que falta es programarlo para que corra solo.

### Cómo pasar de "correos simulados" a correos reales

Ahora mismo, sin nada configurado, los correos **no se pierden**: se van
guardando en `correos_enviados.log` (en la raíz del proyecto, se crea solo)
con fecha, destinatarios, asunto y cuerpo completo, para poder revisar
exactamente qué se hubiera mandado sin necesitar credenciales reales.

Para que empiecen a mandarse de verdad, solo hay que definir estas variables
de entorno antes de correr el servidor (no se toca nada de código):

```bash
export MAIL_SERVER=smtp.tu-proveedor.com
export MAIL_PORT=587
export MAIL_USERNAME=torneo@dcea.ugto.mx
export MAIL_PASSWORD=tu-password
export MAIL_FROM=torneo@dcea.ugto.mx   # opcional, por defecto usa MAIL_USERNAME
```

Falta además:

1. **Correos reales de los capitanes.** Los del seed son inventados
   (`capitan1@dcea.ugto.mx`, etc.). Cuando el torneo sea real, cada `Usuario`
   debe tener el correo verdadero del capitán (se puede editar directo en la
   base de datos, o se puede agregar una pantalla de "editar capitán" si la
   quieres — hoy no existe, solo se asignan al crear el equipo).
2. **Un proveedor de correo.** Las opciones más simples:
   - **Gmail/Google Workspace**: `smtp.gmail.com`, puerto 587. Necesita una
     "contraseña de aplicación" (no la contraseña normal de la cuenta) — se
     genera en la configuración de seguridad de la cuenta de Google. Gratis,
     pero con límite de ~500 correos/día, de sobra para un torneo de este tamaño.
   - **Outlook/Office365** (si la universidad ya tiene cuentas institucionales):
     `smtp.office365.com`, puerto 587, mismo esquema de usuario/password.
   - **Servicio transaccional** (SendGrid, Mailgun, Amazon SES, Resend): más
     robusto y con mejor entregabilidad si el volumen crece, pero es una cuenta
     aparte que hay que dar de alta; para un torneo interno probablemente es
     más de lo que se necesita.

   La ruta más rápida para empezar es Gmail con contraseña de aplicación.

### Programar los recordatorios (día antes / hora antes)

El comando `flask enviar-recordatorios`:
- Revisa los partidos programados de jornadas ya publicadas.
- Si un partido es mañana, manda el recordatorio de "un día antes".
- Si un partido es hoy y faltan entre 0 y 90 minutos, manda el de "una hora antes".
- Cada partido guarda una bandera para no mandar el mismo recordatorio dos
  veces, así que es seguro correr el comando repetidamente (por ejemplo, cada
  hora) sin generar correos duplicados.

Para que corra solo, se programa como tarea periódica del lado del servidor
donde termines desplegando el proyecto. En un servidor Linux normal (VPS),
sería una línea de `cron`:

```bash
# correr cada hora, todos los días
0 * * * * cd /ruta/al/proyecto && /ruta/al/venv/bin/flask enviar-recordatorios
```

Si despliegas en una plataforma tipo Railway/Render, buscas su opción de
"Scheduled Job" / "Cron Job" (varias la ofrecen incluso en el plan gratuito)
y ahí configuras que ejecute `flask enviar-recordatorios` cada hora.

La lógica de todos los correos (por acción y por tiempo) vive en
`app/services/notificacion_service.py`: un único punto de entrada
(`enviar_correo`) y una función por cada tipo de aviso, así que agregar un
nuevo evento en el futuro es cuestión de escribir la función y llamarla desde
donde corresponda.

## Sobre el hospedaje (deployment)

Preguntaste por alternativas ahora que Railway pide pago después de la prueba.
Esto es información general, no algo que haya podido probar desde aquí, pero
te comparto el panorama para que decidas con la mejor información posible:

- **PythonAnywhere** — tiene un plan gratuito pensado justo para apps Flask
  chicas como esta. Es de los más sencillos de configurar para alguien sin
  experiencia en servidores, y no pide tarjeta para el plan gratuito. Limitación:
  el dominio gratuito es tipo `tuusuario.pythonanywhere.com`, y tiene límites de
  CPU/tráfico generosos para un torneo interno pero no ilimitados.
- **Render** — plan gratuito para "Web Services", pero el servicio se "duerme"
  tras un rato sin tráfico y tarda unos segundos en despertar en la siguiente
  visita; para un sitio de consulta ocasional (resultados, calendario) es
  aceptable, para algo que se use todo el día quizá se sienta lento a ratos.
- **Fly.io** — tiene una capa gratuita razonable y permite correr contenedores
  Docker; requiere un poco más de familiaridad con la línea de comandos que
  PythonAnywhere.
- **Un servidor de la propia Universidad de Guanajuato** — vale la pena
  preguntar en el departamento de TI/sistemas de la UG si tienen un servidor
  interno o un dominio `.ugto.mx` donde se pueda alojar un proyecto estudiantil;
  muchas universidades sí tienen esta opción y evita cualquier costo.
- **Una laptop/mini PC dedicada** — para un torneo interno de un semestre, correr
  el proyecto en una máquina física conectada a internet (con `wsgi.py` corriendo
  detrás de algo como `gunicorn` + `nginx`) es una opción totalmente válida y
  gratuita, solo que la organizadora depende de que esa máquina esté encendida.

En cualquiera de estas opciones, dos cosas importan para este proyecto en
particular: (1) que el hospedaje permita **guardar archivos de forma
persistente** entre reinicios (la base de datos es un archivo SQLite —
`torneos.db` — así que si la plataforma borra el disco en cada despliegue, hay
que migrar a una base de datos administrada aparte, por ejemplo el plan
gratuito de Neon o Supabase para PostgreSQL), y (2) que permita programar
tareas periódicas (cron) si quieres que los recordatorios de correo salgan solos.

## Qué falta para producción (siguientes pasos)

- Pantalla para editar el correo de un capitán ya creado (hoy solo se asigna
  al momento de crear el equipo).
- Fases eliminatorias (cuartos/semis/final) — el modelo ya lo soporta vía `Fase`,
  falta la vista de "bracket".
- Migrar de SQLite a PostgreSQL para producción (cambiar `DATABASE_URL`),
  sobre todo si el hospedaje elegido no persiste archivos entre despliegues.
- Subida real de fotos/escudos (hoy son campos de URL), autenticación más robusta.


## Estructura

Ver el archivo de arquitectura discutido en la conversación: modelos en
`app/models/`, lógica de negocio en `app/services/`, rutas en `app/routes/`
separadas por audiencia (`public`, `admin`, `capitan`).
