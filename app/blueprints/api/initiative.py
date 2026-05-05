import random

from flask import request, jsonify
from flask_login import current_user

from app.blueprints.api import api_bp
from app.blueprints.api.auth import api_login_required
from app.blueprints.initiative_helpers import (
    get_tracker_or_403,
    get_combatant_or_404,
    tracker_to_dict,
    combatant_to_dict,
    sorted_combatants,
)
from app.models import db, InitiativeTracker, InitiativeCombatant


@api_bp.route("/initiative/trackers", methods=["GET"])
@api_login_required
def list_trackers():
    trackers = (InitiativeTracker.query
                .filter_by(user_id=current_user.id)
                .order_by(InitiativeTracker.created_at.desc())
                .all())
    return jsonify([tracker_to_dict(t) for t in trackers])


@api_bp.route("/initiative/trackers", methods=["POST"])
@api_login_required
def create_tracker():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "Combat").strip()[:120] or "Combat"
    tracker = InitiativeTracker(user_id=current_user.id, name=name)
    db.session.add(tracker)
    db.session.commit()
    return jsonify(tracker_to_dict(tracker, include_combatants=True)), 201


@api_bp.route("/initiative/trackers/<int:tracker_id>", methods=["GET"])
@api_login_required
def get_tracker(tracker_id):
    tracker = get_tracker_or_403(tracker_id)
    return jsonify(tracker_to_dict(tracker, include_combatants=True))


@api_bp.route("/initiative/trackers/<int:tracker_id>", methods=["DELETE"])
@api_login_required
def delete_tracker(tracker_id):
    tracker = get_tracker_or_403(tracker_id)
    db.session.delete(tracker)
    db.session.commit()
    return jsonify({"message": f'"{tracker.name}" deleted.'})


@api_bp.route("/initiative/trackers/<int:tracker_id>/combatants", methods=["POST"])
@api_login_required
def add_combatant(tracker_id):
    tracker = get_tracker_or_403(tracker_id)
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    try:
        modifier = int(data.get("modifier", 0))
    except (ValueError, TypeError):
        modifier = 0
    combatant = InitiativeCombatant(tracker_id=tracker.id, name=name[:120], modifier=modifier)
    db.session.add(combatant)
    db.session.commit()
    return jsonify(combatant_to_dict(combatant)), 201


@api_bp.route("/initiative/trackers/<int:tracker_id>/combatants/<int:combatant_id>", methods=["DELETE"])
@api_login_required
def delete_combatant(tracker_id, combatant_id):
    tracker = get_tracker_or_403(tracker_id)
    combatant = get_combatant_or_404(tracker, combatant_id)
    db.session.delete(combatant)
    db.session.commit()
    return jsonify({"message": "deleted"})


@api_bp.route("/initiative/trackers/<int:tracker_id>/roll-all", methods=["POST"])
@api_login_required
def roll_all(tracker_id):
    tracker = get_tracker_or_403(tracker_id)
    for c in tracker.combatants:
        if c.roll is None:
            c.roll = random.randint(1, 20)
    db.session.commit()
    return jsonify(tracker_to_dict(tracker, include_combatants=True))


@api_bp.route("/initiative/trackers/<int:tracker_id>/combatants/<int:combatant_id>/roll", methods=["POST"])
@api_login_required
def roll_combatant(tracker_id, combatant_id):
    tracker = get_tracker_or_403(tracker_id)
    combatant = get_combatant_or_404(tracker, combatant_id)
    combatant.roll = random.randint(1, 20)
    db.session.commit()
    return jsonify(combatant_to_dict(combatant))


@api_bp.route("/initiative/trackers/<int:tracker_id>/combatants/<int:combatant_id>/custom-roll", methods=["POST"])
@api_login_required
def custom_roll(tracker_id, combatant_id):
    tracker = get_tracker_or_403(tracker_id)
    combatant = get_combatant_or_404(tracker, combatant_id)
    data = request.get_json(silent=True) or {}
    try:
        roll = int(data.get("roll", ""))
    except (ValueError, TypeError):
        return jsonify({"error": "roll must be a number"}), 400
    combatant.roll = roll
    db.session.commit()
    return jsonify(combatant_to_dict(combatant))


@api_bp.route("/initiative/trackers/<int:tracker_id>/reset", methods=["POST"])
@api_login_required
def reset_rolls(tracker_id):
    tracker = get_tracker_or_403(tracker_id)
    for c in tracker.combatants:
        c.roll = None
    db.session.commit()
    return jsonify(tracker_to_dict(tracker, include_combatants=True))
