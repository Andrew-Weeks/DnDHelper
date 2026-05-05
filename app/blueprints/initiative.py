import random

from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required

from app.models import db, InitiativeTracker, InitiativeCombatant
from app.blueprints.initiative_helpers import (
    get_tracker_or_403 as _get_tracker_or_403,
    get_combatant_or_404 as _get_combatant_or_404,
    sorted_combatants as _sorted_combatants,
)

initiative_bp = Blueprint('initiative', __name__, url_prefix='/initiative')


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@initiative_bp.route('/')
@login_required
def index():
    trackers = (InitiativeTracker.query
                .filter_by(user_id=current_user.id)
                .order_by(InitiativeTracker.created_at.desc())
                .all())
    return render_template('initiative/index.html', trackers=trackers)


@initiative_bp.route('/new', methods=['POST'])
@login_required
def create():
    name = request.form.get('name', '').strip() or 'Combat'
    tracker = InitiativeTracker(user_id=current_user.id, name=name[:120])
    db.session.add(tracker)
    db.session.commit()
    return redirect(url_for('initiative.tracker_view', tracker_id=tracker.id))


@initiative_bp.route('/<int:tracker_id>')
@login_required
def tracker_view(tracker_id):
    tracker = _get_tracker_or_403(tracker_id)
    combatants = _sorted_combatants(tracker.combatants)
    return render_template('initiative/tracker.html', tracker=tracker, combatants=combatants)


@initiative_bp.route('/<int:tracker_id>/delete', methods=['POST'])
@login_required
def delete_tracker(tracker_id):
    tracker = _get_tracker_or_403(tracker_id)
    db.session.delete(tracker)
    db.session.commit()
    flash(f'"{tracker.name}" deleted.', 'info')
    return redirect(url_for('initiative.index'))


@initiative_bp.route('/<int:tracker_id>/combatant', methods=['POST'])
@login_required
def add_combatant(tracker_id):
    tracker = _get_tracker_or_403(tracker_id)
    name = request.form.get('name', '').strip()
    if not name:
        flash('Combatant name is required.', 'error')
        return redirect(url_for('initiative.tracker_view', tracker_id=tracker_id))
    try:
        modifier = int(request.form.get('modifier', 0))
    except (ValueError, TypeError):
        modifier = 0
    combatant = InitiativeCombatant(tracker_id=tracker.id, name=name[:120], modifier=modifier)
    db.session.add(combatant)
    db.session.commit()
    return redirect(url_for('initiative.tracker_view', tracker_id=tracker_id))


@initiative_bp.route('/<int:tracker_id>/combatant/<int:combatant_id>/delete', methods=['POST'])
@login_required
def delete_combatant(tracker_id, combatant_id):
    tracker = _get_tracker_or_403(tracker_id)
    combatant = _get_combatant_or_404(tracker, combatant_id)
    db.session.delete(combatant)
    db.session.commit()
    return redirect(url_for('initiative.tracker_view', tracker_id=tracker_id))


@initiative_bp.route('/<int:tracker_id>/roll-all', methods=['POST'])
@login_required
def roll_all(tracker_id):
    tracker = _get_tracker_or_403(tracker_id)
    for c in tracker.combatants:
        if c.roll is None:
            c.roll = random.randint(1, 20)
    db.session.commit()
    return redirect(url_for('initiative.tracker_view', tracker_id=tracker_id))


@initiative_bp.route('/<int:tracker_id>/combatant/<int:combatant_id>/roll', methods=['POST'])
@login_required
def roll_combatant(tracker_id, combatant_id):
    tracker = _get_tracker_or_403(tracker_id)
    combatant = _get_combatant_or_404(tracker, combatant_id)
    combatant.roll = random.randint(1, 20)
    db.session.commit()
    return redirect(url_for('initiative.tracker_view', tracker_id=tracker_id))


@initiative_bp.route('/<int:tracker_id>/combatant/<int:combatant_id>/custom-roll', methods=['POST'])
@login_required
def custom_roll(tracker_id, combatant_id):
    tracker = _get_tracker_or_403(tracker_id)
    combatant = _get_combatant_or_404(tracker, combatant_id)
    try:
        roll = int(request.form.get('roll', ''))
    except (ValueError, TypeError):
        flash('Roll must be a number.', 'error')
        return redirect(url_for('initiative.tracker_view', tracker_id=tracker_id))
    combatant.roll = roll
    db.session.commit()
    return redirect(url_for('initiative.tracker_view', tracker_id=tracker_id))


@initiative_bp.route('/<int:tracker_id>/reset', methods=['POST'])
@login_required
def reset_rolls(tracker_id):
    tracker = _get_tracker_or_403(tracker_id)
    for c in tracker.combatants:
        c.roll = None
    db.session.commit()
    return redirect(url_for('initiative.tracker_view', tracker_id=tracker_id))
