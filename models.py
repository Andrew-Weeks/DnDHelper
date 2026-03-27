from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone

db = SQLAlchemy()


class User(UserMixin, db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role          = db.Column(db.String(20), nullable=False, default='player')
    # role values: 'player', 'dm'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_dm(self):
        return self.role == 'dm'


class SoundboardItem(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name       = db.Column(db.String(120), nullable=False)
    filename   = db.Column(db.String(256), nullable=False)  # on-disk filename
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', backref=db.backref('soundboard_items', lazy=True))


class ShareRequest(db.Model):
    id                = db.Column(db.Integer, primary_key=True)
    from_user_id      = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    to_user_id        = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    soundboard_item_id = db.Column(db.Integer, db.ForeignKey('soundboard_item.id'), nullable=False)
    status            = db.Column(db.String(20), nullable=False, default='pending')
    # status values: 'pending', 'accepted', 'declined'
    created_at        = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    from_user      = db.relationship('User', foreign_keys=[from_user_id])
    to_user        = db.relationship('User', foreign_keys=[to_user_id])
    soundboard_item = db.relationship('SoundboardItem', backref=db.backref('share_requests', lazy=True))


# ---------------------------------------------------------------------------
# Campaign system
# ---------------------------------------------------------------------------

class Campaign(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(120), nullable=False)
    dm_id      = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    dm      = db.relationship('User', backref=db.backref('campaigns', lazy=True))
    members = db.relationship('CampaignMember', backref='campaign', lazy=True, cascade='all, delete-orphan')
    invites = db.relationship('CampaignInvite', backref='campaign', lazy=True, cascade='all, delete-orphan')
    sessions = db.relationship('Session', backref='campaign', lazy=True, cascade='all, delete-orphan')


class CampaignMember(db.Model):
    __tablename__ = 'campaign_member'
    __table_args__ = (db.UniqueConstraint('campaign_id', 'user_id'),)

    id          = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'), nullable=False)
    user_id     = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    joined_at   = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', backref=db.backref('campaign_memberships', lazy=True))


class CampaignInvite(db.Model):
    __tablename__ = 'campaign_invite'

    id          = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'), nullable=False)
    to_user_id  = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status      = db.Column(db.String(20), nullable=False, default='pending')
    # status values: 'pending', 'accepted', 'declined'
    created_at  = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    to_user = db.relationship('User', backref=db.backref('campaign_invites', lazy=True))


# ---------------------------------------------------------------------------
# Session recording & transcription
# ---------------------------------------------------------------------------

class Session(db.Model):
    __tablename__ = 'session'

    id               = db.Column(db.Integer, primary_key=True)
    campaign_id      = db.Column(db.Integer, db.ForeignKey('campaign.id'), nullable=False)
    title            = db.Column(db.String(200), nullable=False)
    audio_filename   = db.Column(db.String(256), nullable=True)
    duration_seconds = db.Column(db.Integer, nullable=True)
    status           = db.Column(db.String(20), nullable=False, default='uploaded')
    # status values: 'uploaded', 'processing', 'completed', 'failed'
    error_message    = db.Column(db.Text, nullable=True)
    created_at       = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    segments = db.relationship('TranscriptSegment', backref='session', lazy=True,
                               cascade='all, delete-orphan',
                               order_by='TranscriptSegment.start_time')


class TranscriptSegment(db.Model):
    __tablename__ = 'transcript_segment'

    id              = db.Column(db.Integer, primary_key=True)
    session_id      = db.Column(db.Integer, db.ForeignKey('session.id'), nullable=False)
    speaker_label   = db.Column(db.String(50), nullable=False)   # e.g. 'SPEAKER_00'
    speaker_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    start_time      = db.Column(db.Float, nullable=False)
    end_time        = db.Column(db.Float, nullable=False)
    text            = db.Column(db.Text, nullable=False)

    speaker_user = db.relationship('User', foreign_keys=[speaker_user_id])


# ---------------------------------------------------------------------------
# Voice samples (stored for future auto-matching)
# ---------------------------------------------------------------------------

class VoiceSample(db.Model):
    __tablename__ = 'voice_sample'
    __table_args__ = (db.UniqueConstraint('user_id', 'campaign_id'),)

    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'), nullable=False)
    filename    = db.Column(db.String(256), nullable=False)
    created_at  = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', backref=db.backref('voice_samples', lazy=True))
