from flask import Blueprint, render_template
from flask_login import login_required
from decorators import role_required

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    return render_template('main/index.html')


@main_bp.route('/dashboard')
@login_required
def dashboard():
    return render_template('main/dashboard.html')


@main_bp.route('/dm')
@login_required
@role_required('dm')
def dm_dashboard():
    return render_template('main/dm_dashboard.html')
