import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def _normalizar_database_url(url):
    """Algunos proveedores (Render, Heroku viejo) todavia dan la URL de
    Postgres con el prefijo 'postgres://', pero SQLAlchemy 1.4+ solo acepta
    'postgresql://'. Aqui se corrige automaticamente para no tener que
    acordarse de eso al configurar la variable de entorno."""
    if url and url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-cambiar-en-produccion")
    SQLALCHEMY_DATABASE_URI = _normalizar_database_url(
        os.environ.get("DATABASE_URL")
    ) or f"sqlite:///{os.path.join(BASE_DIR, 'torneos.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
