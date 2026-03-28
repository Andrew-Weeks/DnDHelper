import os
import shutil
import uuid

from flask import (Blueprint, render_template, redirect, url_for, request,
                   flash, current_app, send_from_directory, abort)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from models import (
    db,
    Character,
    Friendship,
    ShareRequest,
    SoundboardItem,
    User,
    get_or_create_default_character,
)

soundboard_bp = Blueprint('soundboard', __name__, url_prefix='/soundboard')

ALLOWED_EXTENSIONS = {'mp3', 'wav', 'ogg', 'webm', 'm4a', 'aac', 'mp4'}


def _character_upload_dir(character_id):
    """Return (and create if needed) the upload directory for a character."""
    upload_root = current_app.config['SOUNDBOARD_UPLOAD_ROOT']
    path = os.path.join(upload_root, 'characters', str(character_id))
    os.makedirs(path, exist_ok=True)
    return path


def _legacy_user_upload_dir(user_id):
    upload_root = current_app.config['SOUNDBOARD_UPLOAD_ROOT']
    path = os.path.join(upload_root, str(user_id))
    os.makedirs(path, exist_ok=True)
    return path


def _allowed(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _list_characters_for_current_user():
    characters = (Character.query
                  .filter_by(user_id=current_user.id)
                  .order_by(Character.is_default.desc(), Character.created_at.asc(), Character.id.asc())
                  .all())
    if characters:
        return characters

    character = get_or_create_default_character(current_user)
    db.session.commit()
    return [character]


def _select_active_character(characters, character_id=None):
    if character_id is not None:
        for character in characters:
            if character.id == character_id:
                return character
        abort(403)

    for character in characters:
        if character.is_default:
            return character
    return characters[0]


def _owned_character(character_id):
    character = db.session.get(Character, character_id)
    if not character or character.user_id != current_user.id:
        abort(403)
    return character


def _posted_character():
    character_id = request.form.get('character_id', type=int)
    if character_id:
        return _owned_character(character_id)
    return _select_active_character(_list_characters_for_current_user())


def _item_storage_path(item):
    candidate_paths = []
    if item.character_id:
        candidate_paths.append(os.path.join(_character_upload_dir(item.character_id), item.filename))
    candidate_paths.append(os.path.join(_legacy_user_upload_dir(item.user_id), item.filename))

    for path in candidate_paths:
        if os.path.exists(path):
            return path
    return candidate_paths[0]


def _own_item(item_id):
    """Return the SoundboardItem if it belongs to current_user, else abort 403."""
    item = db.session.get(SoundboardItem, item_id)
    if not item or item.user_id != current_user.id:
        abort(403)
    return item


# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------

@soundboard_bp.route('/')
@login_required
def index():
    characters = _list_characters_for_current_user()
    active_character = _select_active_character(
        characters,
        request.args.get('character_id', type=int),
    )

    sounds = (SoundboardItem.query
              .filter_by(user_id=current_user.id, character_id=active_character.id)
              .order_by(SoundboardItem.created_at.desc())
              .all())
    pending_requests = (ShareRequest.query
                        .filter_by(to_user_id=current_user.id, status='pending')
                        .order_by(ShareRequest.created_at.desc())
                        .all())
    
    # Get user's friends (both directions)
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
    
    return render_template('soundboard/index.html',
                           characters=characters,
                           active_character=active_character,
                           sounds=sounds,
                           pending_requests=pending_requests,
                           friends=friends)


@soundboard_bp.route('/characters', methods=['POST'])
@login_required
def create_character():
    name = request.form.get('character_name', '').strip()

    if len(name) < 2 or len(name) > 80:
        flash('Character name must be between 2 and 80 characters.', 'error')
        return redirect(url_for('soundboard.index'))

    existing = Character.query.filter_by(user_id=current_user.id, name=name).first()
    if existing:
        flash('You already have a character with that name.', 'error')
        return redirect(url_for('soundboard.index', character_id=existing.id))

    character = Character(user_id=current_user.id, name=name)
    db.session.add(character)
    db.session.commit()

    flash(f'Character "{name}" created.', 'success')
    return redirect(url_for('soundboard.index', character_id=character.id))


@soundboard_bp.route('/import-account', methods=['POST'])
@login_required
def import_legacy_account():
    legacy_username = request.form.get('legacy_username', '').strip()
    legacy_password = request.form.get('legacy_password', '')
    character_name = request.form.get('character_name', '').strip()

    if not legacy_username or not legacy_password:
        flash('Enter the old account username and password to import it.', 'error')
        return redirect(url_for('soundboard.index'))

    legacy_user = User.query.filter_by(username=legacy_username).first()
    if not legacy_user or not legacy_user.check_password(legacy_password):
        flash('Old account credentials were not valid.', 'error')
        return redirect(url_for('soundboard.index'))

    if legacy_user.id == current_user.id:
        flash('You are already signed into that account.', 'error')
        return redirect(url_for('soundboard.index'))

    character_name = character_name or legacy_user.username
    if len(character_name) < 2 or len(character_name) > 80:
        flash('Imported character name must be between 2 and 80 characters.', 'error')
        return redirect(url_for('soundboard.index'))

    existing_character = Character.query.filter_by(user_id=current_user.id, name=character_name).first()
    if existing_character:
        flash('Choose a different character name before importing.', 'error')
        return redirect(url_for('soundboard.index', character_id=existing_character.id))

    source_items = (SoundboardItem.query
                    .filter_by(user_id=legacy_user.id)
                    .order_by(SoundboardItem.created_at.asc(), SoundboardItem.id.asc())
                    .all())
    if not source_items:
        flash(f'{legacy_user.username} does not have any sounds to import.', 'error')
        return redirect(url_for('soundboard.index'))

    character = Character(user_id=current_user.id, name=character_name)
    db.session.add(character)
    db.session.flush()

    dest_dir = _character_upload_dir(character.id)
    imported_count = 0
    for item in source_items:
        source_path = _item_storage_path(item)
        if not os.path.exists(source_path):
            continue

        ext = item.filename.rsplit('.', 1)[1].lower()
        new_filename = f'{uuid.uuid4().hex}.{ext}'
        shutil.copy2(source_path, os.path.join(dest_dir, new_filename))
        db.session.add(SoundboardItem(
            user_id=current_user.id,
            character_id=character.id,
            name=item.name,
            filename=new_filename,
        ))
        imported_count += 1

    if imported_count == 0:
        db.session.rollback()
        flash('No sound files could be copied from that account.', 'error')
        return redirect(url_for('soundboard.index'))

    db.session.commit()
    flash(f'Imported {imported_count} sound(s) from {legacy_user.username} into {character.name}.', 'success')
    return redirect(url_for('soundboard.index', character_id=character.id))


# ---------------------------------------------------------------------------
# Upload audio file(s)
# ---------------------------------------------------------------------------

@soundboard_bp.route('/upload', methods=['POST'])
@login_required
def upload():
    character = _posted_character()
    files = request.files.getlist('audio_files')
    if not files or all(f.filename == '' for f in files):
        flash('No files selected.', 'error')
        return redirect(url_for('soundboard.index', character_id=character.id))

    saved = 0
    for f in files:
        if f.filename == '':
            continue
        if not _allowed(f.filename):
            flash(f'"{f.filename}" is not a supported audio format.', 'error')
            continue

        ext = f.filename.rsplit('.', 1)[1].lower()
        unique_name = f'{uuid.uuid4().hex}.{ext}'
        dest_dir = _character_upload_dir(character.id)
        f.save(os.path.join(dest_dir, unique_name))

        # Use the provided display name or fall back to the original filename
        display_name = request.form.get(f'name_{f.filename}', '').strip()
        if not display_name:
            display_name = os.path.splitext(secure_filename(f.filename))[0]

        item = SoundboardItem(user_id=current_user.id,
                      character_id=character.id,
                      name=display_name,
                      filename=unique_name)
        db.session.add(item)
        saved += 1

    if saved:
        db.session.commit()
        flash(f'{saved} sound(s) added to {character.name}.', 'success')
    return redirect(url_for('soundboard.index', character_id=character.id))


# ---------------------------------------------------------------------------
# Save a browser recording
# ---------------------------------------------------------------------------

@soundboard_bp.route('/record', methods=['POST'])
@login_required
def save_recording():
    character = _posted_character()
    audio_blob = request.files.get('audio_blob')
    name = request.form.get('name', '').strip()

    if not audio_blob:
        flash('No recording received.', 'error')
        return redirect(url_for('soundboard.index', character_id=character.id))
    if not name:
        flash('Please give the recording a name.', 'error')
        return redirect(url_for('soundboard.index', character_id=character.id))

    # Detect file extension from the uploaded filename (iOS sends .mp4, others .webm)
    uploaded_name = audio_blob.filename or 'recording.webm'
    ext = uploaded_name.rsplit('.', 1)[-1].lower()
    if ext not in {'webm', 'mp4', 'm4a', 'ogg', 'wav', 'aac'}:
        ext = 'webm'
    unique_name = f'{uuid.uuid4().hex}.{ext}'
    dest_dir = _character_upload_dir(character.id)
    audio_blob.save(os.path.join(dest_dir, unique_name))

    item = SoundboardItem(user_id=current_user.id,
                          character_id=character.id,
                          name=name,
                          filename=unique_name)
    db.session.add(item)
    db.session.commit()

    flash(f'"{name}" saved to {character.name}.', 'success')
    return redirect(url_for('soundboard.index', character_id=character.id))


# ---------------------------------------------------------------------------
# Serve audio for playback
# ---------------------------------------------------------------------------

@soundboard_bp.route('/play/<int:item_id>')
@login_required
def play(item_id):
    item = _own_item(item_id)
    dest_dir = os.path.dirname(_item_storage_path(item))
    return send_from_directory(dest_dir, item.filename)


# ---------------------------------------------------------------------------
# Download audio
# ---------------------------------------------------------------------------

@soundboard_bp.route('/download/<int:item_id>')
@login_required
def download(item_id):
    item = _own_item(item_id)
    dest_dir = os.path.dirname(_item_storage_path(item))
    ext = item.filename.rsplit('.', 1)[1]
    download_name = f'{secure_filename(item.name)}.{ext}'
    return send_from_directory(dest_dir, item.filename,
                               as_attachment=True,
                               download_name=download_name)


# ---------------------------------------------------------------------------
# Delete a sound
# ---------------------------------------------------------------------------

@soundboard_bp.route('/delete/<int:item_id>', methods=['POST'])
@login_required
def delete(item_id):
    item = _own_item(item_id)
    file_path = _item_storage_path(item)
    redirect_character_id = request.form.get('character_id', type=int) or item.character_id

    # Remove pending share requests for this item
    ShareRequest.query.filter_by(soundboard_item_id=item.id).delete()
    db.session.delete(item)
    db.session.commit()

    if os.path.exists(file_path):
        os.remove(file_path)

    flash(f'"{item.name}" deleted.', 'success')
    return redirect(url_for('soundboard.index', character_id=redirect_character_id))


# ---------------------------------------------------------------------------
# Rename a sound
# ---------------------------------------------------------------------------

@soundboard_bp.route('/rename/<int:item_id>', methods=['POST'])
@login_required
def rename(item_id):
    item = _own_item(item_id)
    new_name = request.form.get('name', '').strip()
    redirect_character_id = request.form.get('character_id', type=int) or item.character_id
    if not new_name:
        flash('Name cannot be empty.', 'error')
        return redirect(url_for('soundboard.index', character_id=redirect_character_id))
    item.name = new_name
    db.session.commit()
    flash('Sound renamed.', 'success')
    return redirect(url_for('soundboard.index', character_id=redirect_character_id))


# ---------------------------------------------------------------------------
# Share a sound
# ---------------------------------------------------------------------------

@soundboard_bp.route('/share', methods=['POST'])
@login_required
def share():
    item_id = request.form.get('item_id', type=int)
    redirect_character_id = request.form.get('character_id', type=int)

    # Get friend IDs (from checkboxes) or a manually typed username
    friend_id_list = request.form.getlist('friend_id')
    target_username = request.form.get('target_username', '').strip()

    if not item_id:
        flash('Missing sound ID.', 'error')
        return redirect(url_for('soundboard.index', character_id=redirect_character_id))

    item = _own_item(item_id)
    targets = []

    # Handle friend checkboxes
    if friend_id_list:
        for fid in friend_id_list:
            if not fid.isdigit():
                continue
            target = db.session.get(User, int(fid))
            if target and target.id != current_user.id:
                targets.append(target)
        if not targets:
            flash('No valid friends selected.', 'error')
            return redirect(url_for('soundboard.index', character_id=redirect_character_id or item.character_id))
    # Handle typed username
    elif target_username:
        target = User.query.filter_by(username=target_username).first()
        if not target:
            flash(f'No user found with username "{target_username}".', 'error')
            return redirect(url_for('soundboard.index', character_id=redirect_character_id or item.character_id))
        if target.id == current_user.id:
            flash("You can't share a sound with yourself.", 'error')
            return redirect(url_for('soundboard.index', character_id=redirect_character_id or item.character_id))
        targets = [target]
    else:
        flash('Select friends or enter a username.', 'error')
        return redirect(url_for('soundboard.index', character_id=redirect_character_id or item.character_id))

    if not targets:
        flash('No valid targets to share with.', 'error')
        return redirect(url_for('soundboard.index', character_id=redirect_character_id or item.character_id))

    # Create share requests for each target
    shared_count = 0
    for target in targets:
        # Don't create a duplicate pending request
        existing = ShareRequest.query.filter_by(
            from_user_id=current_user.id,
            to_user_id=target.id,
            soundboard_item_id=item.id,
            status='pending'
        ).first()
        if existing:
            continue
        
        req = ShareRequest(from_user_id=current_user.id,
                           to_user_id=target.id,
                           soundboard_item_id=item.id)
        db.session.add(req)
        shared_count += 1
    
    if shared_count > 0:
        db.session.commit()
        if shared_count == 1:
            flash(f'Share request sent to {targets[0].username}.', 'success')
        else:
            flash(f'Share request sent to {shared_count} friends.', 'success')
    else:
        flash('No new share requests created (may already be sent).', 'info')
    
    return redirect(url_for('soundboard.index', character_id=redirect_character_id or item.character_id))


# ---------------------------------------------------------------------------
# Accept a share request
# ---------------------------------------------------------------------------

@soundboard_bp.route('/share/<int:req_id>/accept', methods=['POST'])
@login_required
def accept_share(req_id):
    character = _posted_character()
    share_req = db.session.get(ShareRequest, req_id)
    if not share_req or share_req.to_user_id != current_user.id or share_req.status != 'pending':
        abort(403)

    original_item = share_req.soundboard_item
    src_path = _item_storage_path(original_item)
    dest_dir = _character_upload_dir(character.id)

    ext = original_item.filename.rsplit('.', 1)[1]
    new_filename = f'{uuid.uuid4().hex}.{ext}'

    shutil.copy2(src_path, os.path.join(dest_dir, new_filename))

    new_item = SoundboardItem(user_id=current_user.id,
                              character_id=character.id,
                              name=original_item.name,
                              filename=new_filename)
    db.session.add(new_item)
    share_req.status = 'accepted'
    db.session.commit()

    flash(f'"{original_item.name}" added to {character.name}.', 'success')
    return redirect(url_for('soundboard.index', character_id=character.id))


# ---------------------------------------------------------------------------
# Decline a share request
# ---------------------------------------------------------------------------

@soundboard_bp.route('/share/<int:req_id>/decline', methods=['POST'])
@login_required
def decline_share(req_id):
    redirect_character_id = request.form.get('character_id', type=int)
    share_req = db.session.get(ShareRequest, req_id)
    if not share_req or share_req.to_user_id != current_user.id or share_req.status != 'pending':
        abort(403)
    share_req.status = 'declined'
    db.session.commit()
    flash('Share request declined.', 'success')
    return redirect(url_for('soundboard.index', character_id=redirect_character_id))
