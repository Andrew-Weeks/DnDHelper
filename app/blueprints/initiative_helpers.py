from flask import abort
from flask_login import current_user

from app.models import db, InitiativeTracker, InitiativeCombatant


def get_tracker_or_403(tracker_id):
    tracker = db.session.get(InitiativeTracker, tracker_id)
    if not tracker or tracker.user_id != current_user.id:
        abort(403)
    return tracker


def get_combatant_or_404(tracker, combatant_id):
    combatant = db.session.get(InitiativeCombatant, combatant_id)
    if not combatant or combatant.tracker_id != tracker.id:
        abort(404)
    return combatant


def sorted_combatants(combatants):
    """Rolled combatants first (highest total), unrolled at the bottom."""
    def sort_key(c):
        return (1, c.total) if c.total is not None else (0, 0)
    return sorted(combatants, key=sort_key, reverse=True)


def combatant_to_dict(c, rank=None):
    return {
        "id": c.id,
        "name": c.name,
        "modifier": c.modifier,
        "roll": c.roll,
        "total": c.total,
        "rank": rank,
    }


def tracker_to_dict(tracker, include_combatants=False):
    d = {
        "id": tracker.id,
        "name": tracker.name,
        "created_at": tracker.created_at.isoformat(),
        "combatant_count": len(tracker.combatants),
    }
    if include_combatants:
        ranked = sorted_combatants(tracker.combatants)
        d["combatants"] = [
            combatant_to_dict(c, rank=i + 1 if c.roll is not None else None)
            for i, c in enumerate(ranked)
        ]
    return d
