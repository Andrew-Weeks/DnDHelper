from functools import wraps

from flask import request, jsonify, current_app
from flask_login import current_user
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from app.blueprints.api import api_bp
from app.extensions import db
from app.models import User

_TOKEN_SALT = "api-token"
_TOKEN_MAX_AGE = 60 * 60 * 24 * 30  # 30 days


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


def generate_token(user_id: int) -> str:
    return _serializer().dumps(user_id, salt=_TOKEN_SALT)


def verify_token(token: str):
    try:
        user_id = _serializer().loads(token, salt=_TOKEN_SALT, max_age=_TOKEN_MAX_AGE)
        return db.session.get(User, user_id)
    except (BadSignature, SignatureExpired):
        return None


def api_login_required(f):
    """Accept either a Flask-Login session cookie or a Bearer token."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_user.is_authenticated:
            return f(*args, **kwargs)
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            user = verify_token(token)
            if user:
                # Temporarily bind the user for this request context
                from flask_login import login_user
                login_user(user)
                return f(*args, **kwargs)
        return jsonify({"error": "Unauthorized"}), 401
    return decorated


@api_bp.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"error": "username and password required"}), 400

    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid credentials"}), 401

    token = generate_token(user.id)
    return jsonify({
        "token": token,
        "user": {"id": user.id, "username": user.username, "role": user.role},
    })
