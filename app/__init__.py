from flask import Flask
from config import Config
from app.extensions import db, login_manager, migrate


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    login_manager.login_view = "admin.login"
    login_manager.login_message = "Inicia sesión para continuar."

    from app.models import Usuario

    @login_manager.user_loader
    def load_user(user_id):
        return Usuario.query.get(int(user_id))

    from app.routes.public import public_bp
    from app.routes.admin import admin_bp
    from app.routes.capitan import capitan_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(capitan_bp, url_prefix="/capitan")

    from app.cli import registrar_comandos_cli
    registrar_comandos_cli(app)

    @app.context_processor
    def inject_globals():
        from app.models import Organizacion
        org = Organizacion.query.first()
        return {"organizacion": org}

    return app
