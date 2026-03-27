import os
from flask import Flask, render_template
from flask_login import LoginManager
from models import db, User

app = Flask(__name__)
app.config['SECRET_KEY'] = 'change-me-to-a-random-secret-before-deploying'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///dndhelper.db'

# Optional: require this passphrase when registering as DM.
# Set to None to allow anyone to register as DM.
app.config['DM_SECRET'] = 'dungeon-master'

# Soundboard uploads: stored in <project_root>/uploads/soundboard/<user_id>/
app.config['SOUNDBOARD_UPLOAD_ROOT'] = os.path.join(app.root_path, 'uploads', 'soundboard')
app.config['SESSION_UPLOAD_ROOT']    = os.path.join(app.root_path, 'uploads', 'sessions')
app.config['VOICE_SAMPLE_ROOT']      = os.path.join(app.root_path, 'uploads', 'voice_samples')
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200 MB (session recordings can be large)

# Transcription settings — set via environment variables before running
app.config['WHISPER_MODEL_SIZE'] = os.environ.get('WHISPER_MODEL_SIZE', 'base')
app.config['HF_AUTH_TOKEN']      = os.environ.get('HF_AUTH_TOKEN', '')

db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.errorhandler(403)
def forbidden(e):
    return render_template('errors/403.html'), 403


from auth import auth_bp
from main import main_bp
from soundboard import soundboard_bp
from campaign import campaign_bp

app.register_blueprint(auth_bp)
app.register_blueprint(main_bp)
app.register_blueprint(soundboard_bp)
app.register_blueprint(campaign_bp)

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True, ssl_context=('cert.pem', 'key.pem'))
