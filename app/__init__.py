import os
from flask import Flask, render_template

from config import Config
from app.extensions import db, login_manager


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Upload paths are relative to the project root (one level above the app package)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app.config['SOUNDBOARD_UPLOAD_ROOT'] = os.path.join(project_root, 'uploads', 'soundboard')
    app.config['SESSION_UPLOAD_ROOT']    = os.path.join(project_root, 'uploads', 'sessions')
    app.config['VOICE_SAMPLE_ROOT']      = os.path.join(project_root, 'uploads', 'voice_samples')

    # Extensions
    db.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        return db.session.get(User, int(user_id))

    # Blueprints
    from app.blueprints.auth import auth_bp
    from app.blueprints.main import main_bp
    from app.blueprints.soundboard import soundboard_bp
    from app.blueprints.campaign import campaign_bp
    from app.blueprints.friends import friends_bp
    from app.blueprints.suggestions import suggestions_bp
    from app.blueprints.initiative import initiative_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(soundboard_bp)
    app.register_blueprint(campaign_bp)
    app.register_blueprint(friends_bp)
    app.register_blueprint(suggestions_bp)
    app.register_blueprint(initiative_bp)

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    with app.app_context():
        from app.models import (
            db as _db,
            ensure_schema_upgrades,
            ensure_default_characters_and_migrate_soundboards,
        )
        _db.create_all()
        ensure_schema_upgrades()
        ensure_default_characters_and_migrate_soundboards(app.config['SOUNDBOARD_UPLOAD_ROOT'])

    return app
