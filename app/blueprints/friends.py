from flask import Blueprint, render_template, redirect, url_for, request, flash, abort
from flask_login import login_required, current_user
from app.models import db, Friendship, User

friends_bp = Blueprint('friends', __name__, url_prefix='/friends')


# ---------------------------------------------------------------------------
# View friends and pending requests
# ---------------------------------------------------------------------------

@friends_bp.route('/')
@login_required
def index():
    """Display current friends and pending friend requests."""

    # Get accepted friendships (both directions)
    sent_friendships = Friendship.query.filter_by(
        user_id=current_user.id,
        status='accepted'
    ).all()
    received_friendships = Friendship.query.filter_by(
        friend_id=current_user.id,
        status='accepted'
    ).all()

    friends = []
    for f in sent_friendships:
        friends.append(f.friend)
    for f in received_friendships:
        friends.append(f.user)

    # Get pending friend requests (sent by others to current user)
    pending_requests = Friendship.query.filter_by(
        friend_id=current_user.id,
        status='pending'
    ).all()

    return render_template('friends/index.html',
                           friends=friends,
                           pending_requests=pending_requests)


# ---------------------------------------------------------------------------
# Send a friend request
# ---------------------------------------------------------------------------

@friends_bp.route('/add', methods=['POST'])
@login_required
def add_friend():
    """Send a friend request to another user."""
    target_username = request.form.get('username', '').strip()

    if not target_username:
        flash('Username cannot be empty.', 'error')
        return redirect(url_for('friends.index'))

    target = User.query.filter_by(username=target_username).first()
    if not target:
        flash(f'No user found with username "{target_username}".', 'error')
        return redirect(url_for('friends.index'))

    if target.id == current_user.id:
        flash("You can't send a friend request to yourself.", 'error')
        return redirect(url_for('friends.index'))

    # Check if friendship already exists (in either direction)
    existing = Friendship.query.filter(
        db.or_(
            db.and_(
                Friendship.user_id == current_user.id,
                Friendship.friend_id == target.id
            ),
            db.and_(
                Friendship.user_id == target.id,
                Friendship.friend_id == current_user.id
            )
        )
    ).first()

    if existing:
        if existing.status == 'pending':
            flash(f'Friend request with {target.username} is already pending.', 'error')
        else:
            flash(f'You are already friends with {target.username}.', 'error')
        return redirect(url_for('friends.index'))

    # Create friendship request
    friendship = Friendship(user_id=current_user.id, friend_id=target.id, status='pending')
    db.session.add(friendship)
    db.session.commit()

    flash(f'Friend request sent to {target.username}.', 'success')
    return redirect(url_for('friends.index'))


# ---------------------------------------------------------------------------
# Accept a friend request
# ---------------------------------------------------------------------------

@friends_bp.route('/<int:req_id>/accept', methods=['POST'])
@login_required
def accept_friend(req_id):
    """Accept an incoming friend request."""
    friendship = db.session.get(Friendship, req_id)

    if not friendship or friendship.friend_id != current_user.id or friendship.status != 'pending':
        abort(403)

    friendship.status = 'accepted'
    db.session.commit()

    flash(f'You are now friends with {friendship.user.username}.', 'success')
    return redirect(url_for('friends.index'))


# ---------------------------------------------------------------------------
# Decline a friend request
# ---------------------------------------------------------------------------

@friends_bp.route('/<int:req_id>/decline', methods=['POST'])
@login_required
def decline_friend(req_id):
    """Decline an incoming friend request."""
    friendship = db.session.get(Friendship, req_id)

    if not friendship or friendship.friend_id != current_user.id or friendship.status != 'pending':
        abort(403)

    db.session.delete(friendship)
    db.session.commit()

    flash(f'Friend request from {friendship.user.username} declined.', 'success')
    return redirect(url_for('friends.index'))


# ---------------------------------------------------------------------------
# Remove a friend
# ---------------------------------------------------------------------------

@friends_bp.route('/<int:friend_id>/remove', methods=['POST'])
@login_required
def remove_friend(friend_id):
    """Remove a friend."""
    # Find friendship in either direction
    friendship = Friendship.query.filter(
        db.or_(
            db.and_(
                Friendship.user_id == current_user.id,
                Friendship.friend_id == friend_id,
                Friendship.status == 'accepted'
            ),
            db.and_(
                Friendship.user_id == friend_id,
                Friendship.friend_id == current_user.id,
                Friendship.status == 'accepted'
            )
        )
    ).first()

    if not friendship:
        abort(403)

    friend_name = friendship.user.username if friendship.user_id != current_user.id else friendship.friend.username
    db.session.delete(friendship)
    db.session.commit()

    flash(f'{friend_name} removed from your friends.', 'success')
    return redirect(url_for('friends.index'))
