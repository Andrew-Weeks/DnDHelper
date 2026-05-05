from flask import Blueprint

api_bp = Blueprint('api', __name__, url_prefix='/api')

from app.blueprints.api import auth, initiative  # noqa: E402, F401
