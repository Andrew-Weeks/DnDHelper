from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_user, logout_user, login_required
from models import db, User, get_or_create_default_character

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')
        role     = request.form.get('role', 'player')
        dm_secret = request.form.get('dm_secret', '')
        dev_secret = request.form.get('dev_secret', '')

        # Validation
        if len(username) < 3 or len(username) > 80:
            flash('Username must be between 3 and 80 characters.', 'error')
            return render_template('auth/register.html')

        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
            return render_template('auth/register.html')

        if password != confirm:
            flash('Passwords do not match.', 'error')
            return render_template('auth/register.html')

        if role not in ('player', 'dm', 'developer'):
            role = 'player'

        if role == 'dm':
            required_secret = current_app.config.get('DM_SECRET')
            if required_secret and dm_secret != required_secret:
                flash('Invalid DM secret passphrase.', 'error')
                return render_template('auth/register.html')

        if role == 'developer':
            required_secret = current_app.config.get('DEV_SECRET')
            if required_secret and dev_secret != required_secret:
                flash('Invalid developer secret passphrase.', 'error')
                return render_template('auth/register.html')

        if User.query.filter_by(username=username).first():
            flash('Username already taken.', 'error')
            return render_template('auth/register.html')

        user = User(username=username, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        get_or_create_default_character(user)
        db.session.commit()

        flash('Account created! Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username    = request.form.get('username', '').strip()
        password    = request.form.get('password', '')
        remember_me = bool(request.form.get('remember_me'))

        user = User.query.filter_by(username=username).first()
        if not user or not user.check_password(password):
            flash('Invalid username or password.', 'error')
            return render_template('auth/login.html')

        login_user(user, remember=remember_me)

        next_page = request.args.get('next')
        return redirect(next_page or url_for('main.dashboard'))

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('main.index'))
