import os
import uuid
import threading

from flask import (Blueprint, render_template, redirect, url_for, request,
                   flash, current_app, abort, jsonify, send_from_directory)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app.models import (db, User, Campaign, CampaignMember, CampaignInvite,
                        Session, TranscriptSegment, VoiceSample, SessionAnalysis)
from app.services.analysis import ANALYSIS_TYPES
from app.decorators import role_required

campaign_bp = Blueprint('campaign', __name__, url_prefix='/campaign')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _session_upload_dir(campaign_id):
    root = current_app.config['SESSION_UPLOAD_ROOT']
    path = os.path.join(root, str(campaign_id))
    os.makedirs(path, exist_ok=True)
    return path


def _voice_sample_dir(campaign_id):
    root = current_app.config['VOICE_SAMPLE_ROOT']
    path = os.path.join(root, str(campaign_id))
    os.makedirs(path, exist_ok=True)
    return path


def _is_campaign_accessible(campaign):
    """Return True if current_user is the DM, a member, or a developer."""
    if current_user.is_developer():
        return True
    if campaign.dm_id == current_user.id:
        return True
    return CampaignMember.query.filter_by(
        campaign_id=campaign.id, user_id=current_user.id
    ).first() is not None


def _is_campaign_dm(campaign):
    """Return True if current_user is the DM of this campaign or a developer."""
    return campaign.dm_id == current_user.id or current_user.is_developer()


def _get_campaign_or_403(campaign_id):
    campaign = db.session.get(Campaign, campaign_id)
    if not campaign or not _is_campaign_accessible(campaign):
        abort(403)
    return campaign


# ---------------------------------------------------------------------------
# Campaign list
# ---------------------------------------------------------------------------

@campaign_bp.route('/')
@login_required
def campaign_list():
    if current_user.is_dm():
        campaigns = Campaign.query.filter_by(dm_id=current_user.id).order_by(Campaign.created_at.desc()).all()
        pending_invites = []
    else:
        memberships = CampaignMember.query.filter_by(user_id=current_user.id).all()
        campaigns = [m.campaign for m in memberships]
        pending_invites = (CampaignInvite.query
                           .filter_by(to_user_id=current_user.id, status='pending')
                           .all())
    return render_template('campaign/list.html',
                           campaigns=campaigns,
                           pending_invites=pending_invites)


# ---------------------------------------------------------------------------
# Create campaign (DM only)
# ---------------------------------------------------------------------------

@campaign_bp.route('/create', methods=['GET', 'POST'])
@login_required
@role_required('dm')
def campaign_create():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Campaign name is required.', 'error')
            return redirect(url_for('campaign.campaign_create'))
        c = Campaign(name=name, dm_id=current_user.id)
        db.session.add(c)
        db.session.commit()
        flash(f'Campaign "{name}" created!', 'success')
        return redirect(url_for('campaign.campaign_view', campaign_id=c.id))
    return render_template('campaign/create.html')


# ---------------------------------------------------------------------------
# Campaign detail
# ---------------------------------------------------------------------------

@campaign_bp.route('/<int:campaign_id>')
@login_required
def campaign_view(campaign_id):
    campaign = _get_campaign_or_403(campaign_id)
    members = CampaignMember.query.filter_by(campaign_id=campaign.id).all()
    pending_invites = CampaignInvite.query.filter_by(
        campaign_id=campaign.id, status='pending'
    ).all()
    sessions = (Session.query
                .filter_by(campaign_id=campaign.id)
                .order_by(Session.created_at.desc())
                .all())

    # Voice sample for current player
    my_voice_sample = None
    if not current_user.is_dm():
        my_voice_sample = VoiceSample.query.filter_by(
            user_id=current_user.id, campaign_id=campaign.id
        ).first()

    return render_template('campaign/view.html',
                           campaign=campaign,
                           members=members,
                           pending_invites=pending_invites,
                           sessions=sessions,
                           my_voice_sample=my_voice_sample)


# ---------------------------------------------------------------------------
# Invite a player (DM only)
# ---------------------------------------------------------------------------

@campaign_bp.route('/<int:campaign_id>/invite', methods=['POST'])
@login_required
@role_required('dm')
def campaign_invite(campaign_id):
    campaign = db.session.get(Campaign, campaign_id)
    if not campaign or not _is_campaign_dm(campaign):
        abort(403)

    username = request.form.get('username', '').strip()
    target = User.query.filter_by(username=username).first()
    if not target:
        flash(f'No user found with username "{username}".', 'error')
        return redirect(url_for('campaign.campaign_view', campaign_id=campaign_id))
    if target.role != 'player':
        flash('Only players can be invited to a campaign.', 'error')
        return redirect(url_for('campaign.campaign_view', campaign_id=campaign_id))

    already_member = CampaignMember.query.filter_by(
        campaign_id=campaign_id, user_id=target.id
    ).first()
    if already_member:
        flash(f'{target.username} is already in this campaign.', 'error')
        return redirect(url_for('campaign.campaign_view', campaign_id=campaign_id))

    pending = CampaignInvite.query.filter_by(
        campaign_id=campaign_id, to_user_id=target.id, status='pending'
    ).first()
    if pending:
        flash(f'An invite is already pending for {target.username}.', 'error')
        return redirect(url_for('campaign.campaign_view', campaign_id=campaign_id))

    invite = CampaignInvite(campaign_id=campaign_id, to_user_id=target.id)
    db.session.add(invite)
    db.session.commit()
    flash(f'Invite sent to {target.username}.', 'success')
    return redirect(url_for('campaign.campaign_view', campaign_id=campaign_id))


# ---------------------------------------------------------------------------
# Accept / decline invite (player)
# ---------------------------------------------------------------------------

@campaign_bp.route('/invite/<int:invite_id>/accept', methods=['POST'])
@login_required
def accept_invite(invite_id):
    invite = db.session.get(CampaignInvite, invite_id)
    if not invite or invite.to_user_id != current_user.id or invite.status != 'pending':
        abort(403)
    invite.status = 'accepted'
    member = CampaignMember(campaign_id=invite.campaign_id, user_id=current_user.id)
    db.session.add(member)
    db.session.commit()
    flash(f'You joined "{invite.campaign.name}"!', 'success')
    return redirect(url_for('campaign.campaign_list'))


@campaign_bp.route('/invite/<int:invite_id>/decline', methods=['POST'])
@login_required
def decline_invite(invite_id):
    invite = db.session.get(CampaignInvite, invite_id)
    if not invite or invite.to_user_id != current_user.id or invite.status != 'pending':
        abort(403)
    invite.status = 'declined'
    db.session.commit()
    flash('Invite declined.', 'success')
    return redirect(url_for('campaign.campaign_list'))


# ---------------------------------------------------------------------------
# Remove member (DM only)
# ---------------------------------------------------------------------------

@campaign_bp.route('/<int:campaign_id>/remove/<int:user_id>', methods=['POST'])
@login_required
@role_required('dm')
def remove_member(campaign_id, user_id):
    campaign = db.session.get(Campaign, campaign_id)
    if not campaign or not _is_campaign_dm(campaign):
        abort(403)
    member = CampaignMember.query.filter_by(
        campaign_id=campaign_id, user_id=user_id
    ).first_or_404()
    db.session.delete(member)
    db.session.commit()
    flash('Player removed from campaign.', 'success')
    return redirect(url_for('campaign.campaign_view', campaign_id=campaign_id))


# ---------------------------------------------------------------------------
# Record / upload new session (DM only)
# ---------------------------------------------------------------------------

_ALLOWED_AUDIO_EXTENSIONS = {'.webm', '.mp3', '.wav', '.m4a', '.ogg', '.flac', '.aac', '.mp4'}


def _allowed_audio(filename):
    ext = os.path.splitext(filename)[1].lower()
    return ext in _ALLOWED_AUDIO_EXTENSIONS


@campaign_bp.route('/<int:campaign_id>/session/new', methods=['GET', 'POST'])
@login_required
@role_required('dm')
def session_new(campaign_id):
    campaign = db.session.get(Campaign, campaign_id)
    if not campaign or not _is_campaign_dm(campaign):
        abort(403)

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash('Please give the session a title.', 'error')
            return redirect(url_for('campaign.session_new', campaign_id=campaign_id))

        source = request.form.get('source', 'record')  # 'record' or 'upload'
        dest_dir = _session_upload_dir(campaign_id)

        if source == 'upload':
            audio_file = request.files.get('audio_file')
            if not audio_file or not audio_file.filename:
                flash('No file selected.', 'error')
                return redirect(url_for('campaign.session_new', campaign_id=campaign_id))
            original_name = secure_filename(audio_file.filename)
            if not _allowed_audio(original_name):
                flash('Unsupported file type. Allowed: mp3, wav, m4a, ogg, flac, aac, mp4, webm.', 'error')
                return redirect(url_for('campaign.session_new', campaign_id=campaign_id))
            ext = os.path.splitext(original_name)[1].lower()
            filename = f'{uuid.uuid4().hex}{ext}'
            audio_file.save(os.path.join(dest_dir, filename))
        else:
            audio_blob = request.files.get('audio_blob')
            if not audio_blob:
                flash('No audio received.', 'error')
                return redirect(url_for('campaign.session_new', campaign_id=campaign_id))
            filename = f'{uuid.uuid4().hex}.webm'
            audio_blob.save(os.path.join(dest_dir, filename))

        sess = Session(campaign_id=campaign_id, title=title,
                       audio_filename=filename, status='uploaded')
        db.session.add(sess)
        db.session.commit()
        flash(f'Session "{title}" saved. You can now process it for transcription.', 'success')
        return redirect(url_for('campaign.session_view',
                                campaign_id=campaign_id, session_id=sess.id))

    return render_template('campaign/session_new.html', campaign=campaign)


# ---------------------------------------------------------------------------
# Session detail
# ---------------------------------------------------------------------------

@campaign_bp.route('/<int:campaign_id>/session/<int:session_id>')
@login_required
def session_view(campaign_id, session_id):
    campaign = _get_campaign_or_403(campaign_id)
    sess = db.session.get(Session, session_id)
    if not sess or sess.campaign_id != campaign_id:
        abort(404)

    members = CampaignMember.query.filter_by(campaign_id=campaign_id).all()
    member_users = [m.user for m in members] + [campaign.dm]

    # Unique speaker labels from segments
    unique_labels = []
    seen = set()
    for seg in sess.segments:
        if seg.speaker_label not in seen:
            unique_labels.append(seg.speaker_label)
            seen.add(seg.speaker_label)

    return render_template('campaign/session_view.html',
                           campaign=campaign,
                           sess=sess,
                           member_users=member_users,
                           unique_labels=unique_labels)


# ---------------------------------------------------------------------------
# Trigger transcription processing (DM only)
# ---------------------------------------------------------------------------

@campaign_bp.route('/<int:campaign_id>/session/<int:session_id>/process', methods=['POST'])
@login_required
@role_required('dm')
def session_process(campaign_id, session_id):
    campaign = db.session.get(Campaign, campaign_id)
    if not campaign or not _is_campaign_dm(campaign):
        abort(403)
    sess = db.session.get(Session, session_id)
    if not sess or sess.campaign_id != campaign_id:
        abort(404)

    if sess.status == 'processing':
        flash('This session is already being processed.', 'error')
        return redirect(url_for('campaign.session_view',
                                campaign_id=campaign_id, session_id=session_id))

    hf_token = current_app.config.get('HF_AUTH_TOKEN', '')
    if not hf_token:
        flash('HuggingFace auth token is not configured. Set the HF_AUTH_TOKEN environment variable.', 'error')
        return redirect(url_for('campaign.session_view',
                                campaign_id=campaign_id, session_id=session_id))

    sess.status = 'processing'
    sess.error_message = None
    db.session.commit()

    from app.services.transcription import process_session
    app = current_app._get_current_object()
    t = threading.Thread(target=process_session, args=(app, session_id), daemon=True)
    t.start()

    flash('Transcription started. This may take several minutes.', 'success')
    return redirect(url_for('campaign.session_view',
                            campaign_id=campaign_id, session_id=session_id))


# ---------------------------------------------------------------------------
# Session processing status (JSON, for frontend polling)
# ---------------------------------------------------------------------------

@campaign_bp.route('/<int:campaign_id>/session/<int:session_id>/status')
@login_required
def session_status(campaign_id, session_id):
    campaign = _get_campaign_or_403(campaign_id)
    sess = db.session.get(Session, session_id)
    if not sess or sess.campaign_id != campaign_id:
        abort(404)
    return jsonify(status=sess.status, error_message=sess.error_message)


# ---------------------------------------------------------------------------
# Map speakers to users (DM only)
# ---------------------------------------------------------------------------

@campaign_bp.route('/<int:campaign_id>/session/<int:session_id>/map-speakers', methods=['POST'])
@login_required
@role_required('dm')
def map_speakers(campaign_id, session_id):
    campaign = db.session.get(Campaign, campaign_id)
    if not campaign or not _is_campaign_dm(campaign):
        abort(403)
    sess = db.session.get(Session, session_id)
    if not sess or sess.campaign_id != campaign_id:
        abort(404)

    # Form fields: speaker_<label> = user_id (or '' for unmapped)
    for key, value in request.form.items():
        if not key.startswith('speaker_'):
            continue
        label = key[len('speaker_'):]
        user_id = int(value) if value else None

        TranscriptSegment.query.filter_by(
            session_id=session_id, speaker_label=label
        ).update({'speaker_user_id': user_id})

    db.session.commit()
    flash('Speaker mapping saved.', 'success')
    return redirect(url_for('campaign.session_view',
                            campaign_id=campaign_id, session_id=session_id))


# ---------------------------------------------------------------------------
# Trigger batch analysis (DM only)
# ---------------------------------------------------------------------------

@campaign_bp.route('/<int:campaign_id>/session/<int:session_id>/analyze', methods=['POST'])
@login_required
@role_required('dm')
def session_analyze(campaign_id, session_id):
    campaign = db.session.get(Campaign, campaign_id)
    if not campaign or not _is_campaign_dm(campaign):
        abort(403)
    sess = db.session.get(Session, session_id)
    if not sess or sess.campaign_id != campaign_id:
        abort(404)
    if sess.status != 'completed':
        flash('Transcription must be completed before running analysis.', 'error')
        return redirect(url_for('campaign.session_view',
                                campaign_id=campaign_id, session_id=session_id))

    api_key = current_app.config.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        flash('ANTHROPIC_API_KEY is not configured. Set it as an environment variable.', 'error')
        return redirect(url_for('campaign.session_view',
                                campaign_id=campaign_id, session_id=session_id))

    # Prevent re-triggering while any analysis is still running
    running = SessionAnalysis.query.filter_by(
        session_id=session_id, status='processing'
    ).first()
    if running:
        flash('Analysis is already in progress.', 'error')
        return redirect(url_for('campaign.session_view',
                                campaign_id=campaign_id, session_id=session_id))

    from app.services.analysis import analyze_session
    app = current_app._get_current_object()
    t = threading.Thread(target=analyze_session, args=(app, session_id), daemon=True)
    t.start()

    flash('Analysis started. Results will appear on this page as each pass completes.', 'success')
    return redirect(url_for('campaign.session_view',
                            campaign_id=campaign_id, session_id=session_id))


# ---------------------------------------------------------------------------
# Analysis status (JSON polling)
# ---------------------------------------------------------------------------

@campaign_bp.route('/<int:campaign_id>/session/<int:session_id>/analysis/status')
@login_required
def analysis_status(campaign_id, session_id):
    campaign = _get_campaign_or_403(campaign_id)
    sess = db.session.get(Session, session_id)
    if not sess or sess.campaign_id != campaign_id:
        abort(404)

    rows = SessionAnalysis.query.filter_by(session_id=session_id).all()
    statuses = {r.analysis_type: r.status for r in rows}
    return jsonify(statuses)


# ---------------------------------------------------------------------------
# Analysis result views
# ---------------------------------------------------------------------------

@campaign_bp.route('/<int:campaign_id>/session/<int:session_id>/analysis/<analysis_type>')
@login_required
def analysis_view(campaign_id, session_id, analysis_type):
    if analysis_type not in ANALYSIS_TYPES:
        abort(404)

    campaign = _get_campaign_or_403(campaign_id)
    sess = db.session.get(Session, session_id)
    if not sess or sess.campaign_id != campaign_id:
        abort(404)

    analysis = SessionAnalysis.query.filter_by(
        session_id=session_id, analysis_type=analysis_type
    ).first_or_404()

    result = None
    if analysis.status == 'completed' and analysis.result_json:
        import json
        result = json.loads(analysis.result_json)

    # For ic_ooc we also need the segments with their context labels
    segments = None
    if analysis_type == 'ic_ooc' and analysis.status == 'completed':
        segments = (TranscriptSegment.query
                    .filter_by(session_id=session_id)
                    .order_by(TranscriptSegment.start_time)
                    .all())

    return render_template(
        f'campaign/analysis_{analysis_type}.html',
        campaign=campaign,
        sess=sess,
        analysis=analysis,
        result=result,
        segments=segments,
    )


# ---------------------------------------------------------------------------
# Delete session (DM only)
# ---------------------------------------------------------------------------

@campaign_bp.route('/<int:campaign_id>/session/<int:session_id>/delete', methods=['POST'])
@login_required
@role_required('dm')
def session_delete(campaign_id, session_id):
    campaign = db.session.get(Campaign, campaign_id)
    if not campaign or not _is_campaign_dm(campaign):
        abort(403)
    sess = db.session.get(Session, session_id)
    if not sess or sess.campaign_id != campaign_id:
        abort(404)

    if sess.audio_filename:
        audio_path = os.path.join(_session_upload_dir(campaign_id), sess.audio_filename)
        if os.path.exists(audio_path):
            os.remove(audio_path)

    db.session.delete(sess)
    db.session.commit()
    flash(f'Session "{sess.title}" deleted.', 'success')
    return redirect(url_for('campaign.campaign_view', campaign_id=campaign_id))


# ---------------------------------------------------------------------------
# Serve session audio (DM only)
# ---------------------------------------------------------------------------

@campaign_bp.route('/<int:campaign_id>/session/<int:session_id>/audio')
@login_required
@role_required('dm')
def session_audio(campaign_id, session_id):
    campaign = db.session.get(Campaign, campaign_id)
    if not campaign or not _is_campaign_dm(campaign):
        abort(403)
    sess = db.session.get(Session, session_id)
    if not sess or sess.campaign_id != campaign_id or not sess.audio_filename:
        abort(404)
    return send_from_directory(_session_upload_dir(campaign_id), sess.audio_filename)


# ---------------------------------------------------------------------------
# Voice sample upload/delete
# ---------------------------------------------------------------------------

@campaign_bp.route('/<int:campaign_id>/voice-sample', methods=['POST'])
@login_required
def upload_voice_sample(campaign_id):
    campaign = _get_campaign_or_403(campaign_id)
    audio_blob = request.files.get('audio_blob')
    if not audio_blob:
        flash('No audio received.', 'error')
        return redirect(url_for('campaign.campaign_view', campaign_id=campaign_id))

    # Replace existing voice sample if present
    existing = VoiceSample.query.filter_by(
        user_id=current_user.id, campaign_id=campaign_id
    ).first()
    if existing:
        old_path = os.path.join(_voice_sample_dir(campaign_id), existing.filename)
        if os.path.exists(old_path):
            os.remove(old_path)
        db.session.delete(existing)

    filename = f'{current_user.id}_{uuid.uuid4().hex}.webm'
    audio_blob.save(os.path.join(_voice_sample_dir(campaign_id), filename))

    sample = VoiceSample(user_id=current_user.id, campaign_id=campaign_id, filename=filename)
    db.session.add(sample)
    db.session.commit()
    flash('Voice sample saved.', 'success')
    return redirect(url_for('campaign.campaign_view', campaign_id=campaign_id))


@campaign_bp.route('/<int:campaign_id>/voice-sample/delete', methods=['POST'])
@login_required
def delete_voice_sample(campaign_id):
    campaign = _get_campaign_or_403(campaign_id)
    sample = VoiceSample.query.filter_by(
        user_id=current_user.id, campaign_id=campaign_id
    ).first_or_404()

    file_path = os.path.join(_voice_sample_dir(campaign_id), sample.filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    db.session.delete(sample)
    db.session.commit()
    flash('Voice sample deleted.', 'success')
    return redirect(url_for('campaign.campaign_view', campaign_id=campaign_id))
