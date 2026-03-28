from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user

from decorators import role_required
from models import db, Suggestion, User


suggestions_bp = Blueprint('suggestions', __name__, url_prefix='/suggestions')


def _pick_developer(exclude_user_id=None):
    query = User.query.filter_by(role='developer').order_by(User.id.asc())
    if exclude_user_id is not None:
        query = query.filter(User.id != exclude_user_id)
    return query.first()


@suggestions_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        details = request.form.get('details', '').strip()

        if len(title) < 5 or len(title) > 120:
            flash('Suggestion title must be between 5 and 120 characters.', 'error')
            return redirect(url_for('suggestions.index'))

        if len(details) < 10:
            flash('Suggestion details must be at least 10 characters.', 'error')
            return redirect(url_for('suggestions.index'))

        assignee = _pick_developer(exclude_user_id=current_user.id)
        if assignee is None and current_user.is_developer():
            assignee = current_user

        suggestion = Suggestion(
            submitted_by_user_id=current_user.id,
            assigned_dev_user_id=assignee.id if assignee else None,
            title=title,
            details=details,
        )
        db.session.add(suggestion)
        db.session.commit()

        if assignee:
            flash(f'Suggestion sent to developer user "{assignee.username}".', 'success')
        else:
            flash('Suggestion saved, but no developer account exists yet to assign it.', 'error')

        return redirect(url_for('suggestions.index'))

    my_suggestions = (Suggestion.query
                      .filter_by(submitted_by_user_id=current_user.id)
                      .order_by(Suggestion.created_at.desc())
                      .all())
    return render_template('suggestions/index.html', my_suggestions=my_suggestions)


@suggestions_bp.route('/inbox')
@login_required
@role_required('developer')
def inbox():
    suggestions = (Suggestion.query
                   .order_by(Suggestion.status.asc(), Suggestion.created_at.desc())
                   .all())
    return render_template('suggestions/inbox.html', suggestions=suggestions)


@suggestions_bp.route('/<int:suggestion_id>/status', methods=['POST'])
@login_required
@role_required('developer')
def update_status(suggestion_id):
    suggestion = db.session.get(Suggestion, suggestion_id)
    if not suggestion:
        flash('Suggestion not found.', 'error')
        return redirect(url_for('suggestions.inbox'))

    new_status = request.form.get('status', '').strip().lower()
    allowed_statuses = {'new', 'reviewing', 'planned', 'done'}
    if new_status not in allowed_statuses:
        flash('Invalid status.', 'error')
        return redirect(url_for('suggestions.inbox'))

    suggestion.status = new_status
    if suggestion.assigned_dev_user_id is None:
        suggestion.assigned_dev_user_id = current_user.id

    db.session.commit()
    flash('Suggestion status updated.', 'success')
    return redirect(url_for('suggestions.inbox'))
